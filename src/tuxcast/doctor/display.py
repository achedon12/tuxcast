"""Display server: what screen capture and global hotkeys can rely on."""

from __future__ import annotations

from collections.abc import Iterator

from tuxcast.doctor import Finding, check, info, ok, warn
from tuxcast.system import System

PORTAL_BINARIES = ("/usr/libexec/xdg-desktop-portal", "/usr/lib/xdg-desktop-portal")


@check("display", "Display server")
def display(system: System) -> Iterator[Finding]:
    session = system.env.get("XDG_SESSION_TYPE", "").lower()
    desktop = system.env.get("XDG_CURRENT_DESKTOP", "unknown desktop")

    if session == "wayland":
        yield ok(f"Wayland session ({desktop})")
        if any(system.path(binary).exists() for binary in PORTAL_BINARIES):
            yield ok("xdg-desktop-portal is installed", "OBS captures screens through the PipeWire portal.")
        else:
            yield warn(
                "xdg-desktop-portal is missing",
                "On Wayland, OBS can only capture screens and windows through the portal.",
                "Install xdg-desktop-portal and the backend of your desktop "
                "(xdg-desktop-portal-gnome, -kde, -wlr or -hyprland).",
            )
        yield info(
            "Global hotkeys are limited on Wayland",
            "Apps cannot read keys pressed in other windows. Drive OBS from a Stream Deck "
            "or obs-websocket rather than OBS hotkeys.",
        )
    elif session == "x11":
        yield ok(f"X11 session ({desktop})", "Screen capture and global hotkeys work without a portal.")
    else:
        yield warn(
            "Unknown session type",
            "XDG_SESSION_TYPE is not set, so tuxcast cannot tell Wayland from X11.",
            "Run tuxcast from a terminal inside your graphical session, not over SSH.",
        )
