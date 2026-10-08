"""Reading Elgato Stream Deck profiles.

Accepted inputs: an exported ``.streamDeckProfile`` (a zip), a ``.streamDeckProfilesBackup``
(a zip of several profiles), or a ``.sdProfile`` folder copied from Windows
(``%appdata%/Elgato/StreamDeck/ProfilesV2``) or macOS.

Two layouts exist. Version 1 profiles keep their keys in ``X.sdProfile/manifest.json`` and
folders in nested ``Profiles/Y.sdProfile``. Version 2 profiles (Stream Deck 6 and later) keep
one folder per page in ``X.sdProfile/Profiles/<page id>``, each with a ``Keypad`` controller,
and folders are extra pages that no page list mentions.
"""

from __future__ import annotations

import base64
import json
import uuid
import zipfile
import zlib
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp")


class ProfileError(ValueError):
    pass


# --- sources: a zip or a folder, read the same way -------------------------------------------

class Source:
    def names(self) -> list[str]:
        raise NotImplementedError

    def read(self, name: str) -> bytes:
        raise NotImplementedError

    def json(self, name: str) -> dict:
        try:
            data = json.loads(self.read(name).decode("utf-8-sig"))
        except (KeyError, OSError, ValueError) as exc:
            raise ProfileError(f"{name} is not a readable manifest: {exc}") from exc
        if not isinstance(data, dict):
            raise ProfileError(f"{name} is not a Stream Deck manifest (expected an object)")
        return data


class ZipSource(Source):
    def __init__(self, path: Path):
        try:
            self.archive = zipfile.ZipFile(path)
        except (OSError, zipfile.BadZipFile) as exc:
            raise ProfileError(f"{path.name} is not a Stream Deck profile export (not a zip file)") from exc
        self._names = [n for n in self.archive.namelist() if not n.endswith("/")]

    def names(self) -> list[str]:
        return self._names

    def read(self, name: str) -> bytes:
        try:
            return self.archive.read(name)
        except (zipfile.BadZipFile, NotImplementedError, RuntimeError, zlib.error) as exc:
            raise OSError(f"cannot extract {name}: {exc}") from exc


class FolderSource(Source):
    def __init__(self, path: Path):
        self.root = path.parent if path.suffix == ".sdProfile" else path
        self._names = sorted(p.relative_to(self.root).as_posix() for p in path.rglob("*") if p.is_file())

    def names(self) -> list[str]:
        return self._names

    def read(self, name: str) -> bytes:
        return (self.root / name).read_bytes()


def open_source(path: Path) -> Source:
    if not path.exists():
        raise ProfileError(f"{path} does not exist")
    return FolderSource(path) if path.is_dir() else ZipSource(path)


# --- model -----------------------------------------------------------------------------------

@dataclass
class Action:
    uuid: str
    name: str = ""
    settings: dict = field(default_factory=dict)
    children: list[Action] = field(default_factory=list)  # the steps of a multi action


@dataclass
class Key:
    column: int
    row: int
    action: Action
    title: str = ""
    show_title: bool = True
    alignment: str = "bottom"
    color: str = "#ffffff"
    font_size: int | None = None
    image: str | None = None  # path of the image inside the source

    @property
    def position(self) -> str:
        return f"{self.column},{self.row}"


@dataclass
class Page:
    id: str
    folder: str  # where the page lives inside the source
    keys: list[Key]
    name: str = ""
    dials: int = 0  # Stream Deck + encoders, which StreamController pages do not map


@dataclass
class Profile:
    name: str
    model: str
    version: str
    pages: list[Page]  # in the order the Stream Deck shows them
    folders: list[Page]  # pages reached through a folder key
    source: Source

    def page(self, reference: str) -> Page | None:
        """The page or folder an action points to, whichever way Elgato wrote its id."""
        wanted = aliases(reference)
        for page in self.pages + self.folders:
            if wanted & aliases(page.id):
                return page
        return None


def aliases(identifier: str) -> set[str]:
    """Every spelling of a page id that Elgato uses.

    Page folders are named after the page UUID encoded in base32hex (26 characters), while
    actions and page lists spell the UUID itself. The last character only carries padding
    bits, so it is left out of the comparison.
    """
    identifier = identifier.removesuffix(".sdProfile").strip()
    found = {identifier.lower()}
    try:
        value = uuid.UUID(identifier)
    except ValueError:
        if len(identifier) == 26:
            found.add(identifier[:25].lower())
        return found
    found.add(str(value))
    found.add(base64.b32hexencode(value.bytes).decode().rstrip("=")[:25].lower())
    return found


# --- parsing ---------------------------------------------------------------------------------

def _dict(value: object) -> dict:
    return value if isinstance(value, dict) else {}


def _list(value: object) -> list:
    return value if isinstance(value, list) else []


def _str(value: object) -> str:
    return value if isinstance(value, str) else ""


def _int(value: object, default: int | None = None) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def parse_action(data: dict) -> Action:
    uuid_ = _str(data.get("UUID")) or _str(_dict(data.get("Plugin")).get("UUID"))
    children = []
    # Multi actions keep their steps in "Actions": [{"Actions": [...]}, ...] (one list per state)
    for routine in _list(data.get("Actions"))[:1]:
        children = [parse_action(step) for step in _list(_dict(routine).get("Actions")) if isinstance(step, dict)]
    return Action(uuid_.lower(), _str(data.get("Name")), _dict(data.get("Settings")), children)


def parse_key(source: Source, folder: str, position: str, data: dict) -> Key | None:
    column, _, row = position.partition(",")
    column_, row_ = _int(column), _int(row)
    if column_ is None or row_ is None:
        return None
    states = _list(data.get("States")) or [{}]
    state = _dict(states[max(0, min(_int(data.get("State"), 0) or 0, len(states) - 1))])
    title = _str(state.get("Title"))
    show = state.get("ShowTitle", state.get("TitleShow", "") != "hide")
    key = Key(
        column=column_,
        row=row_,
        action=parse_action(data),
        title=title,
        show_title=bool(show) and bool(title),
        alignment=(_str(state.get("TitleAlignment")) or "bottom").lower(),
        color=_str(state.get("TitleColor")) or "#ffffff",
        font_size=_int(state.get("FontSize") or state.get("FSize")),
    )
    key.image = find_image(source, folder, position, state)
    return key


def find_image(source: Source, folder: str, position: str, state: dict) -> str | None:
    names = set(source.names())
    image = _str(state.get("Image"))
    if image:
        candidate = str(PurePosixPath(folder) / image)
        if candidate in names:
            return candidate
    # version 1 keeps images next to the key: <profile>/<col,row>/CL/<state>.png
    prefix = f"{folder}/{position}/"
    found = sorted(n for n in names if n.startswith(prefix) and n.lower().endswith(IMAGE_SUFFIXES))
    return found[0] if found else None


def parse_keys(source: Source, folder: str, actions: dict) -> list[Key]:
    keys = []
    for position, data in _dict(actions).items():
        if isinstance(data, dict):
            key = parse_key(source, folder, position, data)
            if key is not None:
                keys.append(key)
    return sorted(keys, key=lambda k: (k.row, k.column))


def profile_roots(source: Source) -> list[str]:
    """The top-level .sdProfile folders, which are profiles (nested ones are folders)."""
    roots = []
    for name in source.names():
        path = PurePosixPath(name)
        if path.name != "manifest.json":
            continue
        parent = path.parent
        if parent.suffix == ".sdProfile" and not any(p.suffix == ".sdProfile" for p in parent.parents):
            roots.append(str(parent))
    return sorted(roots)


def read_profiles(path: Path) -> list[Profile]:
    source = open_source(path)
    roots = profile_roots(source)
    if not roots:
        raise ProfileError(f"{path.name} contains no Stream Deck profile (no .sdProfile/manifest.json)")
    try:
        return [read_profile(source, root) for root in roots]
    except ProfileError:
        raise
    except (OSError, ValueError, TypeError, AttributeError, KeyError, IndexError) as exc:
        # an export edited by hand or written by a future Stream Deck version
        raise ProfileError(f"{path.name} has an unexpected layout ({type(exc).__name__}: {exc})") from exc


def read_profile(source: Source, root: str) -> Profile:
    manifest = source.json(f"{root}/manifest.json")
    name = _str(manifest.get("Name")) or PurePosixPath(root).stem
    model = _str(_dict(manifest.get("Device")).get("Model")) or _str(manifest.get("DeviceModel"))
    if "Pages" in manifest:
        return _read_v2(source, root, manifest, name, model)
    return _read_v1(source, root, manifest, name, model)


def _read_v1(source: Source, root: str, manifest: dict, name: str, model: str) -> Profile:
    main = Page(PurePosixPath(root).stem, root, parse_keys(source, root, manifest.get("Actions")), name)
    folders = []
    for entry in source.names():
        path = PurePosixPath(entry)
        if path.name == "manifest.json" and path.parent.suffix == ".sdProfile" and str(path.parent) != root \
                and str(path.parent).startswith(root + "/"):
            child = source.json(entry)
            folders.append(Page(path.parent.stem, str(path.parent),
                                parse_keys(source, str(path.parent), child.get("Actions")), _str(child.get("Name"))))
    return Profile(name, model, manifest.get("Version", "1.0"), [main], folders, source)


def _read_v2(source: Source, root: str, manifest: dict, name: str, model: str) -> Profile:
    pages = []
    for entry in source.names():
        path = PurePosixPath(entry)
        if path.name == "manifest.json" and path.parent.parent == PurePosixPath(root) / "Profiles":
            data = source.json(entry)
            keys, dials = [], 0
            for item in _list(data.get("Controllers")):
                controller = _dict(item)
                if (_str(controller.get("Type")) or "Keypad") == "Keypad":
                    keys += parse_keys(source, str(path.parent), controller.get("Actions"))
                else:
                    dials += len(_dict(controller.get("Actions")))
            pages.append(Page(path.parent.name, str(path.parent), sorted(keys, key=lambda k: (k.row, k.column)),
                              _str(data.get("Name")), dials))

    listed = [str(r) for r in _list(_dict(manifest.get("Pages")).get("Pages"))]
    ordered: list[Page] = []
    for reference in listed:
        match = next((p for p in pages if aliases(reference) & aliases(p.id) and p not in ordered), None)
        if match:
            ordered.append(match)
    folders = [p for p in pages if p not in ordered]
    if not ordered:
        # the page list could not be matched: every page not opened by a folder key is a page
        opened = {s.lower() for p in pages for k in p.keys
                  if (s := str(k.action.settings.get("ProfileUUID", "")))}
        ordered = [p for p in pages if not aliases(p.id) & set().union(*(aliases(o) for o in opened))] \
            if opened else pages
        folders = [p for p in pages if p not in ordered]
    return Profile(name, model, manifest.get("Version", "2.0"), ordered, folders, source)
