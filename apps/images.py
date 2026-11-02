NAME = "Images"
ICON = "image"
COLOR = 0xDB2777

# Browse the SD card and view JPG / PNG / BMP pictures.
#   List:   ; . (up/down)  Enter or / = open   , or Backspace = up a folder   Esc = back
#   Viewer: , / = previous / next picture   = / - = zoom in / out (then , / ; . move around)
#           0 = fit   h = hide hints   Esc = un-zoom / back   Enter or Backspace = back to list
import os
import time
from cardos import sd

IMG_EXT = (".jpg", ".jpeg", ".png", ".bmp")
ROW_H = 14
LIST_TOP = 31          # below the path header
MAX_PATH = 60          # the display driver silently fails on longer paths
TMP = sd.ROOT + "/.cardos_view"


# ------------------------------------------------------------ files
def join(a, b):
    return a + b if a.endswith("/") else a + "/" + b


def parent(path):
    i = path.rstrip("/").rfind("/")
    return path[:i] if i > 0 else sd.ROOT


def scan(path):
    """Folders first, then pictures. Hidden entries are skipped."""
    dirs, files = [], []
    try:
        for e in os.ilistdir(path):
            name, typ = e[0], e[1]
            if name.startswith("."):
                continue
            if typ & 0x4000:
                dirs.append((name, True))
            elif name.lower().endswith(IMG_EXT):
                files.append((name, False))
    except OSError as e:
        print("listdir failed:", e)
    dirs.sort(key=lambda x: x[0].lower())
    files.sort(key=lambda x: x[0].lower())
    return dirs + files


def image_info(path):
    """Return (width, height, problem) from the file header; problem is None if drawable."""
    try:
        with open(path, "rb") as f:
            head = f.read(26)
            if head[:8] == b"\x89PNG\r\n\x1a\n":
                return (int.from_bytes(head[16:20], "big"),
                        int.from_bytes(head[20:24], "big"), None)
            if head[:2] == b"BM":
                w = int.from_bytes(head[18:22], "little")
                h = int.from_bytes(head[22:26], "little")
                if h > 0x7FFFFFFF:
                    h = 0x100000000 - h  # top-down BMP stores a negative height
                return (w, h, None)
            if head[:2] != b"\xff\xd8":
                return (0, 0, "not a picture file")
            f.seek(2)
            while True:
                b = f.read(1)
                if not b:
                    return (0, 0, "damaged JPEG")
                if b != b"\xff":
                    continue
                m = f.read(1)
                while m == b"\xff":
                    m = f.read(1)
                if not m:
                    return (0, 0, "damaged JPEG")
                mv = m[0]
                if mv in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                          0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                    f.read(3)
                    h = int.from_bytes(f.read(2), "big")
                    w = int.from_bytes(f.read(2), "big")
                    if mv == 0xC2:
                        return (w, h, "progressive JPEG (not supported)")
                    return (w, h, None)
                if mv in (0xD8, 0xD9) or 0xD0 <= mv <= 0xD7:
                    continue
                f.seek(int.from_bytes(f.read(2), "big") - 2, 1)
    except OSError as e:
        return (0, 0, "can't read file (%s)" % e)


def short_path(path):
    """Long paths make the display driver fail, so copy those to a short temp file."""
    if len(path) <= MAX_PATH:
        return path
    tmp = TMP + path[path.rfind("."):].lower()
    buf = bytearray(4096)
    mv = memoryview(buf)
    with open(path, "rb") as src, open(tmp, "wb") as dst:
        while True:
            n = src.readinto(buf)
            if not n:
                break
            dst.write(mv[:n])
    return tmp


def remove_tmp():
    for ext in IMG_EXT:
        try:
            os.remove(TMP + ext)
        except OSError:
            pass


# ------------------------------------------------------------ app
class Images:
    def __init__(self, ctx):
        self.ctx = ctx
        self.lcd = ctx.lcd
        self.C = ctx.config
        self.rows = (ctx.BOTTOM - LIST_TOP) // ROW_H
        self.cwd = sd.ROOT
        self.entries = []
        self.sel = 0
        self.offset = 0

    # ---- list screen
    def open_dir(self, path, select_name=None):
        self.cwd = path
        self.entries = scan(path)
        self.sel = 0
        if select_name:
            for i, (name, _) in enumerate(self.entries):
                if name == select_name:
                    self.sel = i
                    break
        self.offset = max(0, self.sel - self.rows + 1)

    def draw_list(self):
        lcd, C = self.lcd, self.C
        self.ctx.clear()
        lcd.fillRect(0, self.ctx.TOP, self.ctx.W, LIST_TOP - self.ctx.TOP - 1, 0x1E293B)
        lcd.setFont(lcd.FONTS.DejaVu9)
        lcd.setTextColor(C.ACCENT, 0x1E293B)
        path = self.cwd if len(self.cwd) <= 30 else "..." + self.cwd[-27:]
        lcd.drawString(path, 4, self.ctx.TOP + 3)
        n_img = sum(1 for e in self.entries if not e[1])
        lcd.setTextColor(C.DIM, 0x1E293B)
        lcd.drawRightString("%d pics" % n_img, self.ctx.W - 4, self.ctx.TOP + 3)

        if not self.entries:
            lcd.setFont(lcd.FONTS.DejaVu12)
            lcd.setTextColor(C.DIM, C.BG)
            lcd.drawCenterString("No folders or pictures here", self.ctx.W // 2, LIST_TOP + 30)
            return

        if self.sel < self.offset:
            self.offset = self.sel
        elif self.sel >= self.offset + self.rows:
            self.offset = self.sel - self.rows + 1

        lcd.setFont(lcd.FONTS.DejaVu12)
        for row in range(self.rows):
            i = self.offset + row
            if i >= len(self.entries):
                break
            self.draw_row(i)

        # scrollbar when the list is longer than the screen
        n = len(self.entries)
        if n > self.rows:
            track = self.rows * ROW_H
            bar = max(6, track * self.rows // n)
            y = LIST_TOP + (track - bar) * self.offset // (n - self.rows)
            lcd.fillRect(self.ctx.W - 3, LIST_TOP, 3, track, 0x1E293B)
            lcd.fillRect(self.ctx.W - 3, y, 3, bar, C.DIM)

    def draw_row(self, i):
        lcd, C = self.lcd, self.C
        name, is_dir = self.entries[i]
        y = LIST_TOP + (i - self.offset) * ROW_H
        bg = 0x334155 if i == self.sel else C.BG
        lcd.fillRect(0, y, self.ctx.W - 4, ROW_H, bg)
        if is_dir:
            lcd.fillRect(6, y + 3, 5, 2, C.YELLOW)
            lcd.fillRect(6, y + 4, 11, 7, C.YELLOW)
        else:
            lcd.drawRect(6, y + 2, 11, 9, 0xF472B6)
            lcd.fillTriangle(7, y + 9, 10, y + 5, 13, y + 9, 0xF472B6)
        lcd.setTextColor(0xFFFFFF if i == self.sel else C.FG, bg)
        label = name + "/" if is_dir else name
        lcd.drawString(label if len(label) <= 31 else label[:29] + "..", 22, y + 1)

    def move(self, step):
        if not self.entries:
            return
        new = max(0, min(len(self.entries) - 1, self.sel + step))
        if new == self.sel:
            return
        old, self.sel = self.sel, new
        if self.offset <= new < self.offset + self.rows:
            self.lcd.setFont(self.lcd.FONTS.DejaVu12)
            self.draw_row(old)       # only repaint the two rows that changed
            self.draw_row(new)
        else:
            self.draw_list()

    # ---- viewer
    def pictures(self):
        return [name for name, is_dir in self.entries if not is_dir]

    def view(self, name):
        """Full-screen viewer. Returns the name of the last picture shown."""
        pics = self.pictures()
        return Viewer(self.ctx, self.cwd, pics, pics.index(name)).run()

    # ---- main loop
    def wait_for_card(self):
        """Show a message until the SD card mounts. Returns False if the user pressed Esc."""
        lcd, C = self.lcd, self.C
        while not sd.mount():
            self.ctx.clear()
            lcd.setFont(lcd.FONTS.DejaVu12)
            lcd.setTextColor(C.RED, C.BG)
            lcd.drawCenterString("No SD card found", self.ctx.W // 2, self.ctx.TOP + 30)
            lcd.setTextColor(C.DIM, C.BG)
            lcd.drawCenterString("Enter = try again   Esc = back", self.ctx.W // 2, self.ctx.TOP + 55)
            while True:
                keys = self.ctx.tick()
                if self.ctx.ESC in keys:
                    return False
                if self.ctx.ENTER in keys:
                    break
                time.sleep_ms(20)
        return True

    def run(self):
        ctx = self.ctx
        ctx.clear()
        self.lcd.setFont(self.lcd.FONTS.DejaVu12)
        self.lcd.setTextColor(self.C.DIM, self.C.BG)
        self.lcd.drawCenterString("Reading SD card...", ctx.W // 2, ctx.TOP + 40)
        if not self.wait_for_card():
            return
        self.open_dir(sd.ROOT)
        self.draw_list()
        while True:
            for k in ctx.tick():
                if k in (ctx.UP, ";", "w"):
                    self.move(-1)
                elif k in (ctx.DOWN, ".", "s"):
                    self.move(1)
                elif k in (ctx.ENTER, ctx.RIGHT, " ") and self.entries:
                    name, is_dir = self.entries[self.sel]
                    if is_dir:
                        self.open_dir(join(self.cwd, name))
                    else:
                        last = self.view(name)
                        self.open_dir(self.cwd, last)
                    self.draw_list()
                elif k in (ctx.ESC, ctx.BACKSPACE, ctx.LEFT):
                    if self.cwd == sd.ROOT:
                        if k == ctx.ESC:
                            return             # only Esc leaves the app
                        continue
                    old = self.cwd[self.cwd.rfind("/") + 1:]
                    self.open_dir(parent(self.cwd), old)
                    self.draw_list()
            time.sleep_ms(15)


# ------------------------------------------------------------ viewer
SW, SH = 240, 135                       # full screen
ZOOMS = (1, 1.5, 2, 3, 4, 6, 8, 12)     # multiples of the fit-to-screen size
WHITE, BLACK = 0xFFFFFF, 0x000000


class Viewer:
    """Full-screen picture viewer with zoom and pan.

    Not zoomed: , / = previous / next picture
    Zoomed:     , / ; . = pan left / right / up / down
    = or +: zoom in   - : zoom out   0: fit   h: hide/show the on-screen hints
    Esc: zoom back to fit, or back to the list   Enter / Backspace: back to the list
    """

    def __init__(self, ctx, folder, pics, idx):
        self.ctx = ctx
        self.lcd = ctx.lcd
        self.C = ctx.config
        self.folder = folder
        self.pics = pics
        self.idx = idx
        self.hints = True

    # ---- picture state
    def load(self):
        """Read the current picture's header and reset zoom/pan."""
        self.path = join(self.folder, self.pics[self.idx])
        self.src = None             # short path, copied lazily on first draw
        self.w, self.h, self.problem = image_info(self.path)
        if not self.problem and (self.w <= 0 or self.h <= 0):
            self.problem = "unknown picture size"
        self.level = 0
        self.max_level = 0
        if not self.problem:
            self.fit = min(SW / self.w, SH / self.h, 2.0)
            self.cx, self.cy = self.w / 2, self.h / 2
            # only offer zoom levels up to the picture's real (100%) size
            for i, z in enumerate(ZOOMS):
                if self.fit * z <= max(1.0, self.fit):
                    self.max_level = i

    def scale(self):
        return self.fit * ZOOMS[self.level]

    def clamp(self):
        """Keep the view inside the picture; center an axis that fits on screen."""
        s = self.scale()
        half_w, half_h = SW / 2 / s, SH / 2 / s
        if half_w * 2 >= self.w:
            self.cx = self.w / 2
        else:
            self.cx = min(max(self.cx, half_w), self.w - half_w)
        if half_h * 2 >= self.h:
            self.cy = self.h / 2
        else:
            self.cy = min(max(self.cy, half_h), self.h - half_h)

    def placement(self):
        """Screen position and size of the scaled picture (may be partly off-screen)."""
        s = self.scale()
        return (int(SW / 2 - self.cx * s), int(SH / 2 - self.cy * s),
                int(self.w * s), int(self.h * s))

    # ---- drawing
    def render(self, busy_text=None):
        lcd = self.lcd
        if self.problem:
            self.draw_problem()
            self.draw_hints()
            return
        x, y, dw, dh = self.placement()
        if busy_text:
            self.pill(busy_text, SW - 4, 3, align="right")
        if x > 0 or y > 0 or x + dw < SW or y + dh < SH:
            lcd.fillScreen(BLACK)   # picture doesn't cover the screen: clear the margins
        low = self.path.lower()
        if low.endswith(".png"):
            draw = lcd.drawPng
        elif low.endswith(".bmp"):
            draw = lcd.drawBmp
        else:
            draw = lcd.drawJpg
        try:
            if self.src is None:
                self.src = short_path(self.path)
            s = self.scale()
            # negative x/y just pushes the picture off-screen; the display clips it
            draw(self.src, x, y, 0, 0, 0, 0, s, s)
        except Exception as e:
            self.problem = str(e)
            self.draw_problem()
        self.draw_hints()

    def draw_problem(self):
        lcd = self.lcd
        lcd.fillScreen(BLACK)
        lcd.setFont(lcd.FONTS.DejaVu12)
        lcd.setTextColor(self.C.RED, BLACK)
        lcd.drawCenterString("Can't show this picture", SW // 2, 40)
        lcd.setFont(lcd.FONTS.DejaVu9)
        lcd.setTextColor(self.C.FG, BLACK)
        lcd.drawCenterString(self.problem[:40], SW // 2, 62)
        name = self.pics[self.idx]
        lcd.setTextColor(self.C.DIM, BLACK)
        lcd.drawCenterString(name if len(name) <= 40 else name[:38] + "..", SW // 2, 80)

    def pill(self, text, x, y, align="center"):
        """Small dark rounded label so text stays readable on top of a picture."""
        lcd = self.lcd
        lcd.setFont(lcd.FONTS.DejaVu9)
        w = lcd.textWidth(text) + 10
        if align == "center":
            left = x - w // 2
        elif align == "right":
            left = x - w
        else:
            left = x
        lcd.fillRoundRect(left, y, w, 13, 6, BLACK)
        lcd.drawRoundRect(left, y, w, 13, 6, 0x475569)
        lcd.setTextColor(WHITE, BLACK)
        lcd.drawString(text, left + 5, y + 2)

    def arrow_button(self, cx, cy, direction):
        """Round button with a triangle pointing 'l', 'r', 'u' or 'd'."""
        lcd = self.lcd
        lcd.fillCircle(cx, cy, 10, BLACK)
        lcd.drawCircle(cx, cy, 10, WHITE)
        if direction == "l":
            lcd.fillTriangle(cx - 4, cy, cx + 3, cy - 6, cx + 3, cy + 6, WHITE)
        elif direction == "r":
            lcd.fillTriangle(cx + 4, cy, cx - 3, cy - 6, cx - 3, cy + 6, WHITE)
        elif direction == "u":
            lcd.fillTriangle(cx, cy - 4, cx - 6, cy + 3, cx + 6, cy + 3, WHITE)
        else:
            lcd.fillTriangle(cx, cy + 4, cx - 6, cy - 3, cx + 6, cy - 3, WHITE)

    def draw_hints(self):
        if not self.hints:
            return
        n = len(self.pics)
        label = "%d/%d" % (self.idx + 1, n)
        if self.level == 0:
            if n > 1:                       # , / flip to the previous / next picture
                self.arrow_button(13, SH // 2, "l")
                self.arrow_button(SW - 13, SH // 2, "r")
            if not self.problem:
                self.pill("= zoom in   h hide", SW // 2, SH - 16)
        else:
            z = ZOOMS[self.level]
            label += "  %sx" % (("%d" % z) if z == int(z) else ("%.1f" % z))
            # arrows only toward the parts of the picture that are off-screen
            x, y, dw, dh = self.placement()
            if x < 0:
                self.arrow_button(13, SH // 2, "l")
            if x + dw > SW:
                self.arrow_button(SW - 13, SH // 2, "r")
            if y < 0:
                self.arrow_button(SW // 2, 30, "u")
            if y + dh > SH:
                self.arrow_button(SW // 2, SH - 13, "d")
            self.pill("- zoom out", 4, SH - 16, align="left")
        self.pill(label, SW // 2, 3)

    # ---- actions
    def show_new(self):
        self.load()
        self.lcd.fillScreen(BLACK)
        self.pill("Loading %d/%d ..." % (self.idx + 1, len(self.pics)), SW // 2, SH // 2 - 6)
        self.render()

    def flip(self, step):
        if len(self.pics) > 1:
            self.idx = (self.idx + step) % len(self.pics)
            self.show_new()

    def zoom(self, level):
        if self.problem:
            return
        level = max(0, min(self.max_level, level))
        if level != self.level:
            self.level = level
            self.clamp()
            self.render("zooming...")

    def pan(self, dx, dy):
        """Move the view a third of the screen in the given direction."""
        s = self.scale()
        old = (self.cx, self.cy)
        self.cx += dx * (SW / 3) / s
        self.cy += dy * (SH / 3) / s
        self.clamp()
        if (self.cx, self.cy) != old:
            self.render("moving...")

    def run(self):
        ctx = self.ctx
        ctx.fullscreen(True)
        self.show_new()
        while True:
            for k in ctx.tick():
                zoomed = self.level > 0
                if k in (ctx.ENTER, ctx.BACKSPACE) or (k == ctx.ESC and not zoomed):
                    ctx.fullscreen(False)
                    return self.pics[self.idx]
                elif k == ctx.ESC or k == "0":
                    self.zoom(0)
                elif k in ("=", "+"):
                    self.zoom(self.level + 1)
                elif k in ("-", "_"):
                    self.zoom(self.level - 1)
                elif k in ("h", "H"):
                    self.hints = not self.hints
                    self.render()
                elif k in (ctx.LEFT, ",", "a"):
                    if zoomed:
                        self.pan(-1, 0)
                    else:
                        self.flip(-1)
                elif k in (ctx.RIGHT, "/", "d", " "):
                    if zoomed:
                        self.pan(1, 0)
                    else:
                        self.flip(1)
                elif k in (ctx.UP, ";", "w"):
                    if zoomed:
                        self.pan(0, -1)
                    else:
                        self.flip(-1)
                elif k in (ctx.DOWN, ".", "s"):
                    if zoomed:
                        self.pan(0, 1)
                    else:
                        self.flip(1)
            time.sleep_ms(20)


def run(ctx):
    try:
        Images(ctx).run()
    finally:
        remove_tmp()
