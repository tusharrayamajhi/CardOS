# CardOS user settings, saved on the flash so they survive a reboot.
#
#   from cardos import settings
#   settings.get("volume")        # read
#   settings.set("volume", 120)   # change (call settings.save() to write it)
#
# WiFi name/password are NOT kept here: they live in the UIFlow settings
# (NVS "ssid0"/"pswd0"), so the firmware and CardOS share one WiFi setup.
import json
from cardos import config as C

PATH = "/flash/cardos_settings.json"

DEFAULTS = {
    "brightness": 160,          # screen backlight 0-255
    "volume": C.CLICK_VOLUME,   # speaker 0-255
    "click": C.KEY_CLICK,       # key click sound on/off
    "tz": C.TZ_OFFSET_MIN,      # minutes from UTC
    "sleep": 60,                # seconds without a key press before the screen turns off (0 = never)
}

_data = None
_dirty = False


def _load():
    global _data
    _data = dict(DEFAULTS)
    try:
        with open(PATH) as f:
            saved = json.load(f)
        for k in DEFAULTS:
            if k in saved:
                _data[k] = saved[k]
    except (OSError, ValueError):
        pass


def get(key):
    if _data is None:
        _load()
    return _data[key]


def set(key, value):
    global _dirty
    if _data is None:
        _load()
    if _data.get(key) != value:
        _data[key] = value
        _dirty = True


def save():
    global _dirty
    if not _dirty:
        return
    try:
        with open(PATH, "w") as f:
            json.dump(_data, f)
        _dirty = False
    except OSError as e:
        print("settings save failed:", e)


def apply():
    """Push brightness and volume to the hardware (called at boot)."""
    import M5
    try:
        M5.Lcd.setBrightness(get("brightness"))
    except Exception as e:
        print("brightness:", e)
    try:
        M5.Speaker.setVolume(get("volume"))
    except Exception as e:
        print("volume:", e)
