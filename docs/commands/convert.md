# tuxcast convert

Turns Elgato Stream Deck profiles into [StreamController](https://streamcontroller.core447.com/)
pages, so switching to Linux does not mean rebuilding every key by hand.

```sh
tuxcast convert Streaming.streamDeckProfile
```

```text
Wrote 3 pages to ~/.var/app/com.core447.StreamController/data/pages
  • Streaming
  • Streaming 2
  • Streaming - Scenes

✔ 13/15 keys converted, 12 images copied (keyboard layout: fr)

Redo these by hand (2)
  • Streaming [2,1] “Airhorn”: no StreamController equivalent for com.elgato.streamdeck.soundboard.playaudio
  • Streaming - Scenes [2,0] “Game”: opens C:\Games\game.exe on Windows/macOS: set a Linux command

StreamController plugins these pages use
  Deck, Discord, OBS, Twitch  (install them from the StreamController store)
```

Restart StreamController and pick the page in its page list.

## Getting your profile out of Windows or macOS

=== "Export one profile"

    In the Stream Deck app: **Preferences → Profiles**, select the profile, then
    **⋯ → Export**. You get a `.streamDeckProfile` file.

=== "Every profile at once"

    **Preferences → General → Create backup** gives a `.streamDeckProfilesBackup`. tuxcast
    converts every profile inside it.

=== "Copy the folder"

    The profiles live in `%appdata%\Elgato\StreamDeck\ProfilesV2` (Windows) or
    `~/Library/Application Support/com.elgato.StreamDeck/ProfilesV2` (macOS). Copy a
    `.sdProfile` folder, or the whole `ProfilesV2` folder, and pass it to tuxcast.

## What is converted

| Elgato | StreamController |
| --- | --- |
| Pages | One page each: `Name`, `Name 2`, `Name 3`… |
| Folders | A page named `Name - <folder title>`, with a back key |
| Key images | Copied next to StreamController's assets |
| Titles | Labels, with their position, color and size |
| Multi actions | Several actions on the same key, delays included |
| Hotkeys | Key presses, [translated for your keyboard layout](#keyboard-layouts) |
| Websites, text, media keys | OS and Media plugin actions |
| OBS, Discord, Twitch | Actions of the matching StreamController plugins |

The full list is in the [Elgato actions reference](../reference/elgato-actions.md). Anything
else keeps its image and title, and the report tells you which keys to finish by hand.

## Options

| Option | |
| --- | --- |
| `--name NAME` | Name the pages `NAME`, `NAME 2`… instead of the profile's name |
| `--layout LAYOUT` | Keyboard layout the hotkeys were recorded with: `us`, `fr`, `be`, `de`, `ch`, `at`, `cz`, `hu`. Detected from your session by default |
| `--pages-dir DIR` | Where to write pages (default: StreamController's, Flatpak or native) |
| `--assets-dir DIR` | Where to copy images |
| `-n`, `--dry-run` | Show the report, write nothing |
| `-f`, `--force` | Overwrite pages that already exist |

## Keyboard layouts

Elgato records hotkeys as Windows *virtual keys*, which name the character a key types.
Linux sends *key codes*, which name the physical key on a US keyboard. On AZERTY, the key
labelled **A** is the one a US keyboard labels **Q**: converted naively, your `Ctrl+A` would
become `Ctrl+Q`. tuxcast moves letters back to the right physical key for AZERTY and QWERTZ
layouts. Punctuation keys differ on every layout and are only exact on US; the report flags
hotkeys that use them.

## Limits

- **Stream Deck + dials** are not converted (StreamController pages handle them differently);
  the report counts them.
- **Programs** opened by path (`C:\…\game.exe`) need a Linux command.
- **Soundboard** and third-party plugin actions keep their key but need an action.

Found an action that should convert? [Open an issue](https://github.com/achedon12/tuxcast/issues/new?template=elgato_action.yml)
with its UUID from the report.
