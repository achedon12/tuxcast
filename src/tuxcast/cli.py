"""Command line interface."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

from tuxcast import __version__, audio, bridge, deck, doctor, patch, paths, systemd, ui
from tuxcast.system import System

DOCS = "https://achedon12.github.io/tuxcast"

SYMBOLS = {
    doctor.Status.OK: ("✔", "green"),
    doctor.Status.INFO: ("•", "blue"),
    doctor.Status.WARN: ("⚠", "yellow"),
    doctor.Status.FAIL: ("✖", "red"),
    doctor.Status.SKIP: ("○", "dim"),
}


# --- doctor --------------------------------------------------------------------------------------

def cmd_doctor(args: argparse.Namespace) -> int:
    only = [key.strip() for key in args.only.split(",")] if args.only else []
    unknown = [key for key in only if key not in doctor.TOPIC_ORDER]
    if unknown:
        ui.error(f"unknown topic: {', '.join(unknown)} (topics: {', '.join(doctor.TOPIC_ORDER)})")
        return 2
    results = doctor.run(System(), only)

    if args.json:
        print(json.dumps(doctor.as_json(results), indent=2))
    else:
        ui.title(f"tuxcast doctor {ui.style('v' + __version__, 'dim')}")
        for topic, findings in results:
            ui.section(topic.title)
            for finding in findings:
                symbol, colour = SYMBOLS[finding.status]
                print(f"  {ui.style(symbol, colour)} {ui.clean(finding.summary)}")
                if finding.detail and (args.verbose or finding.status in (doctor.Status.WARN, doctor.Status.FAIL)
                                       or finding.status is doctor.Status.INFO):
                    print(ui.style(f"      {ui.clean(finding.detail)}", "dim"))
                if finding.fix:
                    print(f"      {ui.style('fix:', 'cyan')} {ui.clean(finding.fix)}")
        statuses = [f.status for _, findings in results for f in findings]
        failed, warned = statuses.count(doctor.Status.FAIL), statuses.count(doctor.Status.WARN)
        print()
        if failed or warned:
            summary = ", ".join(part for part in (
                f"{failed} problem{'s' * (failed > 1)}" if failed else "",
                f"{warned} warning{'s' * (warned > 1)}" if warned else "") if part)
            print(f"{ui.style(summary, 'bold', 'red' if failed else 'yellow')}. Guides: {DOCS}/guides/")
        else:
            print(ui.style("Everything looks ready to go live.", "bold", "green"))
    return 1 if any(f.status is doctor.Status.FAIL for _, fs in results for f in fs) else 0


# --- convert -------------------------------------------------------------------------------------

def detect_layout() -> str:
    from tuxcast.convert import keymap

    for command in (["setxkbmap", "-query"], ["localectl", "status"]):
        try:
            out = subprocess.run(command, capture_output=True, text=True, timeout=3, check=False).stdout
        except (OSError, subprocess.TimeoutExpired):
            continue
        for line in out.splitlines():
            if "layout" in line.lower() and ":" in line:
                return keymap.layout_from_xkb(line.split(":", 1)[1])
    return "us"


def cmd_convert(args: argparse.Namespace) -> int:
    from tuxcast.convert import ConversionError, convert

    data = paths.streamcontroller_data_dir()
    pages_dir = Path(args.pages_dir).expanduser() if args.pages_dir else data / "pages"
    assets_dir = Path(args.assets_dir).expanduser() if args.assets_dir else data / "Assets" / "tuxcast"
    layout = args.layout or detect_layout()
    try:
        result = convert(Path(args.profile).expanduser(), pages_dir, assets_dir, name=args.name,
                         layout=layout, dry_run=args.dry_run, force=args.force)
    except ConversionError as exc:
        ui.error(str(exc))
        return 1

    verb = "Would write" if args.dry_run else "Wrote"
    ui.title(f"{verb} {len(result.pages)} page{'s' * (len(result.pages) > 1)} to {pages_dir}")
    for page in result.pages:
        ui.info(f"• {ui.clean(page.stem)}")
    print()
    total = len(result.keys)
    images = f"{result.images} image{'s' * (result.images != 1)}"
    ui.success(f"{result.count('converted')}/{total} keys converted, {images} copied (keyboard layout: {layout})")
    for status, colour, heading in (("partial", "yellow", "Converted, check these"),
                                    ("manual", "red", "Redo these by hand")):
        keys = [k for k in result.keys if k.status == status]
        if not keys:
            continue
        ui.section(f"{heading} ({len(keys)})")
        for key in keys:
            title = f" “{key.title}”" if key.title else ""
            line = f"{key.page} [{key.position}]{title}: {'; '.join(key.notes) or key.uuid}"
            print(f"  {ui.style('•', colour)} {ui.clean(line)}")
    for warning in result.warnings:
        ui.warning(ui.clean(warning))
    if result.plugins:
        ui.section("StreamController plugins these pages use")
        ui.info(", ".join(sorted(result.plugins)) + "  (install them from the StreamController store)")
    if not args.dry_run:
        print()
        ui.info("Restart StreamController, then pick the page in its page list.")
    return 0


# --- bridge --------------------------------------------------------------------------------------

def cmd_bridge_discord(args: argparse.Namespace) -> int:
    system = System()
    if args.uninstall:
        removed = systemd.uninstall([bridge.UNIT])
        ui.success("Removed the login service" if removed else "No login service was installed")
        return 0

    links = bridge.plan(system)
    changed = [] if args.dry_run else bridge.apply(links)
    if not args.quiet:
        if not links:
            ui.info("No link needed: no Discord outside the folder clients scan was found.")
        for link in links:
            mark = "+" if link in changed or args.dry_run else "="
            ui.info(f"{mark} {link.path} → {link.target}  ({link.variant.name})")

    for app in args.app or bridge.default_clients(system):
        if args.dry_run or args.no_grant:
            ui.hint(" ".join(bridge.grant_command(app, links)))
            continue
        error = bridge.grant(app, links)
        if not error:
            if not args.quiet:
                ui.success(f"{app} may now reach Discord (restart it to apply)")
        else:
            ui.error(f"flatpak override failed for {app}: {error}")

    if args.install and not args.dry_run:
        systemd.install({bridge.UNIT: bridge.unit(systemd.tuxcast_command())}, enable=[bridge.UNIT])
        if not args.quiet:
            ui.success(f"Installed {bridge.UNIT}: the bridge comes back at every login")
    return 0


# --- audio ---------------------------------------------------------------------------------------

def restart_pipewire(requested: bool) -> None:
    if requested:
        if audio.restart():
            ui.success("PipeWire restarted")
        else:
            ui.error("PipeWire could not be restarted: " + " ".join(audio.RESTART))
    else:
        ui.hint("Apply now with: " + " ".join(audio.RESTART) + "   (cuts sound for a second), or log out and in.")


def cmd_audio_setup(args: argparse.Namespace) -> int:
    try:
        sinks = audio.parse_sinks(args.sinks)
    except ValueError as exc:
        ui.error(str(exc))
        return 2
    path = audio.setup(sinks)
    ui.success(f"Declared {len(sinks)} sinks in {path}")
    for sink in sinks:
        ui.info(f"• {sink.description}  ({sink.node})")
    restart_pipewire(args.restart)
    ui.hint("Then send apps to them: tuxcast audio route <app> <sink>, and add each sink to OBS "
            "as an Audio Output Capture.")
    return 0


def cmd_audio_remove(args: argparse.Namespace) -> int:
    if not audio.remove():
        ui.success("No tuxcast sinks are configured")
        return 0
    ui.success(f"Removed {audio.drop_in_path()}")
    restart_pipewire(args.restart)
    return 0


def cmd_audio_status(_args: argparse.Namespace) -> int:
    configured = audio.configured()
    ui.section("Sinks")
    if configured:
        for name in configured:
            ui.info(f"• {name}")
    else:
        ui.info("None. Create them with: tuxcast audio setup")
    ui.section("Apps playing now")
    streams = audio.playing(System())
    for stream in streams:
        ui.info(ui.clean(f"• {stream.application}  → sink {stream.sink}  (#{stream.index})"))
    if not streams:
        ui.info("None")
    return 0


def cmd_audio_route(args: argparse.Namespace) -> int:
    sink = args.sink if args.sink.startswith(audio.PREFIX) or args.sink.isdigit() else audio.PREFIX + args.sink
    matches = [s for s in audio.playing(System()) if args.app.lower() in s.application.lower()]
    if not matches:
        ui.error(f"no app named like {args.app!r} is playing sound right now")
        return 1
    for stream in matches:
        error = audio.move(stream.index, sink)
        if error:
            ui.error(ui.clean(f"{stream.application}: {error}"))
            return 1
        ui.success(ui.clean(f"{stream.application} → {sink}"))
    ui.hint("PipeWire remembers this choice for the next time the app plays.")
    return 0


# --- deck ----------------------------------------------------------------------------------------

def cmd_deck_list(_args: argparse.Namespace) -> int:
    system = System()
    found = deck.decks(system)
    if not found:
        ui.info("No Stream Deck plugged in")
        return 1
    for item in found:
        access = "ok" if deck.accessible(system, item) else ui.style("no permission (tuxcast deck udev)", "red")
        ui.info(f"• {item.name}  {item.node}  serial {item.serial or '?'}  {access}")
    return 0


def cmd_deck_reset(_args: argparse.Namespace) -> int:
    found = deck.decks(System())
    if not found:
        ui.error("No Stream Deck plugged in")
        return 1
    status = 0
    for item in found:
        try:
            deck.reset(item.node)
        except OSError as exc:
            ui.error(f"{item.name} ({item.node}): {exc.strerror}. Is the udev rule installed? (tuxcast deck udev)")
            status = 1
        else:
            ui.success(f"Reset {item.name} ({item.node}). Restart StreamController if it was running.")
    return status


def cmd_deck_udev(_args: argparse.Namespace) -> int:
    # the rule alone goes to stdout, so it can be piped straight into the rules file
    print(deck.UDEV_RULE, end="")
    print(ui.style(f"\nInstall it (needs root once):\n  tuxcast deck udev | sudo tee {deck.UDEV_RULE_PATH}"
                   "\n  sudo udevadm control --reload && sudo udevadm trigger", "dim"), file=sys.stderr)
    return 0


# --- patch ---------------------------------------------------------------------------------------

def load_patches() -> list[patch.Patch] | None:
    try:
        return patch.load_all()
    except patch.PatchError as exc:
        ui.error(str(exc))
        return None


def cmd_patch_list(_args: argparse.Namespace) -> int:
    patches = load_patches()
    if patches is None:
        return 1
    if not patches:
        ui.info(f"No patches in {patch.folder()}. Examples: {DOCS}/guides/patches/")
        return 0
    for item in patches:
        state = patch.apply(item, dry_run=True).state
        label = {"applied": "needs applying", "unchanged": "applied", "missing": "file missing",
                 "no-match": "pattern not found", "error": "error"}[state]
        ui.info(f"• {item.name}: {label}  ({item.file})")
    return 0


def cmd_patch_apply(args: argparse.Namespace) -> int:
    patches = load_patches()
    if patches is None:
        return 1
    status = 0
    for item in patches:
        outcome = patch.apply(item, dry_run=args.dry_run)
        if outcome.state == "applied":
            if not args.quiet:
                ui.success(f"{item.name}: {'would patch' if args.dry_run else 'patched'} {item.file}")
        elif outcome.state == "no-match":
            ui.warning(f"{item.name}: no pattern matches {item.file}: the app may have changed")
            status = 1
        elif outcome.state == "error":
            ui.error(f"{item.name}: {outcome.error}")
            status = 1
        elif not args.quiet:
            ui.info(f"{item.name}: {'already applied' if outcome.state == 'unchanged' else 'file not found'}")
    return status


def cmd_patch_install(_args: argparse.Namespace) -> int:
    patches = load_patches()
    if not patches:
        ui.error(f"No patches to watch in {patch.folder()}")
        return 1
    systemd.install(patch.units(patches, systemd.tuxcast_command()),
                    enable=["tuxcast-patch.path"], start=["tuxcast-patch.path", "tuxcast-patch.service"])
    ui.success("Patches are now re-applied whenever these folders change:")
    for folder in sorted({str(p.watch) for p in patches}):
        ui.info(f"• {folder}")
    return 0


def cmd_patch_uninstall(_args: argparse.Namespace) -> int:
    removed = systemd.uninstall(["tuxcast-patch.path", "tuxcast-patch.service"])
    ui.success("Removed the patch watcher" if removed else "The patch watcher was not installed")
    return 0


# --- ui ------------------------------------------------------------------------------------------

def cmd_ui(args: argparse.Namespace) -> int:
    import webbrowser

    from tuxcast.dashboard import Dashboard, serve

    dashboard = Dashboard(layout=args.layout or detect_layout())
    try:
        server = serve(dashboard, args.port)
    except OSError as exc:
        ui.error(f"cannot listen on port {args.port}: {exc.strerror}")
        return 1
    url = f"http://127.0.0.1:{server.server_address[1]}/?token={dashboard.token}"
    ui.title("tuxcast dashboard")
    ui.info(url)
    ui.info(ui.style("Local only: it runs on this machine. Ctrl+C to stop.", "dim"))
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
    finally:
        server.server_close()
        dashboard.close()
    return 0


# --- parser --------------------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tuxcast",
        description="The toolkit for streaming on Linux.",
        epilog=f"Documentation: {DOCS}",
    )
    parser.add_argument("--version", action="version", version=f"tuxcast {__version__}")
    commands = parser.add_subparsers(dest="command", metavar="<command>")

    p = commands.add_parser("doctor", help="check your streaming setup and explain the fixes")
    p.add_argument("--only", metavar="TOPICS", help=f"comma-separated topics: {','.join(doctor.TOPIC_ORDER)}")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    p.add_argument("-v", "--verbose", action="store_true", help="show details of passing checks too")
    p.set_defaults(handler=cmd_doctor)

    p = commands.add_parser("ui", help="open the dashboard in your browser")
    p.add_argument("--port", type=int, default=0, help="port to listen on (default: a free one)")
    p.add_argument("--no-browser", action="store_true", help="print the address without opening it")
    p.add_argument("--layout", help="keyboard layout for converted hotkeys (default: detected)")
    p.set_defaults(handler=cmd_ui)

    p = commands.add_parser("convert", help="convert an Elgato Stream Deck profile to StreamController pages")
    p.add_argument("profile", help=".streamDeckProfile, .streamDeckProfilesBackup or .sdProfile folder")
    p.add_argument("--name", help="name of the pages (default: the profile's name)")
    p.add_argument("--layout", help="keyboard layout the hotkeys were recorded with (default: detected)")
    p.add_argument("--pages-dir", help="where to write pages (default: StreamController's pages folder)")
    p.add_argument("--assets-dir", help="where to copy key images")
    p.add_argument("-n", "--dry-run", action="store_true", help="show what would be converted, write nothing")
    p.add_argument("-f", "--force", action="store_true", help="overwrite pages that already exist")
    p.set_defaults(handler=cmd_convert)

    p = commands.add_parser("bridge", help="connect apps that cannot see each other")
    bridges = p.add_subparsers(dest="bridge", metavar="<bridge>", required=True)
    b = bridges.add_parser("discord", help="expose Discord's IPC socket to every client")
    b.add_argument("--install", action="store_true", help="also recreate the bridge at every login")
    b.add_argument("--uninstall", action="store_true", help="remove the login service")
    b.add_argument("--app", action="append", metavar="APP_ID", help="Flatpak client to grant access (repeatable)")
    b.add_argument("--no-grant", action="store_true", help="print the flatpak override instead of running it")
    b.add_argument("-n", "--dry-run", action="store_true")
    b.add_argument("-q", "--quiet", action="store_true")
    b.set_defaults(handler=cmd_bridge_discord)

    p = commands.add_parser("audio", help="separate sinks for game, music, voice and alerts")
    sub = p.add_subparsers(dest="action", metavar="<action>", required=True)
    a = sub.add_parser("setup", help="create the sinks")
    a.add_argument("--sinks", default=",".join(audio.DEFAULT_SINKS), help="comma-separated (default: %(default)s)")
    a.add_argument("--restart", action="store_true", help="restart PipeWire now to create them")
    a.set_defaults(handler=cmd_audio_setup)
    a = sub.add_parser("remove", help="remove the sinks")
    a.add_argument("--restart", action="store_true")
    a.set_defaults(handler=cmd_audio_remove)
    sub.add_parser("status", help="show the sinks and what plays where").set_defaults(handler=cmd_audio_status)
    a = sub.add_parser("route", help="send an app to a sink, e.g. route spotify music")
    a.add_argument("app")
    a.add_argument("sink")
    a.set_defaults(handler=cmd_audio_route)

    p = commands.add_parser("deck", help="Stream Deck hardware: list, reset, permissions")
    sub = p.add_subparsers(dest="action", metavar="<action>", required=True)
    sub.add_parser("list", help="list plugged decks").set_defaults(handler=cmd_deck_list)
    sub.add_parser("reset", help="recover a deck stuck after a crash").set_defaults(handler=cmd_deck_reset)
    sub.add_parser("udev", help="print the udev rule that grants access").set_defaults(handler=cmd_deck_udev)

    p = commands.add_parser("patch", help="re-apply local fixes that app updates wipe")
    sub = p.add_subparsers(dest="action", metavar="<action>", required=True)
    sub.add_parser("list", help="show patches and their state").set_defaults(handler=cmd_patch_list)
    a = sub.add_parser("apply", help="apply every patch")
    a.add_argument("-n", "--dry-run", action="store_true")
    a.add_argument("-q", "--quiet", action="store_true")
    a.set_defaults(handler=cmd_patch_apply)
    sub.add_parser("install", help="re-apply when watched folders change").set_defaults(handler=cmd_patch_install)
    sub.add_parser("uninstall", help="stop watching").set_defaults(handler=cmd_patch_uninstall)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "handler", None):
        parser.print_help()
        return 0
    if os.geteuid() == 0 and args.command != "deck":
        ui.warning("tuxcast configures your user session: run it without sudo.")
    try:
        return args.handler(args)
    except systemd.SystemdError as exc:
        ui.error(f"{exc}. Is a systemd user session running (not over plain SSH or in a container)?")
        return 1
    except KeyboardInterrupt:
        return 130
    except BrokenPipeError:
        sys.stderr.close()
        return 0
