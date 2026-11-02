# Turn Any Meta Portal Into a Muse Terminal

## A setup guide for humans

A Meta Portal is a good screen, a good microphone, and good speakers — stuck inside software that doesn't do much anymore. This setup gives it a new job: an always-on display in your kitchen or living room where you can see the time, weather, and your day, talk to your Muse by voice, set timers, run your smart home, and cast YouTube — all through a small computer already on your home network.

It works with any Portal model — the original Portal, Portal Mini, Portal+, Portal Go, and later generations. Models differ in screen size, Android version, and how you get an app onto them, so a few steps below are "check your model" rather than one fixed recipe. The idea itself is the same for all of them.

This guide covers what gets built and what you need to build it. There's a companion guide for your Muse with the technical build instructions — hand that one to your Muse, and work through this one yourself.

## TL;DR — the whole guide in under a minute

- **What was built —** Three pieces — a Portal app, a bridge program on an always-on home computer, and a dedicated Muse conversation — turn a Portal into a voice-and-dashboard terminal without replacing its system.
- **What you get when it's running —** A glanceable dashboard plus streaming voice and text chat (with the words shown live on screen), near-instant local answers and timers, smart-home scenes, recipes, YouTube casting, your security cameras, a Plex client, and live TV — with an optional wake word.
- **What you need —** Any Portal, a Muse, an always-on home computer, a Mac or PC plus a data cable for the first install, and shared home Wi-Fi; Home Assistant is optional.
- **Do you need a Raspberry Pi? —** No — any always-on computer on your network works; you can't skip a home computer entirely, because speech, timers, and local control happen there, not in the cloud.
- **Check your model first —** Portals differ by Android version, debug access, and screen size, so verify your specific model before assuming any step or timeline.
- **How to set it up, in outline —** Prepare the Portal, enable developer access, have Muse build and test the bridge first, install by cable, point the app at the bridge, and test one layer at a time.
- **Setting up ADB, step by step —** Install Google's free platform-tools, enable USB debugging via Meta's guide for your model, approve the prompt on the Portal itself, and watch for charge-only cables and reboot resets.
- **Loading the app, step by step —** One computer command installs the app (updates install over the top and keep settings), allow microphone access on first launch, and use Wi-Fi installs only after the wired route works.
- **Honest limitations — on any Portal —** YouTube is the casting ceiling, the on-device installer and debug access can be unreliable, voice will sometimes mishear, a wake word trades misses for false wakes, and it stays a home-network appliance.
- **A sensible way to start —** Start with just the dashboard, text chat, and tap-to-talk, live with it for a day, then add timers, scenes, recipes, casting, and a wake word one at a time.

## What was built

In plain terms, three things working together:

1. **A simple app on the Portal** that shows a dashboard full-screen and lets the Portal use its own microphone and speakers to talk to Muse. A native app matters because a web page on the Portal can't reliably use the microphone — the app can.
2. **A small helper program (a "bridge") on an always-on computer at home.** It listens to the Portal, turns your speech into text, passes messages to Muse, turns Muse's replies back into speech, and handles quick local jobs like timers itself. In the current revision, voice runs as a realtime streaming session hosted on that computer, so replies begin playing in seconds and the conversation is captioned live on screen; the simpler turn-by-turn relay described later in this guide is how it started and remains a fine first version to build. For speech-to-text, the current build uses a fast local speech model (NVIDIA's Parakeet) that stays running and ready — "warm" — on that home computer, so your words are transcribed in a fraction of a second instead of a couple of seconds. It is still fully local and private: your speech is understood on your home network, not sent to a cloud speech service. If that fast model ever fails to answer — including while it's still warming up just after the home computer restarts — the previous speech engine (Whisper) steps in automatically as a backup, so voice keeps working, just a little slower, rather than stopping.
3. **A dedicated conversation with your Muse for the Portal,** separate from your main chats, so kitchen questions don't clutter — or get cluttered by — everything else.

Nothing about this replaces the Portal's operating system or unlocks it. The Portal stays a Portal; it just gains an app and something useful to talk to.

## What you get when it's running

- **A dashboard you can glance at** — a big clock, the weather, and today's calendar, designed to be read from across the room.
- **Voice and text chat with your Muse** — tap to talk through the Portal's far-field microphone, hear the reply spoken back, and see it written on screen. In the current build, voice is a live streaming conversation, not walkie-talkie turns: the reply starts playing within a few seconds of you finishing, both sides of the conversation appear as live text on the voice card, and a small status pill tells the truth about whose turn it is ("Replying…" while Muse is speaking, "Listening…" when it's your turn — Portal has no echo cancellation, so it listens between replies rather than over them). Your speech is transcribed locally in a fraction of a second, so speaking feels responsive rather than laggy. Text chat is there when you don't want to talk out loud.
- **Fast answers for simple things** — time, date, weather, simple maths, and timers are answered locally by the computer at home, almost instantly. Open-ended questions go to Muse and take longer, the way any Muse reply does.
- **Timers that ring on the Portal itself** — including named timers, so "your pasta timer is done" instead of a generic beep. There's always a tap on screen to stop one, because no voice system hears a shouted "stop" over a loud alarm every time.
- **Smart-home scenes, not single switches** — one tap or one sentence for a set of actions: a "bedtime" scene, a "cooking" scene, a "movie night" scene. If you already run Home Assistant, the Portal can drive it; if you don't, this part is optional.
- **Recipes where you cook** — this week's meals, favourites, and search, with a step-by-step cook mode, if your Muse connects it to wherever your recipes live.
- **YouTube casting** — your phone finds the Portal on your home Wi-Fi and casts YouTube to it, the way you'd cast to a TV.
- **Your security cameras** — if you run cameras the host can restream (many Wi-Fi cameras can be, via a small open-source restreamer called go2rtc), the Portal shows a live camera grid on the dashboard and any camera full-screen on tap or by voice.
- **A Plex client** — browse and play your own Plex library on the Portal, including from voice ("play…" requests), if you run a Plex server at home.
- **Live TV** — the host periodically builds a local snapshot of one or more IPTV channel catalogs plus program guide data into a single searchable database on the Portal, so channel browsing, search, favourites, and "what's on" are instant and keep working through provider hiccups. A second IPTV provider and an over-the-air tuner (HDHomeRun) have since been folded into the same catalog in the reference build, each in its own labelled category — see the advanced notes at the end of this guide. Tuner channels currently ship without guide data.
- **A wake word (optional)** — say your Muse's name instead of tapping. This is the hardest extra to get right and the last thing to add, not the first. In always-listening live-voice mode, an extra check is worth having: the open microphone will otherwise pick up TV and background conversation as if it were a command, so the reference build also verifies the speaker's voice and requires the wake phrase at the start of each prompt before acting on it.

## What you need

- **Any Meta Portal** — original, Mini, +, Go, or a later generation. It needs to be powered on, on your home Wi-Fi, and in a place where its microphone can hear the room.
- **A Muse** — a Muse subscription and an agent you already talk to. Your Muse does the building: the app, the bridge, and the checks. You don't need to be a programmer, but you do need a Muse willing to do the technical work in the companion guide.
- **An always-on computer on your home network** — this runs the bridge. See the next section; it does not have to be a Raspberry Pi.
- **A computer for the one-time install** — a Mac or Windows PC, plus a data cable that fits your Portal, for getting the app onto the device the first time.
- **Your home Wi-Fi** — the Portal, the always-on computer, and your phone (for casting) all need to be on the same network.
- **Optional: Home Assistant** — only if you want the smart-home scenes. The dashboard, chat, timers, recipes, and casting don't need it.

No new subscription is needed for the basic setup beyond the Muse you already have.

## Do you need a Raspberry Pi?

No. A Raspberry Pi is just one cheap, quiet, low-power way to be the always-on computer — it's popular for this because many homes already have one running something else.

Any computer that stays on and stays on your home network can do the job: an old laptop left plugged in, a Mac mini, a Windows PC that's already always on, a home server, or a NAS that can run small programs. What matters is that it's awake when you want to use the Portal and has enough power to handle speech without making you wait — the fast speech model stays running on it, ready for the moment you speak, rather than starting up fresh for every command.

What you can't do is skip the computer entirely. The Portal on its own has nowhere to do the work: understanding speech, speaking replies, running timers, and relaying messages to Muse all happen on that home computer, not on the Portal.

Could that computer be replaced by a cloud server? Partly, for chat — but you'd lose the point of the setup. Controlling things in your home needs something in your home to talk to them, casting needs to be discovered on your local network, and a round trip to the cloud adds delay to every reply. Local and always-on is what makes it feel like an appliance instead of a website.

## Check your model first

Portals are not all the same under the hood, and the differences decide how the install goes. Before starting, have your Muse help you confirm three things about your specific model:

- **Android version and app support** — later generations run newer Android than the original. That affects which app features are available and how it's built. Note your model's Android version from its Settings.
- **Developer / debug access** — getting a custom app onto a Portal uses Android's developer tools (called ADB). Meta has published guidance for enabling this on Portal, but availability and the exact steps vary by model and software version. Verify it on yours before promising yourself a timeline — if your model or software version doesn't allow it, the rest of the project can't start.
- **Screen size and orientation** — a Mini on a counter and a large Portal+ are read from different distances. The dashboard should be designed for your screen: type and buttons sized for how far away you'll actually stand.

Treat any step you read elsewhere — including in guides written for the original Portal — as "proven on that model, verify on mine," not as guaranteed for yours.

## How to set it up, in outline

You handle the Portal, the cable, and anything that appears on its screen. Your Muse handles the building and checking. In order:

1. **Place and prepare the Portal.** Put it where it will live, join your home Wi-Fi, and let it finish any system updates.
2. **Enable developer access** following Meta's guidance for your model, so a computer can install the app. (Full walkthrough: "Setting up ADB, step by step" below.)
3. **Have your Muse build the pieces first** — the Portal app, the bridge on your always-on computer, and the dedicated Portal conversation — and confirm the bridge is running and reachable on your home network *before* you touch the Portal. Testing a Portal against a bridge that isn't up yet looks like an app problem when it isn't.
4. **Install the app from your computer** using the developer tools, then open it on the Portal and allow microphone access when asked. Installing by cable from a computer is the reliable route on Portal hardware. (Full walkthrough: "Loading the app, step by step" below.)
5. **Point the app at your bridge** in the app's settings, using the address your Muse gives you for your network. If you can, reserve a fixed address for the always-on computer in your router, so the Portal doesn't lose it later.
6. **Test one layer at a time:** the dashboard loads → text chat gets a reply → tap-to-talk gets a spoken reply → a timer works → a simple question answers quickly and an open question answers fully. Fix each layer before blaming the next.
7. **Make it permanent, if you like:** set the app to open when the Portal starts, and ask your Muse about pushing future updates over Wi-Fi instead of reaching for the cable each time.

## Setting up ADB, step by step

Step 2 above — "enable developer access" — is the part people most often get stuck on, so here it is in full. ADB (Android Debug Bridge) is the standard way a computer talks to an Android device for installing apps. You only set it up once; after that, installing and updating the app takes seconds.

**What you need**

- A Mac or Windows computer — the same one you'll install the app from.
- The Android platform-tools — a small, free download from Google that includes ADB. Your Muse can point you to the official download for your computer and unzip it for you.
- A USB cable that carries data, not just power. This matters more than it sounds — see the gotchas below.

**Turning on developer access on the Portal**

This project exists because Meta deliberately left a door open: current Portal software includes an official ADB setting intended as the device's end-of-life offramp. On the reference model it's **Settings › Debug › ADB Enabled**, behind your Meta account PIN. That one toggle is the foundation of everything in this guide — no unlocking, no exploits, no system modification.

1. Follow Meta's own Portal developer guide for your model to switch on developer mode and USB debugging (on many models, the Settings › Debug › ADB switch above). The exact settings path varies by Portal generation and software version, so don't copy steps written for a different model — check the guide for yours.
2. Plug the Portal into your computer with the data cable.
3. Watch the Portal's screen, not the computer's: a prompt asking whether to allow USB debugging from this computer will appear on the Portal itself. Approve it there. (Ticking "always allow from this computer," if offered, saves you approving it again later.)
4. Ask your Muse — or run the check yourself — to list the devices ADB can see. If your Portal shows up in that list, you're connected and everything else can proceed. If it doesn't, work through the gotchas before assuming anything is broken.

**Common gotchas**

- **Charge-only cables don't work.** Many cables that come bundled with chargers carry power but no data. The Portal will happily charge and ADB will see nothing. If the device never appears, a different cable is the first thing to try.
- **The approval prompt is on the Portal.** People often stare at the computer waiting for it. It appears on the Portal's screen, and until you approve it there, the computer can see the device is attached but isn't allowed to do anything with it.
- **A reboot may switch it off.** On some models, the debug connection doesn't survive the Portal restarting, and you need the cable once more to turn it back on. That's normal behaviour for these devices, not a sign you set it up wrong.

## Loading the app, step by step

Once ADB is connected, installing the app is anticlimactic — in a good way.

1. **Your Muse builds the app file** and keeps it somewhere you or it can reach from the install computer.
2. **One command from the computer installs it.** Your Muse will give you the exact command for your setup (or run it for you, if it has access to that computer). It takes a few seconds.
3. **On the Portal, almost nothing visibly happens** — no progress bar, no wizard. The app simply appears in the Portal's app list when the command finishes. Open it from there.
4. **Allow microphone access** when the app asks on first launch. Without it, the dashboard works but voice doesn't.

**Updates work exactly the same way.** Installing a newer app file over the old one replaces the app and keeps its settings and data — as long as every build is signed with the same key, which is a detail your Muse handles when building it. You don't uninstall first, and you shouldn't: uninstalling would wipe the settings you'd have to re-enter.

**Why not just install on the Portal itself?** Because on some Portal models and software versions, the built-in on-device installer doesn't render properly for sideloaded apps — it can show a blank or unusable screen. The cable-and-computer route looks more old-fashioned, but it's the dependable one, which is why it's the plan rather than a fallback.

**Optional: install over Wi-Fi later.** After a one-time setup while connected by cable, later installs and updates can go over your home Wi-Fi instead — no reaching behind the counter for a cable each time there's a new version. Ask your Muse to set this up once the wired install is proven. Just remember the gotcha above: on some models a reboot turns the wireless debug connection off, and one wired reconnection is needed to switch it back on.

## Honest limitations — on any Portal

These aren't faults of one build; they're inherent to putting a custom app on a closed consumer device. Expect them, and check how each lands on your model:

- **YouTube is the casting ceiling.** The Portal can be made to receive YouTube casting, but it cannot become a certified receiver for Netflix and other protected apps — that requires certification no home setup can grant. If DRM casting is the main thing you want, this project won't give it to you.
- **The on-device installer may not cooperate.** On some Portal models and software versions, the built-in app installer doesn't render or behave usefully for sideloaded apps, which is why the computer-and-cable install is the plan rather than a fallback. Don't trust an update flow that promises the Portal will install the next version by itself until your Muse has verified it on your model.
- **Debug access may not survive a reboot.** On some Portals, the developer connection switches off when the device restarts, and you need the cable once more to turn it back on. Ask your Muse how yours behaves before relying on remote updates.
- **Settings and prompts need care on Portal's system software.** Standard Android pop-up dialogs don't always display legibly on Portal. Anything important — settings especially — should be a full screen designed for the device, with its version clearly shown. If a screen ever looks blank or unreadable, that's a known quirk to design around, not something you did wrong.
- **Voice will sometimes mishear.** Short commands, loud rooms, and ringing timers are the hard cases for any speech system. Even the new, faster Parakeet engine once heard a cleanly spoken "stop" as a completely different word in testing — which is why timers always keep a tap-to-stop on screen, and why one-word commands that matter should be tested in your own voice, in your own kitchen, before you rely on them. Anything noisy or urgent needs a non-voice way to do it — a button on screen — not just a command.
- **A wake word is a trade-off, not a feature checkbox.** A model tuned to catch how you naturally say the name will also wake occasionally on TV or conversation; one tuned never to false-wake will miss you. Your Muse should report both numbers and let you choose — and everyone's voice in the house needs testing, not just yours.
- **It's a home-network appliance.** It works at home, on your network. It isn't designed to follow you, and remote access, if you want it later, is a separate decision with its own security questions — not a default.
- **Keep secrets on the home computer, not on the Portal and not in shared notes.** Smart-home passwords and access keys belong in protected storage on the always-on computer. A guide you share — like this one — should contain no addresses, keys, or household specifics from your setup.

## Advanced, optional: over-the-air TV via HDHomeRun

If you have a SiliconDust HDHomeRun tuner on your network, its local broadcast channels can join the same Live TV catalog as the IPTV sources. The pattern: your host reads the tuner's channel lineup, adds those channels to the snapshot database in their own labelled category with their own ID range (so favourites from other sources never shift), skips any DRM-flagged channels and the ATSC 3.0 duplicates (their audio format doesn't play on Portal), and plays each channel by having go2rtc pull the tuner's stream on demand and restream it in the format the Portal plays — the tuner is only in use while someone is actually watching, and is released when they stop, so scheduled DVR recordings on the same tuner aren't disturbed. This has since been built and run in the reference build (over a hundred local channels alongside the IPTV sources, no guide data yet): two hard-won details from that build are in the agent guide — transcode the tuner streams with a flag-free ffmpeg process rather than a restreamer's built-in low-delay producer (which scrambles frame order on interlaced sources), and expect the motion-smoothness fix to need an on-device eye check during fast motion before you call it done. Treat this as an advanced pattern to adapt once basic Live TV works, not as a first-weekend step.

## One thing this project is not: a reflash

People often ask about wiping the Portal and installing stock Android or Linux on it. That is not possible on this hardware, and this project does not attempt it: the bootloader is locked, there is no OEM unlock or public root path, and the microphone, speakers, screen, and camera depend on Portal's own system services that a stock system wouldn't have. Meta's ADB setting (above) is the supported opening — this whole setup is built to need nothing more than that.

## A sensible way to start

Build the smallest version that proves the idea: dashboard, text chat, and tap-to-talk voice, at home, installed by cable. Live with it for a day. Then add one thing at a time — timers, then scenes, then recipes, then casting, then a wake word if you still want one — and test each addition before starting the next.

Almost every frustration with a project like this comes from adding five things at once and not knowing which one broke. Added one at a time, this is a genuinely useful second life for a device that was otherwise headed for a drawer.
