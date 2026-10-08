# Security policy

## Supported versions

Security fixes go into the latest release. Please update before reporting.

## Reporting a vulnerability

Please do not open a public issue. Use
[GitHub's private vulnerability reporting](https://github.com/achedon12/tuxcast/security/advisories/new)
instead. You will get an answer within a week.

## What tuxcast touches

tuxcast runs as your user and only changes what a command says it changes:

| Command | Writes |
| --- | --- |
| `doctor` | nothing |
| `convert` | StreamController pages and images |
| `bridge discord` | symlinks in `$XDG_RUNTIME_DIR`, Flatpak overrides, an optional user service |
| `audio` | one PipeWire drop-in file in `~/.config/pipewire` |
| `deck reset` | nothing on disk (a USB reset ioctl) |
| `patch` | the files your own patch files name, and an optional user service |

It never needs root. The only privileged step, installing the Stream Deck udev rule, is
printed for you to run.
