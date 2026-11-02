# CardOS

**A tiny operating system for the M5Stack Cardputer ADV, with live Nepal Premier League cricket scores.**

CardOS turns the Cardputer ADV into a pocket computer with a home screen, a status bar and apps you open with the keyboard. It is written in MicroPython and runs on the Cardputer's standard UIFlow2 firmware, so you don't need to flash anything custom. One command installs everything.

> Only want the cricket scores, without the home screen and other apps? Use **[NPL Cricket for Cardputer ADV](https://github.com/tusharrayamajhi/npl-cricket-cardputer)**. It boots straight into the app.

<!-- Demo: drag your screen recording into this README on GitHub to embed it here -->

```
┌──────────────────────────────────────────┐
│ ▂▄▆ MyWiFi          Tushar          [87] │  ← WiFi, title, battery
│                                          │
│      ▫    ◻     ┌──────┐     ◻    ▫      │  ← app carousel
│                 │ NPL  │                 │     (← → to slide)
│                 └──────┘                 │
│               NPL Cricket                │
│ 14:32   Sun 2 Nov             192.168.1.5│  ← time, date, IP
└──────────────────────────────────────────┘
```

---

## Features

**The OS**
- Home screen carousel with a slide animation. The selected app is big, and its neighbours are small on each side.
- Top bar: WiFi strength and network name, plus a battery icon with the charge level inside.
- Bottom bar: time and date (synced over the internet, with your time zone), plus the IP address.
- Key click sound, screen dimming and sleep, and settings that survive reboots.
- Every app is a separate file. Add a `.py` file to `apps/` and it shows up on the home screen.

**The apps**

| App | What it does |
|---|---|
| 🏏 **NPL Cricket** | Live scores, today's matches, fixtures, results, points table, team pages with squads and captain photos |
| ⚙️ **Settings** | WiFi picker with password typing, brightness, screen-off timer, volume, key click, time zone |
| 🖼️ **Images** | Browse and view JPG/PNG/BMP pictures from the SD card, with zoom and pan |
| 🕐 **Clock** | Big full-screen clock |
| ℹ️ **System Info** | Battery, IP address, free RAM and free flash |
| 🎙️ **Voice Agent** | Experimental Gemini voice chat. *Not working yet: the microphone records silence on current firmware.* |

### NPL Cricket

- **Today:** today's matches, with live scores that refresh every 45 seconds during a game.
- **Next:** upcoming fixtures in Nepal time.
- **Results:** every finished match, with the winner highlighted.
- **Teams:** points table with team logos. Press Enter on a team to open its page:
  - captain, coach, record and position
  - last result and next match
  - full squad, with captain (c) and wicket-keeper (wk) marked
  - captain photo
- Scores are large and white, so you can read them from across the room.
- After the first load the data is saved to flash, so the app opens instantly and still works offline.

---

## What you need

| | |
|---|---|
| **Device** | [M5Stack Cardputer **ADV**](https://docs.m5stack.com/en/core/Cardputer-Adv). The original Cardputer has a different keyboard and isn't supported yet. |
| **Firmware** | **UIFlow2** for Cardputer (MicroPython 1.27), flashed with M5Burner |
| **SD card** | microSD card, FAT32. Holds team pages and photos (about 100 KB). |
| **Computer** | Windows, macOS or Linux with [Python 3.8+](https://www.python.org/downloads/) |
| **Cable** | USB-C **data** cable. Some cables only charge. |
| **WiFi** | 2.4 GHz network for live scores and the clock |

---

## Install

### 1. Flash UIFlow2 (skip this if your Cardputer already runs UIFlow2)

1. Download and open **[M5Burner](https://docs.m5stack.com/en/download)**.
2. Choose **Cardputer** in the device list, then find the **UIFlow2.0** firmware for Cardputer / Cardputer ADV.
3. Download the latest version, connect the Cardputer and click **Burn**.

> If the computer doesn't see the Cardputer, hold the **G0** button while you plug it in. That puts it in download mode.

### 2. Get CardOS

```bash
git clone https://github.com/tusharrayamajhi/CardOS.git
```

```bash
cd CardOS
```

No git? Click **Code → Download ZIP** on GitHub and unzip it instead.

### 3. Insert the SD card and run the installer

Put the microSD card in the Cardputer, connect it with USB, turn it on and run:

```bash
python install.py
```

On macOS and Linux, use `python3` if `python` isn't found.

The installer checks everything before it changes anything:

```
CardOS installer

[ OK ] PC tools ready (mpremote, mpy-cross)
[ OK ] Cardputer found on COM5
[ OK ] Compiled 14 CardOS modules and 6 apps
  Checking the Cardputer ...
[ OK ] Firmware: v1.27.0 ... (UIFlow2)
[ OK ] Board: Cardputer ADV
[ OK ] MicroPython version matches
[ OK ] Flash space: 1953 KB free, 272 KB needed
[ OK ] SD card: 28 MB free
  Your old main.py is saved as /flash/main_before_cardos.py
  Uploading 74 files (276 KB) ...
[ OK ] All 74 files uploaded and verified
[ OK ] Rebooting the Cardputer

Done! CardOS starts in a few seconds.
```

**What it does, step by step:**

1. Installs `mpremote` and `mpy-cross` into `tools/mpyx/`. It doesn't touch your system Python.
2. Finds the Cardputer on USB automatically.
3. Compiles CardOS to `.mpy` bytecode. Compiled files load with far less RAM, which big apps like NPL Cricket need.
4. Checks the device:
   - it's a Cardputer **ADV**, running **UIFlow2**
   - the MicroPython version matches
   - there's enough flash space
   - an **SD card** is inserted and has room

   If any check fails, it stops with a clear message, and the Cardputer is left exactly as it was.
5. Backs up your existing `main.py`.
6. Uploads everything:
   - CardOS and the apps
   - logos to flash
   - team data and photos to the SD card
7. Reads every file back to make sure its size matches.
8. Sets the Cardputer to start CardOS on power-up, and reboots it.

**Installer options**

| Command | What it does |
|---|---|
| `python install.py --check` | Only run the checks. Changes nothing. |
| `python install.py --wifi` | Set the WiFi name and password from the computer, then reboot (or use the Settings app) |
| `python install.py --port COM5` | Use a specific port (`/dev/ttyACM0` on Linux, `/dev/cu.usbmodem…` on macOS) |
| `python install.py --no-sd` | Install without an SD card. NPL team pages and photos won't be available. |
| `python install.py --no-reset` | Don't reboot at the end |
| `python install.py --restore` | Uninstall: put back your old `main.py` and how the Cardputer started before |

### 4. Connect to WiFi

On the Cardputer, open **Settings → WiFi**, pick your network and type the password. The time sets itself once WiFi connects. Then open **NPL Cricket**.

---

## Using CardOS

The Cardputer ADV has no separate arrow keys. CardOS uses the keys with arrows printed on them:

| Key | Action |
|---|---|
| `,` and `/` | Left / right: move between apps or tabs |
| `;` and `.` | Up / down: scroll lists |
| `Enter` | Open |
| `Esc` (top-left `` ` `` key) | Back / close the app |
| Any key | Wake the screen when it's off |

**NPL Cricket keys**

| Key | Action |
|---|---|
| `,` `/` | Switch tab: Today, Next, Results, Teams |
| `;` `.` | Move up and down |
| `Enter` | Match details, team page or team photos |
| `r` | Refresh now |
| `R` | Reload the whole season |
| `p` | NPL photos |
| `Esc` | Back |

**Images keys:** `,` `/` previous/next, `=` `-` zoom, `;` `.` `,` `/` pan while zoomed, `0` fit, `h` hide hints.

---

## Personalise it

Edit [`cardos/config.py`](cardos/config.py), then run `python install.py` again:

```python
TITLE = "Tushar"         # name in the middle of the top bar - put yours here
TZ_OFFSET_MIN = 345      # default time zone (Nepal = +5:45). Also changeable in Settings.
WIFI_COUNTRY = "NP"      # WiFi country code
ACCENT = 0x38BDF8        # highlight colour
```

**Add your own photos.** Copy JPG files into `sd/npl/<TEAM>/` (for example `sd/npl/KAG/`) or `sd/npl/photos/` and re-run the installer. The team page shows every JPG in its folder. Use **baseline** (not progressive) JPEGs, about 240×135 pixels.

---

## Write your own app

An app is one Python file in `apps/`. The first lines tell the launcher its name, icon and colour:

```python
NAME = "Hello"
ICON = "info"        # built-in: clock info wifi folder image game gear mic cricket
COLOR = 0xF59E0B

def run(ctx):
    lcd = ctx.lcd
    ctx.clear()
    lcd.drawCenterString("Hello, Cardputer!", ctx.W // 2, ctx.TOP + 40)
    while True:
        keys = ctx.tick()            # keep calling this: keyboard, bars, sleep
        if ctx.ESC in keys:
            return                   # back to the home screen
```

Save it as `apps/hello.py`, run `python install.py`, and it shows up on the home screen.

**What `ctx` gives your app:**

| Name | What it is |
|---|---|
| `ctx.lcd` | The screen (M5GFX: `drawString`, `fillRect`, `drawJpg`, …) |
| `ctx.tick()` | Updates everything and returns the keys pressed since the last call |
| `ctx.ESC` `ctx.ENTER` `ctx.LEFT` `ctx.RIGHT` `ctx.UP` `ctx.DOWN` | Key names |
| `ctx.W` `ctx.TOP` `ctx.BOTTOM` | Screen width and the area between the bars |
| `ctx.clear()` | Clear the app area |
| `ctx.fullscreen(True)` | Hide the bars and use the whole 240×135 screen |
| `ctx.keep_awake = True` | Stop the screen from sleeping |
| `ctx.config` | Colours and settings from `cardos/config.py` |

Useful modules: `cardos.net` (streaming HTTP), `cardos.jsonstream` (parse big JSON without loading it all), `cardos.sd` (mount the SD card), `cardos.settings` (saved settings).

---

## How it fits in 50 KB of RAM

The ESP32-S3 in the Cardputer ADV has no PSRAM. After WiFi and the screen take their share, Python apps get about 50 KB. One day of match data is about 17 KB of JSON, and parsing it the normal way needs several times that.

| Problem | Fix |
|---|---|
| Big JSON replies don't fit in RAM | [`cardos/jsonstream.py`](cardos/jsonstream.py) parses the feed as it streams in and keeps only the fields the screen shows. |
| HTTPS needs ~30 KB of contiguous memory | Public scores are fetched over plain HTTP. CardOS also reserves a memory block for apps that need HTTPS. |
| Decoding PNG logos needs extra memory | Logos are pre-shrunk on the PC to exact sizes (14, 26, 36 px) and stored as uncompressed BMP files, which draw straight to the screen. |
| Compiling big `.py` files on the device runs out of RAM | Everything is pre-compiled to `.mpy` bytecode on the PC. Speed-critical parts use `@micropython.native` / `viper`. |
| One big team file is too much to load | Each team has its own small JSON file on the SD card. Only the team you open is loaded. |

---

## Project layout

```
CardOS/
├── install.py            one-command installer (checks + upload)
├── main.py               boot file: starts CardOS
├── cardos/               the OS: launcher, bars, keyboard, networking, settings
├── apps/                 one file per app
├── res/npl/              logos as BMP (go to the Cardputer's flash)
├── sd/npl/               team data and photos (go to the SD card)
└── tools/
    ├── npl_logos.py      PNG logos  → res/npl/*.bmp at every size
    ├── npl_teams.py      Wikipedia  → sd/npl/<TEAM>/team.json + captain.jpg
    ├── npl_seed.py       pre-builds the season cache on the PC
    └── make_npl_repo.py  builds the NPL-only repo from this one (with standalone/)
```

**Rebuild the NPL data** (for example, for a new season):

```bash
pip install pillow
```

```bash
python tools/npl_teams.py
```

```bash
python tools/npl_logos.py path/to/folder-with-logo-pngs
```

---

## Troubleshooting

| Problem | Fix |
|---|---|
| **"No Cardputer found on USB"** | Use a data cable, not a charge-only one. Restart the Cardputer while it's plugged in. Close Thonny, Arduino IDE or any other serial monitor. |
| **"UIFlow2 firmware not found"** | Flash UIFlow2 with M5Burner (Install step 1). |
| **"Cardputer ADV keyboard not found"** | This is an original Cardputer. CardOS only supports the ADV for now. |
| **"MicroPython version mismatch"** | Update to the latest UIFlow2 for Cardputer in M5Burner. |
| **"No SD card found"** | Re-insert the card. It must be FAT32 (cards over 32 GB usually come as exFAT, so reformat them). Or use `--no-sd`. |
| **WiFi list is empty** | Only 2.4 GHz networks work. Move closer to the router and press `r` to scan again. |
| **Time shows "connect WiFi for time"** | The Cardputer has no clock battery. The time sets itself once WiFi connects. |
| **NPL shows no matches** | Check WiFi, then press `R` to reload the season. Outside the season there are no live games. |
| **I want the original UIFlow back** | `python install.py --restore` |

---

## Credits and disclaimer

CardOS is an **unofficial fan project**. It is not affiliated with the Nepal Premier League, its teams, ESPN or M5Stack.

- **Scores** come from ESPN's public cricket scoreboard feed. It is unofficial and may change without notice.
- **Squads and captains** come from [Wikipedia](https://en.wikipedia.org/wiki/2026_Nepal_Premier_League) (CC BY-SA).
- **Logos** are trademarks of their owners and are used only to identify the league and teams.
- **Captain and venue photos** come from Wikimedia Commons, under their own licences.

See [CREDITS.md](CREDITS.md) for each photo's author and licence.

## Licence

Code: [MIT](LICENSE) © 2026 Tushar Rayamajhi. Logos and photos are not covered by the MIT licence; see [CREDITS.md](CREDITS.md).
