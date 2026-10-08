# Getting started

## Install

tuxcast needs **Python 3.11 or newer**, which every current distribution ships. Install it
for your user with [pipx](https://pipx.pypa.io/):

=== "pipx (recommended)"

    ```sh
    pipx install git+https://github.com/achedon12/tuxcast.git
    ```

=== "Installer script"

    ```sh
    curl -fsSL https://raw.githubusercontent.com/achedon12/tuxcast/main/install.sh | sh
    ```

    The script uses pipx (or uv) and refuses to run as root. [Read it first](https://github.com/achedon12/tuxcast/blob/main/install.sh).

=== "uv"

    ```sh
    uv tool install git+https://github.com/achedon12/tuxcast.git
    ```

No pipx yet? `sudo apt install pipx` (Debian, Ubuntu), `sudo dnf install pipx` (Fedora) or
`sudo pacman -S python-pipx` (Arch), then `pipx ensurepath`.

Update with `pipx upgrade tuxcast`, remove with `pipx uninstall tuxcast`.

## Check your setup

```sh
tuxcast doctor
```

Each line is a check: ✔ fine, • worth knowing, ⚠ will probably bite you, ✖ broken. Warnings
and failures come with a `fix:` line. Start from the top: display and audio problems explain
many of the ones below.

Prefer clicking? `tuxcast ui` opens the same checks in a [dashboard](commands/ui.md), with a button
for each fix tuxcast can apply.

## Fix what it found

| The doctor says | Run |
| --- | --- |
| Your stream audio is a single mix | [`tuxcast audio setup`](commands/audio.md) |
| Discord is invisible to most Discord clients | [`tuxcast bridge discord --install`](commands/bridge.md) |
| Stream Deck: no permission | [`tuxcast deck udev`](commands/deck.md) |
| Coming from Windows or macOS? | [`tuxcast convert MyProfile.streamDeckProfile`](commands/convert.md) |
| You stream over Wi-Fi | read the [network guide](guides/network.md) |

Then run `tuxcast doctor` again. When everything is green, you are ready to go live.

## Next

- New to streaming on Linux? Read [Streaming on Linux in 2026](guides/streaming-on-linux.md).
- Switching from Windows with a Stream Deck? Go to [Stream Deck on Linux](guides/stream-deck.md).
