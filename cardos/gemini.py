# CardOS Gemini client: text/audio in -> text out, and text -> speech file.
# Big payloads are streamed (audio is read from / written to files) so they
# never have to fit in the Cardputer's RAM.
#
#   from cardos import gemini
#   out = gemini.generate(contents, system="Be brief")             # -> text
#   out = gemini.generate(contents, schema={...})                  # -> parsed JSON
#   gemini.audio_part("/sd/clip.wav")                              # use inside contents
#   gemini.speak("Hello", "/sd/reply.ulaw")                        # 8 kHz mu-law file
#
# The API key is read from /flash/cardos_secrets.json {"gemini_api_key": "..."}.
import json
import os
import binascii
from cardos import net

HOST = "generativelanguage.googleapis.com"
SECRETS = "/flash/cardos_secrets.json"
MODEL = "gemini-3.5-flash"
TTS_MODEL = "gemini-3.8-flash-lite-tts"
TTS_RATE = 8000

_AUDIO_MARK = "@@AUDIO_DATA@@"
_key = None


class GeminiError(Exception):
    def __init__(self, status, message):
        super().__init__("%s: %s" % (status, message))
        self.status = status
        self.message = message


def api_key():
    global _key
    if _key is None:
        try:
            with open(SECRETS) as f:
                _key = json.load(f)["gemini_api_key"]
        except (OSError, ValueError, KeyError):
            raise GeminiError(0, "No API key in " + SECRETS)
    return _key


def audio_part(path, mime="audio/wav"):
    """A content part for an audio file (it is base64-streamed when sent)."""
    return {"inline_data": {"mime_type": mime, "data": _AUDIO_MARK}, "_file": path}


def _b64_len(n):
    return (n + 2) // 3 * 4


def _file_b64(path, block=3 * 512):
    with open(path, "rb") as f:
        while True:
            chunk = f.read(block)
            if not chunk:
                break
            yield binascii.b2a_base64(chunk)[:-1]  # drop the trailing newline


def _error_message(resp):
    try:
        js = json.loads(resp.read(4096))
        return js.get("error", {}).get("message", "")[:120]
    except Exception:
        return "HTTP %d" % resp.status


def _post(path, body, audio_file=None, timeout=60):
    """POST JSON; an audio file marked in `body` is spliced in as base64."""
    text = json.dumps(body)
    headers = {"Content-Type": "application/json", "x-goog-api-key": api_key()}
    if audio_file is None:
        data = text.encode()
        return net.request("POST", HOST, path, headers, data, timeout=timeout)
    head, _, tail = text.partition(_AUDIO_MARK)
    head, tail = head.encode(), tail.encode()
    length = len(head) + _b64_len(os.stat(audio_file)[6]) + len(tail)

    def chunks():
        yield head
        for c in _file_b64(audio_file):
            yield c
        yield tail
    return net.request("POST", HOST, path, headers, chunks(), length=length, timeout=timeout)


def generate(contents, system=None, schema=None, model=MODEL, max_tokens=400):
    """Run generateContent. Returns text, or parsed JSON when `schema` is given."""
    audio_file = None
    for turn in contents:
        for part in turn.get("parts", []):
            if "_file" in part:
                audio_file = part.pop("_file")
    cfg = {"maxOutputTokens": max_tokens, "thinkingConfig": {"thinkingBudget": 0}}
    if schema:
        cfg["responseMimeType"] = "application/json"
        cfg["responseSchema"] = schema
    body = {"contents": contents, "generationConfig": cfg}
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    r = _post("/v1beta/models/%s:generateContent" % model, body, audio_file)
    try:
        if r.status != 200:
            raise GeminiError(r.status, _error_message(r))
        js = json.loads(r.read(16384))
    finally:
        r.close()
    try:
        parts = js["candidates"][0]["content"]["parts"]
    except (KeyError, IndexError):
        raise GeminiError(200, "empty answer (%s)" % js.get("candidates", [{}])[0].get("finishReason", "?"))
    text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
    return json.loads(text) if schema else text.strip()


def speak(text, out_path, voice="Kore", style=None):
    """Turn `text` into speech, saved as headerless 8 kHz mu-law. Returns bytes written."""
    item = {"type": "text", "text": text}
    if style:
        item["annotations"] = [{"type": "speech_metadata", "style": style}]
    body = {
        "model": TTS_MODEL,
        "input": [{"type": "user_input", "content": [item]}],
        "response_format": {"type": "audio", "mime_type": "audio/mulaw", "sample_rate": TTS_RATE},
        "generation_config": {"speech_config": [{"voice": voice}]},
    }
    r = _post("/v1beta/interactions", body)
    try:
        if r.status != 200:
            raise GeminiError(r.status, _error_message(r))
        return _save_audio_field(r, out_path)
    finally:
        r.close()


def _save_audio_field(resp, out_path):
    """Find the base64 "data" value in a streamed JSON response; decode it to a file."""
    buf = bytearray(1024)
    carry = b""        # undecoded base64 (length not a multiple of 4) or search tail
    found = False
    written = 0
    with open(out_path, "wb") as out:
        while True:
            n = resp.readinto(buf)
            if not n:
                break
            chunk = carry + bytes(buf[:n])
            carry = b""
            if not found:
                i = chunk.find(b'"data"')
                if i < 0:
                    carry = chunk[-8:]   # marker may be split across reads
                    continue
                q = chunk.find(b'"', i + 6)
                if q < 0:
                    carry = chunk[i:]
                    continue
                chunk = chunk[q + 1:]
                found = True
            end = chunk.find(b'"')
            data = chunk if end < 0 else chunk[:end]
            data = data.replace(b"\\", b"")
            usable = len(data) // 4 * 4
            if usable:
                part = binascii.a2b_base64(data[:usable])
                out.write(part)
                written += len(part)
            carry = data[usable:]
            if end >= 0:
                break
    if not found:
        raise GeminiError(200, "no audio in reply")
    return written
