# Discord and Spotify in sandboxes

Flatpak and snap run apps in sandboxes. Each app sees only what it was granted, which is
good for security and confusing when two apps need to talk: your Stream Deck app (a Flatpak)
has to reach Discord and Spotify to control them.

`tuxcast doctor` checks both. Here is what it looks for and why.

## Discord

Discord accepts commands (mute, deafen, change channel) and rich presence through an **IPC
socket** named `discord-ipc-0`. Where that socket lives depends on how Discord is installed,
and clients only look in one or two places:

| Discord installed as | Socket | Seen by a Flatpak client |
| --- | --- | --- |
| Flathub | `$XDG_RUNTIME_DIR/app/com.discordapp.Discord/` | With `--filesystem=xdg-run/app/com.discordapp.Discord:create` |
| snap | `$XDG_RUNTIME_DIR/snap.discord/` | Never looked for |
| Vesktop | `$XDG_RUNTIME_DIR/.flatpak/dev.vencord.Vesktop/xdg-run/` | Never looked for |
| native | `$XDG_RUNTIME_DIR/` | With `--filesystem=xdg-run/discord-ipc-0` |

The symptom: Discord keys do nothing, rich presence never shows, no error anywhere.

**Fix:** `tuxcast bridge discord --install`. It links the socket where clients look, grants the
Flatpak permissions, and recreates the links at each login. [Details](../commands/bridge.md).

By hand, for the snap and StreamController:

```sh
mkdir -p "$XDG_RUNTIME_DIR/app/com.discordapp.Discord"
ln -sfn "$XDG_RUNTIME_DIR/snap.discord/discord-ipc-0" "$XDG_RUNTIME_DIR/app/com.discordapp.Discord/discord-ipc-0"
flatpak override --user --filesystem=xdg-run/app/com.discordapp.Discord:create \
  --filesystem=xdg-run/snap.discord com.core447.StreamController
```

(`$XDG_RUNTIME_DIR` is emptied at logout, hence the login service.)

## Spotify

Media keys and Stream Deck media buttons control players through **MPRIS**, a D-Bus interface.

**Use the Flathub build of Spotify**, not the snap:

- The snap answers MPRIS commands with *success* but ignores them: play/pause does nothing.
- AppArmor stops Flatpak apps (such as StreamController) from calling into the snap at all.
- With both installed and running, they claim the same MPRIS name, and commands reach
  whichever started first.

```sh
snap remove spotify
flatpak install flathub com.spotify.Client
```

Your playlists live in your account, so nothing is lost.

## Granting permissions by hand

`flatpak override --user` changes an app's sandbox for your user; the app must be restarted.
[Flatseal](https://flathub.org/apps/com.github.tchx84.Flatseal) does the same with a GUI.

```sh
flatpak override --user --show com.core447.StreamController   # current grants
flatpak override --user --reset com.core447.StreamController  # back to defaults
```
