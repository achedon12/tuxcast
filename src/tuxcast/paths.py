"""Where things live on a Linux desktop: XDG directories and app data folders."""

from __future__ import annotations

import os
from pathlib import Path

STREAMCONTROLLER_FLATPAK_ID = "com.core447.StreamController"


def home() -> Path:
    return Path(os.environ.get("HOME", Path.home()))


def runtime_dir() -> Path:
    """$XDG_RUNTIME_DIR, where per-user sockets (Discord, PipeWire) live."""
    value = os.environ.get("XDG_RUNTIME_DIR")
    return Path(value) if value else Path(f"/run/user/{os.getuid()}")


def config_dir() -> Path:
    value = os.environ.get("XDG_CONFIG_HOME")
    return Path(value) if value else home() / ".config"


def tuxcast_config_dir() -> Path:
    return config_dir() / "tuxcast"


def systemd_user_dir() -> Path:
    return config_dir() / "systemd" / "user"


def streamcontroller_data_dir() -> Path:
    """StreamController's data folder, for the flatpak first, then a native install."""
    flatpak = home() / ".var" / "app" / STREAMCONTROLLER_FLATPAK_ID / "data"
    if flatpak.is_dir():
        return flatpak
    native = Path(os.environ.get("XDG_DATA_HOME", home() / ".local" / "share")) / "StreamController"
    return native if native.is_dir() else flatpak
