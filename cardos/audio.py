# CardOS audio: record the mic to a WAV file and play mu-law / PCM files,
# streaming through small buffers so long clips never sit in RAM.
#
#   rec = audio.Recorder("/sd/clip.wav")      # starts recording (speaker is paused)
#   while ...: level = rec.poll()              # call often; returns 0..100 loudness
#   seconds = rec.stop()                       # finishes the WAV, speaker comes back
#
#   audio.play_mulaw("/sd/reply.ulaw", 8000, stop=lambda: ctx.tick())
#
# The speaker and mic share one audio chip, so only one can run at a time.
import struct
import time
import array
import micropython
import M5

PLAY_CH = 0


# ------------------------------------------------------------ fast helpers
@micropython.viper
def _peak16(buf: ptr16, n: int) -> int:
    """Largest absolute sample in an int16 buffer."""
    peak = 0
    for i in range(n):
        v = buf[i]
        if v & 0x8000:
            v = 0x10000 - v
        if v > peak:
            peak = v
    return peak


@micropython.viper
def _gain16(buf: ptr16, n: int, gain: int):
    """Multiply int16 samples by `gain`, clipping instead of wrapping."""
    for i in range(n):
        v = buf[i]
        if v & 0x8000:
            v = v - 0x10000
        v = v * gain
        if v > 32767:
            v = 32767
        elif v < -32768:
            v = -32768
        buf[i] = v & 0xFFFF


@micropython.viper
def _ulaw_to_16(src: ptr8, dst: ptr16, n: int, table: ptr16):
    for i in range(n):
        dst[i] = table[src[i]]


def _ulaw_table():
    t = array.array("H", bytes(512))
    for b in range(256):
        u = ~b & 0xFF
        mag = (((u & 0x0F) << 3) + 0x84) << ((u >> 4) & 7)
        s = 0x84 - mag if u & 0x80 else mag - 0x84
        t[b] = s & 0xFFFF
    return t


_ULAW = None


# ------------------------------------------------------------ recording
def wav_header(rate, data_bytes):
    return (b"RIFF" + struct.pack("<I", 36 + data_bytes) + b"WAVEfmt " +
            struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16) +
            b"data" + struct.pack("<I", data_bytes))


class Recorder:
    """Records 16-bit mono WAV straight to a file (double-buffered)."""

    def __init__(self, path, rate=8000, gain=4, buf_samples=1024):
        self.rate = rate
        self.gain = gain
        self.bytes = 0
        self.level = 0
        self._f = open(path, "wb")
        self._f.write(wav_header(rate, 0))
        self._bufs = [bytearray(buf_samples * 2), bytearray(buf_samples * 2)]
        self._queue = []               # buffer indexes in recording order
        M5.Speaker.end()
        M5.Mic.begin()
        for i in (0, 1):
            M5.Mic.record(self._bufs[i], rate, False)
            self._queue.append(i)

    def _save_oldest(self):
        i = self._queue.pop(0)
        b = self._bufs[i]
        n = len(b) // 2
        if self.gain > 1:
            _gain16(b, n, self.gain)
        self._f.write(b)
        self.bytes += len(b)
        self.level = min(100, _peak16(b, n) * 100 // 32768)
        return i

    def poll(self):
        """Save finished buffers and keep the mic busy. Returns loudness 0..100."""
        # isRecording(): 2 = both buffers queued, 1 = oldest one is finished
        while self._queue and M5.Mic.isRecording() < len(self._queue):
            i = self._save_oldest()
            M5.Mic.record(self._bufs[i], self.rate, False)
            self._queue.append(i)
        return self.level

    def seconds(self):
        return self.bytes / (self.rate * 2)

    def stop(self, keep=True):
        """Finish the file. Returns its length in seconds."""
        while M5.Mic.isRecording():
            time.sleep_ms(5)
        while self._queue:
            self._save_oldest()
        M5.Mic.end()
        if keep:
            self._f.seek(0)
            self._f.write(wav_header(self.rate, self.bytes))
        self._f.close()
        M5.Speaker.begin()
        return self.seconds()


# ------------------------------------------------------------ playback
def play_mulaw(path, rate=8000, stop=None, chunk=2048):
    """Play a headerless mu-law file. `stop()` returning truthy ends it early.

    Returns True if it played to the end.
    """
    global _ULAW
    if _ULAW is None:
        _ULAW = _ulaw_table()
    spk = M5.Speaker
    raw = bytearray(chunk)
    outs = [bytearray(chunk * 2), bytearray(chunk * 2)]
    idx = 0
    finished = True
    with open(path, "rb") as f:
        while True:
            n = f.readinto(raw)
            if not n:
                break
            # wait until one of the two buffers is free again
            while spk.isPlaying(PLAY_CH) >= 2:
                if stop and stop():
                    spk.stop(PLAY_CH)
                    return False
                time.sleep_ms(5)
            _ulaw_to_16(raw, outs[idx], n, _ULAW)
            spk.playRaw(memoryview(outs[idx])[:n * 2], rate, False, 1, PLAY_CH, False)
            idx ^= 1
    while spk.isPlaying(PLAY_CH):
        if stop and stop():
            spk.stop(PLAY_CH)
            finished = False
            break
        time.sleep_ms(10)
    return finished
