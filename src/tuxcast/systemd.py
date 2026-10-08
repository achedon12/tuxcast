"""Installing user services, so fixes survive reboots without root."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from tuxcast import paths


class SystemdError(RuntimeError):
    pass


def tuxcast_command() -> str:
    """How a unit should call tuxcast: the installed script, else this interpreter."""
    script = shutil.which("tuxcast")
    return script if script else f"{sys.executable} -m tuxcast"


def install(units: dict[str, str], *, enable: list[str], start: list[str] | None = None) -> list[Path]:
    """Writes units to ~/.config/systemd/user, enables `enable` and starts `start` now.

    Only units with an [Install] section can be enabled; the others are started by them.
    """
    folder = paths.systemd_user_dir()
    folder.mkdir(parents=True, exist_ok=True)
    written = []
    for name, content in units.items():
        path = folder / name
        path.write_text(content)
        written.append(path)
    systemctl("daemon-reload")
    if enable:
        systemctl("enable", *enable)
    if start:
        systemctl("start", *start)
    return written


def uninstall(names: list[str]) -> list[Path]:
    folder = paths.systemd_user_dir()
    present = [name for name in names if (folder / name).exists()]
    if present:
        systemctl("disable", "--now", *present, check=False)
    removed = []
    for name in present:
        (folder / name).unlink()
        removed.append(folder / name)
    systemctl("daemon-reload", check=False)
    return removed


def systemctl(*args: str, check: bool = True) -> None:
    try:
        done = subprocess.run(["systemctl", "--user", *args], capture_output=True, text=True, check=False)
    except OSError as exc:
        if check:
            raise SystemdError(f"cannot run systemctl: {exc.strerror}") from exc
        return
    if check and done.returncode != 0:
        message = done.stderr.strip() or f"exit status {done.returncode}"
        raise SystemdError(f"systemctl --user {' '.join(args)} failed: {message}")
