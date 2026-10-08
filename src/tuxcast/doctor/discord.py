"""Discord: where its IPC socket is, and whether sandboxed clients can reach it."""

from __future__ import annotations

from collections.abc import Iterator

from tuxcast import bridge, paths
from tuxcast.doctor import Finding, check, info, ok, skip, warn
from tuxcast.system import System

# Flatpak apps that talk to Discord over IPC
CLIENTS = {paths.STREAMCONTROLLER_FLATPAK_ID: "StreamController", "com.obsproject.Studio": "OBS"}


def granted(system: System, app_id: str) -> set[str]:
    out = system.run("flatpak", "override", "--user", "--show", app_id)
    if not out or not out.ok:
        return set()
    for line in out.stdout.splitlines():
        if line.startswith("filesystems="):
            return {entry for entry in line.split("=", 1)[1].strip(";").split(";") if entry}
    return set()


@check("discord", "Discord")
def discord(system: System) -> Iterator[Finding]:
    variants = bridge.installed_variants(system)
    sockets = bridge.live_sockets(system.runtime_dir)
    if not variants and not sockets:
        yield skip("Discord is not installed")
        return

    for variant in variants:
        yield ok(variant.name)
    if sockets:
        yield ok("Discord is running", ", ".join(str(s.path) for s in sockets))
    else:
        yield info("Discord is not running", "Its socket could not be checked.")

    missing = [link for link in bridge.plan(system) if not
               (link.path.is_symlink() and link.path.readlink() == link.target)]
    clients = [app for app in CLIENTS if app in system.flatpak_apps()]
    if missing:
        names = ", ".join(sorted({link.variant.name for link in missing}))
        yield warn(
            f"{names} is invisible to most Discord clients",
            "Its socket is not where clients look, so Stream Deck mute keys and rich presence "
            "cannot find Discord.",
            "tuxcast bridge discord --install",
            action="discord",
        )
    elif any(variant is not bridge.SCANNED for variant in variants):
        yield ok("The Discord bridge is in place")

    links = bridge.plan(system)
    for app in clients:
        lacking = [g for g in bridge.grants(links) if g not in granted(system, app)
                   and g.removesuffix(":create") not in granted(system, app)]
        if lacking:
            yield warn(
                f"{CLIENTS[app]} (Flatpak) cannot see Discord's socket",
                "Missing sandbox permissions: " + ", ".join(lacking),
                " ".join(bridge.grant_command(app, links)),
                action="discord",
            )
        else:
            yield ok(f"{CLIENTS[app]} (Flatpak) can reach Discord")
