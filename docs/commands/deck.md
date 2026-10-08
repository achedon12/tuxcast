# tuxcast deck

Stream Deck hardware: who may use it, which decks are plugged in, and how to recover one.

```sh
tuxcast deck list    # plugged decks, their USB node and whether you can open them
tuxcast deck udev    # the udev rule giving your user access, and how to install it
tuxcast deck reset   # recover a deck that froze after a crash
```

## Permissions

Linux only lets root open USB devices unless a udev rule says otherwise. Without one,
StreamController sees no deck. `tuxcast deck udev` prints the rule:

```text
SUBSYSTEM=="usb", ATTRS{idVendor}=="0fd9", TAG+="uaccess"
KERNEL=="hidraw*", ATTRS{idVendor}=="0fd9", TAG+="uaccess"
```

`uaccess` grants access to whoever is logged in at the screen, which is what you want on a
desktop. Install it once (this is the only step in tuxcast that needs root):

```sh
tuxcast deck udev | sudo tee /etc/udev/rules.d/70-streamdeck.rules
sudo udevadm control --reload && sudo udevadm trigger
```

The StreamController Flatpak installs an equivalent rule on many distributions; `tuxcast
doctor` tells you whether you need it.

## Reset

When an app crashes while talking to the deck, the deck can stay stuck: keys go dark and
the app logs `Failed to read feature report (-1)`. Unplugging fixes it; `tuxcast deck reset`
does the same through a USB reset (`USBDEVFS_RESET`), without touching the cable. Restart
StreamController afterwards.

## Supported models

Stream Deck (original, v2, MK.2, scissor keys), Mini (both versions), XL (both versions), +,
Neo and Pedal. Other Elgato devices share the same USB vendor id (Cam Link, HD60, Wave
microphones, Facecam) and are deliberately ignored: `tuxcast deck reset` would otherwise drop
your capture card or microphone. A deck model missing from this list?
[Open an issue](https://github.com/achedon12/tuxcast/issues/new?template=bug_report.yml) with
the output of `lsusb | grep 0fd9`.
