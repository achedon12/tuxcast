#!/bin/sh
# Installs tuxcast for the current user:
#   curl -fsSL https://raw.githubusercontent.com/achedon12/tuxcast/main/install.sh | sh
# It uses pipx when available (recommended), and never needs root.
set -eu

SOURCE="${TUXCAST_SOURCE:-tuxcast}"   # TUXCAST_SOURCE=git+https://github.com/achedon12/tuxcast.git for main

say() { printf '\033[1;36m==>\033[0m %s\n' "$*"; }
die() { printf '\033[1;31merror:\033[0m %s\n' "$*" >&2; exit 1; }

[ "$(id -u)" -ne 0 ] || die "run this as your user, not root: tuxcast configures your session."
command -v python3 >/dev/null 2>&1 || die "python3 is required (3.11 or newer)."
python3 -c 'import sys; sys.exit(sys.version_info < (3, 11))' \
    || die "python3 is $(python3 -V 2>&1 | cut -d' ' -f2), tuxcast needs 3.11 or newer."

if command -v pipx >/dev/null 2>&1; then
    say "Installing tuxcast with pipx"
    pipx install --force "$SOURCE"
elif command -v uv >/dev/null 2>&1; then
    say "Installing tuxcast with uv"
    uv tool install --force "$SOURCE"
else
    die "install pipx first (sudo apt install pipx, sudo dnf install pipx, or sudo pacman -S python-pipx), then run this again."
fi

say "Done. Start with:  tuxcast doctor"
case ":$PATH:" in
    *":$HOME/.local/bin:"*) ;;
    *) say "Add ~/.local/bin to your PATH if the tuxcast command is not found (pipx ensurepath)." ;;
esac
