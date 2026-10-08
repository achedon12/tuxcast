"""Builds the website's live demo of tuxcast ui into docs/demo/.

usage: build-demo.py

The demo is the dashboard itself, copied from the package, with demo.js answering instead of a
server (sample data from .github/demo/fixtures.json). Run it before `mkdocs build`.
"""

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "src/tuxcast/dashboard/static"
DEMO = ROOT / ".github/demo"
TARGET = ROOT / "docs/demo"

BANNER = """<div class="demo-banner">This is a demo with sample data: click around, nothing leaves this page.
  <a href="../getting-started/">Install tuxcast</a> to use it on your setup.</div>"""


def main() -> None:
    shutil.rmtree(TARGET, ignore_errors=True)
    shutil.copytree(STATIC, TARGET)
    for name in ("demo.js", "fixtures.json"):
        shutil.copy(DEMO / name, TARGET / name)
    index = (TARGET / "index.html").read_text()
    index = index.replace('<script src="app.js" defer></script>',
                          '<script src="demo.js"></script>\n  <script src="app.js" defer></script>')
    index = index.replace("<title>tuxcast</title>", "<title>tuxcast dashboard demo</title>")
    index = index.replace("<body>", "<body>\n  " + BANNER, 1)
    (TARGET / "index.html").write_text(index)
    print(f"demo written to {TARGET.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
