# CardOS launcher: home screen, app discovery and the app runner.
#
# An app is one .py file in /flash/apps with this at the top:
#
#   NAME = "Clock"          # shown under the icon
#   ICON = "clock"          # glyph name from cardos/icons.py, or a .png path
#   COLOR = 0x2563EB        # icon tile color
#   NET = True              # optional: the app uses the internet (HTTPS)
#
#   def run(ctx):           # called when the user opens the app
#       ctx.clear()
#       while True:
#           keys = ctx.tick()        # keeps the bars alive, returns key presses
#           if ctx.ESC in keys:
#               return               # back to the home screen
#
# Other ctx helpers: ctx.clear(), ctx.fullscreen(True/False), ctx.lcd, ctx.config,
# ctx.keep_awake = True (stop screen sleep), ctx.wake(), ctx.click = False (no key beep).
# Shared services live in cardos/ too, e.g. `from cardos import sd; sd.mount()`.
#
# Files without NAME are ignored, so other scripts can live in the folder too.
import gc
import os
import sys
import time
import M5
from M5 import Lcd
from cardos import config as C
from cardos import keys as K
from cardos import icons
from cardos import settings
from cardos import net
from cardos.statusbar import StatusBar
from cardos.bottombar import BottomBar

# Home screen carousel. Slot 0 is the selected app in the middle, slot 1 the
# apps right next to it, slot 2 the ones near the edges, slot 3 off-screen.
SLOT_X = (0, 64, 104, 150)          # distance of the icon center from screen center
SLOT_SIZE = (56, 36, 24, 16)
SLOT_DIM = (0.0, 0.45, 0.65, 0.85)  # how much the icon fades into the background
BAND_Y = C.APP_TOP + 4              # top of the icon strip
BAND_H = 60
NAME_Y = BAND_Y + BAND_H + 4
ANIM_FRAMES = 9
ANIM_FRAME_MS = 20                  # ~180 ms per slide


def _slot(p):
    """Center x, size and dim for a (fractional) position p from the middle."""
    a = min(abs(p), 3.0)
    i = min(int(a), 2)
    t = a - i
    x = SLOT_X[i] + (SLOT_X[i + 1] - SLOT_X[i]) * t
    size = SLOT_SIZE[i] + (SLOT_SIZE[i + 1] - SLOT_SIZE[i]) * t
    dim = SLOT_DIM[i] + (SLOT_DIM[i + 1] - SLOT_DIM[i]) * t
    return int(C.W // 2 + (x if p >= 0 else -x)), int(size), dim


SCREEN_ON, SCREEN_DIM, SCREEN_OFF = 0, 1, 2


class Context:
    """What the OS hands to every app."""
    # screen area apps may draw on (between the bars)
    TOP = C.APP_TOP
    BOTTOM = C.APP_BOTTOM
    W = C.W
    # key names
    ESC = K.ESC
    ENTER = K.ENTER
    LEFT = K.LEFT
    RIGHT = K.RIGHT
    UP = K.UP
    DOWN = K.DOWN
    BACKSPACE = K.BACKSPACE

    def __init__(self, kb, top, bottom):
        self.lcd = Lcd
        self.config = C
        self._kb = kb
        self._top = top
        self._bottom = bottom
        self._bars = True
        self.click = settings.get("click")  # apps may set False to silence key clicks
        self.keep_awake = False             # apps may set True to stop the screen sleeping
        self._last_input = time.ticks_ms()
        self._screen = SCREEN_ON

    def tick(self):
        """Call once per loop: updates both bars, returns new key presses."""
        M5.update()
        pressed = self._kb.poll() if self._kb else []
        now = time.ticks_ms()
        if pressed:
            self._last_input = now
            if self._screen != SCREEN_ON:
                self.wake()
                pressed = []  # the key that wakes the screen does nothing else
        elif not self.keep_awake:
            self._check_sleep(now)
        if pressed and self.click:
            self._click(pressed[-1])
        if self._bars and self._screen != SCREEN_OFF:
            self._top.update()
            self._bottom.update()
        return pressed

    # ---- screen sleep: dim a little before the timeout, then turn the backlight off
    def _check_sleep(self, now):
        timeout = settings.get("sleep") * 1000
        if timeout <= 0 or self._screen == SCREEN_OFF:
            return
        idle = time.ticks_diff(now, self._last_input)
        if idle >= timeout:
            Lcd.setBrightness(0)
            self._screen = SCREEN_OFF
        elif self._screen == SCREEN_ON and idle >= timeout - min(10000, timeout // 2):
            Lcd.setBrightness(max(8, settings.get("brightness") // 4))
            self._screen = SCREEN_DIM

    def wake(self):
        """Turn the screen back on (apps can call this, e.g. when an alarm goes off)."""
        self._last_input = time.ticks_ms()
        if self._screen != SCREEN_ON:
            Lcd.setBrightness(settings.get("brightness"))
            self._screen = SCREEN_ON

    def screen_on(self):
        return self._screen == SCREEN_ON

    def caps(self):
        """True while Caps Lock is on (for showing a CAPS indicator)."""
        return bool(self._kb and self._kb.caps)

    def _click(self, key):
        """Short non-blocking beep; Enter sounds higher, Esc lower."""
        if key == K.ENTER:
            freq = C.CLICK_FREQ_ENTER
        elif key == K.ESC:
            freq = C.CLICK_FREQ_ESC
        else:
            freq = C.CLICK_FREQ
        try:
            M5.Speaker.tone(freq, C.CLICK_MS)
        except Exception:
            pass

    def fullscreen(self, on=True):
        """Hide the bars so the app owns the whole 240x135 screen (or bring them back)."""
        self._bars = not on
        if not on:
            self.redraw_bars()

    def clear(self, color=C.BG):
        """Clear the app area (everything between the bars)."""
        Lcd.fillRect(0, self.TOP, self.W, self.BOTTOM - self.TOP, color)

    def wifi_autoconnect(self, on):
        """Pause (False) or resume (True) re-joining the saved WiFi in the background."""
        self._top.paused = not on

    def redraw_bars(self):
        self._top.invalidate()
        self._bottom.invalidate()
        self._top.update()
        self._bottom.update()


# ------------------------------------------------------------ app discovery
def _parse_value(raw):
    raw = raw.split("#")[0].strip()
    if raw[:1] in ("'", '"'):
        return raw[1:-1]
    try:
        return int(raw, 0)
    except ValueError:
        return raw


def read_app_info(path):
    """Read NAME / ICON / COLOR from the top of an app file without importing it."""
    info = {}
    try:
        with open(path) as f:
            for _ in range(40):
                line = f.readline()
                if not line:
                    break
                for key in ("NAME", "ICON", "COLOR", "NET"):
                    if line.startswith(key) and "=" in line:
                        name, _, value = line.partition("=")
                        if name.strip() == key:
                            info[key] = _parse_value(value)
    except OSError:
        return None
    if "NAME" not in info:
        return None
    return info


def scan_apps():
    apps = []
    try:
        files = sorted(os.listdir(C.APPS_DIR))
    except OSError:
        return apps
    for fname in files:
        if not fname.endswith(".py") or fname.startswith("_"):
            continue
        info = read_app_info(C.APPS_DIR + "/" + fname)
        if info:
            apps.append({
                "module": fname[:-3],
                "name": str(info["NAME"]),
                "icon": info.get("ICON", ""),
                "color": info.get("COLOR", C.ACCENT),
                "net": info.get("NET") == "True",
            })
    return apps


# ----------------------------------------------------------------- launcher
class Launcher:
    def __init__(self, ctx):
        self.ctx = ctx
        self.apps = scan_apps()
        self.sel = 0
        self.canvas = None
        # Pre-compiled apps (made by deploy.ps1) load first: importing a .py
        # means compiling it on the device, which needs a lot of free RAM.
        for path in (C.APPS_DIR + "/mpy", C.APPS_DIR):
            if path not in sys.path:
                sys.path.append(path)

    # ---- off-screen strip for flicker-free animation
    def open_canvas(self):
        if self.canvas is None:
            gc.collect()   # an app that just closed may still be giving RAM back
            self.canvas = net.new_canvas(C.W, BAND_H)
            if self.canvas is None:
                print("no RAM for the canvas, drawing without animation")

    def close_canvas(self):
        if self.canvas is not None:
            try:
                self.canvas.delete()
            except Exception:
                pass
            self.canvas = None

    # ---- drawing
    def draw_strip(self, phase=0.0, sel=None, mid=0.0):
        """Draw the icon strip with every app shifted left by `phase` slots.

        `mid` is where the selection is heading (0 when still, +-0.5 while
        sliding), so each app appears only once even when the list wraps.
        """
        sel = self.sel if sel is None else sel
        n = len(self.apps)
        g = self.canvas
        if g is not None:
            g.fillScreen(C.BG)
            oy = 0
        else:
            g = Lcd
            oy = BAND_Y
            Lcd.fillRect(0, BAND_Y, C.W, BAND_H, C.BG)
        items = []
        for j in range(n):
            d = (j - sel) % n
            o = d if abs(d - mid) <= abs(d - n - mid) else d - n
            p = o - phase
            if abs(p) < 2.95:
                items.append((abs(p), p, j))
        items.sort(reverse=True)            # far icons first, the middle one on top
        for _, p, j in items:
            cx, size, dim = _slot(p)
            app = self.apps[j]
            icons.draw(app["icon"], app["name"], cx - size // 2,
                       oy + (BAND_H - size) // 2, size, app["color"],
                       g=g, dim=dim, dim_to=C.BG)
        if self.canvas is not None:
            self.canvas.push(0, BAND_Y)

    def draw_info(self):
        """Name of the selected app and the page dots under the strip."""
        Lcd.fillRect(0, NAME_Y, C.W, C.APP_BOTTOM - NAME_Y, C.BG)
        n = len(self.apps)
        Lcd.setFont(Lcd.FONTS.DejaVu18)
        Lcd.setTextColor(C.FG, C.BG)
        Lcd.drawCenterString(self.apps[self.sel]["name"], C.W // 2, NAME_Y)

        # page dots (or "3/12" when there are many apps)
        dy = C.APP_BOTTOM - 8
        if n <= 10:
            x0 = C.W // 2 - (n - 1) * 5
            for i in range(n):
                if i == self.sel:
                    Lcd.fillCircle(x0 + i * 10, dy, 3, C.ACCENT)
                else:
                    Lcd.fillCircle(x0 + i * 10, dy, 2, C.DIM)
        else:
            Lcd.setFont(Lcd.FONTS.DejaVu9)
            Lcd.setTextColor(C.DIM, C.BG)
            Lcd.drawCenterString("%d/%d" % (self.sel + 1, n), C.W // 2, dy - 4)

    def draw_home(self):
        self.ctx.clear()
        if not self.apps:
            Lcd.setFont(Lcd.FONTS.DejaVu12)
            Lcd.setTextColor(C.DIM, C.BG)
            Lcd.drawCenterString("No apps in " + C.APPS_DIR, C.W // 2, C.APP_TOP + 40)
            return
        self.open_canvas()
        self.draw_strip()
        self.draw_info()

    def move(self, step):
        """Slide the strip one app left (-1) or right (+1)."""
        n = len(self.apps)
        if n < 2:
            return
        old = self.sel
        self.sel = (old + step) % n
        if self.canvas is None:
            self.open_canvas()          # retry: RAM may have freed up since
        if self.canvas is not None:
            for f in range(1, ANIM_FRAMES):
                start = time.ticks_ms()
                t = f / ANIM_FRAMES
                ease = 1 - (1 - t) ** 3     # fast start, gentle stop
                self.draw_strip(step * ease, old, step * 0.5)
                wait = ANIM_FRAME_MS - time.ticks_diff(time.ticks_ms(), start)
                if wait > 0:
                    time.sleep_ms(wait)
        self.draw_strip()
        self.draw_info()

    def run_app(self, app):
        mod_name = app["module"]
        if app["net"] and self.canvas is not None:
            # hand the canvas's RAM to HTTPS as its reserve (see cardos/net.py)
            net.hold_reserve(self.canvas)
            self.canvas = None
        else:
            self.close_canvas()  # give its memory to the app
        self.ctx.clear()
        try:
            mod = __import__(mod_name)
            mod.run(self.ctx)
        except Exception as e:
            sys.print_exception(e)
            self.show_error(app["name"], e)
        finally:
            net.drop_reserve()
            self.ctx._bars = True
            # unload the app so its RAM is freed
            mod = None
            if mod_name in sys.modules:
                del sys.modules[mod_name]
            gc.collect()

    def show_error(self, name, err):
        self.ctx.clear(0x450A0A)
        Lcd.setFont(Lcd.FONTS.DejaVu12)
        Lcd.setTextColor(0xFFFFFF, 0x450A0A)
        Lcd.drawString(name + " crashed:", 6, C.APP_TOP + 8)
        msg = "%s: %s" % (type(err).__name__, err)
        Lcd.setFont(Lcd.FONTS.DejaVu9)
        Lcd.setTextColor(0xFCA5A5, 0x450A0A)
        for i in range(5):
            part = msg[i * 38:(i + 1) * 38]
            if not part:
                break
            Lcd.drawString(part, 6, C.APP_TOP + 28 + i * 12)
        Lcd.setTextColor(0xFFFFFF, 0x450A0A)
        Lcd.drawString("press any key", 6, C.APP_BOTTOM - 14)
        while not self.ctx.tick():
            time.sleep_ms(20)

    def loop(self):
        Lcd.fillScreen(C.BG)
        self.ctx.redraw_bars()
        self.draw_home()
        while True:
            pressed = self.ctx.tick()
            n = len(self.apps)
            for k in pressed:
                if n and k in (K.LEFT, "a", ","):
                    self.move(-1)
                elif n and k in (K.RIGHT, "d", "/"):
                    self.move(1)
                elif n and k in (K.ENTER, " "):
                    self.run_app(self.apps[self.sel])
                    Lcd.fillScreen(C.BG)
                    self.ctx.redraw_bars()
                    self.draw_home()
                    break
            time.sleep_ms(15)


def start():
    M5.begin()
    K.silence_irq()  # M5.begin() may re-arm the firmware keyboard IRQ
    try:
        M5.Speaker.begin()
    except Exception as e:
        print("speaker init failed:", e)
    settings.apply()  # saved brightness and volume
    try:
        kb = K.Keyboard()
    except Exception as e:
        print("keyboard init failed:", e)
        kb = None
    ctx = Context(kb, StatusBar(), BottomBar())
    print("CardOS started")
    Launcher(ctx).loop()
