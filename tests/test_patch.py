import pytest

from tuxcast import patch

TWITCH = '''OAUTH_REDIRECT_URI = "http://localhost:3000/auth"
OAUTH_PORT = 3000
'''


def write_patch(folder, target, body=None):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "twitch-port.toml").write_text(body or f'''
file = "{target}"

[[replace]]
pattern = '^OAUTH_PORT = \\d+$'
with = "OAUTH_PORT = 6948"

[[replace]]
pattern = 'localhost:\\d+/auth'
with = "localhost:6948/auth"
''')


def test_apply_then_unchanged(tmp_path):
    target = tmp_path / "constants.py"
    target.write_text(TWITCH)
    write_patch(tmp_path / "patches", target)
    [item] = patch.load_all(tmp_path / "patches")

    assert patch.apply(item, dry_run=True).state == "applied"
    assert target.read_text() == TWITCH
    assert patch.apply(item).state == "applied"
    assert target.read_text() == 'OAUTH_REDIRECT_URI = "http://localhost:6948/auth"\nOAUTH_PORT = 6948\n'
    assert patch.apply(item).state == "unchanged"
    assert item.watch == tmp_path


def test_missing_file_and_changed_app(tmp_path):
    target = tmp_path / "constants.py"
    write_patch(tmp_path / "patches", target)
    [item] = patch.load_all(tmp_path / "patches")
    assert patch.apply(item).state == "missing"
    target.write_text("PORT = 1\n")
    assert patch.apply(item).state == "no-match"


@pytest.mark.parametrize(("body", "message"), [
    ("file = ", "twitch-port.toml"),
    ('watch = "/tmp"', "`file` is required"),
    ('file = "/x"', "at least one"),
    ('file = "/x"\n[[replace]]\npattern = "("\nwith = ""', "replacement 1"),
    ('file = "/x"\n[[replace]]\npattern = "a"', "needs `pattern` and `with`"),
    ('file = "/x"\nreplace = "oops"', "\\[\\[replace\\]\\] tables"),
    ('file = 3\n[[replace]]\npattern = "a"\nwith = "b"', "must be strings"),
])
def test_invalid_patches(tmp_path, body, message):
    write_patch(tmp_path, None, body)
    with pytest.raises(patch.PatchError, match=message):
        patch.load_all(tmp_path)


def test_units_watch_each_folder_once(tmp_path):
    target = tmp_path / "a" / "constants.py"
    write_patch(tmp_path / "patches", target)
    patches = patch.load_all(tmp_path / "patches") * 2
    units = patch.units(patches, "/home/me/.local/bin/tuxcast")
    assert units["tuxcast-patch.path"].count("PathChanged=") == 2  # the folder and the file
    assert "ExecStart=/home/me/.local/bin/tuxcast patch apply --quiet" in units["tuxcast-patch.service"]


def test_shipped_twitch_patch(tmp_path, monkeypatch):
    from pathlib import Path

    shipped = Path(__file__).parents[1] / "contrib/patches/twitch-oauth-port.toml"
    monkeypatch.setenv("HOME", str(tmp_path))
    item = patch.load(shipped)
    item.file.parent.mkdir(parents=True)
    item.file.write_text(TWITCH)
    assert patch.apply(item).state == "applied"
    assert "OAUTH_PORT = 6948" in item.file.read_text()
    assert 'OAUTH_REDIRECT_URI = "http://localhost:6948/auth"' in item.file.read_text()


def test_bad_replacement_template_is_reported(tmp_path):
    target = tmp_path / "constants.py"
    target.write_text(TWITCH)
    write_patch(tmp_path / "patches", target, f'''
file = "{target}"
[[replace]]
pattern = 'OAUTH_PORT'
with = '\\9'
''')
    [item] = patch.load_all(tmp_path / "patches")
    outcome = patch.apply(item)
    assert outcome.state == "error" and "invalid" in outcome.error
    assert target.read_text() == TWITCH
