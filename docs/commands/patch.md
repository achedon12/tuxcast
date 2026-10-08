# tuxcast patch

Re-applies small edits that app updates keep wiping.

Some apps reinstall their plugins from scratch at every update. If you changed a line (a
port, a path, a timeout), the update silently reverts it, and the bug you fixed comes back
the next time you go live. A patch file describes the edit once; tuxcast re-applies it.

```sh
tuxcast patch list       # your patches and whether they are applied
tuxcast patch apply      # apply them now (--dry-run to preview)
tuxcast patch install    # re-apply whenever the watched folders change
tuxcast patch uninstall  # stop watching
```

## Writing a patch

Patches are TOML files in `~/.config/tuxcast/patches/`. The file name is the patch name.

```toml title="~/.config/tuxcast/patches/twitch-oauth-port.toml"
# StreamController's Twitch plugin listens on port 3000 for its OAuth login, which clashes
# with every local web dev server. Move it to 6948.
file = "~/.var/app/com.core447.StreamController/data/plugins/com_imdevinc_StreamControllerTwitchPlugin/constants.py"

# Updates delete and recreate the plugin folder, so watch its parent.
watch = "~/.var/app/com.core447.StreamController/data/plugins"

[[replace]]
pattern = '^OAUTH_PORT = \d+$'
with = "OAUTH_PORT = 6948"

[[replace]]
pattern = 'localhost:\d+/auth'
with = "localhost:6948/auth"
```

| Key | |
| --- | --- |
| `file` | The file to edit. `~` is expanded |
| `watch` | A folder watched in addition to the file: when an update deletes and recreates it, the patch is re-applied. Default: the file's folder |
| `[[replace]]` | One or more. `pattern` is a Python regular expression (multi-line mode: `^` and `$` match at each line), `with` its replacement (`\1` refers to groups) |

Write replacements so that applying twice changes nothing. `tuxcast patch apply` warns when no
pattern matches any more, which usually means the app changed that file and the patch needs
updating.

This example ships in the repository under
[`contrib/patches/`](https://github.com/achedon12/tuxcast/tree/main/contrib/patches).

## How it works

`install` writes two user units: `tuxcast-patch.path` watches every patched file and `watch` folder and starts
`tuxcast-patch.service`, which runs `tuxcast patch apply --quiet`. No root, no polling.
