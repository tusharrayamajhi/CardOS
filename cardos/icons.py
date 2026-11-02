# CardOS app icons: a colored rounded tile with a simple glyph, at any size.
# An app picks a glyph by name (ICON = "clock"), or gives a PNG path
# (ICON = "/flash/apps/myapp.png", drawn as-is), or an image set prefix
# (ICON = "/flash/res/npl/icon" -> icon_56.bmp, _36, _24, _16), or gets its
# first letter.
#
# Glyphs are designed on a 56 px tile and scaled by k = size / 56.
# `g` is where to draw: the Lcd itself or an off-screen canvas.
from M5 import Lcd

WHITE = 0xFFFFFF
IMAGE_SIZES = (56, 36, 24, 16)   # sizes an image icon set provides, largest first


def _s(v, k):
    return max(1, int(v * k + 0.5))


def _clock(g, cx, cy, k, col, fg):
    g.fillCircle(cx, cy, _s(18, k), fg)
    g.fillCircle(cx, cy, _s(15, k), col)
    g.fillRect(cx - _s(1, k), cy - _s(11, k), _s(3, k), _s(12, k), fg)   # minute hand
    g.fillRect(cx, cy - _s(1, k), _s(9, k), _s(3, k), fg)                # hour hand
    g.fillCircle(cx, cy, _s(2, k), fg)


def _info(g, cx, cy, k, col, fg):
    g.fillCircle(cx, cy, _s(18, k), fg)
    g.fillCircle(cx, cy, _s(15, k), col)
    g.fillCircle(cx, cy - _s(8, k), _s(3, k), fg)
    g.fillRect(cx - _s(2, k), cy - _s(2, k), _s(5, k), _s(13, k), fg)


def _wifi(g, cx, cy, k, col, fg):
    by = cy + _s(10, k)
    for r in (20, 13, 6):
        g.fillArc(cx, by, _s(r - 3, k), _s(r, k), 225, 315, fg)
    g.fillCircle(cx, by, _s(2, k), fg)


def _folder(g, cx, cy, k, col, fg):
    g.fillRoundRect(cx - _s(18, k), cy - _s(13, k), _s(14, k), _s(6, k), _s(2, k), fg)
    g.fillRoundRect(cx - _s(18, k), cy - _s(9, k), _s(36, k), _s(24, k), _s(3, k), fg)


def _image(g, cx, cy, k, col, fg):
    g.fillRoundRect(cx - _s(18, k), cy - _s(14, k), _s(36, k), _s(28, k), _s(3, k), fg)
    g.fillRect(cx - _s(15, k), cy - _s(11, k), _s(30, k), _s(22, k), col)
    g.fillCircle(cx + _s(7, k), cy - _s(5, k), _s(3, k), fg)
    b = cy + _s(10, k)
    g.fillTriangle(cx - _s(14, k), b, cx - _s(4, k), cy - _s(3, k), cx + _s(6, k), b, fg)
    g.fillTriangle(cx + _s(1, k), b, cx + _s(8, k), cy + _s(2, k), cx + _s(14, k), b, fg)


def _game(g, cx, cy, k, col, fg):
    g.fillRoundRect(cx - _s(20, k), cy - _s(10, k), _s(40, k), _s(22, k), _s(9, k), fg)
    g.fillRect(cx - _s(14, k), cy, _s(10, k), _s(3, k), col)
    g.fillRect(cx - _s(10, k), cy - _s(4, k), _s(3, k), _s(11, k), col)
    g.fillCircle(cx + _s(9, k), cy - _s(1, k), _s(2, k), col)
    g.fillCircle(cx + _s(13, k), cy + _s(4, k), _s(2, k), col)


def _gear(g, cx, cy, k, col, fg):
    for dx, dy in ((0, -15), (0, 15), (-15, 0), (15, 0),
                   (-11, -11), (11, 11), (-11, 11), (11, -11)):
        g.fillCircle(cx + int(dx * k), cy + int(dy * k), _s(4, k), fg)
    g.fillCircle(cx, cy, _s(13, k), fg)
    g.fillCircle(cx, cy, _s(5, k), col)


def _mic(g, cx, cy, k, col, fg):
    g.fillRoundRect(cx - _s(7, k), cy - _s(17, k), _s(14, k), _s(24, k), _s(7, k), fg)  # capsule
    g.fillArc(cx, cy - _s(1, k), _s(10, k), _s(13, k), 0, 180, fg)                     # holder
    g.fillRect(cx - _s(1, k), cy + _s(12, k), _s(3, k), _s(5, k), fg)                  # stem
    g.fillRoundRect(cx - _s(8, k), cy + _s(16, k), _s(16, k), _s(3, k), _s(1, k), fg)  # base


def _cricket(g, cx, cy, k, col, fg):
    # bat: a slanted blade made of two triangles, plus a handle
    bx, by = cx - _s(4, k), cy + _s(2, k)
    g.fillTriangle(bx - _s(13, k), by + _s(13, k), bx - _s(7, k), by + _s(17, k), bx + _s(6, k), by - _s(6, k), fg)
    g.fillTriangle(bx - _s(13, k), by + _s(13, k), bx + _s(6, k), by - _s(6, k), bx, by - _s(10, k), fg)
    g.fillTriangle(bx + _s(2, k), by - _s(9, k), bx + _s(5, k), by - _s(7, k), bx + _s(11, k), by - _s(16, k), fg)
    g.fillTriangle(bx + _s(2, k), by - _s(9, k), bx + _s(11, k), by - _s(16, k), bx + _s(8, k), by - _s(18, k), fg)
    # ball
    g.fillCircle(cx + _s(11, k), cy + _s(10, k), _s(6, k), fg)
    g.drawArc(cx + _s(11, k), cy + _s(10, k), _s(3, k), _s(3, k), 300, 60, col)


GLYPHS = {
    "cricket": _cricket,
    "mic": _mic,
    "clock": _clock, "info": _info, "wifi": _wifi, "folder": _folder,
    "image": _image, "game": _game, "gear": _gear,
}


def blend(c1, c2, t):
    """Mix two 0xRRGGBB colors: t=0 -> c1, t=1 -> c2."""
    r = int(((c1 >> 16) & 255) * (1 - t) + ((c2 >> 16) & 255) * t)
    gr = int(((c1 >> 8) & 255) * (1 - t) + ((c2 >> 8) & 255) * t)
    b = int((c1 & 255) * (1 - t) + (c2 & 255) * t)
    return (r << 16) | (gr << 8) | b


def draw(icon, name, x, y, size, color, g=None, dim=0.0, dim_to=0x000000):
    """Draw an app icon tile with its top-left corner at (x, y).

    dim (0..1) fades the icon toward `dim_to` (used for the side icons).
    """
    g = g or Lcd
    if icon and icon.startswith("/") and "." not in icon:
        # image icon set: <icon>_56.bmp, _36, _24, _16 (full tiles, one per carousel size)
        s = 16
        for s in IMAGE_SIZES:
            if s <= size:
                break
        try:
            off = (size - s) // 2
            g.drawBmp("%s_%d.bmp" % (icon, s), x + off, y + off)
            return
        except Exception:
            pass
    if icon and icon.endswith(".png"):
        try:
            g.drawPng(icon, x, y)
            return
        except Exception:
            pass
    col = blend(color, dim_to, dim) if dim else color
    fg = blend(WHITE, dim_to, dim) if dim else WHITE
    k = size / 56
    g.fillRoundRect(x, y, size, size, _s(10, k), col)
    cx, cy = x + size // 2, y + size // 2
    glyph = GLYPHS.get(icon)
    if glyph:
        glyph(g, cx, cy, k, col, fg)
    else:
        if size >= 44:
            font, h = Lcd.FONTS.DejaVu24, 24
        elif size >= 28:
            font, h = Lcd.FONTS.DejaVu18, 18
        else:
            font, h = Lcd.FONTS.DejaVu12, 12
        g.setFont(font)
        g.setTextColor(fg, col)
        g.drawCenterString((name or "?")[:1].upper(), cx, cy - h // 2)
