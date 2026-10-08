"""Audio: PipeWire, its session manager, and separate sinks for the stream mix."""

from __future__ import annotations

from collections.abc import Iterator

from tuxcast import audio as virtual_sinks
from tuxcast.doctor import Finding, check, fail, info, ok, warn
from tuxcast.system import System


@check("audio", "Audio")
def audio(system: System) -> Iterator[Finding]:
    if not (system.runtime_dir / "pipewire-0").exists():
        out = system.run("pactl", "info")
        server = next((line for line in out.stdout.splitlines() if "Server Name" in line), "") if out else ""
        yield fail(
            "PipeWire is not running",
            server.strip() or "No PipeWire socket was found in your runtime directory.",
            "Switch to PipeWire (the default on every current distribution): it lets OBS capture "
            "single applications and is what `tuxcast audio` builds on.",
        )
        return
    yield ok("PipeWire is running")

    if system.has("wpctl"):
        status = system.run("wpctl", "status")
        if status and status.ok:
            yield ok("WirePlumber answers")
        else:
            yield warn("WirePlumber does not answer", fix="systemctl --user restart wireplumber")
    else:
        yield info("wpctl is not installed, WirePlumber was not checked")

    sinks = system.run("pactl", "list", "short", "sinks")
    names = {line.split("\t")[1] for line in sinks.stdout.splitlines() if "\t" in line} if sinks else set()
    ours = sorted(name for name in names if name.startswith(virtual_sinks.PREFIX))
    if ours:
        yield ok(f"{len(ours)} tuxcast sinks", ", ".join(ours))
    else:
        yield info(
            "Your stream audio is a single mix",
            "Game, music, Discord and alerts all reach OBS together, so you cannot mute the music "
            "in your VODs or lower Discord alone.",
            "tuxcast audio setup",
        )
