from __future__ import annotations

import base64
import json
import shutil
import socket
import tempfile
import uuid
import zipfile
from collections.abc import Callable
from pathlib import Path

import pytest

from tuxcast.system import Output, System

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")


@pytest.fixture
def runtime():
    """A short $XDG_RUNTIME_DIR: socket paths must fit in 108 bytes, tmp_path is too deep."""
    path = Path(tempfile.mkdtemp(prefix="tuxcast-"))
    yield path
    shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def fake_system(tmp_path: Path, runtime: Path) -> Callable[..., System]:
    """A System rooted in tmp_path, with canned commands and their output."""

    def make(*, env: dict[str, str] | None = None, commands: dict[str, str] | None = None,
             outputs: dict[tuple[str, ...], str] | None = None, flatpaks: tuple[str, ...] = (),
             snaps: tuple[str, ...] = ()) -> System:
        root = tmp_path / "root"
        root.mkdir(exist_ok=True)
        home = tmp_path / "home"
        home.mkdir(exist_ok=True)
        installed = dict(commands or {})
        canned = dict(outputs or {})
        if flatpaks:
            installed.setdefault("flatpak", "/usr/bin/flatpak")
            canned[("flatpak", "list", "--app", "--columns=application")] = "\n".join(flatpaks)
        if snaps:
            installed.setdefault("snap", "/usr/bin/snap")
            canned[("snap", "list")] = "Name Version\n" + "\n".join(f"{s} 1.0" for s in snaps)

        def runner(args: list[str], _timeout: float) -> Output | None:
            text = canned.get(tuple(args))
            return Output(0, text) if text is not None else Output(1, "")

        return System(
            root=root,
            env={"HOME": str(home), "XDG_RUNTIME_DIR": str(runtime), **(env or {})},
            runner=runner,
            commands=installed.get,
        )

    return make


def write(root: Path, path: str, text: str = "") -> Path:
    target = root / path.lstrip("/")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text)
    return target


def unix_socket(path: Path) -> socket.socket:
    path.parent.mkdir(parents=True, exist_ok=True)
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(str(path))
    return server


# --- Elgato profiles ---------------------------------------------------------------------------

def page_folder(page_id: uuid.UUID) -> str:
    """How Stream Deck 6 names page folders: the UUID in base32hex."""
    return base64.b32hexencode(page_id.bytes).decode().rstrip("=")


def key(uuid_: str, title: str = "", settings: dict | None = None, image: str | None = None,
        **extra: object) -> dict:
    state: dict = {"Title": title, "ShowTitle": bool(title), "TitleAlignment": "bottom", "TitleColor": "#ff0000"}
    if image:
        state["Image"] = image
    return {"UUID": uuid_, "Name": uuid_.rsplit(".", 1)[-1], "Settings": settings or {}, "State": 0,
            "States": [state], **extra}


def make_v2_profile(path: Path, name: str = "Gaming", pages: list[dict] | None = None,
                    folders: list[tuple[uuid.UUID, dict]] | None = None) -> dict[str, uuid.UUID]:
    """Writes a Stream Deck 6 export. pages: one {"col,row": action} dict per page."""
    profile = uuid.uuid4()
    root = f"{str(profile).upper()}.sdProfile"
    ids = [uuid.uuid4() for _ in pages or []]
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(f"{root}/manifest.json", json.dumps({
            "Name": name, "Version": "2.0", "Device": {"Model": "20GBA9901", "UUID": ""},
            "Pages": {"Current": str(ids[0]), "Default": str(ids[0]), "Pages": [str(i) for i in ids]},
        }))
        for page_id, actions in [*zip(ids, pages or [], strict=True), *(folders or [])]:
            folder = f"{root}/Profiles/{page_folder(page_id)}"
            archive.writestr(f"{folder}/manifest.json", json.dumps(
                {"Controllers": [{"Type": "Keypad", "Actions": actions}], "Name": ""}))
            for action in actions.values():
                states = action.get("States")
                image = states[0].get("Image") if isinstance(states, list) and states else None
                if isinstance(image, str):
                    archive.writestr(f"{folder}/{image}", PNG)
    return {"profile": profile, **{f"page{n}": i for n, i in enumerate(ids, start=1)}}
