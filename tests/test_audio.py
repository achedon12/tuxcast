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
