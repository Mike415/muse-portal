# Portal → Muse Setup Guide (For Your Muse)

You are a Muse whose human has a Meta Portal and wants it to work as an always-on screen and voice terminal for you. This guide is written for you, the agent doing the build. Your human has a companion human-readable version focused on what was built and what is needed; this one is the technical playbook.

This pattern was validated end-to-end on one model — the original 2018 Portal (Gen 1, 10-inch, Android 9 / API 28). It is written here as a general pattern for any Portal, with explicit **[Verify on your model]** checkpoints where generations differ. Do not assume a step validated on Gen 1 behaves the same way on another model until you have checked it on that device, in the room.

Read the whole guide before building anything. Several failures on Portal OS are silent.

## What you are building

A Portal cannot become a native Muse gadget. The Muse Gadget SDK targets ESP32 and Linux only, Portal bootloaders are not unlockable for this purpose, and there is no Android gadget target. Do not promise your human a native gadget, Bluetooth pairing as a gadget, or Google Cast certification.

What does work is a Portal as a Muse terminal:

- A small native Android app on the Portal shows a dashboard page and gives you the Portal's own microphone and speakers.
- A bridge program on an always-on computer on the home network serves that page, receives voice and text, and relays requests to you.
- You answer through a dedicated Muse side chat, using a reply-file contract described below.
- Optional local services on the same host — speech-to-text, text-to-speech, timers, and smart-home control — handle common requests in seconds and fall through to you for everything else.

Everything runs on the home network. No cloud account, tunnel, or new subscription is required for use at home.

**Current revision notes (read before building):** the reference build has grown past the base pattern below. Voice now runs as a **realtime streaming session** (Step 2b) rather than only the turn-by-turn `/api/voice` relay — build the relay first, then streaming. The dashboard also grew **security cameras via go2rtc, a native Plex client, and Live TV from host-built IPTV snapshot catalogs** (Step 5b). The Android app source is **not included in this repository** — Appendix A is a rebuild specification detailed enough to reproduce it; the app contains per-household trained models and device identities that must never be copied between households anyway.

## Which Portal do you have?

Identify the exact model before you write any code. Layout, Android version, and developer access vary.

| Model | Released | Screen | Notes for this build |
|---|---|---|---|
| Portal (Gen 1) | 2018 | 10" fixed | Reference model. Android 9 / API 28 validated. |
| Portal+ (Gen 1) | 2018 | 15.6" rotating | Same generation as above; layout must handle rotation and larger canvas. **[Verify on your model]** |
| Portal Mini | 2019 | 8" fixed | Smaller canvas; dashboard density needs adjustment. **[Verify on your model]** |
| Portal (Gen 2) | 2019 | 10" fixed | Newer Android build than Gen 1; re-validate ADB, WebView, and dialogs. **[Verify on your model]** |
| Portal+ (Gen 2) | 2021 | 14" tilting | Re-validate all Gen 1 assumptions. **[Verify on your model]** |
| Portal Go | 2021 | 10" portable, battery | Portable / battery use changes always-on assumptions; re-validate power, wake, and placement. **[Verify on your model]** |
| Portal TV | 2019 | No built-in screen — uses a TV | Different form factor entirely. The WebView dashboard pattern in this guide does not apply directly; treat as out of scope until separately validated. |

Record in your build notes: model, Android version, API level, WebView version if available, and screen size / orientation. Every **[Verify on your model]** checkpoint below should be checked against that record.

## Architecture at a glance

```text
Portal app (Android, Kotlin — minSdk set to your model's API level)
  ├─ WebView  →  dashboard page served by the bridge
  ├─ Mic      →  POST /api/voice  (audio)
  └─ Text     →  POST /api/chat   (text)
        │
        ▼
Host bridge (always-on LAN computer)
  ├─ Serves the dashboard page and the app installer file
  ├─ Fast lane: answers simple questions locally, immediately
  ├─ Writes chat_inbox.json  { "ts": ..., "text": "..." }
  └─ Polls chat_reply.json for a reply with the same "ts"
        │
        ▼
Dedicated Muse side chat (yours)
  ├─ On every turn: read the inbox file first
  └─ Write chat_reply.json { "ts": <same ts>, "reply": "..." }
     BEFORE sending your normal chat reply
        │
        ▼
Bridge returns the reply; the Portal speaks it (text-to-speech
on the host) and shows it as a caption.
```

Keep the Portal bridge separate from any other dashboard or bridge you already run: its own directory, its own port, its own inbox, reply, and history files, and its own access token. That separation lets you change one without breaking the other.

Use placeholders for addresses throughout your own build notes — for example `<HOST_IP>` for the bridge computer and `<PORTAL_IP>` for the Portal — and record the real values in one place only. Do not hardcode one household's addresses, paths, or filenames into a shared guide.

## Host hardware substitutions

The bridge host is a role, not a specific board. In the reference build it was a Raspberry Pi; any always-on machine already on the home network can fill it.

The bridge host does five jobs:

1. **Always-on LAN server** — serves the dashboard page and the `/api/chat` and `/api/voice` endpoints, on the same network as the Portal.
2. **Local speech** — runs speech-to-text (NVIDIA Parakeet as a persistent warm service in the current reference build, with whisper.cpp as the automatic fallback — see Step 2) and text-to-speech (e.g. Piper), so voice does not need to leave the house and replies stay fast.
3. **File relay** — holds the `chat_inbox.json` / `chat_reply.json` pair you read and write, with the matching `ts` described above. You need a reliable way to reach those files on every turn in the dedicated side chat.
4. **Home Assistant adjacency** — sits next to (or runs) Home Assistant, if your human wants lights, scenes, and other device control from the Portal.
5. **APK staging** — stores the current Portal app installer, its version file, and the previous build as a backup, and pushes updates to the Portal.

Any always-on Linux, Windows, or macOS machine on the same LAN that you can reach — over SSH, Tailscale, or whatever access you already have in that household — can fill the role. Pick the machine that is already on all day; do not ask your human to buy new hardware if they already have a suitable host.

Two arrangements do **not** work:

- **Portal-only.** The Portal itself cannot run you, the speech services, or the file relay. It is a terminal — microphone, speakers, screen, and nothing more. Something else on the network has to be the host.
- **Cloud-only hosting.** Moving the bridge to a cloud server breaks LAN discovery for DIAL casting and for local device control, and adds a round trip to every voice request. The point of the design is that voice, timers, and lights stay local and fast; host the bridge in the house.

## Before you start — ask your human

Validate what is possible first, explain it plainly, and stop. Do not build until your human greenlights the build. These choices are theirs, not yours:

- The name the Portal shows and answers to, and the wake word, if any
- Which integrations to include at first — start with voice, chat, and the dashboard; add casting, scenes, and recipes only if they want them
- Which smart-home scenes exist, and exactly which devices each one touches
- How updates are installed (the pushed-update flow in Step 8 needs their one-time wired setup, where that flow is available on their model)
- Any trade-off numbers you discover along the way, especially wake-word false wakes per hour

If your human overrules a researched recommendation, execute immediately and record the trade-off they accepted. If new evidence arrives after their call, argue once, with numbers, and hand the decision back.

## Step 1 — Prepare the Portal

1. Confirm the hardware: exact model (see table above), Android version, and API level.
   - *Validated on Gen 1:* Android 9 (API 28), no Google Play Services, and Play Services cannot be added.
   - **[Verify on your model]** Newer models may ship a different Android base, API level, and services availability. Record what you actually find; set your app's `minSdk` from it, do not copy API 28 blindly.
2. Enable ADB / developer access using Meta's official Portal development guidance for that model. Current Portal software ships an official ADB offramp — on the Gen 1 reference it's **Settings › Debug › ADB Enabled** behind the Meta account PIN — and that sanctioned toggle, not any unlock or exploit, is the foundation of this whole build (the bootloader is locked; no stock-Android/Linux reflash exists, so do not let your human plan around one). Your human does this part — it needs the device in hand, a USB cable, and accepting the authorization prompt on the Portal screen.
   - **[Verify on your model]** Whether ADB is available the same way, what cable/port it uses, and how authorization persists differ across generations. Confirm you can run `adb devices` and `adb shell` reliably before designing an update flow around it.
3. Test the stock Android installer on the device before relying on it.
   - *Validated on Gen 1:* Portal OS renders its installer dialog blank, so on-device tap-to-install is a dead end. Plan to install and update over ADB.
   - **[Verify on your model]** Try one harmless install on other models. If the installer renders and works there, you may have a simpler path — but keep the ADB push flow as your verified fallback until the on-device path has succeeded end-to-end.
4. Put the Portal on the home Wi-Fi and keep it there. Note its LAN address as `<PORTAL_IP>`; a DHCP reservation on the router saves future debugging.

## Step 2 — Build the host bridge

Create a dedicated bridge directory on the host (separate from any existing dashboard bridge) containing:

- The dashboard page (`index.html`) the app will display
- `chat_inbox.json` and `chat_reply.json` for the relay
- `chat_history.jsonl` — an append-only history, capped at a sensible size (200 entries in the reference build)
- A token file, readable only by the bridge, that the app uses to authenticate
- The staged app installer and a small version file (see Step 8)

Serve it on its own port. The bridge's chat flow is:

1. On `POST /api/chat` or `/api/voice`, write `{"ts": <millisecond timestamp>, "text": "..."}` to `chat_inbox.json`.
2. Deliver that text into the dedicated Muse side chat.
3. Poll `chat_reply.json` until it contains the same `ts` with a non-empty `reply`, or a timeout passes (150 seconds in the reference build — voice turns through a full agent relay take 20–35 seconds, so do not set this short).
4. Return or speak that reply, and append the exchange to the history file.

For voice, transcribe the audio locally, then treat the transcript exactly like typed chat. Synthesise the reply locally and return the audio for the Portal to play. Also expose the two halves separately — `POST /api/transcribe` (audio → `{text}`) and `POST /api/speak` (`{text}` → audio) — so the app can run staged flows (show the transcript before sending, replay a reply) and the streaming layer in Step 2b can reuse them.

This bridge pattern is host- and model-independent — it was validated on Gen 1, but nothing in the inbox/reply contract depends on the Portal generation.

### Speech-to-text: Parakeet as a warm service (current reference pattern)

The latest reference revision swapped the primary speech-to-text engine. Use this pattern, not a Whisper-only setup:

- **Engine:** NVIDIA Parakeet TDT 0.6B v2 (int8) via sherpa-onnx.
- **Run it as a persistent warm service** on the host — a localhost HTTP endpoint the bridge calls — **not** spawned per request. Parakeet's cold model load is ~10 seconds, which makes per-call spawning far worse than Whisper. Kept warm, it decodes in ~0.30s per clip, versus ~1.8s per call for whisper.cpp base.en.
- **Benchmark before you swap on a new host or model.** In the reference build, Parakeet and whisper.cpp (ggml-base.en, `-bs 1`) were benchmarked head-to-head on the primary user's real voice clips before swapping: Parakeet edged Whisper on exact matches of short voice takes and was word-perfect on a clean diagnostic sentence where Whisper erred. Both engines still mangled an idiosyncratic wake phrase — do not expect a new engine to fix pronunciation-specific problems.
- **Keep Whisper as the automatic fallback.** The bridge keeps an engine switch (an environment variable, with Parakeet as the default) and automatically falls back to the previous whisper.cpp transcribe script if the Parakeet service is unreachable — requests degrade to Whisper speed and accuracy instead of failing. While the Parakeet service warms up after a (re)start (~10s), requests also ride the fallback.
- **Validate safety-critical one-word commands on real recordings.** Known caveat from the reference benchmark: Parakeet once transcribed a clean synthetic "stop" as "Dump", while Whisper got it. Any local short-command safeguards in the bridge (Step 5, timers) must stay downstream of the transcript and engine-agnostic, and a word like "stop" needs testing on real, ideally shouted, recordings — not just synthetic speech — before you trust the new engine with it.
- **Implementation notes:** sherpa-onnx 1.13.x dropped the `from_parakeet_tdt` constructor — build the recogniser via `from_transducer` with `model_type="nemo_transducer"`. Have the bridge process itself spawn and health-check the warm service, so it inherits the bridge's lifecycle (the reference bridge is nohup-launched, with no systemd unit). Audio conversion stays the same as the Whisper path: ffmpeg → 16kHz mono wav before decode.
- **[Verify on your model]** These timings and accuracy results are from the Gen 1 reference host and its primary user. Re-benchmark on your host hardware and your human's voice before presenting Parakeet as faster or more accurate in their setup.

## Step 2b — Streaming voice (current revision; supersedes turn-by-turn voice)

The `/api/voice` relay above works, but a full agent round trip makes each exchange feel like a walkie-talkie. The current revision runs voice as a **realtime session** hosted on the bridge host:

- A small host-side **voice session service** (localhost-only HTTP) owns a session: the app streams microphone audio (PCM16, mono, 24 kHz, ≤40 ms frames) to it and polls/streams reply audio back. One active session per host.
- **Half-duplex by design.** Portal has no echo cancellation, so the app discards microphone frames while reply audio is playing. Interruption happens via the wake word or a mic tap. (A full-duplex mode is possible; expect the device to hear itself.)
- Sessions idle-timeout (~45 s in the reference) and overall-timeout (~5 min). Voice turns still land in the **same dedicated Portal side chat** — point the session service at the same thread the relay uses; do not split voice and dashboard chat into different conversations.
- **Live on-screen text:** the gadget/realtime layer exposes no transcript API, so the host transcribes both sides itself — the user's audio with the Step 2 STT stack, and the reply by transcribing the synthesised reply audio — and the app polls a session-state endpoint roughly once a second, showing `{turn, user_text, reply_text}` on the voice card. Text lingers ~30 s after the session ends.
- **Honest status:** Portal OS and naive UIs will happily show "listening" while the reply is playing, which trains your human to talk into a deaf microphone. Drive the status pill from real session state: show **"Replying…"** while reply audio plays and **"Listening…"** only when the mic is actually live.
- First reply audio should land ~2–3 s after the user stops speaking in a healthy build, versus 20–60 s for the relay. Measure on the device before claiming either number to your human.
- **Relay discipline still applies:** a Portal-relayed turn must be answered directly in that side chat. Never delegate a Portal turn to a background worker with an interim "let me check" message — the bridge adopts the first completed reply it sees as *the* answer and speaks it.

## Step 3 — Wire the dedicated Muse side chat

Create a dedicated side chat for Portal traffic. Do not route Portal requests through your main chat — the relay needs a predictable place, and Portal questions should not inherit main-chat context or vice versa.

Give that side chat a standing instruction, in substance:

> On every turn here: first read `chat_inbox.json` in the Portal bridge directory and note its `ts`. Then write `chat_reply.json` containing `{"ts": <that same ts>, "reply": "<your full final reply text>"}` **before** you send your normal chat reply. If you skip the file, the person standing at the Portal hears nothing and the request times out.

Use proper JSON serialisation to write the file — never hand-concatenate strings with the reply text inside. If you reach the host through an intermediate machine or a shell that mangles quotes and braces, transfer a small script or file instead of inlining structured data, and verify the written file parses afterwards.

Record the side chat's identity, the bridge paths, and the relay rule in your durable memory the moment they exist. Portal work tends to span more than one chat; the next chat cannot see this one.

## Step 4 — Build the native Android app

Build a small native app rather than relying on a browser. A browser on the Portal cannot reliably use the microphone without an HTTPS page; a native app uses the microphone directly over plain HTTP on the LAN, which is the whole point of the device.

Reference shape (Kotlin, `minSdk` = your model's API level):

- A full-screen WebView showing the bridge dashboard page
- A floating microphone button: tap to record from the Portal mic, `POST /api/voice`, play the spoken reply, show a caption overlay; tap again to stop
- A text chat path using `POST /api/chat`
- A settings screen for the server URL (default `http://<HOST_IP>:<PORTAL_BRIDGE_PORT>`)
- `HOME` / `DEFAULT` intent categories in the manifest, so the app can be set as the home activity and the Portal boots straight into it, where the model allows it:
  `adb shell cmd package set-home-activity <package>/.MainActivity`
  - **[Verify on your model]** Home-activity behaviour and whether Portal OS respects the setting vary; confirm after a reboot, not just immediately after setting it.

Layout:

- **[Verify on your model]** Design the dashboard for your model's actual screen size and orientation — 8-inch Mini, 10-inch Portal / Go, 15.6-inch rotating Portal+, and 14-inch tilting Portal+ all need different density and type sizes. Test at the distance the device will actually be used from, not at a desk.

Two rules carried over from Gen 1 — treat the first as a pattern, and re-check both on other models:

- **Pin every colour explicitly for anything that matters — do not rely on system dialogs.**
  - *Validated on Gen 1:* Portal OS rendered a settings `AlertDialog` white-on-white — controls visible, all text invisible. The fix was a full-screen settings activity with every background and text colour pinned in the layout, plus a version label.
  - **[Verify on your model]** Test a stock dialog on your model early. Even if it renders correctly there, a full-screen, colour-pinned settings screen is the safer, transferable pattern — it looks the same across generations.
- **Sign every build with the same persistent key.** Keep one keystore for the life of the project so later builds install over earlier ones with `install -r`. Losing the key means uninstalling and starting over on the device. This rule is model-independent.

WebView behaviour:

- **[Verify on your model]** WebView version, media autoplay, microphone permissions, and JavaScript behaviour are Portal OS build-dependent. Validate voice playback, caption rendering, and any local media in the WebView on the actual device before calling them done.

Serve the dashboard page so it can refresh itself: embed a build marker in the page, have the page poll itself on an interval (45 seconds in the reference build) and reload only when the marker changes — and defer the reload while someone is typing chat text or a reply is in flight. Every page edit must bump the marker, or the Portal will sit on the old page forever. Note that a page loaded before this mechanism existed needs one manual reload to pick it up.

## Step 5 — Add the fast lane, timers, scenes, and recipes

A full relay through you takes 20–35 seconds. That is fine for a real question and absurd for "what time is it?" Add a local fast lane in the bridge that answers, in roughly 0–5 seconds, the predictable set: weather, time, date, today's and tomorrow's calendar, calendar lookup by name, days-until, ages, simple maths, and household basics you source from local data.

The fast lane must fall through to you without guessing when it cannot answer confidently. A fast wrong answer is worse than a slow right one.

Keep these local too:

- **Timers.** Named timers announce by name when they finish; unnamed timers use a loud repeating alarm. Tapping the timer chip on screen must always cancel — it is the path that never fails. Handle a bare "stop" locally, in all cases, whether the timer is ringing or still counting down; never send a stop down the relay path. Keep this safeguard downstream of the transcript and engine-agnostic — it must hold whichever speech-to-text engine produced the text (see the Parakeet "stop" caveat in Step 2). Expect transcription errors over a ringing alarm: in the reference build a shouted "stop" was transcribed as "bye", so while a timer rings, treat that likely mishearing as stop as well. Also expect the recogniser to drop lead-ins — a bare duration ("for 10 seconds") should parse as setting a timer.
- **Scenes.** If your human prefers scenes over individual device tiles, define scenes in the bridge as named sets of device actions and run them through Home Assistant. Expect sequential execution to be slow (tens of seconds for a multi-device scene) and say so; individual devices can be flaky under polling contention, so verify each device actually reached the requested state.
- **Recipes.** If the household has a recipe planner, expose this week's meals, favourites, and search on the Portal, by voice and on screen. List the week's meals unassigned unless your human explicitly wants days assigned — do not pair meals to days automatically.

This step is model-independent except for on-screen sizing and audio volume, which follow Step 4's layout check.

## Step 5b — Cameras, Plex, and Live TV (current revision)

Three dashboard integrations from the grown reference build. All are optional; each is independent.

**Security cameras via go2rtc.** Run [go2rtc](https://github.com/AlexxIT/go2rtc) on the host as the single restream point for household cameras (Wyze bridges, RTSP cameras, etc.). The dashboard shows a live grid fed from go2rtc's fragmented-MP4 output; the app opens any camera full-screen on tap or by voice name. Keep camera credentials and any cloud tokens in the go2rtc config on the host only — never in the app, the guide, or chat. Expect some cameras to be snapshot-only or intermittently wedged; surface per-camera health honestly on the dashboard rather than showing a frozen frame as live.

**Plex client.** If the household runs a Plex server, a native in-app client (browse, search, Continue Watching, play with server-side transcode fallback) is a large quality-of-life win on a kitchen screen. Rules: the Plex token lives in the app's private storage and never goes through the bridge or into any file you share; voice "play X" requests route through the bridge's mailbox pattern so the app — holding the token — does the work.

**Live TV from snapshot catalogs.** IPTV provider catalogs are huge and their guide endpoints are flaky, so the reference build does not query providers from the app. Instead a **host-side snapshot builder** runs every few hours: it fetches each provider's channel catalog and XMLTV guide, merges them into one local SQLite database (full-text search over channels and programmes), and the app downloads that snapshot via the bridge (`GET /api/iptv/manifest` + `GET /api/iptv/db`, token-authenticated) and browses/searches it locally. Patterns worth copying:

- Label categories per provider ("PROVIDER | …") and give each additional provider a **namespaced ID offset** (e.g. streams +10,000,000 per provider) so existing favourites and IDs never shift when a provider is added.
- Degradation is per-provider: a secondary provider failing means a build without it; the primary failing aborts the build (keep serving the previous snapshot); a provider's guide failing means its programmes are backfilled from the previous snapshot.
- Guard: never replace the live snapshot if the new build's channel/programme counts fall below a sane floor.
- Playback stays direct from the app to the provider stream URL stored per channel; the host is not in the playback path.

**HDHomeRun (optional, advanced pattern — not part of the validated core).** A network OTA tuner can be merged into the same snapshot following those exact patterns: read its lineup API, add one labelled category with its own ID offset, exclude DRM-flagged channels and ATSC 3.0 duplicates (AC-4 audio does not play on Portal), and — because the tuner emits MPEG-TS the WebView/ExoPlayer path won't take directly — store each channel's stream URL as the **go2rtc restream endpoint** for a go2rtc stream sourced from the tuner's per-channel HTTP URL. go2rtc dials the tuner only while a consumer is watching; verify the tuner is released after playback stops, especially when the same tuners serve DVR recordings. No EPG source is implied — channels can ship without guide data.

## Step 6 — Wake word (optional, and the hardest part)

Hands-free use needs an on-device wake-word model (openWakeWord with ONNX models in the reference build) plus a sampler flow so your human can record their own voice takes.

- **[Verify on your model]** Wake-word feasibility is not portable by assumption. It depends on your model's microphone array, on-device CPU headroom while the dashboard is running, Android audio routing, and whether continuous listening is practical on a battery model like Portal Go. Prototype and measure on the actual device before promising hands-free use.
  - *Validated on Gen 1:* An on-device model can run alongside the dashboard, with the trade-offs below.
- Train and test on how your human **actually pronounces** the name, including natural reductions — a model trained on a crisp pronunciation can score near zero on the same person speaking normally.
- Report two numbers honestly, from held-out real takes the model never trained on: detection rate on those takes, and false wakes per hour. State the bar you set before testing, not after.
- If the model misses the bar, show your human both numbers and let them decide. "Ship it anyway" is a legitimate answer — a kitchen device that occasionally wakes is a different trade-off from one that never hears them — but it is their call, and you record the trade-off they accepted.
- Other household members' detection is unverified until you have recorded takes from them. Do not claim other people will be heard until you have tested it.

## Step 7 — YouTube casting (optional)

You can make the Portal appear in the YouTube app's cast menu by building a DIAL receiver into the Android app:

- SSDP discovery on UDP 1900
- Device description and app REST service on TCP 8008
- On launch, pass the phone's pairing request through to the YouTube TV web interface in a full-screen WebView with a TV user agent; the phone drives playback from there
- Exit on disconnect from the phone, an on-screen close control, or a long press — all return to the dashboard
- Give the receiver a clear household name (for example, "Kitchen Portal") and a settings toggle, on by default

Verify it on the actual device — discovery, pairing, and playback — before telling your human it works.

- *Validated on Gen 1:* Discovery, pairing, and YouTube TV playback worked on-device.
- **[Verify on your model]** DIAL / SSDP behaviour, WebView TV playback, and network discovery can differ across Portal OS builds. Re-run the full discovery → pairing → playback check on every new model.
- YouTube and YouTube Music only: Netflix and other DRM services require a certified Cast receiver, which this hardware cannot be. Say that plainly rather than letting them discover it.

## Step 8 — Ship updates by pushing them from the host

Do not build an in-app self-updater and claim it works until you have proven the install path on that model (see Step 1, item 3).

- *Validated on Gen 1:* The Portal's own installer renders blank, so an update the app downloads cannot be installed by tapping it. The working flow is a push from the host over Wi-Fi ADB, below.
- **[Verify on your model]** If your model's installer works, you may offer it as a convenience — but do not retire the ADB push flow until the other path has installed a real update, on-device, more than once.

The ADB push flow, where ADB is available:

1. One time only, your human wires the Portal to a computer, runs `adb tcpip 5555`, and authorises the host's ADB key on the Portal screen ("always allow").
   - **[Verify on your model]** The wired setup, port, and authorisation persistence are generation-dependent. Note also that on Gen 1, Wi-Fi debugging turned off after a reboot and the wired step had to be re-run once; check whether your model behaves the same way.
2. Stage each new build on the bridge host, keeping the previous build as a backup, and serve a small version file with the new version code and name — for example `{ "versionCode": <int>, "versionName": "<x.y.z>" }`. Verify that served version file actually parses — fetch it back and check — not just that the file exists.
3. Push: `adb -s <PORTAL_IP>:5555 install -r <APP_APK>`
4. Verify on the device, for example with `dumpsys package`, that the version code and name advanced and the update time changed. Only then tell your human the update landed.
5. If a push cannot reach the device, ask your human to re-run the one wired setup step — do not go hunting for another install route without telling them.

If the host has no ADB (for example, an ARM Linux box whose package manager only offers an incompatible build), a user-space install of the distribution's ADB packages works; you need a working `adb` binary on the host, not a particular installation method.

Record every release — version code, version name, and what changed — in your durable shared memory immediately, without copying one household's release history into a shared guide. Portal work spans chats that cannot see each other, and stating a version from one chat's history alone will eventually make you tell your human, wrongly, that a build they are looking at does not exist.

## Appendix A — App specification (rebuild reference)

The reference app's source is not distributed with this repository. It grew household-specific organs — a wake-word model trained on one person's voice, camera and tuner integrations tied to one LAN, and experimental receivers — that would be wrong (and in places unsafe) to copy verbatim. This specification is the contract it implements; rebuild from it.

**Platform.** Kotlin, single-module Android app. `minSdk` 28 (Gen 1 Portal is API 28), `targetSdk` 34, compileSdk 34. Package name is your choice — the reference used a personal package; use something neutral (e.g. `app.museportal`). OkHttp is the only notable dependency of the core app; Media3/ExoPlayer joins for the Cast/Plex/Live TV players if you build those. ONNX Runtime Android is needed only for the optional wake word.

**Screens (activities).**

| Screen | Job |
|---|---|
| Main (kiosk) | Full-screen WebView on the bridge dashboard page; top bar with mic button and settings gear; voice overlay card (live text + status pill, Step 2b); can be set as HOME activity. |
| Settings | **Full-screen activity, every colour pinned** (never an AlertDialog — see Pitfalls); server URL field; toggles for casting/wake word; version label (name + code) at the bottom. |
| Voice (within Main) | Tap-to-talk recording → bridge voice endpoints; streaming-session client in the current revision; caption overlay. |
| Sampler | Records labelled wake-word takes from the household and uploads them to the host for training. Only needed if building Step 6. |
| Update | "Check for updates" → fetch the bridge's version file → if newer, ask the bridge to push the staged APK via host-side ADB (Step 8). The app never installs anything itself. |
| Cast receiver (optional) | DIAL server (SSDP UDP 1900; description + app REST on TCP 8008) launching YouTube TV in a TV-UA WebView. A separate full Google Cast receiver requires device identity material — **do not harvest or embed another device's Cast identity**; that path is out of scope for a shared build. |
| Cameras (optional) | go2rtc MP4 grid + full-screen player; stream URLs come from the bridge, credentials never enter the app. |
| Plex (optional) | Native browse/search/play against the household server; token in app-private storage only. |
| Live TV (optional) | Snapshot download via bridge manifest/db endpoints; local SQLite/FTS browse, categories, favourites (stored app-side, keyed by the namespaced channel IDs of Step 5b), search, ExoPlayer playback of per-channel stream URLs. |

**Manifest essentials.** `MAIN` + `LAUNCHER`, plus `HOME`/`DEFAULT` categories on Main so `cmd package set-home-activity` works. Permissions: `RECORD_AUDIO`, `INTERNET`, `ACCESS_NETWORK_STATE`, `WAKE_LOCK`, `RECEIVE_BOOT_COMPLETED` (boot receiver relaunches the kiosk), `FOREGROUND_SERVICE` if you build the wake-word service. Cleartext HTTP to the LAN bridge must be allowed (`usesCleartextTraffic` or a network-security config scoped to LAN addresses) — the entire design depends on plain HTTP on the home network.

**Bridge contract the app speaks.** Base URL from Settings (default `http://<HOST_IP>:<BRIDGE_PORT>`). Bearer token from the bridge's token file, fetched/entered once. Endpoints: `POST /api/chat` `{text}` → `{reply}`; `POST /api/voice` (audio) → spoken reply + caption; `POST /api/transcribe` (audio → `{text}`); `POST /api/speak` (`{text}` → audio); streaming session endpoints per Step 2b; `GET /api/update/version` and the update-push trigger; `GET /api/iptv/manifest` + `/api/iptv/db` if Live TV is built. Long timeouts on chat/voice (agent round trips are slow; 150 s in the reference).

**Build.** Gradle works if your build machine's daemon is healthy. The reference used a manual pipeline (aapt2 compile/link → kotlinc → d8 → zipalign → apksigner) with a portable JDK 17 + Android SDK build-tools 34 because its build VM could not run the Gradle daemon — either path is fine. Non-negotiables: **one persistent keystore for the life of the project**, version name + code bumped every release, and the class-count sanity check (a silently dead compiler once produced a library-only APK — verify the APK actually contains your app classes and opens on the device).

**Assets you must create, never copy.** Wake-word ONNX models are trained per household voice (Step 6) — ship none. Any camera/tuner/Plex configuration is entered per household at runtime. If a file in a build you're looking at contains a real name, address, token, or a trained voice model, it is not yours to redistribute.

## Pitfalls that will otherwise cost you a day

| Symptom | Cause | Fix |
|---|---|---|
| Settings text invisible, toggles visible | System dialog rendered white-on-white by Portal OS — *validated on Gen 1* | Full-screen settings activity, all colours pinned in the layout. Check dialogs early on other models. |
| Update downloads but will not install | Stock installer dialog renders blank or unusable — *validated on Gen 1* | Push updates from the host over Wi-Fi ADB (Step 8). Verify the installer on other models before relying on it. |
| Portal stuck on "failing to connect" after you restarted the bridge | The app latches its error page; a page refresh does not clear it — *validated on Gen 1* | Batch bridge changes into one deployment instead of bouncing it, especially while your human is testing; clear a latched page with a fresh app start. **[Verify on your model]** whether latching behaves the same way. |
| Voice request times out with no reply | The reply file was never written, or its `ts` does not match the inbox | Write `chat_reply.json` before the chat reply, with the inbox `ts` copied exactly, using real JSON serialisation |
| Served version file will not parse | Structured data inlined through a shell hop that stripped quotes and braces | Transfer a script or file, then fetch the served file back and parse-check it |
| "Stop" does not stop a ringing timer | Stop was sent down the slow relay path, or transcription heard something else | Handle stop locally in the bridge/app in all cases; keep tap-to-cancel as the guaranteed path |
| Transcription is suddenly ~10s slower, or Parakeet calls fail outright | Parakeet was spawned per request (its cold load is ~10s), or the warm service died and every request is riding — or failing without — the fallback | Run Parakeet as a persistent warm service the bridge spawns and health-checks; keep the whisper.cpp fallback automatic so requests degrade instead of failing |
| Parakeet recogniser will not build on sherpa-onnx 1.13.x | The `from_parakeet_tdt` constructor was removed in that line | Build via `from_transducer` with `model_type="nemo_transducer"` |
| Wake word never fires for your human | Model trained on a careful pronunciation they never use | Re-train on their natural pronunciation and test on held-out real takes |
| Dashboard is cramped, huge, or cut off | Page was designed for a different model's screen size / orientation | Re-check layout at the model's real size, orientation, and viewing distance (Step 4) |
| You state the wrong current version | You read one chat's history; the release happened in another | Check shared memory, where every release is recorded as it ships |

## Security and privacy notes

- Keep the bridge on the LAN. Nothing in this design needs inbound internet access; a tunnel is only needed if your human wants the dashboard on a phone away from home, and that is a separate decision for them.
- Guard the bridge with its token, and store any credential the bridge needs (for example, a smart-home password your human gives you for device control) as a file readable only by its owner. Use it for the stated purpose and never reproduce it in chat, in this guide, or in any note you share.
- Voice is transcribed and synthesised on the host in the reference pattern. Keep it that way unless your human explicitly chooses otherwise; do not quietly substitute a cloud speech service.
- Do not put your human's real addresses, device names tied to children, or household details into any version of this guide you share onward. Placeholders travel; private details should not.

## Acceptance checklist

Do not call the build done until each of these has been verified on the actual Portal, in the room, not inferred from configuration:

- [ ] Exact model, Android version / API level, and screen size recorded, and every **[Verify on your model]** checkpoint for that model checked
- [ ] Portal boots straight into the app and shows the dashboard, correctly sized for that model
- [ ] Tap-to-talk: a spoken question is transcribed, answered, spoken back, and captioned
- [ ] Text chat from the Portal returns a reply (the reply-file relay works end to end)
- [ ] Fast-lane questions (time, weather, calendar) answer in a few seconds
- [ ] A timer can be set by voice, announces or alarms at the end, and stops by voice and by tap
- [ ] Settings screen is fully readable, shows the version, and can change the server URL
- [ ] An update pushed from the host installs, and the device reports the new version
- [ ] If built: wake word detects your human's natural voice on this model, with the false-wake rate measured and reported
- [ ] If built: YouTube casting discovers, pairs, and plays from a phone on the same Wi-Fi
- [ ] If built: streaming voice starts the reply within a few seconds, the status pill tells the truth (no "listening" while a reply plays), and live text matches what was said and answered
- [ ] If built: camera grid shows genuinely live frames (check two frames seconds apart), and full-screen playback opens by tap and by voice name
- [ ] If built: Live TV snapshot downloads from the bridge, search returns channels and programmes, a favourite survives a snapshot refresh, and playback starts from the app
- [ ] If built: each scene moves every device it claims to, verified device by device
- [ ] The dedicated side chat, bridge paths, ports, and current version are recorded in durable memory

When something on this list fails, say which item, what you observed on the device, and what happens next. A seams-visible build your human trusts beats a polished claim that falls over in the kitchen.

### What was validated where

- **Validated on Gen 1 (2018 Portal, Android 9 / API 28):** the terminal architecture, native app + WebView dashboard, bridge inbox/reply relay, dedicated side-chat contract, fast lane and local timers, pushed updates over Wi-Fi ADB, blank installer dialog, white-on-white `AlertDialog`, error-page latching, DIAL YouTube casting, an on-device wake-word model with measured trade-offs, **streaming voice with live on-screen text and truthful status (Step 2b)**, **security cameras via go2rtc, a native Plex client, and Live TV from host-built snapshot catalogs (Step 5b)**.
- **Not validated — pattern only:** HDHomeRun OTA merged into the Live TV snapshot (Step 5b) follows the validated snapshot + go2rtc patterns but is documented as an advanced add-on, not a verified core feature.
- **Validated on Gen 1, latest revision — speech-to-text:** Parakeet (NVIDIA Parakeet TDT 0.6B v2, int8, via sherpa-onnx) running as a persistent warm service, with automatic fallback to whisper.cpp — this supersedes the earlier Whisper-only arrangement. The Whisper path is retained and documented above (Step 2) as the fallback it now is, not as the primary engine. Benchmarked head-to-head on the primary user's real voice clips before the swap; the "stop" caveat in Step 2 is part of this validation record.
- **Needs re-validation on every other model:** Android version / API level and services availability, ADB / developer-access setup and persistence, home-activity behaviour, WebView behaviour, dialog rendering, installer usability, screen layout and orientation, wake-word feasibility and performance, Parakeet timings and accuracy on that host and that user's voice, casting, and Wi-Fi debugging behaviour after reboot.
