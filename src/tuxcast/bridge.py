"""``tuxcast bridge discord``: lets sandboxed apps reach Discord's IPC socket.

Discord publishes its IPC socket in a different place for each way of installing it,
and most clients only look where the official Flatpak puts it. Rich presence, Stream Deck
mute keys and overlays then fail with Discord installed as a snap, as Vesktop, or when the
client itself is a Flatpak.

The bridge links every Discord socket into the folder clients scan,
``$XDG_RUNTIME_DIR/app/com.discordapp.Discord``, and grants Flatpak clients access to both
that folder and the real socket's. The links are lazy: they may point at a socket Discord
has not created yet, and start working as soon as it does.
"""

from __future__ import annotations

import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path

from tuxcast import paths
from tuxcast.system import System

DISCORD_FLATPAK_ID = "com.discordapp.Discord"
SOCKETS = 10  # clients try discord-ipc-0 to discord-ipc-9
# The official Flatpak owns the low indexes of the scanned folder (and the StreamController
# Discord plugin relays to index 1), so bridged sockets go above when it is installed too.
FIRST_FREE_INDEX = 5


@dataclass(frozen=True)
class Variant:
    key: str
    name: str
    folder: str  # relative to $XDG_RUNTIME_DIR, where this variant creates its sockets
    grant: str  # the Flatpak --filesystem grant that makes that folder visible
    snap: str = ""
    flatpak: str = ""


VARIANTS = [
    Variant("flatpak", "Discord (Flathub)", f"app/{DISCORD_FLATPAK_ID}",
            f"xdg-run/app/{DISCORD_FLATPAK_ID}:create", flatpak=DISCORD_FLATPAK_ID),
    Variant("snap", "Discord (snap)", "snap.discord", "xdg-run/snap.discord", snap="discord"),
    Variant("vesktop", "Vesktop (Flathub)", ".flatpak/dev.vencord.Vesktop/xdg-run",
            "xdg-run/.flatpak/dev.vencord.Vesktop", flatpak="dev.vencord.Vesktop"),
    Variant("native", "Discord (native package)", "", "xdg-run/discord-ipc-0"),
]
SCANNED = VARIANTS[0]


@dataclass(frozen=True)
class Socket:
    variant: Variant
    path: Path
    index: int


@dataclass(frozen=True)
class Link:
    path: Path
    target: Path
    variant: Variant


def is_socket(path: Path) -> bool:
    try:
        return stat.S_ISSOCK(path.lstat().st_mode)
    except OSError:
        return False


def live_sockets(runtime: Path) -> list[Socket]:
    """The sockets Discord actually created (links to them are not counted)."""
    found = []
    for variant in VARIANTS:
        folder = runtime / variant.folder
        for index in range(SOCKETS):
            path = folder / f"discord-ipc-{index}"
            if is_socket(path):
                found.append(Socket(variant, path, index))
    return found


def installed_variants(system: System) -> list[Variant]:
    flatpaks, snaps = system.flatpak_apps(), system.snaps()
    found = []
    for variant in VARIANTS:
        packaged = (variant.flatpak and variant.flatpak in flatpaks) or (variant.snap and variant.snap in snaps)
        if packaged or (variant.key == "native" and native_discord(system)):
            found.append(variant)
    return found


def native_discord(system: System) -> bool:
    """A Discord from a .deb, .rpm or tarball (snap and Flatpak put launchers on PATH too)."""
    for name in ("discord", "Discord"):
        location = system.commands(name)
        if location and not location.startswith("/snap/") and "/flatpak/exports/" not in location:
            return True
    return False


def plan(system: System) -> list[Link]:
    """The links to create so the scanned folder exposes every Discord install."""
    runtime = system.runtime_dir
    variants = installed_variants(system)
    sockets = live_sockets(runtime)
    for socket in sockets:  # a running Discord counts even if we could not tell how it was installed
        if socket.variant not in variants:
            variants.append(socket.variant)

    next_index = FIRST_FREE_INDEX if SCANNED in variants else 0
    links = []
    for variant in variants:
        if variant is SCANNED:
            continue  # already where clients look
        indexes = sorted({s.index for s in sockets if s.variant is variant}) or [0]
        for index in indexes:
            target = runtime / variant.folder / f"discord-ipc-{index}"
            links.append(Link(runtime / SCANNED.folder / f"discord-ipc-{next_index}", target, variant))
            next_index += 1
            if next_index >= SOCKETS:
                return links
    return links


def apply(links: list[Link]) -> list[Link]:
    """Creates the links, replacing stale ones, and returns those that changed."""
    changed = []
    for link in links:
        if link.path.is_symlink() and link.path.readlink() == link.target:
            continue
        if link.path.exists() and not link.path.is_symlink():
            continue  # a real socket lives there: never replace Discord's own
        link.path.parent.mkdir(parents=True, exist_ok=True)
        if link.path.is_symlink():
            link.path.unlink()
        link.path.symlink_to(link.target)
        changed.append(link)
    return changed


def grants(links: list[Link]) -> list[str]:
    """The Flatpak filesystem grants a sandboxed client needs to follow the links."""
    needed = [SCANNED.grant]
    for link in links:
        if link.variant.grant not in needed:
            needed.append(link.variant.grant)
    return needed


def grant_command(app_id: str, links: list[Link]) -> list[str]:
    return ["flatpak", "override", "--user", *(f"--filesystem={g}" for g in grants(links)), app_id]


def default_clients(system: System) -> list[str]:
    """The Flatpak clients to grant access to when none is named."""
    return [app for app in (paths.STREAMCONTROLLER_FLATPAK_ID,) if app in system.flatpak_apps()]


def grant(app_id: str, links: list[Link]) -> str:
    """Runs the Flatpak override for a client; returns an error message, or "" on success."""
    try:
        done = subprocess.run(grant_command(app_id, links), capture_output=True, text=True, check=False)
    except OSError as exc:
        return f"cannot run flatpak: {exc.strerror}"
    return "" if done.returncode == 0 else (done.stderr.strip() or f"flatpak exited with {done.returncode}")


UNIT = "tuxcast-discord-bridge.service"


def unit(command: str) -> str:
    return f"""[Unit]
Description=Expose Discord's IPC socket to every client (tuxcast bridge discord)
After=graphical-session.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart={command} bridge discord --quiet --no-grant

[Install]
WantedBy=default.target
"""
