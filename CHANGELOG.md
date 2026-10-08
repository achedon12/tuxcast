# Changelog

All notable changes to tuxcast are listed here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and tuxcast uses
[semantic versioning](https://semver.org/).

## [Unreleased]

## [0.1.0] - 2026-10-08

The first release, on PyPI (`pipx install tuxcast`): the problems every Linux streamer hits, each
solved by one command.

### Added

- `tuxcast ui` opens a control desk for everything below: a go-live tally, the Stream Deck with
  StreamController's real pages and a key-by-key preview of dropped Elgato profiles, the doctor's
  checks with one-click fixes, an audio mixer with faders, mute and drag-and-drop app routing, the
  Discord bridge and patches. It listens on 127.0.0.1 only and requires the token it prints. The
  website has a live demo of it.
- `tuxcast doctor` checks a streaming setup in eight areas (display server, audio, GPU
  encoding, OBS, Stream Deck, Discord, Spotify, network) and prints the fix for each
  problem. `--json` for scripts, `--only` to focus on some areas.
- `tuxcast convert` turns Elgato Stream Deck profiles (`.streamDeckProfile`, backups and
  `.sdProfile` folders, versions 1 and 2) into StreamController pages: images, titles,
  folders, multi actions, hotkeys translated for AZERTY and QWERTZ keyboards, OBS,
  Discord and Twitch actions. A report lists the keys to redo by hand.
- `tuxcast bridge discord` exposes Discord's IPC socket installed as a snap, Vesktop or a
  native package to Flatpak clients such as StreamController, with an optional login service.
- `tuxcast audio` creates separate PipeWire sinks (game, music, voice, alerts) and routes
  apps to them, so each part of the mix is its own OBS source.
- `tuxcast deck` lists Stream Decks, prints the udev rule they need, and resets a deck stuck
  after a crash without unplugging it.
- `tuxcast patch` re-applies local edits that app updates wipe, through a systemd path unit.

[Unreleased]: https://github.com/achedon12/tuxcast/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/achedon12/tuxcast/releases/tag/v0.1.0
