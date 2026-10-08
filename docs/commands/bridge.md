# tuxcast bridge discord

Lets sandboxed apps reach Discord's IPC socket, the channel Stream Deck mute keys, rich
presence and overlays use to talk to Discord.

```sh
tuxcast bridge discord --install
```

```text
  + /run/user/1000/app/com.discordapp.Discord/discord-ipc-0 → /run/user/1000/snap.discord/discord-ipc-0  (Discord (snap))
✔ com.core447.StreamController may now reach Discord (restart it to apply)
✔ Installed tuxcast-discord-bridge.service: the bridge comes back at every login
```

## The problem

Discord publishes its socket in a different place for each way of installing it:

| Discord installed as | Socket |
| --- | --- |
| Flathub | `$XDG_RUNTIME_DIR/app/com.discordapp.Discord/discord-ipc-0` |
| snap | `$XDG_RUNTIME_DIR/snap.discord/discord-ipc-0` |
| Vesktop (Flathub) | `$XDG_RUNTIME_DIR/.flatpak/dev.vencord.Vesktop/xdg-run/discord-ipc-0` |
| .deb, .rpm, tarball | `$XDG_RUNTIME_DIR/discord-ipc-0` |

Clients look in one or two of them. A Flatpak client, such as StreamController, sees none
of them unless its sandbox is opened to that folder. The result: the Discord keys of your
Stream Deck do nothing, and no error says why.

## What the bridge does

1. Links every Discord socket into `$XDG_RUNTIME_DIR/app/com.discordapp.Discord/`, the folder
   Flatpak-aware clients scan. Links are lazy: they may point at a socket Discord has not
   created yet and start working when it does.
2. Grants Flatpak clients access to that folder and to the real socket's folder with
   `flatpak override --user`.
3. With `--install`, adds a user service that recreates the links at every login, since
   `$XDG_RUNTIME_DIR` is emptied at logout.

It never replaces a real socket. When the official Flatpak is installed too, bridged
sockets take indexes 5 and above, so Discord's own keep priority.

## Options

| Option | |
| --- | --- |
| `--install` | Also install `tuxcast-discord-bridge.service` (user service) |
| `--uninstall` | Remove that service |
| `--app APP_ID` | Flatpak client to grant access to (repeatable). Default: StreamController, if installed |
| `--no-grant` | Print the `flatpak override` command instead of running it |
| `-n`, `--dry-run` | Show the links, change nothing |
| `-q`, `--quiet` | Only print errors |

Restart the client after the first run: Flatpak applies permissions when an app starts.
