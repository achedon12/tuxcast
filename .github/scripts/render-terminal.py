"""Renders a command's colored output as a terminal window in SVG, for the README and the site.

usage: render-terminal.py <output.svg> <title> -- <command> [args...]

The command runs with FORCE_COLOR=1; its ANSI colors become SVG text spans. Run it again
whenever the output of a command changes, so screenshots never lie.
"""

from __future__ import annotations

import html
import os
import re
import subprocess
import sys
from pathlib import Path

PALETTE = {
    "31": "#f87171", "32": "#4ade80", "33": "#fbbf24", "34": "#60a5fa",
    "35": "#c084fc", "36": "#22d3ee",
}
FOREGROUND, DIM = "#e5e7eb", "#9ca3af"
BACKGROUND, BAR = "#0f1117", "#1c1f2a"
CHAR_WIDTH, LINE_HEIGHT, FONT_SIZE = 8.4, 20, 14
PAD_X, PAD_TOP, PAD_BOTTOM, BAR_HEIGHT = 22, 52, 22, 34
ANSI = re.compile(r"\033\[([0-9;]*)m")
# Status symbols are missing from many coding fonts: name fonts that have them, since some
# renderers do not fall back glyph by glyph
SYMBOLS = re.compile("([✔⚠✖○])")
SYMBOL_FONTS = "'DejaVu Sans Mono', 'Segoe UI Symbol', 'Apple Symbols', 'Noto Sans Symbols 2', sans-serif"


def spans(line: str) -> list[tuple[str, dict]]:
    style: dict = {}
    parts, position = [], 0
    for match in ANSI.finditer(line):
        if match.start() > position:
            parts.append((line[position:match.start()], dict(style)))
        for code in (match.group(1) or "0").split(";"):
            if code == "0":
                style = {}
            elif code == "1":
                style["bold"] = True
            elif code == "2":
                style["dim"] = True
            elif code in PALETTE:
                style["color"] = PALETTE[code]
        position = match.end()
    if position < len(line):
        parts.append((line[position:], dict(style)))
    return parts


def render(title: str, prompt: str, output: str) -> str:
    lines = [f"\033[32m$\033[0m {prompt}", *output.rstrip("\n").split("\n")]
    width_chars = max(60, *(len(ANSI.sub("", line)) for line in lines))
    width = int(PAD_X * 2 + width_chars * CHAR_WIDTH)
    height = PAD_TOP + PAD_BOTTOM + LINE_HEIGHT * len(lines)
    rows = []
    for number, line in enumerate(lines):
        y = PAD_TOP + LINE_HEIGHT * number + FONT_SIZE
        tspans = []
        for text, style in spans(line):
            attributes = [f'fill="{style.get("color", DIM if style.get("dim") else FOREGROUND)}"']
            if style.get("bold"):
                attributes.append('font-weight="700"')
            content = SYMBOLS.sub(f'<tspan font-family="{SYMBOL_FONTS}">\\1</tspan>', html.escape(text))
            tspans.append(f"<tspan {' '.join(attributes)}>{content}</tspan>")
        rows.append(f'<text x="{PAD_X}" y="{y}" xml:space="preserve">{"".join(tspans)}</text>')
    dots = "".join(f'<circle cx="{22 + i * 20}" cy="{BAR_HEIGHT / 2}" r="6" fill="{c}"/>'
                   for i, c in enumerate(("#ff5f57", "#febc2e", "#28c840")))
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{html.escape(title)}">
<rect width="{width}" height="{height}" rx="10" fill="{BACKGROUND}"/>
<path d="M0 10 a10 10 0 0 1 10 -10 h{width - 20} a10 10 0 0 1 10 10 v{BAR_HEIGHT - 10} h-{width} z" fill="{BAR}"/>
{dots}
<text x="{width / 2}" y="{BAR_HEIGHT / 2 + 5}" text-anchor="middle" fill="{DIM}" font-family="ui-sans-serif, system-ui, sans-serif" font-size="13">{html.escape(title)}</text>
<g font-family="'JetBrains Mono', 'DejaVu Sans Mono', 'Fira Code', ui-monospace, Menlo, Consolas, monospace" font-size="{FONT_SIZE}">
{chr(10).join(rows)}
</g>
</svg>
"""


def main() -> int:
    if "--" not in sys.argv or len(sys.argv) < 5:
        print(__doc__, file=sys.stderr)
        return 2
    separator = sys.argv.index("--")
    target, title = Path(sys.argv[1]), sys.argv[2]
    command = sys.argv[separator + 1:]
    shown = os.environ.get("RENDER_PROMPT") or " ".join(Path(command[0]).name if i == 0 else part
                                                         for i, part in enumerate(command))
    done = subprocess.run(command, capture_output=True, text=True, check=False,
                          env={**os.environ, "FORCE_COLOR": "1", "NO_COLOR": ""})
    target.write_text(render(title, shown, done.stdout + done.stderr))
    print(f"wrote {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
