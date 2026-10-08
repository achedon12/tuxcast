"""Windows virtual-key codes (what Elgato stores) to Linux evdev codes (what StreamController sends).

Virtual-key codes name the character a key types on the Windows layout, while evdev codes
name a physical key on a US keyboard. On a US layout both agree; on AZERTY or QWERTZ the
letters that moved must be moved back, or Ctrl+A becomes Ctrl+Q.
"""

from __future__ import annotations

# evdev codes from linux/input-event-codes.h
KEY_LEFTCTRL, KEY_LEFTSHIFT, KEY_LEFTALT, KEY_LEFTMETA = 29, 42, 56, 125

_LETTERS = dict(zip("ABCDEFGHIJKLMNOPQRSTUVWXYZ",
                    [30, 48, 46, 32, 18, 33, 34, 35, 23, 36, 37, 38, 50,
                     49, 24, 25, 16, 19, 31, 20, 22, 47, 17, 45, 21, 44], strict=True))

VK_TO_EVDEV: dict[int, int] = {
    0x08: 14, 0x09: 15, 0x0D: 28, 0x10: 42, 0x11: 29, 0x12: 56, 0x13: 119, 0x14: 58,
    0x1B: 1, 0x20: 57, 0x21: 104, 0x22: 109, 0x23: 107, 0x24: 102,
    0x25: 105, 0x26: 103, 0x27: 106, 0x28: 108, 0x2C: 99, 0x2D: 110, 0x2E: 111,
    0x30: 11, **{0x31 + i: 2 + i for i in range(9)},
    **{ord(letter): code for letter, code in _LETTERS.items()},
    0x5B: 125, 0x5C: 126, 0x5D: 127,
    0x60: 82, 0x61: 79, 0x62: 80, 0x63: 81, 0x64: 75, 0x65: 76, 0x66: 77, 0x67: 71, 0x68: 72, 0x69: 73,
    0x6A: 55, 0x6B: 78, 0x6D: 74, 0x6E: 83, 0x6F: 98,
    **dict(zip(range(0x70, 0x7C), [59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 87, 88], strict=True)),
    **{0x7C + i: 183 + i for i in range(12)},  # F13-F24, the streamer's favourite hotkeys
    0x90: 69, 0x91: 70,
    0xA0: 42, 0xA1: 54, 0xA2: 29, 0xA3: 97, 0xA4: 56, 0xA5: 100,
    0xAD: 113, 0xAE: 114, 0xAF: 115, 0xB0: 163, 0xB1: 165, 0xB2: 166, 0xB3: 164,
    0xBA: 39, 0xBB: 13, 0xBC: 51, 0xBD: 12, 0xBE: 52, 0xBF: 53, 0xC0: 41,
    0xDB: 26, 0xDC: 43, 0xDD: 27, 0xDE: 40, 0xE2: 86,
}

# Letters that sit elsewhere than on a US keyboard: VK letter -> the US letter at its position
_MOVED_LETTERS = {
    "us": {},
    "fr": {"A": "Q", "Q": "A", "Z": "W", "W": "Z"},
    "be": {"A": "Q", "Q": "A", "Z": "W", "W": "Z"},
    "de": {"Y": "Z", "Z": "Y"},
    "ch": {"Y": "Z", "Z": "Y"},
    "at": {"Y": "Z", "Z": "Y"},
    "cz": {"Y": "Z", "Z": "Y"},
    "hu": {"Y": "Z", "Z": "Y"},
}
# On AZERTY, M is right of L, where US has the semicolon
_MOVED_CODES = {"fr": {ord("M"): 39}, "be": {ord("M"): 39}}

LAYOUTS = sorted(_MOVED_LETTERS)
# Punctuation keys (VK_OEM_*) differ on every layout and are only exact on US
OEM_KEYS = {0xBA, 0xBB, 0xBC, 0xBD, 0xBE, 0xBF, 0xC0, 0xDB, 0xDC, 0xDD, 0xDE, 0xE2}


def evdev(vk: int, layout: str = "us") -> int | None:
    if vk in _MOVED_CODES.get(layout, {}):
        return _MOVED_CODES[layout][vk]
    moved = _MOVED_LETTERS.get(layout, {})
    if 0x41 <= vk <= 0x5A and chr(vk) in moved:
        return _LETTERS[moved[chr(vk)]]
    return VK_TO_EVDEV.get(vk)


def layout_from_xkb(value: str) -> str:
    """The first layout of an XKB setting such as 'fr,us' or 'de(nodeadkeys)'."""
    first = value.split(",", maxsplit=1)[0].split("(", maxsplit=1)[0].strip().lower()
    return first if first in _MOVED_LETTERS else "us"
