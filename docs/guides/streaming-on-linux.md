# Streaming on Linux in 2026

Short answer: **yes, it works**, and for most setups as well as on Windows. OBS is a
first-class Linux app, GPUs encode in hardware, PipeWire gives you finer audio routing than
Windows does out of the box. What is missing is the glue: some tools do not exist (Elgato's
Stream Deck app), and the sandboxes modern distributions use keep apps from seeing each other.

This guide is the map. Each step links to the detailed guide and the tuxcast command that does
it for you.

## 1. Check where you stand

```sh
pipx install git+https://github.com/achedon12/tuxcast.git
tuxcast doctor
```

Keep this output open: the rest of this guide follows its order.

## 2. Display server: Wayland or X11

Both work for streaming.

- **Wayland** (default on GNOME, KDE, most new installs): screen and window capture go through
  the *xdg-desktop-portal*, which asks once which screen to share. Apps cannot read keys
  pressed in other windows, so OBS hotkeys only work while OBS has focus: drive OBS from a
  Stream Deck or obs-websocket instead.
- **X11**: capture and global hotkeys work without asking, which some streamers prefer.

Pick what your desktop defaults to; switch only if a specific tool forces you.

## 3. Audio: PipeWire

Every current distribution uses PipeWire. It accepts PulseAudio and JACK clients, and lets you
create virtual devices with a config file. Use it to split your stream mix: game, music, voice
and alerts as separate OBS sources.

→ [Audio routing](audio.md) · `tuxcast audio setup`

## 4. OBS and your GPU

Install OBS from Flathub (current version, browser source and plugins included) or your
distribution if it is recent. Encode on the GPU: NVENC on NVIDIA (proprietary driver needed),
VA-API on AMD and Intel.

→ [OBS on Linux](obs.md)

## 5. Stream Deck

Elgato's software does not exist for Linux and does not run under Wine. Use
**StreamController**, an open-source app with a plugin store (OBS, Discord, Twitch, media,
system). Your Windows profiles can be converted.

→ [Stream Deck on Linux](stream-deck.md) · `tuxcast convert`

## 6. Discord, Spotify and the sandboxes

Flatpak and snap isolate apps. Great for security, until your Stream Deck (a Flatpak) needs
to reach Discord (a snap) or Spotify. The fixes are known and small.

→ [Discord and Spotify in sandboxes](sandboxes.md) · `tuxcast bridge discord`

## 7. Music

Most music gets VODs muted or claimed, and playing Spotify on stream breaks Spotify's terms
whatever the track. Use music cleared for streaming.

→ [Music without claims](music.md)

## 8. Network

Use a cable. Wi-Fi drops packets in bursts that Twitch shows as an unstable bitrate even when
your speed test looks great.

→ [Network](network.md)

## Before each stream

```sh
tuxcast doctor && obs
```

The doctor exits with an error when something is broken, so OBS only starts on a healthy setup.
