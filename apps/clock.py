NAME = "Clock"
ICON = "clock"
COLOR = 0x2563EB

import time

DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def run(ctx):
    lcd = ctx.lcd
    C = ctx.config
    ctx.clear()
    last = None
    while True:
        keys = ctx.tick()
        if ctx.ESC in keys:
            return

        t = time.localtime()
        if t[0] >= 2024:
            hm = "%02d:%02d" % (t[3], t[4])
            sec = "%02d" % t[5]
            date = "%s, %d %s %d" % (DAYS[t[6]], t[2], MONTHS[t[1] - 1], t[0])
        else:
            hm, sec, date = "--:--", "", "Connect WiFi to set the time"

        if (hm, sec) != last:
            last = (hm, sec)
            top = ctx.TOP
            lcd.fillRect(0, top + 14, ctx.W, 44, C.BG)
            lcd.setFont(lcd.FONTS.DejaVu40)
            lcd.setTextColor(C.FG, C.BG)
            w = lcd.textWidth(hm)
            x = (ctx.W - w) // 2 - 12
            lcd.drawString(hm, x, top + 16)
            lcd.setFont(lcd.FONTS.DejaVu18)
            lcd.setTextColor(C.ACCENT, C.BG)
            lcd.drawString(sec, x + w + 4, top + 34)

            lcd.fillRect(0, top + 66, ctx.W, 16, C.BG)
            lcd.setFont(lcd.FONTS.DejaVu12)
            lcd.setTextColor(C.DIM, C.BG)
            lcd.drawCenterString(date, ctx.W // 2, top + 68)
            lcd.setFont(lcd.FONTS.DejaVu9)
            lcd.drawCenterString("Esc = back", ctx.W // 2, ctx.BOTTOM - 12)
        time.sleep_ms(50)
