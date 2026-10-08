"""Stream Deck: plugged in, reachable without root, and driven by an app that runs on Linux."""

from __future__ import annotations

from collections.abc import Iterator

from tuxcast import deck as hardware
from tuxcast import paths
from tuxcast.doctor import Finding, check, fail, info, ok, skip, warn
from tuxcast.system import System


@check("streamdeck", "Stream Deck")
def streamdeck(system: System) -> Iterator[Finding]:
    decks = hardware.decks(system)
    if not decks:
        yield skip("No Stream Deck plugged in")
        return

    for deck in decks:
        label = f"{deck.name} on {deck.node}"
        if hardware.accessible(system, deck):
            yield ok(label)
        else:
            yield fail(
                f"{label}: no permission",
                "Your user cannot open the device, so no app can draw on its keys.",
                "tuxcast deck udev   (prints the udev rule and how to install it)",
                action="deck",
            )

    flatpak = paths.STREAMCONTROLLER_FLATPAK_ID in system.flatpak_apps()
    if flatpak or system.has("streamcontroller"):
        yield ok("StreamController is installed" + (" (Flathub)" if flatpak else ""))
        yield info(
            "Coming from Windows or macOS?",
            "Your Elgato profiles can be converted instead of rebuilt by hand.",
            "tuxcast convert MyProfile.streamDeckProfile",
            action="convert",
        )
    else:
        yield warn(
            "No Stream Deck app found",
            "Elgato's software does not exist for Linux and does not work under Wine.",
            "flatpak install flathub com.core447.StreamController",
        )
