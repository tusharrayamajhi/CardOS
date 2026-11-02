# Upload CardOS + apps to the Cardputer, then reboot into it.
#   .\deploy.ps1            compile OS + apps, upload them and main.py, then reboot
#   .\deploy.ps1 -Port COM6 use a different serial port
#   .\deploy.ps1 -NoReset   upload only
param([string]$Port = "COM5", [switch]$NoReset)
$ErrorActionPreference = "Stop"

Push-Location $PSScriptRoot
try {
    # mpy-cross must match the firmware's MicroPython (1.27); kept in tools\ so
    # it doesn't touch the global Python install.
    $tools = Join-Path $PSScriptRoot "tools\mpyx"
    if (-not (Test-Path (Join-Path $tools "mpy_cross"))) {
        Write-Host "Installing mpy-cross 1.27 into tools\mpyx ..."
        python -m pip install --quiet --target $tools mpy-cross==1.27.0.post2
    }

    # Pre-compile everything: importing a .py makes the Cardputer compile it,
    # and the RAM that takes is never fully given back (it then starves TLS).
    # -march=xtensawin lets @micropython.viper code compile to machine code.
    $env:PYTHONPATH = $tools
    function Compile($src, $outDir) {
        New-Item -ItemType Directory -Force $outDir | Out-Null
        Remove-Item "$outDir\*.mpy" -ErrorAction SilentlyContinue
        $outs = @()
        foreach ($f in Get-ChildItem "$src\*.py") {
            $out = "$outDir\" + $f.BaseName + ".mpy"
            python -m mpy_cross -march=xtensawin -o $out $f.FullName
            if ($LASTEXITCODE -ne 0) { throw "compile failed: $($f.Name)" }
            $outs += ($out -replace '\\', '/')
        }
        return $outs
    }
    $osMpys = Compile "cardos" "build\cardos"
    $appMpys = Compile "apps" "build\mpy"
    Remove-Item Env:PYTHONPATH
    $appPys = Get-ChildItem "apps\*.py" | ForEach-Object { "apps/" + $_.Name }

    # On the device a .py wins over a .mpy of the same name, so the OS folder
    # holds only .mpy files. Apps keep their .py (the launcher reads NAME/ICON
    # from it) and load the compiled copy from apps/mpy first.
    $prep = "import os`nfor d in ('/flash/libs/cardos', '/flash/apps/mpy'):`n try: os.mkdir(d)`n except OSError: pass`n" +
            "for f in os.listdir('/flash/libs/cardos'):`n if f.endswith('.py'): os.remove('/flash/libs/cardos/' + f)"
    mpremote connect $Port resume exec $prep + cp @osMpys :/flash/libs/cardos/ + `
        cp @appPys :/flash/apps/ + cp @appMpys :/flash/apps/mpy/ + cp main.py :/flash/main.py
    if ($LASTEXITCODE -ne 0) { throw "upload failed" }

    # App images (e.g. res/npl/*.bmp) go to /flash/res/, next to UIFlow's own res folders
    if (Test-Path "res") {
        mpremote connect $Port resume cp -r res :/flash/
        if ($LASTEXITCODE -ne 0) { throw "res upload failed" }
    }

    # sd/ is mirrored onto the SD card (e.g. sd/npl -> /sd/npl: team data and photos)
    if (Test-Path "sd") {
        $dirs = Get-ChildItem "sd" -Directory | ForEach-Object { "sd/" + $_.Name }
        $mountOk = mpremote connect $Port resume exec "from cardos import sd; print('SDOK' if sd.mount() else 'NOSD')"
        if ($mountOk -match "SDOK") {
            $cps = @()
            foreach ($d in $dirs) { $cps += @("+", "cp", "-r", $d, ":/sd/") }
            mpremote connect $Port resume exec "from cardos import sd; sd.mount()" @cps
            if ($LASTEXITCODE -ne 0) { throw "SD upload failed" }
        } else {
            Write-Warning "No SD card found - skipped copying the sd/ folder"
        }
    }

    if (-not $NoReset) {
        # The USB link drops as the board reboots, so mpremote's error here is expected.
        mpremote connect $Port resume exec "import machine; machine.reset()" 2>$null
        Write-Host "Rebooting into CardOS..."
    }
} finally {
    Pop-Location
}
