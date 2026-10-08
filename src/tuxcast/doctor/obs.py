"""OBS Studio: installed, recent enough, and remote-controllable through obs-websocket."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from pathlib import Path

from tuxcast.doctor import Finding, check, fail, info, ok, warn
from tuxcast.system import System

OBS_FLATPAK_ID = "com.obsproject.Studio"
MINIMUM_MAJOR = 30


def websocket_configs(system: System) -> list[Path]:
    relative = Path("obs-studio/plugin_config/obs-websocket/config.json")
    return [
        system.home / ".config" / relative,
        system.home / ".var/app" / OBS_FLATPAK_ID / "config" / relative,
    ]


@check("obs", "OBS Studio")
def obs(system: System) -> Iterator[Finding]:
    flatpak = OBS_FLATPAK_ID in system.flatpak_apps()
    native = system.has("obs")
    if not flatpak and not native:
        yield fail("OBS Studio is not installed", fix="flatpak install flathub com.obsproject.Studio")
        return

    if native:
        out = system.run("obs", "--version")
        match = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", out.stdout if out else "")
        if match and int(match.group(1)) < MINIMUM_MAJOR:
            yield warn(f"OBS {match.group(0)} is old", f"Versions before {MINIMUM_MAJOR} lack the "
                       "PipeWire application capture and current encoders.",
                       "Install the Flathub build, which follows releases.")
        else:
            yield ok(f"OBS {match.group(0) if match else ''} (native package)".replace("  ", " "))
    if flatpak:
        yield ok("OBS (Flathub)")
    if native and flatpak:
        yield info("Two OBS installs", "Scenes and settings are not shared between them.")

    configs = [path for path in websocket_configs(system) if path.is_file()]
    if not configs:
        yield warn(
            "obs-websocket was never configured",
            "Stream Deck apps and most automation drive OBS through obs-websocket.",
            "In OBS: Tools → WebSocket Server Settings → Enable WebSocket server.",
        )
        return
    try:
        config = json.loads(configs[0].read_text())
    except (OSError, ValueError):
        yield warn("The obs-websocket configuration cannot be read", str(configs[0]))
        return
    port = config.get("server_port", 4455)
    if not config.get("server_enabled"):
        yield warn("The obs-websocket server is off",
                   fix="In OBS: Tools → WebSocket Server Settings → Enable WebSocket server.")
    elif not config.get("auth_required", True):
        yield warn(f"obs-websocket listens on port {port} without a password",
                   "Any program on your network can then start your stream or change scenes.",
                   "Tools → WebSocket Server Settings → Enable Authentication.")
    else:
        yield ok(f"obs-websocket is on (port {port}, password protected)")
