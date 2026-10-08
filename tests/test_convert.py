import json
import uuid
import zipfile
from pathlib import Path

import pytest

from tests.conftest import PNG, key, make_v2_profile
from tuxcast.convert import ConversionError, convert

HOTKEY = "com.elgato.streamdeck.system.hotkey"
FOLDER = "com.elgato.streamdeck.profile.openchild"


def ctrl(vk: int) -> dict:
    return {"Hotkeys": [{"KeyCtrl": True, "KeyShift": False, "KeyOption": False, "KeyCmd": False, "VKeyCode": vk},
                        {"KeyCtrl": False, "KeyShift": False, "KeyOption": False, "KeyCmd": False, "VKeyCode": -1}]}


def run(tmp_path: Path, profile: Path, **options):
    pages, assets = tmp_path / "pages", tmp_path / "assets"
    return convert(profile, pages, assets, **options), pages


def load(path: Path) -> dict:
    return json.loads(path.read_text())["keys"]


def test_converts_pages_folders_and_images(tmp_path):
    folder_id = uuid.uuid4()
    profile = tmp_path / "Gaming.streamDeckProfile"
    make_v2_profile(profile, pages=[
        {
            "0,0": key(HOTKEY, "Mute", ctrl(ord("M")), image="Images/mute.png"),
            "1,0": key(FOLDER, "Scenes", {"ProfileUUID": str(folder_id)}),
            "2,0": key("com.elgato.streamdeck.system.website", "Site", {"path": "twitch.tv/achedon12"}),
        },
        {"0,0": key("com.elgato.streamdeck.page.previous", "Back")},
    ], folders=[(folder_id, {"1,0": key("com.elgato.obsstudio.scene", "Live", {"sceneName": "Live"})})])

    result, pages = run(tmp_path, profile)

    assert sorted(p.name for p in result.pages) == ["Gaming - Scenes.json", "Gaming 2.json", "Gaming.json"]
    main = load(pages / "Gaming.json")
    mute = main["0x0"]["states"]["0"]
    assert mute["actions"] == [{"id": "com_core447_OSPlugin::Hotkey", "settings": {
        "keys": [[29, 1], [50, 1], [50, 0], [29, 0]], "delay": 0.02, "repeat": False, "hold_until_release": False}}]
    assert mute["labels"]["bottom"]["text"] == "Mute"
    assert mute["labels"]["bottom"]["color"] == [255, 0, 0, 255]
    assert Path(mute["media"]["path"]).read_bytes() == PNG

    opener = main["1x0"]["states"]["0"]["actions"][0]
    assert opener["id"] == "com_core447_DeckPlugin::ChangePage"
    assert opener["settings"]["selected_page"] == str(pages / "Gaming - Scenes.json")
    assert main["2x0"]["states"]["0"]["actions"][0]["settings"]["url"] == "https://twitch.tv/achedon12"

    previous = load(pages / "Gaming 2.json")["0x0"]["states"]["0"]["actions"][0]
    assert previous["settings"]["selected_page"] == str(pages / "Gaming.json")

    folder = load(pages / "Gaming - Scenes.json")
    assert folder["0x0"]["states"]["0"]["actions"][0]["id"] == "com_core447_DeckPlugin::GoToPreviousPage"
    assert folder["1x0"]["states"]["0"]["actions"][0] == {
        "id": "com_core447_OBSPlugin::SwitchScene", "settings": {"scene": "Live"}}

    assert result.count("converted") == 5
    assert result.images == 1
    assert result.plugins == {"OS", "OBS", "Deck"}


def test_keyboard_layout_is_applied(tmp_path):
    profile = tmp_path / "p.streamDeckProfile"
    make_v2_profile(profile, pages=[{"0,0": key(HOTKEY, "", ctrl(ord("A")))}])
    _, pages = run(tmp_path, profile, layout="fr")
    keys = load(pages / "Gaming.json")["0x0"]["states"]["0"]["actions"][0]["settings"]["keys"]
    assert keys == [[29, 1], [16, 1], [16, 0], [29, 0]]  # the key labelled A on AZERTY is US Q


def test_multi_actions_become_several_actions(tmp_path):
    profile = tmp_path / "p.streamDeckProfile"
    multi = key("com.elgato.streamdeck.multiactions", "Go live")
    multi["Actions"] = [{"Actions": [
        key("com.elgato.obsstudio.scene", settings={"sceneName": "Starting"}),
        key("com.elgato.streamdeck.multiactions.delay", settings={"delay": 2000}),
        key("com.elgato.obsstudio.stream"),
    ]}]
    make_v2_profile(profile, pages=[{"0,0": multi}])
    result, pages = run(tmp_path, profile)
    ids = [a["id"] for a in load(pages / "Gaming.json")["0x0"]["states"]["0"]["actions"]]
    assert ids == ["com_core447_OBSPlugin::SwitchScene", "com_core447_OSPlugin::Delay",
                   "com_core447_OBSPlugin::ToggleStream"]
    assert result.keys[0].status == "converted"


def test_unknown_actions_keep_their_key_and_are_reported(tmp_path):
    profile = tmp_path / "p.streamDeckProfile"
    make_v2_profile(profile, pages=[{"0,0": key("com.example.weird.plugin", "Weird", image="Images/w.png")}])
    result, pages = run(tmp_path, profile)
    state = load(pages / "Gaming.json")["0x0"]["states"]["0"]
    assert state["actions"] == []
    assert state["labels"]["bottom"]["text"] == "Weird"
    assert result.keys[0].status == "manual"
    assert result.keys[0].notes == ("no StreamController equivalent for com.example.weird.plugin",)


def test_windows_programs_are_flagged(tmp_path):
    profile = tmp_path / "p.streamDeckProfile"
    make_v2_profile(profile, pages=[{"0,0": key("com.elgato.streamdeck.system.open", "Game",
                                                 {"path": "C:\\Games\\game.exe"})}])
    result, _ = run(tmp_path, profile)
    assert result.keys[0].status == "manual"
    assert "Linux command" in result.keys[0].notes[0]


def test_dry_run_writes_nothing(tmp_path):
    profile = tmp_path / "p.streamDeckProfile"
    make_v2_profile(profile, pages=[{"0,0": key(HOTKEY, "x", ctrl(ord("A")), image="Images/a.png")}])
    result, pages = run(tmp_path, profile, dry_run=True)
    assert result.pages and not pages.exists()
    assert not (tmp_path / "assets").exists()


def test_existing_pages_are_not_overwritten_without_force(tmp_path):
    profile = tmp_path / "p.streamDeckProfile"
    make_v2_profile(profile, pages=[{"0,0": key(HOTKEY, "x", ctrl(ord("A")))}])
    run(tmp_path, profile)
    with pytest.raises(ConversionError, match="already exist"):
        run(tmp_path, profile)
    run(tmp_path, profile, force=True)
    run(tmp_path, profile, name="Other")


def test_version_1_profiles(tmp_path):
    profile = tmp_path / "old.streamDeckProfile"
    child = str(uuid.uuid4()).upper()
    root = f"{uuid.uuid4()}.sdProfile"
    with zipfile.ZipFile(profile, "w") as archive:
        archive.writestr(f"{root}/manifest.json", json.dumps({"Name": "Old", "Version": "1.0", "Actions": {
            "0,0": key("com.elgato.streamdeck.system.multimedia", "Play", {"actionIdx": 0}),
            "1,0": key(FOLDER, "Sounds", {"ProfileUUID": child}),
        }}))
        archive.writestr(f"{root}/0,0/CL/state0.png", PNG)
        archive.writestr(f"{root}/Profiles/{child}.sdProfile/manifest.json", json.dumps({"Actions": {
            "0,0": key("com.elgato.streamdeck.profile.backtoparent"),
            "1,0": key("com.elgato.discord.mute", "Mute"),
        }}))
    result, pages = run(tmp_path, profile)
    main = load(pages / "Old.json")
    assert main["0x0"]["states"]["0"]["actions"][0]["id"] == "com_core447_MediaPlugin::PlayPause"
    assert main["0x0"]["states"]["0"]["media"]["path"]
    assert main["1x0"]["states"]["0"]["actions"][0]["settings"]["selected_page"] == str(pages / "Old - Sounds.json")
    sounds = load(pages / "Old - Sounds.json")
    assert sounds["1x0"]["states"]["0"]["actions"][0]["id"] == "com_imdevinc_StreamControllerDiscordPlugin::Mute"
    assert result.count("manual") == 0


def test_backups_with_several_profiles(tmp_path):
    first, second = tmp_path / "a.zip", tmp_path / "b.zip"
    make_v2_profile(first, name="Games", pages=[{"0,0": key(HOTKEY, "a", ctrl(ord("A")))}])
    make_v2_profile(second, name="Work", pages=[{"0,0": key(HOTKEY, "b", ctrl(ord("B")))}])
    backup = tmp_path / "all.streamDeckProfilesBackup"
    with zipfile.ZipFile(backup, "w") as out:
        for part in (first, second):
            with zipfile.ZipFile(part) as archive:
                for name in archive.namelist():
                    out.writestr(f"ProfilesV2/{name}", archive.read(name))
    result, _ = run(tmp_path, backup)
    assert sorted(p.stem for p in result.pages) == ["Games", "Work"]


def test_folders_copied_from_windows(tmp_path):
    profile = tmp_path / "x.streamDeckProfile"
    make_v2_profile(profile, pages=[{"0,0": key(HOTKEY, "a", ctrl(ord("A")))}])
    extracted = tmp_path / "extracted"
    with zipfile.ZipFile(profile) as archive:
        archive.extractall(extracted)
    folder = next(extracted.glob("*.sdProfile"))
    result, _ = run(tmp_path, folder)
    assert [p.stem for p in result.pages] == ["Gaming"]


def test_rejects_files_that_are_not_profiles(tmp_path):
    bogus = tmp_path / "bogus.streamDeckProfile"
    bogus.write_text("hello")
    with pytest.raises(ConversionError, match="not a zip"):
        run(tmp_path, bogus)
    empty = tmp_path / "empty.streamDeckProfile"
    with zipfile.ZipFile(empty, "w") as archive:
        archive.writestr("readme.txt", "nothing")
    with pytest.raises(ConversionError, match="no Stream Deck profile"):
        run(tmp_path, empty)


def test_every_mapping_is_documented():
    from tuxcast.convert.actions import MAPPINGS

    reference = (Path(__file__).parents[1] / "docs/reference/elgato-actions.md").read_text()
    missing = [uuid for uuid in MAPPINGS if f"`{uuid}`" not in reference]
    assert not missing, f"add these to docs/reference/elgato-actions.md: {missing}"


def test_profiles_with_the_same_name_do_not_overwrite_each_other(tmp_path):
    first, second = tmp_path / "a.zip", tmp_path / "b.zip"
    make_v2_profile(first, name="Default", pages=[{"0,0": key(HOTKEY, "a", ctrl(ord("A")))}])
    make_v2_profile(second, name="Default", pages=[{"0,0": key(HOTKEY, "b", ctrl(ord("B")))}])
    backup = tmp_path / "all.streamDeckProfilesBackup"
    with zipfile.ZipFile(backup, "w") as out:
        for part in (first, second):
            with zipfile.ZipFile(part) as archive:
                for entry in archive.namelist():
                    out.writestr(entry, archive.read(entry))
    result, pages = run(tmp_path, backup)
    assert sorted(p.stem for p in result.pages) == ["Default", "Default (2)"]
    assert len(list(pages.glob("*.json"))) == 2


@pytest.mark.parametrize("broken", [
    {"States": {"0": {}}, "UUID": HOTKEY},
    {"UUID": HOTKEY, "Settings": ["not", "a", "dict"]},
    {"UUID": HOTKEY, "Settings": {"Hotkeys": ["nope", 3]}},
    {"UUID": "com.elgato.streamdeck.system.multimedia", "Settings": {"actionIdx": "fast"}},
    {"UUID": "com.elgato.streamdeck.multiactions", "Actions": [{"Actions": None}]},
    {"UUID": 42, "Plugin": "x", "States": [{"Image": 7, "Title": None}]},
])
def test_malformed_keys_do_not_crash(tmp_path, broken):
    profile = tmp_path / "p.streamDeckProfile"
    make_v2_profile(profile, pages=[{"0,0": broken, "1,0": key(HOTKEY, "ok", ctrl(ord("A")))}])
    _, pages = run(tmp_path, profile)
    assert load(pages / "Gaming.json")["1x0"]["states"]["0"]["actions"]


def test_malformed_manifests_are_reported(tmp_path):
    profile = tmp_path / "p.streamDeckProfile"
    with zipfile.ZipFile(profile, "w") as archive:
        archive.writestr("X.sdProfile/manifest.json", "[1, 2]")
    with pytest.raises(ConversionError, match="expected an object"):
        run(tmp_path, profile)


def test_next_page_inside_a_folder_moves_from_its_page(tmp_path):
    folder_id = uuid.uuid4()
    profile = tmp_path / "p.streamDeckProfile"
    make_v2_profile(profile, pages=[
        {"0,0": key("com.elgato.streamdeck.page.next", "next")},
        {"0,0": key(FOLDER, "Tools", {"ProfileUUID": str(folder_id)})},
        {"0,0": key("com.elgato.streamdeck.page.next", "next")},
    ], folders=[(folder_id, {"1,0": key("com.elgato.streamdeck.page.next", "next")})])
    _, pages = run(tmp_path, profile)
    target = load(pages / "Gaming - Tools.json")["1x0"]["states"]["0"]["actions"][0]["settings"]["selected_page"]
    assert target == str(pages / "Gaming 3.json")  # the folder opens from page 2


def test_nothing_is_written_when_an_image_fails(tmp_path, monkeypatch):
    profile = tmp_path / "p.streamDeckProfile"
    make_v2_profile(profile, pages=[{"0,0": key(HOTKEY, "a", ctrl(ord("A")), image="Images/a.png")}])
    original = Path.write_bytes

    def failing(self, data):
        if self.suffix == ".json":
            raise PermissionError(13, "Permission denied", str(self))
        return original(self, data)

    monkeypatch.setattr(Path, "write_bytes", failing)
    with pytest.raises(ConversionError, match="Permission denied"):
        run(tmp_path, profile)


@pytest.mark.parametrize("url", ["javascript:alert(1)", "file:///etc/passwd", "steam://run/730"])
def test_websites_must_be_web_addresses(tmp_path, url):
    profile = tmp_path / "p.streamDeckProfile"
    make_v2_profile(profile, pages=[{"0,0": key("com.elgato.streamdeck.system.website", "x", {"path": url})}])
    result, pages = run(tmp_path, profile)
    assert load(pages / "Gaming.json")["0x0"]["states"]["0"]["actions"] == []
    assert "non-web address" in result.keys[0].notes[0]
