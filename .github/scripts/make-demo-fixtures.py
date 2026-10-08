"""Writes .github/demo/fixtures.json, the sample data of the website's dashboard demo.

usage: make-demo-fixtures.py   (needs Pillow, for the demo profile's key icons)

The pages and the conversion preview come from tuxcast itself, converting the demo profile; the
doctor's checks are a typical setup: one Wi-Fi warning, Discord as a snap not yet bridged, and a
single audio mix.
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from tuxcast import __version__, streamcontroller  # noqa: E402
from tuxcast.convert import convert, keymap  # noqa: E402
from tuxcast.dashboard import Dashboard  # noqa: E402


def finding(status, summary, detail="", fix="", action=""):
    return {"status": status, "summary": summary, "detail": detail, "fix": fix, "action": action}


DOCTOR = [
    {"topic": "display", "title": "Display server", "findings": [
        finding("ok", "Wayland session (GNOME)"),
        finding("ok", "xdg-desktop-portal is installed", "OBS captures screens through the PipeWire portal.")]},
    {"topic": "audio", "title": "Audio", "findings": [
        finding("ok", "PipeWire is running"), finding("ok", "WirePlumber answers"),
        finding("info", "Your stream audio is a single mix",
                "Game, music, Discord and alerts all reach OBS together, so you cannot mute the music in your "
                "VODs or lower Discord alone.", "tuxcast audio setup", "audio")]},
    {"topic": "encoders", "title": "Video encoding", "findings": [
        finding("ok", "NVIDIA GPU (card1)", "Use NVENC (H.264 or HEVC), preset P5, multipass off in OBS.")]},
    {"topic": "obs", "title": "OBS Studio", "findings": [
        finding("ok", "OBS (Flathub)"), finding("ok", "obs-websocket is on (port 4455, password protected)")]},
    {"topic": "streamdeck", "title": "Stream Deck", "findings": [
        finding("ok", "Stream Deck Mini (v2) on /dev/bus/usb/003/007"),
        finding("ok", "StreamController is installed (Flathub)"),
        finding("info", "Coming from Windows or macOS?",
                "Your Elgato profiles can be converted instead of rebuilt by hand.",
                "tuxcast convert MyProfile.streamDeckProfile", "convert")]},
    {"topic": "discord", "title": "Discord", "findings": [
        finding("ok", "Discord (snap)"),
        finding("ok", "Discord is running", "/run/user/1000/snap.discord/discord-ipc-0"),
        finding("warn", "Discord (snap) is invisible to most Discord clients",
                "Its socket is not where clients look, so Stream Deck mute keys and rich presence cannot find Discord.",
                "tuxcast bridge discord --install", "discord")]},
    {"topic": "spotify", "title": "Spotify", "findings": [
        finding("ok", "Spotify (Flathub)"), finding("ok", "Spotify is running and exposes MPRIS",
                                                    "org.mpris.MediaPlayer2.spotify")]},
    {"topic": "network", "title": "Network", "findings": [
        finding("warn", "You stream over Wi-Fi (wlan0)",
                "Wi-Fi drops packets in bursts. Twitch reports it as an unstable bitrate, and viewers see buffering "
                "even when your upload speed is high.", "Use an Ethernet cable, even through a powerline adapter."),
        finding("info", "Check your upload before going live",
                "Keep the stream bitrate under 75% of your measured upload: 6000 kbps needs about 8 Mb/s.")]},
]


def main() -> None:
    work = Path(tempfile.mkdtemp())
    profile = work / "Streaming.streamDeckProfile"
    subprocess.run([sys.executable, str(ROOT / ".github/scripts/demo-profile.py"), str(profile)], check=True)

    # the deck's current pages: the demo profile, converted for real
    convert(profile, work / "pages", work / "assets", name="Main", layout="us")
    pages = [{"name": p.name, "keys": [vars(k) for k in p.keys]} for p in streamcontroller.pages(work / "pages")]
    preview = Dashboard._report(convert(profile, work / "preview", work / "assets", dry_run=True))

    fixtures = {
        "overview": {"version": __version__, "decks": [{"name": "Stream Deck Mini (v2)"}], "layout": "us",
                     "layouts": keymap.LAYOUTS},
        "doctor": DOCTOR,
        "deck": {"decks": [{"name": "Stream Deck Mini (v2)", "node": "/dev/bus/usb/003/007", "serial": "DEMO",
                            "accessible": True, "columns": 3, "rows": 2}],
                 "pages": pages, "udev": "SUBSYSTEM==\"usb\", ATTRS{idVendor}==\"0fd9\", TAG+=\"uaccess\"\n",
                 "udevPath": "/etc/udev/rules.d/70-streamdeck.rules",
                 "pagesDir": "~/.var/app/com.core447.StreamController/data/pages"},
        "preview": preview,
    }
    target = ROOT / ".github/demo/fixtures.json"
    target.write_text(json.dumps(fixtures, separators=(",", ":")))
    print(f"wrote {target} ({target.stat().st_size // 1024} KiB)")


if __name__ == "__main__":
    main()
