"""Elgato Stream Deck hardware: discovery, USB permissions and recovery."""

from __future__ import annotations

import fcntl
import os
from dataclasses import dataclass
from pathlib import Path

from tuxcast.system import System

ELGATO_VENDOR_ID = "0fd9"

# USB product id -> model name. Elgato also sells capture cards, cameras and microphones under
# the same vendor id, so only these products are Stream Decks: never reset anything else.
PRODUCTS = {
    "0060": "Stream Deck",
    "0063": "Stream Deck Mini",
    "006c": "Stream Deck XL",
    "006d": "Stream Deck (v2)",
    "0080": "Stream Deck MK.2",
    "0084": "Stream Deck +",
    "0086": "Stream Deck Pedal",
    "008f": "Stream Deck XL (v2)",
    "0090": "Stream Deck Mini (v2)",
    "009a": "Stream Deck Neo",
    "00a5": "Stream Deck MK.2 (scissor keys)",
}

# Grants the logged-in user access to every Elgato device, which is what
# StreamController and the python-elgato-streamdeck library need.
UDEV_RULE = (
    "# Elgato Stream Deck: let the logged-in user talk to the device (installed by tuxcast)\n"
    f'SUBSYSTEM=="usb", ATTRS{{idVendor}}=="{ELGATO_VENDOR_ID}", TAG+="uaccess"\n'
    f'KERNEL=="hidraw*", ATTRS{{idVendor}}=="{ELGATO_VENDOR_ID}", TAG+="uaccess"\n'
)
UDEV_RULE_PATH = Path("/etc/udev/rules.d/70-streamdeck.rules")

# _IO('U', 20) from linux/usbdevice_fs.h
USBDEVFS_RESET = 0x5514


@dataclass(frozen=True)
class Deck:
    product_id: str
    bus: int
    device: int
    serial: str

    @property
    def name(self) -> str:
        return PRODUCTS[self.product_id]

    @property
    def node(self) -> str:
        """The usbfs node, like /dev/bus/usb/003/007."""
        return f"/dev/bus/usb/{self.bus:03d}/{self.device:03d}"


def decks(system: System) -> list[Deck]:
    found = []
    devices = system.path("/sys/bus/usb/devices")
    if not devices.is_dir():
        return found
    for device in sorted(devices.iterdir()):
        base = f"/sys/bus/usb/devices/{device.name}"
        if system.read(f"{base}/idVendor") != ELGATO_VENDOR_ID:
            continue
        product = (system.read(f"{base}/idProduct") or "").lower()
        if product not in PRODUCTS:
            continue  # a Cam Link, Wave mic, Facecam… not a deck
        busnum, devnum = system.read(f"{base}/busnum"), system.read(f"{base}/devnum")
        if not (busnum and devnum and busnum.isdigit() and devnum.isdigit()):
            continue
        found.append(Deck(
            product_id=product,
            bus=int(busnum),
            device=int(devnum),
            serial=system.read(f"{base}/serial") or "",
        ))
    return found


def accessible(system: System, deck: Deck) -> bool:
    return os.access(system.path(deck.node), os.R_OK | os.W_OK)


def reset(node: str) -> None:
    """Resets a USB device, as if it was unplugged and plugged back.

    This recovers a deck left without a driver after an app crashed while talking to it
    ("Failed to read feature report (-1)").
    """
    descriptor = os.open(node, os.O_WRONLY)
    try:
        fcntl.ioctl(descriptor, USBDEVFS_RESET, 0)
    finally:
        os.close(descriptor)
