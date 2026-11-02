# CardOS top bar: WiFi state on the left, battery on the right.
import time
import network
import esp32
import M5
from M5 import Lcd
from cardos import config as C


def _rssi_bars(rssi):
    if rssi is None:
        return 0
    if rssi > -55:
        return 4
    if rssi > -67:
        return 3
    if rssi > -78:
        return 2
    return 1


# Join attempts that have finished without a connection.
_FAILED = tuple(getattr(network, n, -1) for n in (
    "STAT_NO_AP_FOUND", "STAT_WRONG_PASSWORD", "STAT_CONNECT_FAIL",
    "STAT_HANDSHAKE_TIMEOUT", "STAT_BEACON_TIMEOUT", "STAT_ASSOC_FAIL"))


class StatusBar:
    def __init__(self):
        self.wlan = network.WLAN(network.STA_IF)
        self._last = None
        self._next = 0
        self.paused = False   # True while an app (the WiFi picker) manages WiFi itself
        try:
            network.country(C.WIFI_COUNTRY)
        except Exception as e:
            print("wifi country:", e)
        try:
            self.wlan.active(True)
            # Give up after a few tries instead of retrying forever: while the radio
            # retries, the ESP32 refuses to scan, so the WiFi list comes back empty.
            self.wlan.config(reconnects=2)
        except Exception as e:
            print("wifi reconnects:", e)
        self._autoconnect()

    def _autoconnect(self):
        """Start (non-blocking) connecting with the WiFi saved in UIFlow settings."""
        self._next_retry = time.ticks_add(time.ticks_ms(), 30000)
        if self.paused:
            return
        try:
            self.wlan.active(True)
            if self.wlan.isconnected() or self.wlan.status() == network.STAT_CONNECTING:
                return
            nvs = esp32.NVS("uiflow")
            ssid = nvs.get_str("ssid0")
            pswd = nvs.get_str("pswd0")
            if ssid:
                self.wlan.connect(ssid, pswd)
        except Exception as e:
            print("wifi autoconnect:", e)

    def invalidate(self):
        """Force a full redraw on the next update()."""
        self._last = None
        self._next = 0

    def _read(self):
        conn, bars, ssid = False, 0, ""
        try:
            conn = self.wlan.isconnected()
            if conn:
                bars = _rssi_bars(self.wlan.status("rssi"))
                ssid = self.wlan.config("essid")
        except Exception:
            pass
        try:
            level = M5.Power.getBatteryLevel()
        except Exception:
            level = -1
        try:
            charging = bool(M5.Power.isCharging())
        except Exception:
            charging = False
        return (conn, bars, ssid, level, charging)

    def update(self):
        now = time.ticks_ms()
        if self._last is not None and time.ticks_diff(now, self._next) < 0:
            return
        self._next = time.ticks_add(now, 2000)
        state = self._read()
        if not state[0] and not self.paused:
            try:
                if self.wlan.status() in _FAILED:
                    self.wlan.disconnect()   # stop the radio retrying, so scans work
            except Exception:
                pass
            if time.ticks_diff(now, self._next_retry) >= 0:
                self._autoconnect()  # WiFi dropped or never came up: try again every 30 s
        if state != self._last:
            self._draw(state)
            self._last = state

    def _draw(self, state):
        conn, bars, ssid, level, charging = state
        Lcd.fillRect(0, 0, C.W, C.TOP_H, C.BAR_BG)
        Lcd.drawLine(0, C.TOP_H - 1, C.W, C.TOP_H - 1, 0x1E293B)
        Lcd.setFont(Lcd.FONTS.DejaVu9)

        # WiFi signal bars
        for i in range(4):
            h = 3 + i * 3
            col = C.GREEN if (conn and i < bars) else C.DIM
            Lcd.fillRect(4 + i * 4, 13 - h, 3, h, col)
        if conn:
            Lcd.setTextColor(C.FG, C.BAR_BG)
            Lcd.drawString(ssid[:12], 23, 3)
        else:
            Lcd.setTextColor(C.RED, C.BAR_BG)
            Lcd.drawString("No WiFi", 23, 3)

        # Title
        Lcd.setTextColor(C.ACCENT, C.BAR_BG)
        Lcd.drawCenterString(C.TITLE, C.W // 2, 3)

        # Battery icon (body + tip), filled by level, with the number inside.
        # Darker fills keep the white number readable on top of them.
        bx, by, bw, bh = C.W - 31, 2, 26, 12
        if level < 0:
            col = C.DIM
        elif level > 50:
            col = 0x15803D   # green
        elif level > 20:
            col = 0xA16207   # amber
        else:
            col = 0xB91C1C   # red
        Lcd.drawRoundRect(bx, by, bw, bh, 2, C.FG)
        Lcd.fillRect(bx + bw, by + 4, 2, 4, C.FG)
        if level > 0:
            Lcd.fillRect(bx + 1, by + 1, max(1, (bw - 2) * level // 100), bh - 2, col)
        txt = "--" if level < 0 else str(level)
        Lcd.setTextColor(0xFFFFFF, 0xFFFFFF)  # fg == bg -> transparent background
        Lcd.drawCenterString(txt, bx + bw // 2, by - 1)

        # Lightning bolt left of the battery while charging
        if charging:
            x = bx - 10
            Lcd.fillTriangle(x + 4, 2, x, 8, x + 4, 8, C.YELLOW)
            Lcd.fillTriangle(x + 3, 7, x + 7, 7, x + 3, 13, C.YELLOW)
