#!/usr/bin/env python3
"""
bridge_example.py — a MINIMAL reference bridge for the Portal -> Muse setup.

This is a teaching skeleton, not the production bridge. It implements the
core pattern from docs/AGENT_GUIDE.md with the Python standard library only:

  * Serves a placeholder dashboard page            GET  /
  * Text chat relay (inbox/reply file contract)    POST /api/chat
  * Voice relay (staged: transcribe -> chat)       POST /api/voice
  * Speech-to-text stub                            POST /api/transcribe
  * Text-to-speech stub                            POST /api/speak
  * App-update version file + push trigger         GET  /api/update/version
                                                   POST /api/update/install

How the relay works
-------------------
The bridge does not talk to Muse directly. On a chat request it writes
{"ts": <ms>, "text": "..."} to chat_inbox.json; the dedicated Muse side
chat (see AGENT_GUIDE Step 3) reads that file on its next turn and writes
{"ts": <same ts>, "reply": "..."} to chat_reply.json BEFORE replying in
chat. The bridge polls for the matching reply and returns it. If nobody
writes the reply file, the request times out — that timeout is the #1
setup bug, and it means the side-chat contract isn't wired yet.

Configuration (environment variables, all optional)
---------------------------------------------------
  BRIDGE_PORT        Port to serve on                (default 8100)
  BRIDGE_DIR         Where state files live          (default: this dir)
  BRIDGE_TOKEN_FILE  File containing the API token   (default: .api_token)

The app authenticates with "Authorization: Bearer <token>". The token file
is a placeholder-grade secret store for a LAN appliance: keep it readable
only by the bridge user (chmod 600) and never commit it.

TODO markers show where a real build plugs in local services:
  TODO(stt)  transcribe_audio()  -> Parakeet warm service / whisper.cpp
  TODO(tts)  synthesise_speech() -> Piper or your TTS of choice
  TODO(fastlane) answer_locally() -> time/weather/timers answered in ~1s
  TODO(push) push_update()       -> adb install -r of the staged APK

Run:  python3 bridge_example.py
"""

import io
import json
import os
import struct
import subprocess
import sys
import threading
import time
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# ---------------------------------------------------------------- config

BRIDGE_DIR = Path(os.environ.get("BRIDGE_DIR", Path(__file__).parent))
PORT = int(os.environ.get("BRIDGE_PORT", "8100"))
TOKEN_FILE = Path(os.environ.get("BRIDGE_TOKEN_FILE", BRIDGE_DIR / ".api_token"))

INBOX = BRIDGE_DIR / "chat_inbox.json"
REPLY = BRIDGE_DIR / "chat_reply.json"
HISTORY = BRIDGE_DIR / "chat_history.jsonl"
VERSION_FILE = BRIDGE_DIR / "app_version.json"   # {"versionCode": int, "versionName": "x.y.z"}
STAGED_APK = BRIDGE_DIR / "app.apk"              # staged by you; see push_update()

REPLY_TIMEOUT_S = 150        # agent round trips are slow; do not set this short
HISTORY_CAP = 200

_state_lock = threading.Lock()

# ---------------------------------------------------------------- helpers

def read_token() -> str:
    """Placeholder token store: a single-line file next to the bridge."""
    try:
        return TOKEN_FILE.read_text().strip()
    except FileNotFoundError:
        return ""  # empty token == auth disabled (local development only)


def write_json(path: Path, obj: dict) -> None:
    """Write JSON via a real serialiser — never string-concatenate JSON."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj))
    tmp.replace(path)


def read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def append_history(user_text: str, reply_text: str) -> None:
    with _state_lock:
        lines = []
        if HISTORY.exists():
            lines = HISTORY.read_text().splitlines()
        lines.append(json.dumps({"ts": int(time.time() * 1000),
                                 "user": user_text, "reply": reply_text}))
        HISTORY.write_text("\n".join(lines[-HISTORY_CAP:]) + "\n")


def silent_wav(seconds: float = 0.25, rate: int = 22050) -> bytes:
    """A tiny valid WAV of silence, so TTS stubs return playable audio."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * int(rate * seconds))
    return buf.getvalue()

# ---------------------------------------------------------------- Muse relay

def relay_to_claude(text: str) -> str | None:
    """
    The file contract. Write the inbox, poll the reply file for the same
    ts, return the reply text (or None on timeout).
    """
    ts = int(time.time() * 1000)
    with _state_lock:
        write_json(INBOX, {"ts": ts, "text": text})
    deadline = time.time() + REPLY_TIMEOUT_S
    while time.time() < deadline:
        reply = read_json(REPLY)
        if reply.get("ts") == ts and reply.get("reply"):
            return str(reply["reply"])
        time.sleep(0.25)
    return None


def answer_locally(text: str) -> str | None:
    """
    TODO(fastlane): answer predictable questions right here in ~1s —
    time, date, weather, simple maths, timers — and return None for
    anything you cannot answer confidently. A fast wrong answer is
    worse than a slow right one; when in doubt, fall through to Muse.
    """
    lowered = text.strip().lower()
    if lowered in {"what time is it", "what's the time", "the time"}:
        return time.strftime("It's %-I:%M %p.")
    if lowered in {"what day is it", "what's the date", "the date"}:
        return time.strftime("Today is %A, %B %-d.")
    return None


def handle_chat(text: str) -> tuple[int, dict]:
    local = answer_locally(text)
    if local is not None:
        append_history(text, local)
        return 200, {"reply": local, "source": "local"}
    reply = relay_to_claude(text)
    if reply is None:
        return 504, {"error": "no reply from the Muse side chat before "
                              "timeout — check the reply-file contract "
                              "(AGENT_GUIDE Step 3)"}
    append_history(text, reply)
    return 200, {"reply": reply, "source": "Muse"}

# ---------------------------------------------------------------- speech stubs

def transcribe_audio(audio_bytes: bytes, content_type: str) -> str:
    """
    TODO(stt): plug in real local speech-to-text here.

    Reference pattern (AGENT_GUIDE Step 2): convert to 16 kHz mono WAV
    with ffmpeg, then decode with a persistent warm Parakeet service;
    fall back to whisper.cpp automatically if the service is down.
    Return "" when nothing intelligible was heard.
    """
    _ = (audio_bytes, content_type)
    return ""  # stub: pretends it heard nothing


def synthesise_speech(text: str) -> bytes:
    """
    TODO(tts): plug in real local text-to-speech (e.g. Piper) here and
    return WAV/MP3 bytes. The stub returns silence so the request path
    can be exercised end-to-end before TTS exists.
    """
    _ = text
    return silent_wav()

# ---------------------------------------------------------------- update push

def push_update() -> tuple[int, dict]:
    """
    TODO(push): the host pushes updates; the app never installs itself.

    Reference pattern (AGENT_GUIDE Step 8):
      adb -s <PORTAL_IP>:5555 install -r <staged apk>
    then verify with `dumpsys package` that the version advanced.
    <PORTAL_IP> is your Portal's LAN address — a placeholder here.
    """
    portal = os.environ.get("PORTAL_IP", "<PORTAL_IP>")
    if not STAGED_APK.exists():
        return 404, {"error": f"no staged APK at {STAGED_APK}"}
    try:
        out = subprocess.run(
            ["adb", "-s", f"{portal}:5555", "install", "-r", str(STAGED_APK)],
            capture_output=True, text=True, timeout=120)
        ok = out.returncode == 0 and "Success" in out.stdout
        return (200 if ok else 502), {"ok": ok, "output": out.stdout.strip(),
                                      "error": out.stderr.strip()}
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return 502, {"ok": False, "error": f"adb push failed: {exc}"}

# ---------------------------------------------------------------- HTTP layer

DASHBOARD_HTML = """<!doctype html>
<meta charset="utf-8"><title>Portal dashboard (placeholder)</title>
<body style="background:#111;color:#eee;font-family:sans-serif;text-align:center">
<h1 id="clock" style="font-size:18vw;margin:12vh 0 0"></h1>
<p>Placeholder dashboard — your bridge serves the real page here.</p>
<script>
setInterval(() => {
  document.getElementById('clock').textContent =
    new Date().toLocaleTimeString([], {hour:'numeric', minute:'2-digit'});
}, 1000);
</script>
"""


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    # -- plumbing ------------------------------------------------------
    def log_message(self, fmt, *args):  # keep the console readable
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, code: int, obj: dict) -> None:
        self._send(code, json.dumps(obj).encode(), "application/json")

    def _authorised(self) -> bool:
        token = read_token()
        if not token:
            return True  # no token file yet: setup mode (see module docs)
        return self.headers.get("Authorization", "") == f"Bearer {token}"

    def _body(self) -> bytes:
        length = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(length) if length else b""

    def _body_json(self) -> dict:
        try:
            return json.loads(self._body() or b"{}")
        except json.JSONDecodeError:
            return {}

    # -- routes ----------------------------------------------------------
    def do_GET(self):
        if self.path == "/":
            return self._send(200, DASHBOARD_HTML.encode(), "text/html")
        if self.path == "/api/update/version":
            version = read_json(VERSION_FILE)
            if not version:
                return self._send_json(404, {"error": "no app_version.json staged"})
            return self._send_json(200, version)
        if self.path == "/api/health":
            return self._send_json(200, {"ok": True})
        return self._send_json(404, {"error": "not found"})

    def do_POST(self):
        if not self._authorised():
            return self._send_json(401, {"error": "bad or missing bearer token"})

        if self.path == "/api/chat":
            text = str(self._body_json().get("text", "")).strip()
            if not text:
                return self._send_json(400, {"error": "empty text"})
            code, payload = handle_chat(text)
            return self._send_json(code, payload)

        if self.path == "/api/transcribe":
            text = transcribe_audio(self._body(),
                                    self.headers.get("Content-Type", ""))
            return self._send_json(200, {"text": text})

        if self.path == "/api/speak":
            text = str(self._body_json().get("text", "")).strip()
            if not text:
                return self._send_json(400, {"error": "empty text"})
            return self._send(200, synthesise_speech(text), "audio/wav")

        if self.path == "/api/voice":
            # Staged voice: transcribe -> chat -> (app calls /api/speak,
            # or use the "reply" text however your app prefers).
            text = transcribe_audio(self._body(),
                                    self.headers.get("Content-Type", ""))
            if not text:
                return self._send_json(422, {"error": "nothing intelligible heard",
                                             "text": ""})
            code, payload = handle_chat(text)
            payload["text"] = text  # echo the transcript for the caption
            return self._send_json(code, payload)

        if self.path == "/api/update/install":
            code, payload = push_update()
            return self._send_json(code, payload)

        return self._send_json(404, {"error": "not found"})


def main() -> None:
    if not TOKEN_FILE.exists():
        print(f"note: no token file at {TOKEN_FILE} — running in setup "
              "mode with auth disabled. Create it (chmod 600) before "
              "real use.", file=sys.stderr)
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"bridge_example listening on :{PORT} (state dir: {BRIDGE_DIR})")
    server.serve_forever()


if __name__ == "__main__":
    main()
