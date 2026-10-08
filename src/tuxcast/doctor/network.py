"""Network: the link your stream leaves through."""

from __future__ import annotations

import re
from collections.abc import Iterator

from tuxcast.doctor import Finding, check, fail, info, ok, warn
from tuxcast.system import System


def default_interface(system: System) -> str | None:
    out = system.run("ip", "route", "get", "1.1.1.1")
    match = re.search(r"\bdev (\S+)", out.stdout) if out and out.ok else None
    return match.group(1) if match else None


def is_wireless(system: System, interface: str) -> bool:
    return system.path(f"/sys/class/net/{interface}/wireless").exists() or \
        system.path(f"/sys/class/net/{interface}/phy80211").exists()


def wired_links_up(system: System) -> list[str]:
    """Physical Ethernet interfaces with a cable plugged in."""
    net = system.path("/sys/class/net")
    if not net.is_dir():
        return []
    found = []
    for interface in sorted(net.iterdir()):
        name = interface.name
        if is_wireless(system, name) or not system.path(f"/sys/class/net/{name}/device").exists():
            continue  # wireless, or virtual (lo, docker0, veth, bridges)
        if system.read(f"/sys/class/net/{name}/carrier") == "1":
            found.append(name)
    return found


@check("network", "Network")
def network(system: System) -> Iterator[Finding]:
    interface = default_interface(system)
    if interface is None:
        yield fail("No route to the internet", fix="Check your connection before going live.")
        return

    if is_wireless(system, interface):
        wired = wired_links_up(system)
        yield warn(
            f"You stream over Wi-Fi ({interface})",
            "Wi-Fi drops packets in bursts. Twitch reports it as an unstable bitrate, and viewers "
            "see buffering even when your upload speed is high.",
            f"A cable is plugged in ({', '.join(wired)}): make it the default route, or disable Wi-Fi "
            "while streaming." if wired else "Use an Ethernet cable, even through a powerline adapter.",
        )
    else:
        speed = system.read(f"/sys/class/net/{interface}/speed")
        yield ok(f"Wired connection ({interface}" + (f", {speed} Mb/s)" if speed and speed.isdigit()
                                                     and int(speed) > 0 else ")"))
    yield info(
        "Check your upload before going live",
        "Keep the stream bitrate under 75% of your measured upload: 6000 kbps needs about 8 Mb/s.",
        "Run a speed test, or the Twitch Inspector bandwidth test (inspector.twitch.tv).",
    )
