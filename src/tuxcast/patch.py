"""``tuxcast patch``: re-apply small edits that app updates keep wiping.

Some apps reinstall their plugins on every update, which erases local fixes (a port, a
path, a timeout). A patch file describes the edit once; ``tuxcast patch apply`` makes it,
and ``tuxcast patch install`` re-applies it whenever the watched folder changes.

Patches live in ~/.config/tuxcast/patches/*.toml:

    file = "~/.var/app/com.core447.StreamController/data/plugins/X/constants.py"
    watch = "~/.var/app/com.core447.StreamController/data/plugins"

    [[replace]]
    pattern = '^OAUTH_PORT = \\d+$'
    with = "OAUTH_PORT = 6948"
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

from tuxcast import paths


class PatchError(ValueError):
    pass


@dataclass(frozen=True)
class Replacement:
    pattern: re.Pattern[str]
    replacement: str


@dataclass(frozen=True)
class Patch:
    name: str
    file: Path
    watch: Path
    replacements: tuple[Replacement, ...]

    def patched(self, text: str) -> str:
        for item in self.replacements:
            text = item.pattern.sub(item.replacement, text)
        return text


@dataclass(frozen=True)
class Outcome:
    patch: Patch
    state: str  # "applied", "unchanged", "missing", "no-match", "error"
    error: str = ""


def folder() -> Path:
    return paths.tuxcast_config_dir() / "patches"


def expand(value: str) -> Path:
    return Path(value).expanduser()


def load(path: Path) -> Patch:
    try:
        data = tomllib.loads(path.read_text())
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise PatchError(f"{path.name}: {exc}") from exc
    if "file" not in data:
        raise PatchError(f"{path.name}: `file` is required")
    if not isinstance(data["file"], str) or not isinstance(data.get("watch", ""), str):
        raise PatchError(f"{path.name}: `file` and `watch` must be strings")
    items = data.get("replace", [])
    if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
        raise PatchError(f"{path.name}: write replacements as [[replace]] tables")
    replacements = []
    for number, item in enumerate(items, start=1):
        if not isinstance(item.get("pattern"), str) or not isinstance(item.get("with"), str):
            raise PatchError(f"{path.name}: replacement {number} needs `pattern` and `with` (strings)")
        try:
            pattern = re.compile(item["pattern"], re.MULTILINE)
        except re.error as exc:
            raise PatchError(f"{path.name}: replacement {number}: {exc}") from exc
        replacements.append(Replacement(pattern, item["with"]))
    if not replacements:
        raise PatchError(f"{path.name}: add at least one [[replace]] table")
    file = expand(data["file"])
    return Patch(path.stem, file, expand(data["watch"]) if "watch" in data else file.parent,
                 tuple(replacements))


def load_all(directory: Path | None = None) -> list[Patch]:
    directory = directory or folder()
    if not directory.is_dir():
        return []
    return [load(path) for path in sorted(directory.glob("*.toml"))]


def apply(patch: Patch, *, dry_run: bool = False) -> Outcome:
    try:
        text = patch.file.read_text(encoding="utf-8")
    except FileNotFoundError:
        return Outcome(patch, "missing")
    except (OSError, UnicodeDecodeError) as exc:
        return Outcome(patch, "error", f"cannot read {patch.file}: {exc}")
    try:
        result = patch.patched(text)
    except re.error as exc:  # a bad \1 or \g<name> in `with`
        return Outcome(patch, "error", f"invalid `with`: {exc}")
    if result == text:
        matched = any(item.pattern.search(text) for item in patch.replacements)
        return Outcome(patch, "unchanged" if matched else "no-match")
    if not dry_run:
        try:
            patch.file.write_text(result, encoding="utf-8")
        except OSError as exc:
            return Outcome(patch, "error", f"cannot write {patch.file}: {exc.strerror}")
    return Outcome(patch, "applied")


def units(patches: list[Patch], command: str) -> dict[str, str]:
    # A folder watch only sees its direct children being created, deleted or rewritten, so the
    # files themselves are watched too: systemd follows them even when they are recreated.
    watched = sorted({str(patch.watch) for patch in patches} | {str(patch.file) for patch in patches})
    path_lines = "\n".join(f"PathChanged={path}" for path in watched)
    return {
        "tuxcast-patch.service": f"""[Unit]
Description=Re-apply tuxcast patches after app updates

[Service]
Type=oneshot
ExecStart={command} patch apply --quiet
""",
        "tuxcast-patch.path": f"""[Unit]
Description=Watch app folders and re-apply tuxcast patches when they change

[Path]
{path_lines}
Unit=tuxcast-patch.service

[Install]
WantedBy=default.target
""",
    }
