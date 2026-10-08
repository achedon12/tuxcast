import pytest

from tuxcast import audio

PACTL = """Sink Input #42
\tDriver: protocol-native.c
\tSink: 57
\tProperties:
\t\tapplication.name = "Spotify"
\t\tapplication.process.binary = "spotify"
Sink Input #43
\tSink: 57
\tProperties:
\t\tapplication.process.binary = "obs"
"""


def test_render_declares_one_loopback_per_sink():
    text = audio.render(audio.parse_sinks("game,music"))
    assert text.count("libpipewire-module-loopback") == 2
    assert 'node.name      = "tuxcast_game"' in text
    assert 'node.description = "Stream · Music"' in text
    assert audio.configured_from(text) == ["tuxcast_game", "tuxcast_music"]


def test_sink_names_are_validated():
    with pytest.raises(ValueError, match="invalid"):
        audio.parse_sinks("game,Bad Name")
    with pytest.raises(ValueError, match="unique"):
        audio.parse_sinks("game,game")
    assert audio.Sink("my-chat").description == "Stream · My Chat"


def test_playing_streams(fake_system):
    system = fake_system(commands={"pactl": "/usr/bin/pactl"},
                         outputs={("pactl", "list", "sink-inputs"): PACTL})
    assert audio.playing(system) == [audio.Stream("42", "Spotify", "57"), audio.Stream("43", "obs", "57")]


PACTL_SINKS = """Sink #57
\tName: tuxcast_game
\tDescription: Stream · Game
\tMute: yes
\tVolume: front-left: 52428 /  80% / -5.81 dB,   front-right: 52428 /  80% / -5.81 dB
Sink #58
\tName: alsa_output.headset
\tDescription: Headset
\tMute: no
\tVolume: front-left: 65536 / 100% / 0.00 dB
"""


def test_sink_states(fake_system):
    system = fake_system(commands={"pactl": "/usr/bin/pactl"}, outputs={("pactl", "list", "sinks"): PACTL_SINKS})
    assert audio.sink_states(system) == [
        audio.SinkState("57", "tuxcast_game", "Stream · Game", 80, True),
        audio.SinkState("58", "alsa_output.headset", "Headset", 100, False),
    ]
