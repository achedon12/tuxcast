"""Builds the GitHub wiki from docs/, so the documentation lives in one place.

usage: build-wiki.py <repository> <wiki checkout>

Every page of the website becomes a wiki page. Material for MkDocs syntax is turned into
what GitHub renders: content tabs become sub-headings, admonitions become alerts, snippets
are inlined. Links between pages become wiki links, links to images point at the repository.
The wiki also gets a home page, a sidebar and a footer, and loses pages docs/ no longer has.
"""

from __future__ import annotations

import re
import sys
import textwrap
from pathlib import Path

REPO = "https://github.com/achedon12/tuxcast"
SITE = "https://achedon12.github.io/tuxcast"
RAW = "https://raw.githubusercontent.com/achedon12/tuxcast/main"

# docs file -> wiki page, in sidebar order, grouped
SECTIONS = {
    "Start": {
        "getting-started.md": "Getting-Started",
    },
    "Commands": {
        "commands/index.md": "Commands",
        "commands/ui.md": "tuxcast-ui",
        "commands/doctor.md": "tuxcast-doctor",
        "commands/convert.md": "tuxcast-convert",
        "commands/bridge.md": "tuxcast-bridge-discord",
        "commands/audio.md": "tuxcast-audio",
        "commands/deck.md": "tuxcast-deck",
        "commands/patch.md": "tuxcast-patch",
    },
    "Guides": {
        "guides/index.md": "Guides",
        "guides/streaming-on-linux.md": "Streaming-on-Linux-in-2026",
        "guides/obs.md": "OBS-on-Linux",
        "guides/stream-deck.md": "Stream-Deck-on-Linux",
        "guides/audio.md": "Audio-Routing",
        "guides/sandboxes.md": "Discord-and-Spotify-in-Sandboxes",
        "guides/music.md": "Music-Without-Claims",
        "guides/network.md": "Network",
    },
    "Reference": {
        "reference/elgato-actions.md": "Elgato-Actions",
        "reference/faq.md": "FAQ",
        "reference/contributing.md": "Contributing",
        "reference/changelog.md": "Changelog",
    },
}
PAGES = {source: page for section in SECTIONS.values() for source, page in section.items()}

LINK = re.compile(r"(!?)\[([^\]]*)\]\(([^)\s]+)\)")
ATTRIBUTES = re.compile(r"\{\s*[.#:][^}]*\}")
ICON = re.compile(r":(material|octicons|fontawesome)-[a-z0-9-]+:")
SNIPPET = re.compile(r'^--8<-- "([^"]+)"$', re.MULTILINE)
ALERTS = {"note": "NOTE", "tip": "TIP", "info": "NOTE", "warning": "WARNING", "danger": "CAUTION",
          "important": "IMPORTANT", "example": "NOTE"}


def title(text: str) -> str:
    match = re.search(r"^# (.+)$", text, re.MULTILINE)
    return match.group(1).strip() if match else ""


def inline_snippets(text: str, repository: Path) -> str:
    return SNIPPET.sub(lambda m: (repository / m.group(1)).read_text(), text)


def convert_blocks(text: str) -> str:
    """Content tabs and admonitions, which GitHub does not render, to headings and alerts."""
    out: list[str] = []
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        tab = re.match(r'^=== "(.+)"\s*$', line)
        admonition = re.match(r'^(!!!|\?\?\?\+?) (\w+)(?: "(.*)")?\s*$', line)
        if tab or admonition:
            i += 1
            body = []
            while i < len(lines) and (lines[i].startswith("    ") or not lines[i].strip()):
                body.append(lines[i])
                i += 1
            while body and not body[-1].strip():
                body.pop()
            while body and not body[0].strip():
                body.pop(0)
            content = textwrap.dedent("\n".join(body))
            if tab:
                out += [f"**{tab.group(1)}**", "", content, ""]
            else:
                kind = ALERTS.get(admonition.group(2).lower(), "NOTE")
                heading = admonition.group(3)
                quoted = [f"> [!{kind}]"] + ([f"> **{heading}**", ">"] if heading else [])
                quoted += [f"> {row}" if row else ">" for row in content.split("\n")]
                out += [*quoted, ""]
            continue
        out.append(line)
        i += 1
    return "\n".join(out)


def rewrite_link(source: str, image: str, label: str, target: str) -> str:
    if re.match(r"^[a-z]+:", target) or target.startswith("#"):
        return f"{image}[{label}]({target})"
    path, _, anchor = target.partition("#")
    resolved = (Path(source).parent / path).as_posix()
    resolved = re.sub(r"[^/]+/\.\./", "", resolved).removeprefix("./")
    if image:
        return f"{image}[{label}]({RAW}/docs/{resolved})"
    if not resolved.endswith(".md"):  # a page of the website itself, such as the live demo
        return f"[{label}]({SITE}/{resolved}{'#' + anchor if anchor else ''})"
    page = PAGES.get(resolved)
    if page is None:
        return f"[{label}]({SITE}/{resolved.removesuffix('.md').removesuffix('index')}/)"
    return f"[{label}]({page}{'#' + anchor if anchor else ''})"


def outside_code(text: str, transform) -> str:
    """Applies `transform` to the prose only, leaving fenced code blocks as they are."""
    parts = re.split(r"(^```.*?^```[ \t]*$)", text, flags=re.MULTILINE | re.DOTALL)
    return "".join(part if part.startswith("```") else transform(part) for part in parts)


def to_wiki(source: str, text: str, repository: Path) -> str:
    text = re.sub(r"^---\n.*?\n---\n", "", text, flags=re.DOTALL)
    text = inline_snippets(text, repository)
    text = convert_blocks(text)
    text = re.sub(r'^(```\w*) title="[^"]*"', r"\1", text, flags=re.MULTILINE)
    text = outside_code(text, lambda prose: LINK.sub(
        lambda m: rewrite_link(source, m.group(1), m.group(2), m.group(3)),
        ATTRIBUTES.sub("", ICON.sub("", prose))))
    text = re.sub(r"^# .+\n+", "", text, count=1)  # the wiki shows the page name as title
    edit = f"{REPO}/edit/main/docs/{source}"
    return text.rstrip() + f"\n\n---\n\n<sub>Generated from [`docs/{source}`]({edit}). " \
        f"Edit it there: this page is overwritten at each change.</sub>\n"


def home(repository: Path) -> str:
    sections = []
    for section, pages in SECTIONS.items():
        rows = [f"- [{title((repository / 'docs' / s).read_text()) or p.replace('-', ' ')}]({p})"
                for s, p in pages.items() if (repository / "docs" / s).exists()]
        sections.append(f"### {section}\n\n" + "\n".join(rows))
    return f"""<p align="center"><img src="{RAW}/.github/assets/banner.svg" alt="tuxcast" width="100%"></p>

**tuxcast** is the toolkit for streaming on Linux: it diagnoses your setup, converts Elgato
Stream Deck profiles, bridges sandboxed apps and splits your audio.

```sh
pipx install git+{REPO}.git
tuxcast doctor
```

This wiki mirrors the [website]({SITE}/), generated from the repository's `docs/` folder.

{chr(10).join(sections)}
"""


def sidebar(repository: Path) -> str:
    parts = ["**[Home](Home)**", ""]
    for section, pages in SECTIONS.items():
        parts.append(f"**{section}**")
        parts += [f"- [{title((repository / 'docs' / s).read_text()) or p}]({p})" for s, p in pages.items()
                  if (repository / "docs" / s).exists()]
        parts.append("")
    return "\n".join(parts)


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    repository, wiki = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
    if wiki == repository or wiki in repository.parents or (wiki / "docs").is_dir():
        print(f"refusing to write the wiki into {wiki}: pass the wiki checkout or an empty folder",
              file=sys.stderr)
        return 2
    wiki.mkdir(parents=True, exist_ok=True)
    written = {"Home.md", "_Sidebar.md", "_Footer.md"}
    (wiki / "Home.md").write_text(home(repository))
    (wiki / "_Sidebar.md").write_text(sidebar(repository))
    (wiki / "_Footer.md").write_text(
        f"[Website]({SITE}/) · [Repository]({REPO}) · [Issues]({REPO}/issues) · MIT licensed\n")
    for source, page in PAGES.items():
        path = repository / "docs" / source
        if not path.exists():
            continue
        (wiki / f"{page}.md").write_text(to_wiki(source, path.read_text(), repository))
        written.add(f"{page}.md")
    # remove pages docs/ no longer has, but only pages this script generated
    for stale in wiki.glob("*.md"):
        if stale.name not in written and "<sub>Generated from [`docs/" in stale.read_text():
            stale.unlink()
    print(f"{len(written)} wiki pages in {wiki}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
