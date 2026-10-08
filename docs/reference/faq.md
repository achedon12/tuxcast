# FAQ

## Does tuxcast need root?

No. Everything happens in your user session. The one privileged step, installing the Stream
Deck udev rule, is printed by `tuxcast deck udev` for you to run with `sudo`.

## Does it work on my distribution?

tuxcast reads standard Linux interfaces (sysfs, PipeWire, systemd user services, Flatpak), so it
works on any current distribution with Python 3.11 or newer: Ubuntu 24.04+, Debian 13, Fedora,
Arch, openSUSE Tumbleweed, Linux Mint 22, Pop!_OS… The `audio` and `bridge --install` commands
need systemd and PipeWire, which these all use.

## Will `tuxcast doctor` change anything?

No. It only reads files and runs read-only commands (`pactl info`, `flatpak list`, `ip route
get`…). Every other command says what it writes, and most accept `--dry-run`.

## How do I undo what tuxcast did?

| Command | Undo |
| --- | --- |
| `convert` | Delete the pages in StreamController, and `Assets/tuxcast/` in its data folder |
| `bridge discord --install` | `tuxcast bridge discord --uninstall`, then `flatpak override --user --reset <app>` |
| `audio setup` | `tuxcast audio remove --restart` |
| `patch install` | `tuxcast patch uninstall` |
| udev rule | `sudo rm /etc/udev/rules.d/70-streamdeck.rules` |

## Why not a GUI?

The problems tuxcast fixes are one-time setup steps, and a command is easier to document, paste
in a forum answer and run over SSH. A GUI could come later; the doctor's `--json` output is
designed for it.

## My Elgato action was not converted

The report names its UUID. [Open an issue](https://github.com/achedon12/tuxcast/issues/new?template=elgato_action.yml)
with it, or add the mapping yourself: see [Contributing](contributing.md).

## Is it affiliated with Elgato, OBS, Discord, Spotify or Twitch?

No. tuxcast is an independent open-source project. Product names belong to their owners and are
used only to say what tuxcast works with.
