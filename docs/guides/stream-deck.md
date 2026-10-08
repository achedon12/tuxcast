# Stream Deck on Linux

Elgato's Stream Deck software only exists for Windows and macOS, and does not work under
Wine (it needs Windows' USB HID APIs). The deck itself works perfectly on Linux with
**[StreamController](https://streamcontroller.core447.com/)**.

## 1. Install StreamController

```sh
flatpak install flathub com.core447.StreamController
```

Then install the plugins you need from its store: OBS, Media (Spotify, any MPRIS player),
Discord, Twitch, OS (hotkeys, commands, websites).

## 2. Give your user access to the deck

If StreamController shows no deck, your user is not allowed to open it:

```sh
tuxcast deck list   # "no permission"?
tuxcast deck udev | sudo tee /etc/udev/rules.d/70-streamdeck.rules
sudo udevadm control --reload && sudo udevadm trigger
```

→ [`tuxcast deck`](../commands/deck.md)

## 3. Bring your profiles over

Export your profiles on Windows or macOS (**Preferences → Profiles → ⋯ → Export**), copy
them over, and convert:

```sh
tuxcast convert Streaming.streamDeckProfile
```

Images, titles, folders and most actions come along. The report lists the keys to finish by
hand: usually programs opened by a Windows path and soundboard sounds.

→ [`tuxcast convert`](../commands/convert.md)

## 4. Make each plugin work

| Plugin | Needs |
| --- | --- |
| OBS | obs-websocket on, with its password entered in the plugin ([OBS guide](obs.md#obs-websocket)) |
| Media | A player that implements MPRIS. Spotify: the Flathub build, not the snap ([why](sandboxes.md#spotify)) |
| Discord | Discord's socket visible from the Flatpak: `tuxcast bridge discord --install` ([why](sandboxes.md#discord)) |
| Twitch | A one-time OAuth login. The plugin listens on port 3000 for it, which clashes with local web dev servers ([fix](#plugin-fixes-that-survive-updates)) |

## Plugin fixes that survive updates

StreamController reinstalls plugins from scratch when they update, which wipes any change
you made to their files. Describe the change as a [tuxcast patch](../commands/patch.md) and it
is re-applied automatically:

```sh
mkdir -p ~/.config/tuxcast/patches
curl -fsSL https://raw.githubusercontent.com/achedon12/tuxcast/main/contrib/patches/twitch-oauth-port.toml \
  -o ~/.config/tuxcast/patches/twitch-oauth-port.toml
tuxcast patch install
```

## When the deck freezes

After StreamController crashes, the deck can stay dark and the logs show
`Failed to read feature report (-1)`. Instead of unplugging it:

```sh
tuxcast deck reset
```
