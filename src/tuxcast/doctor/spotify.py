"""Spotify: whether media keys and Stream Deck buttons can actually control it."""

from __future__ import annotations

from collections.abc import Iterator

from tuxcast import paths
from tuxcast.doctor import Finding, check, fail, info, ok, skip, warn
from tuxcast.system import System

SPOTIFY_FLATPAK_ID = "com.spotify.Client"


def mpris_players(system: System) -> list[str]:
    out = system.run("busctl", "--user", "--list", "--no-pager", "--no-legend")
    if not out or not out.ok:
        return []
    return [line.split()[0] for line in out.stdout.splitlines()
            if line.startswith("org.mpris.MediaPlayer2.")]


@check("spotify", "Spotify")
def spotify(system: System) -> Iterator[Finding]:
    snap = "spotify" in system.snaps()
    flatpak = SPOTIFY_FLATPAK_ID in system.flatpak_apps()
    native = system.has("spotify") and not snap
    if not (snap or flatpak or native):
        yield skip("Spotify is not installed")
        return

    installs = [name for name, present in (("snap", snap), ("Flathub", flatpak), ("native", native)) if present]
    yield ok(f"Spotify ({', '.join(installs)})")

    if len(installs) > 1:
        yield warn(
            "Several Spotify installs",
            "When two run at once they claim the same MPRIS name, and media keys reach "
            "whichever registered first.",
            "Keep one: the Flathub build controls best (see below).",
        )
    if snap:
        fix = "snap remove spotify && flatpak install flathub com.spotify.Client"
        detail = ("The snap answers MPRIS commands with success but ignores them, so play/pause "
                  "and next buttons do nothing.")
        if paths.STREAMCONTROLLER_FLATPAK_ID in system.flatpak_apps():
            yield fail("StreamController cannot control the Spotify snap",
                       detail + " AppArmor also blocks Flatpak apps from calling it.", fix)
        else:
            yield warn("The Spotify snap ignores remote control", detail, fix)

    players = [p for p in mpris_players(system) if "spotify" in p.lower()]
    if players:
        yield ok("Spotify is running and exposes MPRIS", ", ".join(players))
    else:
        yield info("Spotify is not running", "Remote control was not tested.")

    yield info(
        "Playing Spotify on stream breaks Spotify's terms",
        "Spotify's terms forbid public broadcast whatever the track's license, and many "
        "tracks trigger DMCA strikes or YouTube Content ID claims.",
        "See the music guide: https://achedon12.github.io/tuxcast/guides/music/",
    )
