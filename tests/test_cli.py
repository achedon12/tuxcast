import json

import pytest

from tests.conftest import key, make_v2_profile
from tuxcast import __version__, cli


def test_version(capsys):
    with pytest.raises(SystemExit):
        cli.main(["--version"])
    assert capsys.readouterr().out.strip() == f"tuxcast {__version__}"


def test_help_without_command(capsys):
    assert cli.main([]) == 0
    assert "doctor" in capsys.readouterr().out


def test_doctor_json(fake_system, monkeypatch, capsys):
    monkeypatch.setattr(cli, "System", lambda: fake_system(env={"XDG_SESSION_TYPE": "x11"}))
    assert cli.main(["doctor", "--json", "--only", "display,streamdeck"]) == 0
    topics = json.loads(capsys.readouterr().out)
    assert [t["topic"] for t in topics] == ["display", "streamdeck"]
    assert topics[0]["findings"][0]["status"] == "ok"


def test_doctor_exit_code_reports_failures(fake_system, monkeypatch, capsys):
    monkeypatch.setattr(cli, "System", fake_system)
    assert cli.main(["doctor", "--only", "network"]) == 1  # no route to the internet
    assert "No route" in capsys.readouterr().out


def test_doctor_rejects_unknown_topics(capsys):
    assert cli.main(["doctor", "--only", "toaster"]) == 2
    assert "unknown topic" in capsys.readouterr().err


def test_convert_dry_run(tmp_path, capsys):
    profile = tmp_path / "Live.streamDeckProfile"
    make_v2_profile(profile, name="Live", pages=[{
        "0,0": key("com.elgato.obsstudio.stream", "Go live"),
        "1,0": key("com.example.unknown", "Mystery"),
    }])
    code = cli.main(["convert", str(profile), "--pages-dir", str(tmp_path / "pages"), "--layout", "us", "-n"])
    out = capsys.readouterr().out
    assert code == 0
    assert "Would write 1 page" in out
    assert "1/2 keys converted" in out
    assert "Mystery" in out
    assert not (tmp_path / "pages").exists()


def test_convert_reports_bad_files(tmp_path, capsys):
    assert cli.main(["convert", str(tmp_path / "missing.streamDeckProfile")]) == 1
    assert "does not exist" in capsys.readouterr().err


def test_audio_setup_and_remove(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert cli.main(["audio", "setup", "--sinks", "game,music"]) == 0
    drop_in = tmp_path / "pipewire/pipewire.conf.d/tuxcast-sinks.conf"
    assert "tuxcast_music" in drop_in.read_text()
    assert cli.main(["audio", "remove"]) == 0
    assert not drop_in.exists()
    assert cli.main(["audio", "setup", "--sinks", "Bad Name"]) == 2


def test_patch_list_without_patches(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert cli.main(["patch", "list"]) == 0
    assert "No patches" in capsys.readouterr().out


def test_titles_cannot_inject_terminal_escapes(tmp_path, capsys):
    profile = tmp_path / "p.streamDeckProfile"
    make_v2_profile(profile, pages=[{"0,0": key("com.example.x", "\x1b]0;pwned\x07\x1b[2J")}])
    cli.main(["convert", str(profile), "--pages-dir", str(tmp_path / "pages"), "--layout", "us", "-n"])
    out = capsys.readouterr().out
    assert "\x1b]0;" not in out and "\x1b[2J" not in out
