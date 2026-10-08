"""What each Elgato action becomes in StreamController.

Each Elgato action UUID maps to a function returning StreamController actions
(``{"id": "<plugin>::<action>", "settings": {...}}``). An action with no equivalent
returns nothing: its key keeps its image and title, and the report lists it.

Adding a mapping is the easiest way to contribute: see CONTRIBUTING.md.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field

from tuxcast.convert import keymap
from tuxcast.convert.elgato import Action

DECK = "com_core447_DeckPlugin"
OS = "com_core447_OSPlugin"
MEDIA = "com_core447_MediaPlugin"
OBS = "com_core447_OBSPlugin"
DISCORD = "com_imdevinc_StreamControllerDiscordPlugin"  # also the id of grantabell's maintained fork
TWITCH = "com_imdevinc_StreamControllerTwitchPlugin"

# StreamController plugins an action needs, by id prefix: name shown in the report
PLUGINS = {
    OS: "OS", MEDIA: "Media", OBS: "OBS", DISCORD: "Discord", TWITCH: "Twitch", DECK: "Deck",
}


@dataclass
class Context:
    layout: str = "us"
    pages: dict[str, str] = field(default_factory=dict)  # Elgato page id alias -> page json path
    resolve: Callable[[str], str | None] = lambda reference: None
    page_order: list[str] = field(default_factory=list)  # json paths of the profile's pages, in order
    current_page: int = 0
    notes: list[str] = field(default_factory=list)


Mapper = Callable[[Action, Context], list[dict]]
MAPPINGS: dict[str, Mapper] = {}


def maps(*uuids: str) -> Callable[[Mapper], Mapper]:
    def register(function: Mapper) -> Mapper:
        for uuid in uuids:
            MAPPINGS[uuid] = function
        return function
    return register


def action(identifier: str, **settings: object) -> dict:
    return {"id": identifier, "settings": settings}


def simple(identifier: str, **settings: object) -> Mapper:
    return lambda _action, _context: [action(identifier, **settings)]


def number(value: object, default: float) -> float:
    """A number from a setting users may have typed anything into."""
    try:
        result = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def setting(source: dict, *names: str, default: object = "") -> object:
    for name in names:
        if source.get(name) not in (None, ""):
            return source[name]
    return default


# --- system ------------------------------------------------------------------------------------

def hotkey_keys(hotkeys: list[dict], layout: str, notes: list[str]) -> list[list[int]]:
    """Elgato hotkeys to StreamController's [evdev code, 1 = press / 0 = release] list."""
    events: list[list[int]] = []
    for hotkey in hotkeys if isinstance(hotkeys, list) else []:
        if not isinstance(hotkey, dict):
            continue
        vk = keymap_vk(hotkey)
        modifiers = [code for flag, code in (("KeyCtrl", keymap.KEY_LEFTCTRL), ("KeyShift", keymap.KEY_LEFTSHIFT),
                                              ("KeyOption", keymap.KEY_LEFTALT), ("KeyCmd", keymap.KEY_LEFTMETA))
                     if hotkey.get(flag)]
        if vk is None and not modifiers:
            continue
        key = keymap.evdev(vk, layout) if vk is not None else None
        if vk is not None and key is None:
            notes.append(f"virtual key 0x{vk:02X} has no Linux equivalent")
            continue
        if vk in keymap.OEM_KEYS and layout != "us":
            notes.append("punctuation keys may land on a different key outside the US layout")
        pressed = [*modifiers, *([key] if key is not None else [])]
        events += [[code, 1] for code in pressed] + [[code, 0] for code in reversed(pressed)]
    return events


def keymap_vk(hotkey: dict) -> int | None:
    vk = hotkey.get("VKeyCode", -1)
    try:
        vk = int(vk)
    except (TypeError, ValueError):
        return None
    return vk if vk > 0 else None


@maps("com.elgato.streamdeck.system.hotkey", "com.elgato.streamdeck.system.hotkeyswitch")
def hotkey(source: Action, context: Context) -> list[dict]:
    keys = hotkey_keys(source.settings.get("Hotkeys", []), context.layout, context.notes)
    if source.uuid.endswith("hotkeyswitch"):
        context.notes.append("hotkey switch converted to its first hotkey")
    return [action(f"{OS}::Hotkey", keys=keys, delay=0.02, repeat=False, hold_until_release=False)] if keys else []


@maps("com.elgato.streamdeck.system.website")
def website(source: Action, _context: Context) -> list[dict]:
    url = str(setting(source.settings, "path", "url")).strip()
    if url and "://" not in url:
        url = "https://" + url
    return [action(f"{OS}::OpenInBrowser", url=url, new_window=False)] if url else []


@maps("com.elgato.streamdeck.system.open")
def open_(source: Action, context: Context) -> list[dict]:
    target = str(setting(source.settings, "path", "openInBrowser"))
    if target.startswith(("http://", "https://")):
        return [action(f"{OS}::OpenInBrowser", url=target, new_window=False)]
    context.notes.append(f"opens {target or 'an application'} on Windows/macOS: set a Linux command")
    return []


@maps("com.elgato.streamdeck.system.text")
def text(source: Action, _context: Context) -> list[dict]:
    value = str(setting(source.settings, "pastedText", "text"))
    if source.settings.get("isSendingEnter"):
        value += "\n"
    return [action(f"{OS}::WriteText", text=value, delay=0.01)] if value else []


MULTIMEDIA = {0: "PlayPause", 1: "Next", 2: "Previous"}
MULTIMEDIA_KEYS = {3: 113, 4: 115, 5: 114}  # mute, volume up, volume down


@maps("com.elgato.streamdeck.system.multimedia")
def multimedia(source: Action, _context: Context) -> list[dict]:
    index = int(number(setting(source.settings, "actionIdx", default=0), 0))
    if index in MULTIMEDIA:
        return [action(f"{MEDIA}::{MULTIMEDIA[index]}", player_name="")]
    if index in MULTIMEDIA_KEYS:
        code = MULTIMEDIA_KEYS[index]
        return [action(f"{OS}::Hotkey", keys=[[code, 1], [code, 0]], delay=0.02, repeat=False,
                       hold_until_release=False)]
    return []


@maps("com.elgato.streamdeck.system.delay", "com.elgato.streamdeck.multiactions.delay")
def delay(source: Action, _context: Context) -> list[dict]:
    milliseconds = number(setting(source.settings, "delay", "Delay", default=500), 500)
    return [action(f"{OS}::Delay", delay=milliseconds / 1000)]


@maps("com.elgato.streamdeck.multiactions", "com.elgato.streamdeck.multiactions.routine",
      "com.elgato.streamdeck.multiactions.routine2")
def multi(source: Action, context: Context) -> list[dict]:
    steps = []
    for child in source.children:
        steps += convert_action(child, context)
    return steps


# --- navigation --------------------------------------------------------------------------------

def change_page(path: str) -> dict:
    return action(f"{DECK}::ChangePage", selected_page=path, deck_number=None)


@maps("com.elgato.streamdeck.profile.openchild")
def folder(source: Action, context: Context) -> list[dict]:
    target = context.resolve(str(setting(source.settings, "ProfileUUID")))
    if target is None:
        context.notes.append("the folder this key opens was not found in the export")
        return []
    return [change_page(target)]


@maps("com.elgato.streamdeck.profile.backtoparent")
def back(_source: Action, _context: Context) -> list[dict]:
    return [action(f"{DECK}::GoToPreviousPage")]


@maps("com.elgato.streamdeck.page.next", "com.elgato.streamdeck.page.previous",
      "com.elgato.streamdeck.page.goto")
def page(source: Action, context: Context) -> list[dict]:
    if not context.page_order:
        return []
    count = len(context.page_order)
    if source.uuid.endswith("next"):
        index = (context.current_page + 1) % count
    elif source.uuid.endswith("previous"):
        index = (context.current_page - 1) % count
    else:
        index = int(number(setting(source.settings, "PageIndex", "pageIndex", "Page", default=1), 1)) - 1
        index = max(0, min(index, count - 1))
    return [change_page(context.page_order[index])]


@maps("com.elgato.streamdeck.profile.rotate", "com.elgato.streamdeck.profile.switchprofile")
def switch_profile(source: Action, context: Context) -> list[dict]:
    target = context.resolve(str(setting(source.settings, "ProfileUUID")))
    if target is None:
        context.notes.append("switches to a profile that is not part of this export")
        return []
    return [change_page(target)]


# --- OBS (Elgato's OBS Studio plugin) -------------------------------------------------------------

def obs_scene(source: Action, context: Context) -> list[dict]:
    scene = setting(source.settings, "sceneName", "scene", "sceneId")
    if not scene:
        context.notes.append("pick the OBS scene again")
    return [action(f"{OBS}::SwitchScene", scene=scene)]


def obs_input(identifier: str) -> Mapper:
    def mapper(source: Action, context: Context) -> list[dict]:
        name = setting(source.settings, "sourceName", "source", "inputName", "sourceId")
        if not name:
            context.notes.append("pick the OBS audio source again")
        return [action(f"{OBS}::{identifier}", input=name)]
    return mapper


OBS_PLUGIN = "com.elgato.obsstudio"
MAPPINGS[f"{OBS_PLUGIN}.scene"] = obs_scene
MAPPINGS[f"{OBS_PLUGIN}.stream"] = simple(f"{OBS}::ToggleStream")
MAPPINGS[f"{OBS_PLUGIN}.record"] = simple(f"{OBS}::ToggleRecord")
MAPPINGS[f"{OBS_PLUGIN}.replaybuffer"] = simple(f"{OBS}::ToggleReplayBuffer")
MAPPINGS[f"{OBS_PLUGIN}.savereplay"] = simple(f"{OBS}::SaveReplayBuffer")
MAPPINGS[f"{OBS_PLUGIN}.studiomode"] = simple(f"{OBS}::ToggleStudioMode")
MAPPINGS[f"{OBS_PLUGIN}.virtualcam"] = simple(f"{OBS}::ToggleVirtualCamera")
MAPPINGS[f"{OBS_PLUGIN}.transition"] = simple(f"{OBS}::TriggerTransition")
MAPPINGS[f"{OBS_PLUGIN}.mixeraudio"] = obs_input("ToggleInputMute")

# --- Discord (Elgato's Discord plugin) ------------------------------------------------------------

for _name, _target in (("mute", "Mute"), ("deafen", "Deafen"), ("pushtotalk", "Push_To_Talk"),
                       ("pushtomute", "Push_To_Talk"), ("voicechannel", "ChangeVoiceChannel"),
                       ("textchannel", "ChangeTextChannel")):
    MAPPINGS[f"com.elgato.discord.{_name}"] = simple(f"{DISCORD}::{_target}")

# --- Twitch (Elgato's Twitch plugin) --------------------------------------------------------------

MAPPINGS["com.elgato.twitch.clip"] = simple(f"{TWITCH}::Clip")
MAPPINGS["com.elgato.twitch.marker"] = simple(f"{TWITCH}::Marker")
MAPPINGS["com.elgato.twitch.viewers"] = simple(f"{TWITCH}::ShowViewers")
MAPPINGS["com.elgato.twitch.ad"] = lambda source, _context: [
    action(f"{TWITCH}::PlayAd", ad={"duration": str(setting(source.settings, "duration", "length", default=60))})]
MAPPINGS["com.elgato.twitch.chatmessage"] = lambda source, _context: [
    action(f"{TWITCH}::SendMessage",
           chat={"message_text": str(setting(source.settings, "message", "text")), "channel_id": ""})]


def convert_action(source: Action, context: Context) -> list[dict]:
    mapper = MAPPINGS.get(source.uuid)
    return mapper(source, context) if mapper else []


def is_known(uuid: str) -> bool:
    return uuid in MAPPINGS
