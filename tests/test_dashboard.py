import http.client
import json
import threading

import pytest

from tests.conftest import key, make_v2_profile
from tuxcast.dashboard import Dashboard, serve


@pytest.fixture
def dashboard(fake_system, tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    board = Dashboard(lambda: fake_system(env={"XDG_SESSION_TYPE": "x11"}), layout="us",
                      pages_dir=tmp_path / "pages", assets_dir=tmp_path / "assets")
    server = serve(board)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    board.port = server.server_address[1]
    yield board
    server.shutdown()
    server.server_close()
    board.close()


def call(board, method, path, body=None, *, token=True, headers=None):
    connection = http.client.HTTPConnection("127.0.0.1", board.port, timeout=10)
    sent = {"Host": f"127.0.0.1:{board.port}", **(headers or {})}
    if token:
        sent["X-Tuxcast-Token"] = board.token
    if isinstance(body, dict):
        body = json.dumps(body).encode()
    connection.request(method, path, body=body, headers=sent)
    response = connection.getresponse()
    raw = response.read()
    connection.close()
    try:
        data = json.loads(raw)
    except ValueError:
        data = raw.decode()
    return response.status, data, dict(response.getheaders())


def test_api_needs_the_token(dashboard):
    assert call(dashboard, "GET", "/api/overview", token=False)[0] == 403
    status, data, _ = call(dashboard, "GET", "/api/overview")
    assert status == 200 and data["layout"] == "us"


def test_page_needs_the_token_and_is_locked_down(dashboard):
    assert call(dashboard, "GET", "/", token=False)[0] == 403
    status, body, headers = call(dashboard, "GET", f"/?token={dashboard.token}", token=False)
    assert status == 200 and "<title>tuxcast</title>" in body
    assert "script-src 'self'" in headers["Content-Security-Policy"]
    assert headers["X-Content-Type-Options"] == "nosniff"


def test_other_hosts_and_origins_are_refused(dashboard):
    assert call(dashboard, "GET", "/api/overview", headers={"Host": f"evil.example:{dashboard.port}"})[0] == 421
    assert call(dashboard, "GET", "/api/overview", headers={"Origin": "http://evil.example"})[0] == 403
    origin = f"http://127.0.0.1:{dashboard.port}"
    assert call(dashboard, "GET", "/api/overview", headers={"Origin": origin})[0] == 200


def test_doctor(dashboard):
    status, topics, _ = call(dashboard, "GET", "/api/doctor")
    assert status == 200
    assert topics[0]["topic"] == "display" and topics[0]["findings"][0]["status"] == "ok"


def test_convert_preview_then_write(dashboard, tmp_path):
    profile = tmp_path / "Live.streamDeckProfile"
    make_v2_profile(profile, name="Live", pages=[{"0,0": key("com.elgato.obsstudio.stream", "Go live",
                                                               image="Images/live.png")}])
    status, preview, _ = call(dashboard, "POST", "/api/convert/preview", profile.read_bytes(),
                              headers={"X-Filename": "Live.streamDeckProfile"})
    assert status == 200, preview
    assert preview["file"] == "Live.streamDeckProfile"
    assert preview["pages"][0]["keys"][0]["image"].startswith("data:image/png;base64,")
    assert not (tmp_path / "pages").exists()

    status, done, _ = call(dashboard, "POST", "/api/convert", {"upload": preview["upload"], "name": "Show"})
    assert status == 200, done
    assert (tmp_path / "pages" / "Show.json").exists()
    assert call(dashboard, "POST", "/api/convert", {"upload": preview["upload"], "name": "Show"})[0] == 422
    assert call(dashboard, "POST", "/api/convert", {"upload": "nope"})[0] == 404


def test_uploads_must_be_profiles(dashboard):
    status, data, _ = call(dashboard, "POST", "/api/convert/preview", b"x", headers={"X-Filename": "evil.sh"})
    assert status == 400 and "streamDeckProfile" in data["error"]


def test_audio_setup_validates_and_writes(dashboard, tmp_path):
    assert call(dashboard, "POST", "/api/audio/setup", {"sinks": []})[0] == 400
    assert call(dashboard, "POST", "/api/audio/setup", {"sinks": ["Bad Name"]})[0] == 400
    assert call(dashboard, "POST", "/api/audio/setup", {"sinks": ["game", "music"]})[0] == 200
    drop_in = tmp_path / "config/pipewire/pipewire.conf.d/tuxcast-sinks.conf"
    assert "tuxcast_music" in drop_in.read_text()
    assert call(dashboard, "GET", "/api/audio")[1]["configured"] == ["tuxcast_game", "tuxcast_music"]
    assert call(dashboard, "POST", "/api/audio/route", {"stream": "x;rm", "sink": "a"})[0] == 422
    assert call(dashboard, "POST", "/api/audio/route", {"stream": "1", "sink": "a b"})[0] == 400


def test_malformed_requests(dashboard):
    assert call(dashboard, "POST", "/api/audio/setup", b"{nope")[0] == 400
    assert call(dashboard, "POST", "/api/audio/setup", b"[1]")[0] == 400
    assert call(dashboard, "GET", "/api/unknown")[0] == 404


def test_patches_listing(dashboard):
    status, data, _ = call(dashboard, "GET", "/api/patches")
    assert status == 200 and data["patches"] == [] and data["watching"] is False


def test_body_is_not_read_without_the_token_or_with_a_bad_length(dashboard):
    assert call(dashboard, "POST", "/api/audio/setup", b"{}", token=False)[0] == 403
    status, _, _ = call(dashboard, "POST", "/api/audio/setup", b"", headers={"Content-Length": "-1"})
    assert status == 400


def test_old_uploads_are_dropped(dashboard, tmp_path):
    profile = tmp_path / "p.streamDeckProfile"
    make_v2_profile(profile, pages=[{"0,0": key("com.elgato.obsstudio.stream", "x")}])
    ids = [call(dashboard, "POST", "/api/convert/preview", profile.read_bytes(),
                headers={"X-Filename": "p.streamDeckProfile"})[1]["upload"] for _ in range(12)]
    assert len(dashboard.uploads) == 10
    assert call(dashboard, "POST", "/api/convert", {"upload": ids[0]})[0] == 404


def test_deck_shows_streamcontroller_pages(dashboard, tmp_path):
    image = tmp_path / "key.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 20)
    secret = tmp_path / "secret.txt"
    secret.write_text("not an image")
    pages = tmp_path / "pages"
    pages.mkdir()
    (pages / "Main.json").write_text(json.dumps({"keys": {
        "0x0": {"states": {"0": {"labels": {"bottom": {"text": "Live"}}, "media": {"path": str(image)}}}},
        "1x0": {"states": {"0": {"labels": {}, "media": {"path": str(secret)}}}},
        "bad": {"states": {}},
    }}))
    status, data, _ = call(dashboard, "GET", "/api/deck")
    assert status == 200
    [page] = data["pages"]
    keys = {(k["column"], k["row"]): k for k in page["keys"]}
    assert keys[(0, 0)]["label"] == "Live" and keys[(0, 0)]["image"].startswith("data:image/png;base64,")
    assert keys[(1, 0)]["image"] == ""  # only real images are ever sent


def test_volume_and_mute_are_validated(dashboard, monkeypatch):
    from tuxcast import audio

    calls = []
    monkeypatch.setattr(audio, "set_volume", lambda sink, volume: calls.append((sink, volume)) or "")
    monkeypatch.setattr(audio, "set_mute", lambda sink, muted: calls.append((sink, muted)) or "")
    assert call(dashboard, "POST", "/api/audio/volume", {"sink": "tuxcast_game", "volume": 80})[0] == 200
    assert call(dashboard, "POST", "/api/audio/mute", {"sink": "tuxcast_game", "muted": True})[0] == 200
    assert call(dashboard, "POST", "/api/audio/volume", {"sink": "a b", "volume": 80})[0] == 400
    assert call(dashboard, "POST", "/api/audio/volume", {"sink": "x", "volume": "loud"})[0] == 400
    assert calls == [("tuxcast_game", 80), ("tuxcast_game", True)]
