NAME = "System Info"
ICON = "info"
COLOR = 0x16A34A

import gc
import os
import time
import network
import M5


def _rows():
    rows = []
    try:
        lvl = M5.Power.getBatteryLevel()
        mv = M5.Power.getBatteryVoltage()
        chg = M5.Power.isCharging()
        rows.append(("Battery", "%d%%  %.2fV  %s" % (lvl, mv / 1000, "charging" if chg else "")))
    except Exception:
        rows.append(("Battery", "n/a"))

    w = network.WLAN(network.STA_IF)
    if w.isconnected():
        rows.append(("WiFi", "%s  %ddBm" % (w.config("essid"), w.status("rssi"))))
        rows.append(("IP", w.ifconfig()[0]))
    else:
        rows.append(("WiFi", "not connected"))
        rows.append(("IP", "-"))

    gc.collect()
    rows.append(("RAM free", "%d KB" % (gc.mem_free() // 1024)))
    try:
        st = os.statvfs("/flash")
        rows.append(("Flash free", "%d KB" % (st[0] * st[3] // 1024)))
    except Exception:
        rows.append(("Flash free", "n/a"))
    up = time.ticks_ms() // 1000
    rows.append(("Uptime", "%dh %02dm %02ds" % (up // 3600, up // 60 % 60, up % 60)))
    return rows


def run(ctx):
    lcd = ctx.lcd
    C = ctx.config
    ctx.clear()
    next_draw = 0
    while True:
        keys = ctx.tick()
        if ctx.ESC in keys:
            return
        now = time.ticks_ms()
        if time.ticks_diff(now, next_draw) >= 0:
            next_draw = time.ticks_add(now, 1000)
            lcd.setFont(lcd.FONTS.DejaVu12)
            y = ctx.TOP + 6
            for label, value in _rows():
                lcd.fillRect(0, y, ctx.W, 14, C.BG)
                lcd.setTextColor(C.DIM, C.BG)
                lcd.drawString(label, 6, y)
                lcd.setTextColor(C.FG, C.BG)
                lcd.drawString(value[:24], 82, y)
                y += 14
        time.sleep_ms(30)
