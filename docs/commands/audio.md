# tuxcast audio

Creates separate PipeWire sinks for the parts of your stream mix, so OBS can capture each
one alone.

```sh
tuxcast audio setup --restart
tuxcast audio route spotify music
tuxcast audio route discord voice
```

Then, in OBS, add one **Audio Output Capture (PulseAudio)** per sink and pick
*Monitor of Stream · Music* and so on. Each becomes its own fader, filter chain and track.

## Why

By default, everything you hear reaches OBS as one desktop audio source. You cannot:

- keep the music out of your VODs (Twitch's *Soundtrack* trick, or a separate track in OBS),
- lower Discord without lowering the game,
- put a compressor on voices only.

With one sink per part, you can. You still hear everything on your headset: each sink is a
loopback to your default output.

## Commands

| Command | |
| --- | --- |
| `tuxcast audio setup` | Declare the sinks (default `game,music,voice,alerts`) |
| `tuxcast audio setup --sinks game,music,browser` | Choose your own |
| `tuxcast audio status` | Sinks, and which app plays where right now |
| `tuxcast audio route APP SINK` | Move an app that is playing to a sink. PipeWire remembers it |
| `tuxcast audio remove` | Remove the sinks |

`setup` and `remove` take `--restart` to restart PipeWire right away (sound cuts for a
second); otherwise the change applies at your next login.

## How it works

`setup` writes one file, `~/.config/pipewire/pipewire.conf.d/tuxcast-sinks.conf`, declaring a
`libpipewire-module-loopback` per sink. No service runs; PipeWire creates the sinks when it
starts. `remove` deletes that file. See the [audio routing guide](../guides/audio.md) for an
OBS setup that uses them.
