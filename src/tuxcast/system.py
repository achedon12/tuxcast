"""A thin, fakeable view of the machine.

Every probe in tuxcast goes through a ``System``: environment variables, files under
/sys and /dev, installed commands and their output. Tests swap in a fake root folder and
canned command output, so checks are exercised without the hardware they look for.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from tuxcast import paths

Runner = Callable[[list[str], float], "Output | None"]


@dataclass(frozen=True)
class Output:
    returncode: int
    stdout: str
    stderr: str = ""

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def _run(args: list[str], timeout: float) -> Output | None:
    # probes parse the output, so it must not be translated (pactl speaks French on a French desktop)
    env = {**os.environ, "LC_ALL": "C"}
    try:
        done = subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False, env=env)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return Output(done.returncode, done.stdout, done.stderr)


@dataclass
class System:
    root: Path = Path("/")
    env: Mapping[str, str] = field(default_factory=lambda: dict(os.environ))
    runner: Runner = _run
    commands: Callable[[str], str | None] = shutil.which
    _memo: dict[tuple[str, ...], Output | None] = field(default_factory=dict, repr=False)

    def path(self, absolute: str | os.PathLike[str]) -> Path:
        """An absolute path of the real system, inside the probed root."""
        return self.root / str(absolute).lstrip("/")

    def read(self, absolute: str | os.PathLike[str]) -> str | None:
        try:
            return self.path(absolute).read_text(encoding="utf-8", errors="replace").strip()
        except OSError:
            return None

    def has(self, command: str) -> bool:
        return self.commands(command) is not None

    def run(self, *args: str, timeout: float = 3.0) -> Output | None:
        """Runs a command, or returns None when it is missing, crashes or hangs.

        Probes only read the system, so a command runs once per System and its output is reused.
        """
        if args not in self._memo:
            self._memo[args] = self.runner(list(args), timeout) if self.has(args[0]) else None
        return self._memo[args]

    @property
    def home(self) -> Path:
        return Path(self.env.get("HOME") or paths.home())

    @property
    def runtime_dir(self) -> Path:
        value = self.env.get("XDG_RUNTIME_DIR")
        return Path(value) if value else Path(f"/run/user/{os.getuid()}")

    def flatpak_apps(self) -> set[str]:
        out = self._listing("flatpak", "list", "--app", "--columns=application")
        return set(out.stdout.split()) if out and out.ok else set()

    def snaps(self) -> set[str]:
        out = self._listing("snap", "list")
        if not out or not out.ok:
            return set()
        return {line.split()[0] for line in out.stdout.splitlines()[1:] if line.strip()}

    def _listing(self, *args: str) -> Output | None:
        """Installed packages: slow to list (snap takes seconds), so shared between probes for a while."""
        key = (str(self.root), self.runner, args)
        cached = _LISTINGS.get(key)
        if cached and time.monotonic() - cached[0] < LISTING_TTL:
            return cached[1]
        out = self.run(*args, timeout=20.0)
        _LISTINGS[key] = (time.monotonic(), out)
        return out


LISTING_TTL = 30.0
_LISTINGS: dict[tuple, tuple[float, Output | None]] = {}
