# CardOS text input screen, for any app that needs the user to type something.
#
#   from cardos.textinput import ask
#   pw = ask(ctx, "Password for MyWiFi", secret=True)   # None if cancelled
#
# Keys: type normally (Fn = symbols, Caps toggles capitals), Backspace deletes,
# Tab shows/hides a secret, Enter accepts, Esc cancels.
import time
from cardos import keys as K

# The ; , . / keys report arrow names on their own; in a text box they type.
_ARROW_CHARS = {K.UP: ";", K.LEFT: ",", K.DOWN: ".", K.RIGHT: "/"}

BOX_BG = 0x020617


def ask(ctx, title, initial="", secret=False, max_len=64):
    lcd, C = ctx.lcd, ctx.config
    text = initial
    hidden = secret
    top = ctx.TOP

    def draw_static():
        ctx.clear()
        lcd.setFont(lcd.FONTS.DejaVu12)
        lcd.setTextColor(C.FG, C.BG)
        lcd.drawString(title if len(title) <= 34 else title[:32] + "..", 6, top + 6)
        lcd.setFont(lcd.FONTS.DejaVu9)
        lcd.setTextColor(C.DIM, C.BG)
        hint = "Enter = OK   Esc = cancel"
        if secret:
            hint += "   Tab = show/hide"
        lcd.drawString(hint, 6, ctx.BOTTOM - 14)

    def draw_box():
        y = top + 28
        lcd.fillRoundRect(4, y, ctx.W - 8, 24, 4, BOX_BG)
        lcd.drawRoundRect(4, y, ctx.W - 8, 24, 4, C.ACCENT)
        shown = "*" * len(text) if hidden else text
        lcd.setFont(lcd.FONTS.DejaVu12)
        # keep the end of long text (where the cursor is) visible
        while shown and lcd.textWidth(shown) > ctx.W - 26:
            shown = shown[1:]
        lcd.setTextColor(0xFFFFFF, BOX_BG)
        lcd.drawString(shown, 10, y + 5)
        cx = 10 + lcd.textWidth(shown) + 1
        lcd.fillRect(cx, y + 5, 2, 14, C.ACCENT)   # cursor
        # info line under the box: length and Caps state
        lcd.fillRect(0, y + 28, ctx.W, 14, C.BG)
        lcd.setFont(lcd.FONTS.DejaVu9)
        lcd.setTextColor(C.DIM, C.BG)
        lcd.drawString("%d chars" % len(text), 8, y + 30)
        if ctx.caps():
            lcd.setTextColor(C.YELLOW, C.BG)
            lcd.drawRightString("CAPS", ctx.W - 8, y + 30)

    draw_static()
    draw_box()
    caps = ctx.caps()
    while True:
        changed = ctx.caps() != caps   # Caps Lock sends no key, so watch it
        caps = ctx.caps()
        for k in ctx.tick():
            if k == K.ESC:
                return None
            if k == K.ENTER:
                return text
            if k == K.BACKSPACE:
                if text:
                    text = text[:-1]
                    changed = True
            elif k == K.TAB:
                if secret:
                    hidden = not hidden
                    changed = True
            else:
                ch = _ARROW_CHARS.get(k, k)
                if len(ch) == 1 and len(text) < max_len:
                    text += ch
                    changed = True
        if changed:
            draw_box()
        time.sleep_ms(15)
