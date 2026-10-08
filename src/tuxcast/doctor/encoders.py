"""Hardware encoding: which GPU encoder OBS should use instead of the CPU (x264)."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from tuxcast.doctor import Finding, check, info, ok, warn
from tuxcast.system import System

VENDORS = {"0x10de": "NVIDIA", "0x1002": "AMD", "0x8086": "Intel"}


@dataclass(frozen=True)
class Gpu:
    card: str
    vendor: str


def gpus(system: System) -> list[Gpu]:
    found = []
    drm = system.path("/sys/class/drm")
    if not drm.is_dir():
        return found
    for card in sorted(drm.iterdir()):
        if not card.name.startswith("card") or "-" in card.name:
            continue  # card1-HDMI-A-1 and friends are connectors, not GPUs
        vendor = system.read(f"/sys/class/drm/{card.name}/device/vendor")
        if vendor in VENDORS:
            found.append(Gpu(card.name, VENDORS[vendor]))
    return found


def recommended_encoder(vendor: str) -> str:
    return {
        "NVIDIA": "NVENC (H.264 or HEVC), preset P5, multipass off",
        "AMD": "FFmpeg VAAPI H.264 (or AMD HW H.264 with the AMF driver)",
        "Intel": "QuickSync H.264 (QSV), or FFmpeg VAAPI H.264",
    }[vendor]


@check("encoders", "Video encoding")
def encoders(system: System) -> Iterator[Finding]:
    found = gpus(system)
    if not found:
        yield warn(
            "No GPU encoder found",
            "OBS will encode on the CPU (x264), which costs frames in demanding games.",
            "Use the x264 'veryfast' preset at 1080p60 6000 kbps, or 'faster' on a strong CPU.",
        )
        return

    for gpu in found:
        yield ok(f"{gpu.vendor} GPU ({gpu.card})", f"Use {recommended_encoder(gpu.vendor)} in OBS.")

    vendors = {gpu.vendor for gpu in found}
    if "NVIDIA" in vendors and not system.has("nvidia-smi"):
        yield warn(
            "The NVIDIA driver does not seem to be loaded",
            "NVENC needs the proprietary driver; nouveau cannot encode.",
            "Install your distribution's NVIDIA driver package and reboot.",
        )
    if vendors & {"AMD", "Intel"}:
        if not system.path("/dev/dri").is_dir() or not any(system.path("/dev/dri").glob("renderD*")):
            yield warn("No render node in /dev/dri", "VAAPI encoding needs /dev/dri/renderD128.")
        elif system.has("vainfo"):
            out = system.run("vainfo")
            if out and "VAEntrypointEncSlice" in out.stdout:
                yield ok("VAAPI can encode", "vainfo lists hardware encode entry points.")
            else:
                yield warn(
                    "VAAPI cannot encode",
                    "vainfo lists no encode entry point: the VA driver is missing or decode-only.",
                    "Install mesa-va-drivers (AMD) or intel-media-va-driver-non-free (Intel).",
                )
        else:
            yield info("vainfo is not installed, VAAPI encoding was not verified", fix="Install vainfo.")
