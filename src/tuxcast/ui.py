"""Terminal output: colors, symbols and small layout helpers.

Colors follow the usual conventions: they are off when stdout is not a terminal,
when NO_COLOR is set, and forced on with FORCE_COLOR.
"""

from __future__ import annotations

import os
import sys

_CODES = {
    "bold": "1",
    "dim": "2",
    "red": "31",
    "green": "32",
    "yellow": "33",
    "blue": "34",
    "magenta": "35",
    "cyan": "36",
}


def color_enabled(stream=None) -> bool:
    stream = stream or sys.stdout
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    return hasattr(stream, "isatty") and stream.isatty()


def style(text: str, *names: str) -> str:
    if not names or not color_enabled():
        return text
    codes = ";".join(_CODES[name] for name in names)
    return f"\033[{codes}m{text}\033[0m"


def title(text: str) -> None:
    print(style(text, "bold"))


def section(text: str) -> None:
    print()
    print(style(text, "bold", "cyan"))


def info(text: str) -> None:
    print(f"  {text}")


def hint(text: str) -> None:
    print(style(f"    → {text}", "dim"))


def success(text: str) -> None:
    print(f"{style('✔', 'green')} {text}")


def warning(text: str) -> None:
    print(f"{style('⚠', 'yellow')} {text}", file=sys.stderr)


def error(text: str) -> None:
    print(f"{style('✖', 'red')} {text}", file=sys.stderr)
