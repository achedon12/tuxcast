import os

from tests.conftest import write
from tuxcast import doctor
from tuxcast.doctor import Status, discord, display, encoders, network, spotify, streamdeck


def statuses(findings):
    return [f.status for f in findings]


def test_wayland_without_portal(fake_system):
    system = fake_system(env={"XDG_SESSION_TYPE": "wayland", "XDG_CURRENT_DESKTOP": "GNOME"})
    findings = list(display.display(system))
    assert statuses(findings)[:2] == [Status.OK, Status.WARN]
    assert "portal" in findings[1].summary


def test_x11(fake_system):
    assert statuses(display.display(fake_system(env={"XDG_SESSION_TYPE": "x11"}))) == [Status.OK]


def test_gpu_vendors(fake_system):
    system = fake_system()
    write(system.root, "/sys/class/drm/card0/device/vendor", "0x10de")
    write(system.root, "/sys/class/drm/card0-HDMI-A-1/status", "connected")
    findings = list(encoders.encoders(system))
    assert findings[0].summary == "NVIDIA GPU (card0)"
    assert "NVENC" in findings[0].detail
    assert findings[1].status is Status.WARN  # no nvidia-smi: driver missing


def test_no_gpu_falls_back_to_x264(fake_system):
    assert statuses(encoders.encoders(fake_system())) == [Status.WARN]


def plug_deck(system, product="0090"):
    base = "/sys/bus/usb/devices/7-1"
    for name, value in {"idVendor": "0fd9", "idProduct": product, "busnum": "7", "devnum": "51",
                        "serial": "ABC"}.items():
        write(system.root, f"{base}/{name}", value)
    return write(system.root, "/dev/bus/usb/007/051")


def test_stream_deck_without_permission_or_app(fake_system):
    system = fake_system()
    node = plug_deck(system)
    node.chmod(0o000)
    findings = list(streamdeck.streamdeck(system))
    assert findings[0].summary.startswith("Stream Deck Mini (v2) on /dev/bus/usb/007/051")
    expected = Status.OK if os.geteuid() == 0 else Status.FAIL  # root ignores permissions
    assert findings[0].status is expected
    assert findings[-1].status is Status.WARN  # no StreamController


def test_stream_deck_ready(fake_system):
    system = fake_system(flatpaks=("com.core447.StreamController",))
    plug_deck(system, "0080")
    findings = list(streamdeck.streamdeck(system))
    assert statuses(findings) == [Status.OK, Status.OK, Status.INFO]
    assert "MK.2" in findings[0].summary


def test_no_stream_deck(fake_system):
    assert statuses(streamdeck.streamdeck(fake_system())) == [Status.SKIP]


def test_spotify_snap_with_streamcontroller_fails(fake_system):
    system = fake_system(snaps=("spotify",), flatpaks=("com.core447.StreamController",))
    findings = list(spotify.spotify(system))
    assert Status.FAIL in statuses(findings)


def test_spotify_two_installs_warn(fake_system):
    findings = list(spotify.spotify(fake_system(snaps=("spotify",), flatpaks=("com.spotify.Client",))))
    assert any(f.summary == "Several Spotify installs" for f in findings)


def test_discord_snap_needs_the_bridge(fake_system):
    system = fake_system(snaps=("discord",), flatpaks=("com.core447.StreamController",))
    findings = list(discord.discord(system))
    summaries = [f.summary for f in findings]
    assert "Discord (snap) is invisible to most Discord clients" in summaries
    assert "StreamController (Flatpak) cannot see Discord's socket" in summaries


def test_wifi_with_a_cable_plugged(fake_system):
    system = fake_system(commands={"ip": "/usr/bin/ip"},
                         outputs={("ip", "route", "get", "1.1.1.1"): "1.1.1.1 via 192.168.1.1 dev wlan0 src x"})
    write(system.root, "/sys/class/net/wlan0/wireless/x")
    write(system.root, "/sys/class/net/eth0/device/x")
    write(system.root, "/sys/class/net/eth0/carrier", "1")
    write(system.root, "/sys/class/net/docker0/carrier", "1")
    findings = list(network.network(system))
    assert findings[0].status is Status.WARN
    assert "eth0" in findings[0].fix and "docker0" not in findings[0].fix


def test_a_crashing_check_does_not_hide_the_others(fake_system, monkeypatch):
    def broken(_system):
        raise RuntimeError("boom")

    doctor.run(fake_system(), ["display"])  # make sure every topic is registered
    monkeypatch.setattr(doctor, "TOPICS", [doctor.Topic("network", "Network", broken),
                                           *[t for t in doctor.TOPICS if t.key != "network"]])
    results = {t.key: f for t, f in doctor.run(fake_system(), ["network", "display"])}
    assert results["network"][0].summary == "This check crashed"
    assert results["display"]


def test_other_elgato_devices_are_not_stream_decks(fake_system):
    system = fake_system()
    plug_deck(system, "0066")  # Cam Link 4K
    assert statuses(streamdeck.streamdeck(system)) == [Status.SKIP]
