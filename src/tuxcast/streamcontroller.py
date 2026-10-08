"""Reading StreamController's pages, to show a deck as it is configured."""

from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

MAX_IMAGE = 2 * 1024 * 1024
# Only real images are shown: the type comes from the file's first bytes, not its name
MAGIC = [(b"\x89PNG\r\n\x1a\n", "image/png"), (b"\xff\xd8\xff", "image/jpeg"), (b"GIF8", "image/gif")]
POSITION = re.compile(r"^(\d+)x(\d+)$")


@dataclass
class PageKey:
    column: int
    row: int
    label: str = ""
    image: str = ""  # data: URL


@dataclass
class Page:
    name: str
    keys: list[PageKey] = field(default_factory=list)


def image_url(path: str) -> str:
    """A data: URL for an image file, or "" when it is missing, too big or not an image."""
    try:
        file = Path(path)
        if not file.is_file() or file.stat().st_size > MAX_IMAGE:
            return ""
        data = file.read_bytes()
    except OSError:
        return ""
    kind = next((k for magic, k in MAGIC if data.startswith(magic)), None)
    if kind is None and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        kind = "image/webp"
    return f"data:{kind};base64,{base64.b64encode(data).decode()}" if kind else ""


def pages(folder: Path, limit: int = 40) -> list[Page]:
    """StreamController's pages, sorted by name."""
    found = []
    for file in sorted(folder.glob("*.json"))[:limit]:
        try:
            data = json.loads(file.read_text())
        except (OSError, ValueError):
            continue
        keys = data.get("keys") if isinstance(data, dict) else None
        page = Page(file.stem)
        for position, key in (keys if isinstance(keys, dict) else {}).items():
            match = POSITION.match(str(position))
            state = ((key or {}).get("states") or {}).get("0") if isinstance(key, dict) else None
            if not match or not isinstance(state, dict):
                continue
            labels = state.get("labels") if isinstance(state.get("labels"), dict) else {}
            label = next((str(v.get("text", "")) for v in (labels.get(p) for p in ("center", "bottom", "top"))
                          if isinstance(v, dict) and v.get("text")), "")
            media = state.get("media") if isinstance(state.get("media"), dict) else {}
            page.keys.append(PageKey(int(match.group(1)), int(match.group(2)), label,
                                     image_url(str(media.get("path", ""))) if media.get("path") else ""))
        found.append(page)
    return found
