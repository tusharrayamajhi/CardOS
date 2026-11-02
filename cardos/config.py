# CardOS settings -- edit these to taste.

# Default local time offset from UTC in minutes (Nepal = +5:45 = 345).
# Once changed in the Settings app, the saved value is used instead.
TZ_OFFSET_MIN = 345

# WiFi country (sets the legal channels; Nepal uses 1-13).
WIFI_COUNTRY = "NP"

# Name shown in the middle of the top bar.
TITLE = "Tushar"

# Key click sound (a short beep on every key press, in every app).
# KEY_CLICK and CLICK_VOLUME are defaults; the Settings app overrides them.
KEY_CLICK = True
CLICK_VOLUME = 80      # speaker volume 0-255
CLICK_MS = 50          # beep length in ms (the speaker drops tones shorter than ~45 ms)
CLICK_FREQ = 3000      # normal keys (Hz)
CLICK_FREQ_ENTER = 4200
CLICK_FREQ_ESC = 1800

# Where the launcher looks for apps.
APPS_DIR = "/flash/apps"

# Screen layout (Cardputer display is 240 x 135).
W = 240
H = 135
TOP_H = 16                 # top status bar height
BOTTOM_H = 16              # bottom info bar height
APP_TOP = TOP_H            # first row apps may draw on
APP_BOTTOM = H - BOTTOM_H  # first row of the bottom bar

# Colors (0xRRGGBB)
BG = 0x0F172A
BAR_BG = 0x020617
FG = 0xE2E8F0
DIM = 0x475569
ACCENT = 0x38BDF8
GREEN = 0x22C55E
YELLOW = 0xEAB308
RED = 0xEF4444
