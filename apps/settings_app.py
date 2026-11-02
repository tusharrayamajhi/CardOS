NAME = "Settings"
ICON = "gear"
COLOR = 0x64748B

# Settings: WiFi, screen brightness, screen-off timer, volume, key click and time zone.
#   ; .  choose a setting      , /  change it      Enter  open (WiFi) / toggle
#   Esc  save and go back
import time
import machine
import network
import esp32
from cardos import settings
from cardos.textinput import ask

ITEMS = ("wifi", "brightness", "sleep", "volume", "click", "tz")
LABELS = {"wifi": "WiFi", "brightness": "Brightness", "sleep": "Screen off", "volume": "Volume",
          "click": "Key click", "tz": "Time zone"}
ROW_H = 17
# seconds without a key press before the screen turns off (0 = never)
SLEEP_OPTIONS = (15, 30, 60, 120, 300, 600, 0)
SEL_BG = 0x334155


def sleep_text(s):
    if s == 0:
        return "Never"
    return "%d s" % s if s < 60 else "%d min" % (s // 60)


def tz_text(m):
    sign = "+" if m >= 0 else "-"
    m = abs(m)
    return "UTC%s%d:%02d" % (sign, m // 60, m % 60)


def shift_clock(minutes):
    """Move the clock by `minutes` (when the time zone changes)."""
    if time.localtime()[0] < 2024:
        return
    t = time.localtime(time.time() + minutes * 60)
    machine.RTC().datetime((t[0], t[1], t[2], t[6], t[3], t[4], t[5], 0))


def signal_bars(lcd, x, y, rssi, on, off):
    n = 4 if rssi > -55 else 3 if rssi > -67 else 2 if rssi > -78 else 1
    for i in range(4):
        h = 2 + i * 2
        lcd.fillRect(x + i * 3, y + 8 - h, 2, h, on if i < n else off)


# ------------------------------------------------------------ WiFi
class WifiPicker:
    def __init__(self, ctx):
        self.ctx = ctx
        self.lcd = ctx.lcd
        self.C = ctx.config
        self.wlan = network.WLAN(network.STA_IF)
        self.nets = []          # (ssid, rssi, open)
        self.sel = 0
        self.offset = 0
        self.rows = 5

    def message(self, line1, line2="", color=None):
        lcd, C = self.lcd, self.C
        self.ctx.clear()
        lcd.setFont(lcd.FONTS.DejaVu12)
        lcd.setTextColor(color or C.FG, C.BG)
        lcd.drawCenterString(line1, self.ctx.W // 2, self.ctx.TOP + 32)
        if line2:
            lcd.setFont(lcd.FONTS.DejaVu9)
            lcd.setTextColor(C.DIM, C.BG)
            lcd.drawCenterString(line2, self.ctx.W // 2, self.ctx.TOP + 54)

    def reset_radio(self):
        """Stop any join attempt in progress; the ESP32 can't scan while one runs."""
        w = self.wlan
        try:
            w.disconnect()
        except OSError:
            pass
        w.active(False)
        time.sleep_ms(300)
        w.active(True)
        time.sleep_ms(300)

    def scan(self):
        self.message("Scanning for WiFi...")
        self.wlan.active(True)
        connected = self.wlan.isconnected()
        if not connected:
            self.reset_radio()
        found = []
        for attempt in range(3):
            try:
                found = self.wlan.scan()
            except OSError as e:
                print("scan failed:", e)
                found = []
            if found or connected:
                break
            self.reset_radio()   # an empty list usually means the radio was busy
        best = {}
        for n in found:
            try:
                ssid = n[0].decode()
            except UnicodeError:
                continue
            if not ssid:
                continue  # hidden network
            if ssid not in best or n[3] > best[ssid][1]:
                best[ssid] = (ssid, n[3], n[4] == 0)
        self.nets = sorted(best.values(), key=lambda x: -x[1])
        self.sel = 0
        self.offset = 0

    def current(self):
        try:
            return self.wlan.config("essid") if self.wlan.isconnected() else ""
        except OSError:
            return ""

    def draw(self):
        lcd, C, ctx = self.lcd, self.C, self.ctx
        ctx.clear()
        top = ctx.TOP
        lcd.fillRect(0, top, ctx.W, 14, 0x1E293B)
        lcd.setFont(lcd.FONTS.DejaVu9)
        lcd.setTextColor(C.ACCENT, 0x1E293B)
        lcd.drawString("Choose WiFi (%d found)" % len(self.nets), 4, top + 2)
        lcd.setTextColor(C.DIM, 0x1E293B)
        lcd.drawRightString("r = rescan", ctx.W - 4, top + 2)
        if not self.nets:
            lcd.setFont(lcd.FONTS.DejaVu12)
            lcd.setTextColor(C.DIM, C.BG)
            lcd.drawCenterString("No networks found", ctx.W // 2, top + 40)
            return
        if self.sel < self.offset:
            self.offset = self.sel
        elif self.sel >= self.offset + self.rows:
            self.offset = self.sel - self.rows + 1
        cur = self.current()
        lcd.setFont(lcd.FONTS.DejaVu12)
        for r in range(self.rows):
            i = self.offset + r
            if i >= len(self.nets):
                break
            ssid, rssi, is_open = self.nets[i]
            y = top + 16 + r * 17
            bg = SEL_BG if i == self.sel else C.BG
            lcd.fillRect(0, y, ctx.W, 17, bg)
            signal_bars(lcd, 6, y + 4, rssi, C.GREEN, C.DIM)
            lcd.setTextColor(0xFFFFFF if i == self.sel else C.FG, bg)
            lcd.drawString(ssid if len(ssid) <= 22 else ssid[:21] + "..", 24, y + 2)
            if ssid == cur:
                lcd.setTextColor(C.GREEN, bg)
                lcd.drawRightString("connected", ctx.W - 6, y + 2)
            elif not is_open:
                # small padlock
                lcd.drawRoundRect(ctx.W - 15, y + 3, 7, 6, 3, C.DIM)
                lcd.fillRect(ctx.W - 16, y + 7, 9, 6, C.DIM)

    def connect(self, ssid, password):
        """Try to join `ssid`. Saves it as the WiFi to use if it works."""
        ctx = self.ctx
        w = self.wlan
        self.message("Connecting to", ssid)
        try:
            w.disconnect()
        except OSError:
            pass
        time.sleep_ms(200)
        try:
            w.connect(ssid, password)
        except OSError as e:
            self.message("Could not start WiFi", str(e), self.C.RED)
            self.wait_key()
            return False
        fail = {
            getattr(network, "STAT_WRONG_PASSWORD", 202): "Wrong password",
            getattr(network, "STAT_NO_AP_FOUND", 201): "Network not found",
            getattr(network, "STAT_CONNECT_FAIL", 203): "Connection failed",
            getattr(network, "STAT_HANDSHAKE_TIMEOUT", 204): "Wrong password (timed out)",
        }
        start = time.ticks_ms()
        dots = 0
        while time.ticks_diff(time.ticks_ms(), start) < 20000:
            if ctx.ESC in ctx.tick():
                w.disconnect()
                return False
            if w.isconnected():
                nvs = esp32.NVS("uiflow")
                nvs.set_str("ssid0", ssid)
                nvs.set_str("pswd0", password)
                nvs.commit()
                self.message("Connected!", "IP " + w.ifconfig()[0], self.C.GREEN)
                time.sleep_ms(1500)
                return True
            reason = fail.get(w.status())
            if reason and time.ticks_diff(time.ticks_ms(), start) > 1500:
                self.message(reason, ssid, self.C.RED)
                self.wait_key()
                return False
            dots = (dots + 1) % 40
            if dots % 10 == 0:
                self.lcd.fillRect(0, ctx.TOP + 70, ctx.W, 12, self.C.BG)
                self.lcd.setFont(self.lcd.FONTS.DejaVu12)
                self.lcd.setTextColor(self.C.ACCENT, self.C.BG)
                self.lcd.drawCenterString("." * (dots // 10 + 1), ctx.W // 2, ctx.TOP + 68)
            time.sleep_ms(50)
        self.message("Timed out", "No answer from " + ssid, self.C.RED)
        self.wait_key()
        return False

    def wait_key(self):
        self.lcd.setFont(self.lcd.FONTS.DejaVu9)
        self.lcd.setTextColor(self.C.DIM, self.C.BG)
        self.lcd.drawCenterString("press any key", self.ctx.W // 2, self.ctx.BOTTOM - 14)
        while not self.ctx.tick():
            time.sleep_ms(20)

    def run(self):
        # the status bar's auto-connect would keep the radio busy and break scans
        self.ctx.wifi_autoconnect(False)
        try:
            self._run()
        finally:
            self.ctx.wifi_autoconnect(True)

    def _run(self):
        ctx = self.ctx
        self.scan()
        self.draw()
        while True:
            for k in ctx.tick():
                if k == ctx.ESC:
                    return
                if k in (ctx.UP, ";", "w") and self.sel > 0:
                    self.sel -= 1
                    self.draw()
                elif k in (ctx.DOWN, ".", "s") and self.sel < len(self.nets) - 1:
                    self.sel += 1
                    self.draw()
                elif k in ("r", "R"):
                    self.scan()
                    self.draw()
                elif k in (ctx.ENTER, ctx.RIGHT) and self.nets:
                    ssid, _, is_open = self.nets[self.sel]
                    password = ""
                    if not is_open:
                        saved_ssid = ""
                        saved_pw = ""
                        try:
                            nvs = esp32.NVS("uiflow")
                            saved_ssid = nvs.get_str("ssid0")
                            saved_pw = nvs.get_str("pswd0")
                        except OSError:
                            pass
                        password = ask(ctx, "Password for " + ssid,
                                       initial=saved_pw if saved_ssid == ssid else "",
                                       secret=True)
                        if password is None:
                            self.draw()
                            continue
                    if self.connect(ssid, password):
                        return
                    self.draw()
            time.sleep_ms(15)


# ------------------------------------------------------------ main menu
class SettingsApp:
    def __init__(self, ctx):
        self.ctx = ctx
        self.lcd = ctx.lcd
        self.C = ctx.config
        self.sel = 0

    def value_text(self, item):
        if item == "wifi":
            w = network.WLAN(network.STA_IF)
            try:
                return w.config("essid") if w.isconnected() else "Not connected"
            except OSError:
                return "Not connected"
        if item == "brightness":
            return "%d%%" % (settings.get("brightness") * 100 // 255)
        if item == "sleep":
            return sleep_text(settings.get("sleep"))
        if item == "volume":
            v = settings.get("volume")
            return "Off" if v == 0 else "%d%%" % (v * 100 // 255)
        if item == "click":
            return "On" if settings.get("click") else "Off"
        if item == "tz":
            return tz_text(settings.get("tz"))

    def draw_row(self, i):
        lcd, C, ctx = self.lcd, self.C, self.ctx
        item = ITEMS[i]
        y = ctx.TOP + 1 + i * ROW_H
        selected = i == self.sel
        bg = SEL_BG if selected else C.BG
        lcd.fillRect(0, y, ctx.W, ROW_H, bg)
        lcd.setFont(lcd.FONTS.DejaVu12)
        lcd.setTextColor(0xFFFFFF if selected else C.FG, bg)
        lcd.drawString(LABELS[item], 8, y + 2)
        value = self.value_text(item)
        if len(value) > 15:
            value = value[:14] + ".."
        lcd.setTextColor(C.ACCENT if selected else C.DIM, bg)
        if selected and item != "wifi":
            value = "< %s >" % value
        elif selected:
            value += "  >"
        lcd.drawRightString(value, ctx.W - 8, y + 2)

        # small level bar under brightness / volume
        if item in ("brightness", "volume"):
            frac = settings.get(item) / 255
            lcd.fillRect(8, y + ROW_H - 3, ctx.W - 16, 2, 0x1E293B)
            lcd.fillRect(8, y + ROW_H - 3, int((ctx.W - 16) * frac), 2, C.ACCENT)

    def draw(self):
        self.ctx.clear()
        for i in range(len(ITEMS)):
            self.draw_row(i)

    def change(self, step):
        item = ITEMS[self.sel]
        if item == "brightness":
            v = max(16, min(255, settings.get("brightness") + step * 16))
            settings.set("brightness", v)
            self.lcd.setBrightness(v)
        elif item == "sleep":
            cur = settings.get("sleep")
            i = SLEEP_OPTIONS.index(cur) if cur in SLEEP_OPTIONS else 2
            settings.set("sleep", SLEEP_OPTIONS[max(0, min(len(SLEEP_OPTIONS) - 1, i + step))])
        elif item == "volume":
            v = max(0, min(255, settings.get("volume") + step * 16))
            settings.set("volume", v)
            import M5
            M5.Speaker.setVolume(v)
        elif item == "click":
            settings.set("click", not settings.get("click"))
            self.ctx.click = settings.get("click")
        elif item == "tz":
            old = settings.get("tz")
            new = max(-720, min(840, old + step * 15))
            settings.set("tz", new)
            shift_clock(new - old)
            self.ctx.redraw_bars()
        else:
            return
        self.draw_row(self.sel)

    def run(self):
        ctx = self.ctx
        self.draw()
        while True:
            for k in ctx.tick():
                if k == ctx.ESC:
                    return
                if k in (ctx.UP, ";", "w"):
                    old, self.sel = self.sel, (self.sel - 1) % len(ITEMS)
                    self.draw_row(old)
                    self.draw_row(self.sel)
                elif k in (ctx.DOWN, ".", "s"):
                    old, self.sel = self.sel, (self.sel + 1) % len(ITEMS)
                    self.draw_row(old)
                    self.draw_row(self.sel)
                elif k in (ctx.LEFT, ",", "a"):
                    self.change(-1)
                elif k in (ctx.RIGHT, "/", "d"):
                    if ITEMS[self.sel] == "wifi":
                        WifiPicker(ctx).run()
                        self.draw()
                    else:
                        self.change(1)
                elif k in (ctx.ENTER, " "):
                    if ITEMS[self.sel] == "wifi":
                        WifiPicker(ctx).run()
                        self.draw()
                    elif ITEMS[self.sel] == "click":
                        self.change(1)
            time.sleep_ms(15)


def run(ctx):
    try:
        SettingsApp(ctx).run()
    finally:
        settings.save()
