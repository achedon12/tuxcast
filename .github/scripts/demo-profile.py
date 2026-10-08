"""Writes the demo Elgato profile used for screenshots and videos, with drawn key icons.

usage: demo-profile.py <output.streamDeckProfile>   (needs Pillow, a development tool only)
"""

import io
import json
import sys
import uuid
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tests.conftest import key, page_folder

S = 144  # Elgato key images are 144 by 144 pixels on current decks


def icon(background: str, draw) -> bytes:
    image = Image.new("RGB", (S, S), background)
    draw(ImageDraw.Draw(image))
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()


def live(d):
    d.ellipse((60, 52, 84, 76), fill="white")
    for r, w in ((22, 6), (38, 6)):
        d.arc((72 - r, 64 - r, 72 + r, 64 + r), 300, 60, fill="white", width=w)
        d.arc((72 - r, 64 - r, 72 + r, 64 + r), 120, 240, fill="white", width=w)


def record(d):
    d.ellipse((42, 34, 102, 94), fill="#ff4757")


def scenes(d):
    for x in (36, 76):
        for y in (28, 66):
            d.rounded_rectangle((x, y, x + 32, y + 30), 6, fill="#ece8ff")


def mute(d):
    d.rounded_rectangle((60, 26, 84, 74), 12, fill="#ece8ff")
    d.arc((48, 46, 96, 90), 0, 180, fill="#ece8ff", width=6)
    d.line((72, 90, 72, 104), fill="#ece8ff", width=6)
    d.line((40, 30, 104, 100), fill="#ff4757", width=8)


def clip(d):
    d.ellipse((34, 64, 62, 92), outline="white", width=7)
    d.ellipse((82, 64, 110, 92), outline="white", width=7)
    d.line((56, 70, 100, 26), fill="white", width=7)
    d.line((88, 70, 44, 26), fill="white", width=7)


def horn(d):
    d.polygon([(34, 58), (60, 58), (106, 34), (106, 94), (60, 70), (34, 70)], fill="#1b1540")


def chatting(d):
    d.rounded_rectangle((30, 30, 114, 84), 18, fill="white")
    d.polygon([(50, 82), (48, 104), (70, 84)], fill="white")


def game(d):
    d.rounded_rectangle((28, 46, 116, 92), 22, fill="#0f2d1f")
    d.rectangle((44, 64, 64, 72), fill="white")
    d.rectangle((50, 58, 58, 78), fill="white")
    d.ellipse((86, 56, 96, 66), fill="white")
    d.ellipse((96, 68, 106, 78), fill="white")


ICONS = {
    "live": ("#ff4757", live), "record": ("#2c2459", record), "scenes": ("#6d4aff", scenes),
    "mute": ("#2c2459", mute), "clip": ("#0f9b8e", clip), "horn": ("#ffb84d", horn),
    "chat": ("#3b82f6", chatting), "game": ("#3ddc97", game),
}


def main() -> None:
    target = Path(sys.argv[1])
    folder_id = uuid.uuid4()
    page_id = uuid.uuid4()
    pages = {
        page_id: {
            "0,0": key("com.elgato.obsstudio.stream", "Go live", image="Images/live.png"),
            "1,0": key("com.elgato.obsstudio.record", "Record", image="Images/record.png"),
            "2,0": key("com.elgato.streamdeck.profile.openchild", "Scenes", {"ProfileUUID": str(folder_id)},
                       image="Images/scenes.png"),
            "0,1": key("com.elgato.discord.mute", "Mute", image="Images/mute.png"),
            "1,1": key("com.elgato.twitch.clip", "Clip", image="Images/clip.png"),
            "2,1": key("com.elgato.streamdeck.soundboard.playaudio", "Airhorn", image="Images/horn.png"),
        },
        folder_id: {
            "1,0": key("com.elgato.obsstudio.scene", "Just chatting", {"sceneName": "Chat"}, image="Images/chat.png"),
            "2,0": key("com.elgato.streamdeck.system.open", "Game", {"path": "C:\\Games\\Valorant.exe"},
                       image="Images/game.png"),
        },
    }
    root = f"{str(uuid.uuid4()).upper()}.sdProfile"
    with zipfile.ZipFile(target, "w") as archive:
        archive.writestr(f"{root}/manifest.json", json.dumps({
            "Name": "Streaming", "Version": "2.0", "Device": {"Model": "20GBA9901"},
            "Pages": {"Current": str(page_id), "Default": str(page_id), "Pages": [str(page_id)]}}))
        for identifier, actions in pages.items():
            folder = f"{root}/Profiles/{page_folder(identifier)}"
            manifest = {"Controllers": [{"Type": "Keypad", "Actions": actions}]}
            archive.writestr(f"{folder}/manifest.json", json.dumps(manifest))
            for action in actions.values():
                image = action["States"][0]["Image"]
                name = Path(image).stem
                background, draw = ICONS[name]
                archive.writestr(f"{folder}/{image}", icon(background, draw))


if __name__ == "__main__":
    main()
