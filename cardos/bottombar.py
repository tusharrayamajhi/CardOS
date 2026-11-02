# CardOS bottom bar: time on the left, date in the middle, IP / free RAM on the right.
# Also syncs the clock from the internet (NTP) once WiFi is up.
import gc
import time
import machine
import network
from M5 import Lcd
from cardos import config as C
from cardos import settings

DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def time_is_set():
    return time.localtime()[0] >= 2024


NTP_HOSTS = ("pool.ntp.org", "time.google.com", "time.cloudflare.com")


def sync_time():
    """Set the RTC to local time from NTP. Returns True on success."""
    import ntptime
    for host in NTP_HOSTS:
        try:
            ntptime.host = host
            ntptime.settime()  # sets RTC to UTC
            t = time.localtime(time.time() + settings.get("tz") * 60)
            machine.RTC().datetime((t[0], t[1], t[2], t[6], t[3], t[4], t[5], 0))
            return True
        except Exception as e:
            print("ntp sync failed:", host, e)
    return False


class BottomBar:
    def __init__(self):
        self.wlan = network.WLAN(network.STA_IF)
        self._last = None
        self._next = 0
        self._next_sync = 0
        self.synced = False

    def invalidate(self):
        self._last = None
        self._next = 0

    def _maybe_sync(self, now):
        if self.synced or time.ticks_diff(now, self._next_sync) < 0:
            return
        self._next_sync = time.ticks_add(now, 10000)  # retry every 10 s
        try:
            if self.wlan.isconnected():
                self.synced = sync_time()
        except Exception:
            pass

    def _read(self):
        if time_is_set():
            t = time.localtime()
            clock = "%02d:%02d" % (t[3], t[4])
            date = "%s %d %s" % (DAYS[t[6]], t[2], MONTHS[t[1] - 1])
        else:
            clock, date = "--:--", "connect WiFi for time"
        try:
            right = self.wlan.ifconfig()[0] if self.wlan.isconnected() else ""
        except Exception:
            right = ""
        if not right:
            right = "RAM %dK" % (gc.mem_free() // 1024)
        return (clock, date, right)

    def update(self):
        now = time.ticks_ms()
        self._maybe_sync(now)
        if self._last is not None and time.ticks_diff(now, self._next) < 0:
            return
        self._next = time.ticks_add(now, 1000)
        state = self._read()
        if state != self._last:
            self._draw(state)
            self._last = state

    def _draw(self, state):
        clock, date, right = state
        y = C.APP_BOTTOM
        Lcd.fillRect(0, y, C.W, C.BOTTOM_H, C.BAR_BG)
        Lcd.drawLine(0, y, C.W, y, 0x1E293B)
        Lcd.setFont(Lcd.FONTS.DejaVu12)
        Lcd.setTextColor(C.FG, C.BAR_BG)
        Lcd.drawString(clock, 4, y + 3)
        Lcd.setFont(Lcd.FONTS.DejaVu9)
        Lcd.setTextColor(C.DIM if clock == "--:--" else C.FG, C.BAR_BG)
        Lcd.drawCenterString(date, C.W // 2 - 8, y + 4)
        Lcd.setTextColor(C.ACCENT, C.BAR_BG)
        Lcd.drawRightString(right, C.W - 4, y + 4)
