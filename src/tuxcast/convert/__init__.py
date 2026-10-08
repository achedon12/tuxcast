"""``tuxcast convert``: Elgato Stream Deck profiles to StreamController pages.

Every Elgato page and folder becomes a StreamController page. Keys keep their image, title
and position; actions with a StreamController equivalent are converted, and the report lists
the ones to redo by hand.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from tuxcast.convert import actions
from tuxcast.convert.elgato import Key, Page, Profile, ProfileError, aliases, read_profiles

__all__ = ["ConversionError", "KeyReport", "Result", "convert"]

ALIGNMENTS = {"top": "top", "middle": "center", "center": "center", "bottom": "bottom"}
DEFAULT_FONT_SIZE = 12


class ConversionError(ValueError):
    pass


@dataclass(frozen=True)
class KeyReport:
    page: str
    position: str
    title: str
    uuid: str
    status: str  # "converted", "partial", "manual"
    notes: tuple[str, ...] = ()


@dataclass
class Result:
    pages: list[Path] = field(default_factory=list)
    images: int = 0
    keys: list[KeyReport] = field(default_factory=list)
    plugins: set[str] = field(default_factory=set)
    warnings: list[str] = field(default_factory=list)

    def count(self, status: str) -> int:
        return sum(1 for key in self.keys if key.status == status)


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "page"


def safe_name(text: str) -> str:
    """A page name usable as a file name."""
    return re.sub(r"[/\\\0]+", "-", text).strip(" .") or "Page"


def color(value: str) -> list[int]:
    match = re.fullmatch(r"#?([0-9a-fA-F]{6})", value or "")
    if not match:
        return [255, 255, 255, 255]
    raw = match.group(1)
    return [int(raw[i:i + 2], 16) for i in (0, 2, 4)] + [255]


def page_names(profile: Profile, name: str) -> dict[int, str]:
    """A unique, readable name for each page and folder, keyed by id()."""
    names: dict[int, str] = {}
    for number, page in enumerate(profile.pages, start=1):
        names[id(page)] = name if number == 1 else f"{name} {number}"
    titles: dict[str, str] = {}
    for page in profile.pages + profile.folders:
        for key in page.keys:
            if key.action.uuid == "com.elgato.streamdeck.profile.openchild":
                reference = str(key.action.settings.get("ProfileUUID", ""))
                for alias in aliases(reference):
                    titles.setdefault(alias, key.title.replace("\n", " ").strip())
    taken = set(names.values())
    for number, folder in enumerate(profile.folders, start=1):
        title = next((titles[a] for a in aliases(folder.id) if titles.get(a)), "") or folder.name or f"Folder {number}"
        candidate, suffix = f"{name} - {title}", 2
        while candidate in taken:
            candidate, suffix = f"{name} - {title} {suffix}", suffix + 1
        taken.add(candidate)
        names[id(folder)] = candidate
    return {key: safe_name(value) for key, value in names.items()}


def convert(
    source: Path,
    pages_dir: Path,
    assets_dir: Path,
    *,
    name: str | None = None,
    layout: str = "us",
    dry_run: bool = False,
    force: bool = False,
) -> Result:
    """Converts every profile in `source`.

    Everything is built in memory first and written at the end, so a profile that cannot be
    read leaves no half-converted pages behind.
    """
    try:
        profiles = read_profiles(source)
    except ProfileError as exc:
        raise ConversionError(str(exc)) from exc

    result = Result()
    plans: list[tuple[Profile, Page, Path, bool]] = []  # profile, page, output, is folder
    targets: dict[str, Path] = {}  # alias of an Elgato page or profile -> output page
    labels: set[str] = set()
    for profile in profiles:
        label = safe_name(name if (name and len(profiles) == 1) else profile.name)
        unique, suffix = label, 2
        while unique in labels:  # backups often hold one "Default" profile per device
            unique, suffix = f"{label} ({suffix})", suffix + 1
        labels.add(unique)
        names = page_names(profile, unique)
        for page in profile.pages + profile.folders:
            output = pages_dir / f"{names[id(page)]}.json"
            plans.append((profile, page, output, page in profile.folders))
            for alias in aliases(page.id):
                targets.setdefault(alias, output)
        if profile.pages:
            root_id = PurePosixPath(profile.pages[0].folder).parts[0]
            for alias in aliases(root_id):
                targets.setdefault(alias, pages_dir / f"{names[id(profile.pages[0])]}.json")

    existing = [output for *_, output, _ in plans if output.exists()]
    if existing and not force and not dry_run:
        raise ConversionError(
            "these pages already exist: " + ", ".join(p.name for p in existing)
            + " (use --force to overwrite, or --name to pick another name)")

    def resolve(reference: str) -> str | None:
        for alias in aliases(reference):
            if alias in targets:
                return str(targets[alias])
        return None

    files: dict[Path, bytes] = {}
    for profile, page, output, is_folder in plans:
        order = [str(o) for p, _, o, f in plans if p is profile and not f]
        context = actions.Context(layout=layout, resolve=resolve, page_order=order,
                                  current_page=home_index(profile, page, order, plans))
        keys = {}
        for key in page.keys:
            state, report, image = convert_key(key, output, context, profile, assets_dir)
            keys[f"{key.column}x{key.row}"] = {"states": {"0": state}}
            result.keys.append(report)
            result.plugins |= {actions.PLUGINS[step["id"].split("::")[0]] for step in state["actions"]
                               if step["id"].split("::")[0] in actions.PLUGINS}
            if image:
                files[image[0]] = image[1]
                result.images += 1
        if is_folder and "0x0" not in keys and not any(
                k.action.uuid == "com.elgato.streamdeck.profile.backtoparent" for k in page.keys):
            keys["0x0"] = {"states": {"0": {
                "actions": [actions.action(f"{actions.DECK}::GoToPreviousPage")],
                "labels": {"bottom": label_for("back", "#ffffff", None)},
                "background": {}, "media": {},
            }}}
        if page.dials:
            result.warnings.append(f"{output.stem}: {page.dials} dial actions (Stream Deck +) were not converted")
        files[output] = (json.dumps({"keys": keys}, indent=4, ensure_ascii=False) + "\n").encode()
        result.pages.append(output)

    if not dry_run:
        try:
            for path, content in files.items():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
        except OSError as exc:
            raise ConversionError(f"cannot write {exc.filename}: {exc.strerror}") from exc
    return result


def home_index(profile: Profile, page: Page, order: list[str],
               plans: list[tuple[Profile, Page, Path, bool]]) -> int:
    """The position of the page a page belongs to: itself, or the page its folder opens from.

    Next/previous keys inside a folder move relative to that page, as on a Stream Deck.
    """
    outputs = {id(pg): str(o) for p, pg, o, _ in plans if p is profile}
    seen: set[int] = set()
    current = page
    while outputs[id(current)] not in order and id(current) not in seen:
        seen.add(id(current))
        opener = next((candidate for candidate in profile.pages + profile.folders
                       for key in candidate.keys
                       if key.action.uuid == "com.elgato.streamdeck.profile.openchild"
                       and aliases(str(key.action.settings.get("ProfileUUID", ""))) & aliases(current.id)), None)
        if opener is None:
            return 0
        current = opener
    return order.index(outputs[id(current)]) if outputs[id(current)] in order else 0


def label_for(text: str, hex_color: str, size: int | None) -> dict:
    return {"text": text, "color": color(hex_color), "font_size": None if size in (None, DEFAULT_FONT_SIZE) else size,
            "font_family": ""}


def convert_key(key: Key, output: Path, context: actions.Context, profile: Profile,
                assets_dir: Path) -> tuple[dict, KeyReport, tuple[Path, bytes] | None]:
    context.notes = []
    try:
        converted = actions.convert_action(key.action, context)
    except (TypeError, ValueError, AttributeError, KeyError) as exc:
        # settings in a shape no mapping expected: keep the key, report it
        converted = []
        context.notes.append(f"unexpected settings ({type(exc).__name__}): redo by hand")
    steps = key.action.children or [key.action]
    known = [actions.is_known(step.uuid) for step in steps]
    if converted and all(known) and not context.notes:
        status = "converted"
    elif converted:
        status = "partial"
    else:
        status = "manual"
    if not actions.is_known(key.action.uuid) and key.action.uuid:
        context.notes.append(f"no StreamController equivalent for {key.action.uuid}")

    state: dict = {"actions": converted, "labels": {}, "background": {}, "media": {}}
    if key.show_title:
        position = ALIGNMENTS.get(key.alignment, "bottom")
        state["labels"][position] = label_for(key.title, key.color, key.font_size)
    image = None
    if key.image:
        try:
            content = profile.source.read(key.image)
        except OSError:
            context.notes.append("its image could not be extracted")
        else:
            suffix = PurePosixPath(key.image).suffix.lower()
            path = assets_dir / slug(profile.name) / f"{slug(output.stem)}-{key.column}x{key.row}{suffix}"
            state["media"] = {"path": str(path)}
            image = (path, content)

    report = KeyReport(output.stem, key.position, key.title.replace("\n", " "), key.action.uuid, status,
                       tuple(dict.fromkeys(context.notes)))
    return state, report, image
