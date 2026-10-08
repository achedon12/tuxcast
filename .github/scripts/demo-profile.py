"""Writes the demo Elgato profile used for the `tuxcast convert` screenshot.

usage: demo-profile.py <output.streamDeckProfile>
"""

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tests.conftest import key, make_v2_profile

folder = uuid.uuid4()
make_v2_profile(Path(sys.argv[1]), name="Streaming", pages=[{
    "0,0": key("com.elgato.obsstudio.stream", "Go live", image="Images/live.png"),
    "1,0": key("com.elgato.obsstudio.record", "Record"),
    "2,0": key("com.elgato.streamdeck.profile.openchild", "Scenes", {"ProfileUUID": str(folder)}),
    "0,1": key("com.elgato.discord.mute", "Mute"),
    "1,1": key("com.elgato.twitch.clip", "Clip"),
    "2,1": key("com.elgato.streamdeck.soundboard.playaudio", "Airhorn"),
}], folders=[(folder, {
    "1,0": key("com.elgato.obsstudio.scene", "Just chatting", {"sceneName": "Chat"}),
    "2,0": key("com.elgato.streamdeck.system.open", "Game", {"path": "C:\\Games\\Valorant.exe"}),
})])
