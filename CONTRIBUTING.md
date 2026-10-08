# Contributing to tuxcast

Thanks for helping Linux streamers! Every distribution, desktop and app combination is a
little different, so reports from your setup are as valuable as code.

## The quickest contributions

- **Your doctor output.** Run `tuxcast doctor` and [open an issue](https://github.com/achedon12/tuxcast/issues/new/choose)
  when a check is wrong or misses a problem you had.
- **An Elgato action tuxcast does not convert.** The conversion report names its UUID.
  Open an *Elgato action* issue with that UUID and, if you can, the key's `Settings` from
  the profile's `manifest.json`.
- **A guide.** The [guides](https://achedon12.github.io/tuxcast/guides/) live in `docs/guides/`.
  Fixes and new sections are welcome, especially for desktops and GPUs we don't use.

## Development setup

You need Python 3.11 or newer and nothing else: tuxcast has no runtime dependencies.

```sh
git clone https://github.com/achedon12/tuxcast.git
cd tuxcast
make install   # .venv with tuxcast in editable mode, ruff, pytest and MkDocs Material
make check     # lint, tests and the documentation build, like CI
```

`make help` lists every target. `.venv/bin/tuxcast` runs your working copy.

## Project layout

```text
src/tuxcast/
├── cli.py             commands and their output
├── system.py          the fakeable view of the machine every probe goes through
├── doctor/            one module per doctor topic
├── convert/           Elgato reader, action mappings, keyboard layouts
├── bridge.py          Discord IPC bridge
├── audio.py           PipeWire sinks
├── deck.py            Stream Deck hardware
└── patch.py           patch keeper
docs/                  the website, also published as the wiki
tests/                 pytest suite, with synthetic Elgato profiles and fake machines
```

## Adding an Elgato action mapping

Mappings live in [`src/tuxcast/convert/actions.py`](https://github.com/achedon12/tuxcast/blob/main/src/tuxcast/convert/actions.py). A
one-to-one mapping is a line:

```python
MAPPINGS["com.elgato.twitch.marker"] = simple(f"{TWITCH}::Marker")
```

When settings need translating, register a function with `@maps("<elgato uuid>")` that
returns StreamController actions. Then:

1. add a test in `tests/test_convert.py`,
2. add the row to `docs/reference/elgato-actions.md` (a test checks that every mapping is documented),
3. note it under *Unreleased* in `CHANGELOG.md`.

## Adding a doctor check

Each topic is a module in `src/tuxcast/doctor/`. A check receives a `System` and yields
findings (`ok`, `info`, `warn`, `fail`, `skip`); a warning or failure should always say how
to fix it. Read files with `system.read()`/`system.path()` and run commands with
`system.run()`, never directly: that is what lets tests fake the machine
(see `tests/test_doctor.py`). Checks must only read: the doctor never changes anything.

## Pull requests

- One topic per pull request, with tests for behaviour changes.
- `make check` passes.
- User-facing changes are noted in `CHANGELOG.md` and, when relevant, in `docs/`.
- Commit messages describe what changes for users, in the imperative
  ("Detect Vesktop's socket", not "fixed stuff").

By contributing, you agree that your contributions are licensed under the [MIT license](https://github.com/achedon12/tuxcast/blob/main/LICENSE).
