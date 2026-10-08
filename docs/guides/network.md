# Network

## Use a cable

Wi-Fi loses packets in bursts: a microwave, a neighbour's network, someone walking between you
and the router. Your speed test averages that out and looks great; a live stream cannot, and
Twitch flags the connection as **unstable**, viewers see buffering, and your encoder drops frames.

An Ethernet cable fixes it. If the router is far away:

- a **powerline adapter** (network over the electric wiring) is usually far more stable than
  Wi-Fi,
- otherwise a **mesh node with a wired backhaul** close to your PC.

`tuxcast doctor` warns when your default route is Wi-Fi, and tells you when a cable is plugged
in but not used.

## Pick a bitrate your upload can hold

Keep the stream under about **75% of your measured upload** to leave room for everything else
(Discord, game traffic, the browser).

| Upload | Max stream bitrate | Typical setting |
| --- | --- | --- |
| 5 Mb/s | 3750 kbps | 720p30 at 3000 kbps |
| 8 Mb/s | 6000 kbps | 1080p60 at 6000 kbps |
| 15 Mb/s and more | 6000 kbps per Twitch stream | Multistream at full quality |

Multistreaming adds the bitrates: Twitch and YouTube at 6000 kbps each need about 16 Mb/s of
upload.

## Test before going live

- [Twitch Inspector](https://inspector.twitch.tv/) runs a bandwidth test and analyses past
  streams (bitrate drops, reconnects).
- Append `?bandwidthtest=true` to your Twitch stream key: Twitch receives the stream, measures
  it in the Inspector, and does not broadcast it.
