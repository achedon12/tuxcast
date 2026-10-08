# Commands

```text
tuxcast <command> [options]
```

| Command | What it does | Changes your system |
| --- | --- | --- |
| [`doctor`](doctor.md) | Checks your streaming setup and explains the fixes | No |
| [`convert`](convert.md) | Elgato Stream Deck profiles to StreamController pages | Writes pages and images |
| [`bridge discord`](bridge.md) | Exposes Discord's socket to every client | Symlinks, Flatpak overrides |
| [`audio`](audio.md) | Separate PipeWire sinks for the stream mix | One PipeWire config file |
| [`deck`](deck.md) | Stream Deck permissions, list and reset | No (prints the udev rule) |
| [`patch`](patch.md) | Re-applies local fixes that updates wipe | The files your patches name |

Every command accepts `--help`. Colors turn off when the output is not a terminal or when
`NO_COLOR` is set; `FORCE_COLOR=1` forces them on.
