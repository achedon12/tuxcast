# Elgato actions

What [`tuxcast convert`](../commands/convert.md) turns each Elgato action into. Actions not
listed keep their key, image and title; the conversion report lists them so you can pick a
StreamController action by hand.

!!! tip "Missing one?"
    The report prints the UUID of every action it could not convert.
    [Open an issue](https://github.com/achedon12/tuxcast/issues/new?template=elgato_action.yml)
    with it: most mappings are one line of code.

The built-in Stream Deck actions (system, multi actions, navigation) are documented by Elgato
and stable. The OBS, Discord and Twitch plugin UUIDs follow those plugins' current action
names; if your export spells one differently, the report shows it and an issue gets it fixed.

## System

| Elgato action | StreamController | Notes |
| --- | --- | --- |
| `com.elgato.streamdeck.system.hotkey` | OS › Hotkey | Modifiers included, [translated for your keyboard layout](../commands/convert.md#keyboard-layouts) |
| `com.elgato.streamdeck.system.hotkeyswitch` | OS › Hotkey | First hotkey only |
| `com.elgato.streamdeck.system.website` | OS › Open in browser | `https://` added when missing |
| `com.elgato.streamdeck.system.text` | OS › Write text | *Send Enter* becomes a trailing newline |
| `com.elgato.streamdeck.system.multimedia` | Media › Play/Pause, Next, Previous; OS › Hotkey | Mute and volume become the media keys |
| `com.elgato.streamdeck.system.open` | OS › Open in browser | Only for URLs: programs need a Linux command |
| `com.elgato.streamdeck.system.delay` | OS › Delay | |

## Multi actions

| Elgato action | StreamController | Notes |
| --- | --- | --- |
| `com.elgato.streamdeck.multiactions` | Every step, in order | StreamController runs several actions per key |
| `com.elgato.streamdeck.multiactions.routine` | Every step, in order | |
| `com.elgato.streamdeck.multiactions.routine2` | Every step, in order | |
| `com.elgato.streamdeck.multiactions.delay` | OS › Delay | |

## Navigation

| Elgato action | StreamController | Notes |
| --- | --- | --- |
| `com.elgato.streamdeck.profile.openchild` | Deck › Change page | The folder becomes its own page, with a back key |
| `com.elgato.streamdeck.profile.backtoparent` | Deck › Go to previous page | |
| `com.elgato.streamdeck.page.next` | Deck › Change page | Wraps around like on the Stream Deck |
| `com.elgato.streamdeck.page.previous` | Deck › Change page | |
| `com.elgato.streamdeck.page.goto` | Deck › Change page | |
| `com.elgato.streamdeck.profile.rotate` | Deck › Change page | When the target profile is in the same backup |
| `com.elgato.streamdeck.profile.switchprofile` | Deck › Change page | When the target profile is in the same backup |

## OBS Studio

Needs StreamController's OBS plugin and [obs-websocket](../guides/obs.md#obs-websocket).

| Elgato action | StreamController | Notes |
| --- | --- | --- |
| `com.elgato.obsstudio.scene` | OBS › Switch scene | Scene name kept |
| `com.elgato.obsstudio.stream` | OBS › Toggle stream | |
| `com.elgato.obsstudio.record` | OBS › Toggle record | |
| `com.elgato.obsstudio.replaybuffer` | OBS › Toggle replay buffer | |
| `com.elgato.obsstudio.savereplay` | OBS › Save replay buffer | |
| `com.elgato.obsstudio.studiomode` | OBS › Toggle studio mode | |
| `com.elgato.obsstudio.virtualcam` | OBS › Toggle virtual camera | |
| `com.elgato.obsstudio.transition` | OBS › Trigger transition | |
| `com.elgato.obsstudio.mixeraudio` | OBS › Toggle input mute | Source name kept |

## Discord

Needs StreamController's Discord plugin, and Discord's socket visible to it:
[`tuxcast bridge discord`](../commands/bridge.md).

| Elgato action | StreamController |
| --- | --- |
| `com.elgato.discord.mute` | Discord › Mute |
| `com.elgato.discord.deafen` | Discord › Deafen |
| `com.elgato.discord.pushtotalk` | Discord › Push to talk |
| `com.elgato.discord.pushtomute` | Discord › Push to talk |
| `com.elgato.discord.voicechannel` | Discord › Change voice channel |
| `com.elgato.discord.textchannel` | Discord › Change text channel |

Channels are picked again in StreamController: Elgato stores them by internal id.

## Twitch

Needs StreamController's Twitch plugin.

| Elgato action | StreamController | Notes |
| --- | --- | --- |
| `com.elgato.twitch.clip` | Twitch › Clip | |
| `com.elgato.twitch.marker` | Twitch › Marker | |
| `com.elgato.twitch.viewers` | Twitch › Show viewers | |
| `com.elgato.twitch.ad` | Twitch › Play ad | Duration kept |
| `com.elgato.twitch.chatmessage` | Twitch › Send message | Message kept |
