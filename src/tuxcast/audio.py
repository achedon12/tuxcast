"""``tuxcast audio``: separate PipeWire sinks, so each part of the stream mix is its own source.

Each sink is a loopback: apps play into it, you keep hearing it on your default output, and
OBS captures it alone. The sinks are declared in a PipeWire drop-in file, so they come back
at every login without any service running.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from tuxcast import paths
from tuxcast.system import System

PREFIX = "tuxcast_"
DROP_IN = "tuxcast-sinks.conf"
RESTART = ["systemctl", "--user", "restart", "pipewire", "pipewire-pulse", "wireplumber"]
DEFAULT_SINKS = ["game", "music", "voice", "alerts"]
DESCRIPTIONS = {
    "game": "Game",
    "music": "Music",
    "voice": "Voice chat",
    "alerts": "Alerts",
    "browser": "Browser",
}
NAME = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")


@dataclass(frozen=True)
class Sink:
    key: str

    @property
    def node(self) -> str:
        return PREFIX + self.key

    @property
    def description(self) -> str:
        return "Stream · " + DESCRIPTIONS.get(self.key, self.key.replace("_", " ").replace("-", " ").title())


def drop_in_path() -> Path:
    return paths.config_dir() / "pipewire" / "pipewire.conf.d" / DROP_IN


def parse_sinks(value: str) -> list[Sink]:
    keys = [key.strip().lower() for key in value.split(",") if key.strip()]
    for key in keys:
        if not NAME.match(key):
            raise ValueError(f"invalid sink name {key!r}: use lowercase letters, digits, - and _")
    if len(set(keys)) != len(keys):
        raise ValueError("sink names must be unique")
    return [Sink(key) for key in keys]


def render(sinks: list[Sink]) -> str:
    modules = []
    for sink in sinks:
        modules.append(f"""    {{ name = libpipewire-module-loopback
        args = {{
            node.description = "{sink.description}"
            capture.props = {{
                node.name      = "{sink.node}"
                media.class    = "Audio/Sink"
                audio.position = [ FL FR ]
            }}
            playback.props = {{
                node.name      = "{sink.node}.output"
                node.passive   = true
                audio.position = [ FL FR ]
            }}
        }}
    }}""")
    return (
        "# Written by `tuxcast audio setup`. Remove with `tuxcast audio remove`.\n"
        "# Each loopback is a sink apps can play into: you still hear it on your default output,\n"
        "# and OBS can capture it on its own (Audio Output Capture → the sink's monitor).\n"
        "context.modules = [\n" + "\n".join(modules) + "\n]\n"
    )


def configured(path: Path | None = None) -> list[str]:
    """The sink names the drop-in declares, if it exists."""
    try:
        return configured_from((path or drop_in_path()).read_text())
    except OSError:
        return []


def configured_from(text: str) -> list[str]:
    return re.findall(rf'node.name\s*=\s*"({PREFIX}[^".]+)"', text)


@dataclass(frozen=True)
class Stream:
    index: str
    application: str
    sink: str


def playing(system: System) -> list[Stream]:
    """The apps currently playing sound, from `pactl list sink-inputs`."""
    out = system.run("pactl", "list", "sink-inputs")
    if not out or not out.ok:
        return []
    streams = []
    for block in out.stdout.split("Sink Input #")[1:]:
        index = block.split("\n", 1)[0].strip()
        sink = re.search(r"^\s*Sink:\s*(\S+)", block, re.MULTILINE)
        name = re.search(r'application\.name = "([^"]*)"', block)
        binary = re.search(r'application\.process\.binary = "([^"]*)"', block)
        label = (name.group(1) if name else "") or (binary.group(1) if binary else "unknown")
        streams.append(Stream(index, label, sink.group(1) if sink else ""))
    return streams
