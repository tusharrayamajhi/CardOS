NAME = "Voice Agent"
ICON = "mic"
COLOR = 0x7C3AED
NET = True

# Gemini voice assistant. Chat history is kept on the SD card.
#   Enter  talk (Enter again to send, Esc to cancel)    Tab  type a message
#   ; .    scroll                                        v    voice replies on/off
#   n      new chat (the old one is kept on the SD card) Esc  back
import json
import os
import time
from cardos import sd, gemini, audio, settings
from cardos.textinput import ask

HOME_SD = sd.ROOT + "/voice_agent"
HOME_FLASH = "/flash/voice_agent"       # used when there is no SD card
CONFIG = "/flash/voice_agent.json"
CONTEXT_TURNS = 12                      # messages sent to Gemini as memory
MAX_RECORD_S = 15
LINE_H = 13
CHAT_BOTTOM = 105                       # status line below this

SYSTEM = ("You are Tushar's voice assistant, running on a tiny M5Stack Cardputer. "
          "Answer in one to three short sentences of plain spoken English: "
          "no markdown, lists, emoji or code. Current local time: %s.")
AUDIO_PROMPT = ("The audio clip is my message. Put an exact transcript of only the speech "
                "in the audio into 'heard', and your answer to it into 'reply'.")
SCHEMA = {"type": "OBJECT",
          "properties": {"heard": {"type": "STRING"}, "reply": {"type": "STRING"}},
          "required": ["heard", "reply"]}
DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def now_text():
    t = time.localtime()
    if t[0] < 2024:
        return "unknown"
    return "%s %04d-%02d-%02d %02d:%02d" % (DAYS[t[6]], t[0], t[1], t[2], t[3], t[4])


def wrap(lcd, text, width):
    """Split text into lines that fit `width` pixels (current font)."""
    lines = []
    for para in text.split("\n"):
        line = ""
        for word in para.split(" "):
            test = word if not line else line + " " + word
            if lcd.textWidth(test) <= width:
                line = test
                continue
            if line:
                lines.append(line)
            while lcd.textWidth(word) > width:      # very long word: hard split
                cut = len(word)
                while cut > 1 and lcd.textWidth(word[:cut]) > width:
                    cut -= 1
                lines.append(word[:cut])
                word = word[cut:]
            line = word
        lines.append(line)
    return lines


class History:
    """Chat log as JSON lines: {"r": "user"|"model", "t": text, "ts": epoch}."""

    def __init__(self, folder):
        self.folder = folder
        self.path = folder + "/history.jsonl"
        self.items = []
        try:
            os.mkdir(folder)
        except OSError:
            pass
        try:
            with open(self.path) as f:
                for line in f:
                    try:
                        self.items.append(json.loads(line))
                    except ValueError:
                        pass
                    if len(self.items) > 60:          # keep RAM use small
                        self.items = self.items[-40:]
        except OSError:
            pass

    def add(self, role, text):
        item = {"r": role, "t": text, "ts": time.time()}
        self.items.append(item)
        try:
            with open(self.path, "a") as f:
                f.write(json.dumps(item) + "\n")
        except OSError as e:
            print("history write failed:", e)

    def contents(self):
        """Last messages as Gemini turns (must start with a user turn)."""
        recent = self.items[-CONTEXT_TURNS:]
        while recent and recent[0]["r"] != "user":
            recent = recent[1:]
        return [{"role": m["r"], "parts": [{"text": m["t"]}]} for m in recent]

    def new_chat(self):
        try:
            os.rename(self.path, "%s/chat_%d.jsonl" % (self.folder, time.time()))
        except OSError:
            pass
        self.items = []


class VoiceAgent:
    def __init__(self, ctx):
        self.ctx = ctx
        self.lcd = ctx.lcd
        self.C = ctx.config
        self.scroll = 0          # lines scrolled up from the bottom
        self.voice = True
        try:
            with open(CONFIG) as f:
                self.voice = json.load(f).get("voice", True)
        except (OSError, ValueError):
            pass
        folder = HOME_SD if sd.mount() else HOME_FLASH
        self.on_sd = folder == HOME_SD
        self.history = History(folder)
        self.rec_path = folder + "/rec.wav"
        self.reply_path = folder + "/reply.ulaw"

    def save_config(self):
        try:
            with open(CONFIG, "w") as f:
                json.dump({"voice": self.voice}, f)
        except OSError:
            pass

    # ---- drawing
    def status(self, text, color=None):
        lcd, C, ctx = self.lcd, self.C, self.ctx
        lcd.fillRect(0, CHAT_BOTTOM, ctx.W, ctx.BOTTOM - CHAT_BOTTOM, 0x1E293B)
        lcd.setFont(lcd.FONTS.DejaVu9)
        lcd.setTextColor(color or C.DIM, 0x1E293B)
        lcd.drawString(text, 4, CHAT_BOTTOM + 2)

    def idle_status(self):
        self.status("Enter talk  Tab type  v voice:%s  n new" % ("on" if self.voice else "off"))

    def draw_chat(self):
        lcd, C, ctx = self.lcd, self.C, self.ctx
        lcd.fillRect(0, ctx.TOP, ctx.W, CHAT_BOTTOM - ctx.TOP, C.BG)
        lcd.setFont(lcd.FONTS.DejaVu12)
        lines = []                       # (text, is_user)
        for m in self.history.items[-20:]:
            user = m["r"] == "user"
            for ln in wrap(lcd, m["t"], ctx.W - 30):
                lines.append((ln, user))
            lines.append(("", user))     # gap between messages
        if not lines:
            lcd.setTextColor(C.DIM, C.BG)
            lcd.drawCenterString("Press Enter and talk,", ctx.W // 2, ctx.TOP + 28)
            lcd.drawCenterString("or Tab to type.", ctx.W // 2, ctx.TOP + 44)
            if not self.on_sd:
                lcd.setFont(lcd.FONTS.DejaVu9)
                lcd.setTextColor(C.YELLOW, C.BG)
                lcd.drawCenterString("No SD card: history kept on flash", ctx.W // 2, ctx.TOP + 66)
            return
        rows = (CHAT_BOTTOM - ctx.TOP - 2) // LINE_H
        self.scroll = max(0, min(self.scroll, len(lines) - rows))
        end = len(lines) - self.scroll
        visible = lines[max(0, end - rows):end]
        y = ctx.TOP + 2
        for text, user in visible:
            if text:
                if user:
                    lcd.setTextColor(C.ACCENT, C.BG)
                    lcd.drawRightString(text, ctx.W - 6, y)
                else:
                    lcd.fillRect(4, y + 1, 2, LINE_H - 2, 0xA78BFA)
                    lcd.setTextColor(C.FG, C.BG)
                    lcd.drawString(text, 10, y)
            y += LINE_H
        if self.scroll:
            lcd.setFont(lcd.FONTS.DejaVu9)
            lcd.setTextColor(C.YELLOW, C.BG)
            lcd.drawRightString("more below", ctx.W - 4, CHAT_BOTTOM - 11)

    # ---- talking to Gemini
    def system(self):
        return SYSTEM % now_text()

    def record(self):
        """Record until Enter (send) or Esc (cancel). Returns the WAV path or None."""
        ctx, lcd, C = self.ctx, self.lcd, self.C
        ctx.click = False                 # the speaker is off while the mic runs
        rec = audio.Recorder(self.rec_path)
        peak = 0
        start = time.ticks_ms()
        result = None
        try:
            while True:
                level = rec.poll()
                peak = max(peak, level)
                secs = time.ticks_diff(time.ticks_ms(), start) / 1000
                self.status("Listening %.0fs  Enter = send  Esc = cancel" % secs, C.RED)
                # level meter on the right of the status line
                lcd.fillRect(ctx.W - 44, CHAT_BOTTOM + 3, 40, 7, 0x0F172A)
                lcd.fillRect(ctx.W - 44, CHAT_BOTTOM + 3, max(1, level * 40 // 100), 7, C.GREEN)
                keys = ctx.tick()
                if ctx.ESC in keys:
                    break
                if ctx.ENTER in keys or secs >= MAX_RECORD_S:
                    result = self.rec_path
                    break
                time.sleep_ms(30)
        finally:
            seconds = rec.stop(keep=result is not None)
            ctx.click = settings.get("click")
        if result and seconds < 0.5:
            return None
        if result and peak < 1:
            self.status("Mic hears nothing - press Tab to type", C.YELLOW)
            time.sleep_ms(2500)
            return None
        return result

    def ask_gemini(self, wav=None, text=None):
        """Send one message. Returns the reply text or None on error."""
        self.status("Thinking...", self.C.ACCENT)
        contents = self.history.contents()
        try:
            if wav:
                contents.append({"role": "user", "parts": [gemini.audio_part(wav), {"text": AUDIO_PROMPT}]})
                out = gemini.generate(contents, system=self.system(), schema=SCHEMA)
                heard, reply = out.get("heard", "").strip(), out.get("reply", "").strip()
            else:
                contents.append({"role": "user", "parts": [{"text": text}]})
                heard, reply = text, gemini.generate(contents, system=self.system())
        except gemini.GeminiError as e:
            self.show_error(e)
            return None
        except OSError as e:
            print("network:", repr(e))
            self.status("Network error: %s" % e, self.C.RED)
            time.sleep_ms(2500)
            return None
        if heard:
            self.history.add("user", heard)
        self.history.add("model", reply or "(no answer)")
        self.scroll = 0
        self.draw_chat()
        return reply

    def show_error(self, e):
        if e.status == 429:
            msg = "Gemini rate limit - wait a minute"
        elif e.status in (401, 403):
            msg = "API key rejected (%d)" % e.status
        elif e.status == 0:
            msg = e.message
        else:
            msg = "Gemini error %d" % e.status
        self.status(msg[:44], self.C.RED)
        print("gemini:", e)
        time.sleep_ms(2500)

    def speak(self, reply):
        if not (self.voice and reply):
            return
        self.status("Preparing voice...", self.C.ACCENT)
        try:
            gemini.speak(reply, self.reply_path)
        except gemini.GeminiError as e:
            if e.status == 429:
                self.status("Voice limit reached (3/min) - text only", self.C.YELLOW)
                time.sleep_ms(2000)
            else:
                self.show_error(e)
            return
        except OSError as e:
            self.status("Network error: %s" % e, self.C.RED)
            time.sleep_ms(2000)
            return
        self.status("Speaking...  any key = stop", self.C.GREEN)
        self.ctx.wake()
        audio.play_mulaw(self.reply_path, gemini.TTS_RATE, stop=lambda: bool(self.ctx.tick()))

    # ---- main loop
    def run(self):
        ctx = self.ctx
        ctx.clear()
        self.draw_chat()
        self.idle_status()
        while True:
            for k in ctx.tick():
                if k == ctx.ESC:
                    return
                if k == ctx.ENTER:
                    wav = self.record()
                    if wav:
                        self.speak(self.ask_gemini(wav=wav))
                    self.draw_chat()
                elif k == "\t" or k == "KEY_TAB":
                    text = ask(ctx, "Message to Gemini")
                    ctx.clear()
                    self.draw_chat()
                    if text and text.strip():
                        self.speak(self.ask_gemini(text=text.strip()))
                elif k in (ctx.UP, ";"):
                    self.scroll += 2
                    self.draw_chat()
                elif k in (ctx.DOWN, "."):
                    self.scroll = max(0, self.scroll - 2)
                    self.draw_chat()
                elif k in ("v", "V"):
                    self.voice = not self.voice
                    self.save_config()
                elif k in ("n", "N"):
                    self.history.new_chat()
                    self.scroll = 0
                    self.draw_chat()
                else:
                    continue
                self.idle_status()
            time.sleep_ms(20)


def run(ctx):
    VoiceAgent(ctx).run()
