from tuxcast.convert import keymap


def test_us_letters_digits_and_function_keys():
    assert keymap.evdev(ord("A")) == 30
    assert keymap.evdev(ord("1")) == 2
    assert keymap.evdev(ord("0")) == 11
    assert keymap.evdev(0x70) == 59  # F1
    assert keymap.evdev(0x7C) == 183  # F13
    assert keymap.evdev(0x87) == 194  # F24


def test_azerty_moves_letters_back_to_their_physical_key():
    assert keymap.evdev(ord("A"), "fr") == keymap.evdev(ord("Q"))
    assert keymap.evdev(ord("Q"), "fr") == keymap.evdev(ord("A"))
    assert keymap.evdev(ord("Z"), "fr") == keymap.evdev(ord("W"))
    assert keymap.evdev(ord("M"), "fr") == 39


def test_qwertz_swaps_y_and_z():
    assert keymap.evdev(ord("Z"), "de") == keymap.evdev(ord("Y"))
    assert keymap.evdev(ord("Y"), "de") == keymap.evdev(ord("Z"))


def test_unknown_virtual_key():
    assert keymap.evdev(0xFF) is None


def test_layout_from_xkb():
    assert keymap.layout_from_xkb("fr,us") == "fr"
    assert keymap.layout_from_xkb(" de(nodeadkeys)") == "de"
    assert keymap.layout_from_xkb("dvorak") == "us"
