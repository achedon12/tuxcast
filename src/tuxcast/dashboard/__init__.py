"""``tuxcast ui``: a local dashboard for everything the command line does.

The dashboard is a small web app served by Python's standard library, so it adds no
dependency. It only listens on 127.0.0.1 and every API call must carry the random token
printed at start-up, which other websites open in the same browser cannot know. The Host
header is checked too, so a hostile page cannot reach it through DNS rebinding either.
"""

from __future__ import annotations

import hmac
import json
import re
import secrets
import shutil
import tempfile
import threading
from collections.abc import Callable
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from tuxcast import __version__, audio, bridge, deck, doctor, patch, paths, streamcontroller, systemd
from tuxcast.convert import ConversionError, convert, keymap
from tuxcast.system import System

MAX_UPLOAD = 64 * 1024 * 1024
MAX_UPLOADS = 10  # profiles kept for converting; older ones are deleted
STATIC = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/app.css": ("app.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/logo.svg": ("logo.svg", "image/svg+xml"),
    **{f"/fonts/{name}.woff2": (f"fonts/{name}.woff2", "font/woff2") for name in (
        "Barlow-Regular", "Barlow-Medium", "Barlow-SemiBold", "Barlow-Bold",
        "BarlowCondensed-SemiBold", "BarlowCondensed-Bold")},
}
SECURITY_HEADERS = {
    "Content-Security-Policy": "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; "
                               "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
}


class ApiError(Exception):
    def __init__(self, status: HTTPStatus, message: str):
        super().__init__(message)
        self.status = status


class Dashboard:
    """The state of one `tuxcast ui` session: its token, uploads and the routes of its API."""

    def __init__(self, system_factory: Callable[[], System] = System, *, layout: str = "us",
                 pages_dir: Path | None = None, assets_dir: Path | None = None):
        self.token = secrets.token_urlsafe(24)
        self.system_factory = system_factory
        self.layout = layout
        data = paths.streamcontroller_data_dir()
        self.pages_dir = pages_dir or data / "pages"
        self.assets_dir = assets_dir or data / "Assets" / "tuxcast"
        self.uploads_dir = Path(tempfile.mkdtemp(prefix="tuxcast-ui-"))
        self.uploads: dict[str, Path] = {}
        self.lock = threading.Lock()  # one change at a time: two clicks must not race on the same files
        self.routes: dict[tuple[str, str], Callable[[dict], object]] = {
            ("GET", "/api/overview"): self.overview,
            ("GET", "/api/doctor"): self.doctor,
            ("GET", "/api/deck"): self.deck,
            ("POST", "/api/deck/reset"): self.deck_reset,
            ("POST", "/api/convert/preview"): self.convert_preview,
            ("POST", "/api/convert"): self.convert,
            ("GET", "/api/audio"): self.audio,
            ("POST", "/api/audio/setup"): self.audio_setup,
            ("POST", "/api/audio/remove"): self.audio_remove,
            ("POST", "/api/audio/route"): self.audio_route,
            ("POST", "/api/audio/volume"): self.audio_volume,
            ("POST", "/api/audio/mute"): self.audio_mute,
            ("GET", "/api/discord"): self.discord,
            ("POST", "/api/discord"): self.discord_fix,
            ("GET", "/api/patches"): self.patches,
            ("POST", "/api/patches/apply"): self.patches_apply,
            ("POST", "/api/patches/watch"): self.patches_watch,
        }

    def close(self) -> None:
        shutil.rmtree(self.uploads_dir, ignore_errors=True)

    def authorized(self, token: str | None) -> bool:
        return token is not None and hmac.compare_digest(token, self.token)

    # --- overview and doctor -------------------------------------------------------------------

    def overview(self, _body: dict) -> dict:
        system = self.system_factory()
        return {
            "version": __version__,
            "decks": [{"name": d.name} for d in deck.decks(system)],
            "layout": self.layout,
            "layouts": keymap.LAYOUTS,
        }

    def doctor(self, _body: dict) -> list[dict]:
        return doctor.as_json(doctor.run(self.system_factory()))

    # --- Stream Deck -----------------------------------------------------------------------------

    def deck(self, _body: dict) -> dict:
        system = self.system_factory()
        return {
            "decks": [{"name": d.name, "node": d.node, "serial": d.serial, "accessible": deck.accessible(system, d),
                       "columns": d.grid[0], "rows": d.grid[1]} for d in deck.decks(system)],
            "pages": [{"name": p.name, "keys": [vars(k) for k in p.keys]}
                      for p in streamcontroller.pages(self.pages_dir)],
            "udev": deck.UDEV_RULE,
            "udevPath": str(deck.UDEV_RULE_PATH),
            "pagesDir": str(self.pages_dir),
        }

    def deck_reset(self, _body: dict) -> dict:
        results = []
        for item in deck.decks(self.system_factory()):
            try:
                deck.reset(item.node)
                results.append({"name": item.name, "ok": True})
            except OSError as exc:
                results.append({"name": item.name, "ok": False, "error": exc.strerror or str(exc)})
        if not results:
            raise ApiError(HTTPStatus.NOT_FOUND, "No Stream Deck is plugged in.")
        return {"results": results}

    def convert_preview(self, body: dict) -> dict:
        upload = body["_upload"]
        result = self._convert(upload, dry_run=True)
        return {"upload": upload.parent.name, "file": upload.name, **self._report(result)}

    def convert(self, body: dict) -> dict:
        upload = self.uploads.get(str(body.get("upload", "")))
        if upload is None:
            raise ApiError(HTTPStatus.NOT_FOUND, "That profile is no longer here. Drop it again.")
        name = str(body.get("name") or "").strip() or None
        layout = str(body.get("layout") or self.layout)
        if layout not in keymap.LAYOUTS:
            raise ApiError(HTTPStatus.BAD_REQUEST, f"Unknown keyboard layout {layout!r}.")
        with self.lock:
            result = self._convert(upload, name=name, layout=layout, force=bool(body.get("force")))
        return {"written": [str(p) for p in result.pages], "pagesDir": str(self.pages_dir), **self._report(result)}

    def _convert(self, upload: Path, **options) -> object:
        options.setdefault("layout", self.layout)
        try:
            return convert(upload, self.pages_dir, self.assets_dir, **options)
        except ConversionError as exc:
            raise ApiError(HTTPStatus.UNPROCESSABLE_ENTITY, str(exc)) from exc

    @staticmethod
    def _report(result) -> dict:
        return {
            "pages": [{"name": p.name, "columns": p.columns, "rows": p.rows, "folder": p.folder,
                       "keys": [{"column": k.column, "row": k.row, "title": k.title, "status": k.status,
                                 "notes": list(k.notes), "image": k.image} for k in p.keys]}
                      for p in result.previews],
            "converted": result.count("converted"),
            "total": len(result.keys),
            "images": result.images,
            "plugins": sorted(result.plugins),
            "warnings": result.warnings,
        }

    # --- audio -----------------------------------------------------------------------------------

    def audio(self, _body: dict) -> dict:
        system = self.system_factory()
        states = audio.sink_states(system)
        default = audio.default_sink(system)
        streams = audio.playing(system)
        strips = []
        for state in states:
            ours = state.name.startswith(audio.PREFIX)
            if not ours and state.name != default:
                continue
            strips.append({
                "index": state.index, "name": state.name, "ours": ours, "default": state.name == default,
                "label": audio.Sink(state.name.removeprefix(audio.PREFIX)).description.removeprefix("Stream · ")
                if ours else "Your output",
                "detail": state.description, "volume": state.volume, "muted": state.muted,
                "apps": [{"index": s.index, "application": s.application} for s in streams if s.sink == state.index],
            })
        strips.sort(key=lambda strip: (strip["default"], strip["name"]))  # your output goes last, like a master
        return {
            "configured": audio.configured(),
            "defaults": audio.DEFAULT_SINKS,
            "descriptions": {key: audio.Sink(key).description for key in audio.DESCRIPTIONS},
            "strips": strips,
            "elsewhere": [{"index": s.index, "application": s.application} for s in streams
                          if s.sink not in {strip["index"] for strip in strips}],
        }

    def audio_setup(self, body: dict) -> dict:
        keys = body.get("sinks")
        if not isinstance(keys, list) or not keys:
            raise ApiError(HTTPStatus.BAD_REQUEST, "Pick at least one sink.")
        try:
            sinks = audio.parse_sinks(",".join(str(k) for k in keys))
        except ValueError as exc:
            raise ApiError(HTTPStatus.BAD_REQUEST, str(exc).capitalize() + ".") from exc
        with self.lock:
            path = audio.setup(sinks)
            restarted = audio.restart() if body.get("restart") else False
        return {"path": str(path), "restarted": restarted}

    def audio_remove(self, body: dict) -> dict:
        with self.lock:
            removed = audio.remove()
            restarted = audio.restart() if body.get("restart") and removed else False
        return {"removed": removed, "restarted": restarted}

    def audio_route(self, body: dict) -> dict:
        stream, sink = str(body.get("stream", "")), str(body.get("sink", ""))
        if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,160}", sink):
            raise ApiError(HTTPStatus.BAD_REQUEST, "Invalid sink name.")
        error = audio.move(stream, sink)
        if error:
            raise ApiError(HTTPStatus.UNPROCESSABLE_ENTITY, error)
        return {"ok": True}

    def _sink(self, body: dict) -> str:
        sink = str(body.get("sink", ""))
        if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,160}", sink):
            raise ApiError(HTTPStatus.BAD_REQUEST, "Invalid sink name.")
        return sink

    def audio_volume(self, body: dict) -> dict:
        try:
            volume = int(body.get("volume"))
        except (TypeError, ValueError) as exc:
            raise ApiError(HTTPStatus.BAD_REQUEST, "Volume must be a number.") from exc
        error = audio.set_volume(self._sink(body), volume)
        if error:
            raise ApiError(HTTPStatus.UNPROCESSABLE_ENTITY, error)
        return {"ok": True}

    def audio_mute(self, body: dict) -> dict:
        error = audio.set_mute(self._sink(body), bool(body.get("muted")))
        if error:
            raise ApiError(HTTPStatus.UNPROCESSABLE_ENTITY, error)
        return {"ok": True}

    # --- Discord ---------------------------------------------------------------------------------

    def discord(self, _body: dict) -> dict:
        from tuxcast.doctor.discord import granted

        system = self.system_factory()
        links = bridge.plan(system)
        clients = []
        for app in bridge.default_clients(system):
            have = granted(system, app)
            missing = [g for g in bridge.grants(links) if g not in have and g.removesuffix(":create") not in have]
            clients.append({"app": app, "missing": missing})
        return {
            "installs": [v.name for v in bridge.installed_variants(system)],
            "running": [str(s.path) for s in bridge.live_sockets(system.runtime_dir)],
            "links": [{"path": str(link.path), "target": str(link.target), "variant": link.variant.name,
                       "ok": link.path.is_symlink() and link.path.readlink() == link.target} for link in links],
            "clients": clients,
            "service": (paths.systemd_user_dir() / bridge.UNIT).exists(),
        }

    def discord_fix(self, body: dict) -> dict:
        system = self.system_factory()
        with self.lock:
            links = bridge.plan(system)
            bridge.apply(links)
            errors = {app: error for app in bridge.default_clients(system) if (error := bridge.grant(app, links))}
            if body.get("install", True):
                try:
                    systemd.install({bridge.UNIT: bridge.unit(systemd.tuxcast_command())}, enable=[bridge.UNIT])
                except systemd.SystemdError as exc:
                    errors["service"] = str(exc)
        if errors:
            raise ApiError(HTTPStatus.UNPROCESSABLE_ENTITY, "; ".join(f"{k}: {v}" for k, v in errors.items()))
        return self.discord({})

    # --- patches ---------------------------------------------------------------------------------

    def _patches(self) -> list[patch.Patch]:
        try:
            return patch.load_all()
        except patch.PatchError as exc:
            raise ApiError(HTTPStatus.UNPROCESSABLE_ENTITY, str(exc)) from exc

    def patches(self, _body: dict) -> dict:
        items = []
        for item in self._patches():
            outcome = patch.apply(item, dry_run=True)
            items.append({"name": item.name, "file": str(item.file), "watch": str(item.watch),
                          "state": outcome.state, "error": outcome.error})
        return {"folder": str(patch.folder()), "patches": items,
                "watching": (paths.systemd_user_dir() / "tuxcast-patch.path").exists()}

    def patches_apply(self, _body: dict) -> dict:
        with self.lock:
            for item in self._patches():
                patch.apply(item)
        return self.patches({})

    def patches_watch(self, body: dict) -> dict:
        with self.lock:
            if body.get("enable", True):
                items = self._patches()
                if not items:
                    raise ApiError(HTTPStatus.BAD_REQUEST, f"Add a patch to {patch.folder()} first.")
                try:
                    systemd.install(patch.units(items, systemd.tuxcast_command()), enable=["tuxcast-patch.path"],
                                    start=["tuxcast-patch.path", "tuxcast-patch.service"])
                except systemd.SystemdError as exc:
                    raise ApiError(HTTPStatus.UNPROCESSABLE_ENTITY, str(exc)) from exc
            else:
                systemd.uninstall(["tuxcast-patch.path", "tuxcast-patch.service"])
        return self.patches({})

    # --- uploads ---------------------------------------------------------------------------------

    def store_upload(self, filename: str, content: bytes) -> Path:
        suffix = Path(filename).suffix
        if suffix.lower() not in (".streamdeckprofile", ".streamdeckprofilesbackup", ".zip"):
            raise ApiError(HTTPStatus.BAD_REQUEST, "Drop a .streamDeckProfile or .streamDeckProfilesBackup file.")
        stem = re.sub(r"[^A-Za-z0-9 _-]+", "", Path(filename).stem)[:60].strip() or "profile"
        folder = self.uploads_dir / secrets.token_hex(8)
        folder.mkdir()
        path = folder / f"{stem}{suffix}"
        path.write_bytes(content)
        with self.lock:
            self.uploads[folder.name] = path
            while len(self.uploads) > MAX_UPLOADS:
                oldest = next(iter(self.uploads))
                shutil.rmtree(self.uploads.pop(oldest).parent, ignore_errors=True)
        return path


def sinks_by_index(system: System) -> list[dict]:
    """Every sink an app can be sent to, with the number pactl uses for it."""
    out = system.run("pactl", "list", "short", "sinks")
    if not out or not out.ok:
        return []
    sinks = []
    for line in out.stdout.splitlines():
        fields = line.split("\t")
        if len(fields) >= 2:
            name = fields[1]
            label = audio.Sink(name.removeprefix(audio.PREFIX)).description if name.startswith(audio.PREFIX) else name
            sinks.append({"index": fields[0], "name": name, "label": label})
    return sinks


def make_handler(dashboard: Dashboard, allowed_hosts: set[str]) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = f"tuxcast/{__version__}"
        sys_version = ""

        def log_message(self, *_args) -> None:  # quiet: the terminal shows the URL, not every request
            pass

        def send(self, status: HTTPStatus, body: bytes, content_type: str, *, cache: bool = False) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "max-age=300" if cache else "no-store")
            for name, value in SECURITY_HEADERS.items():
                self.send_header(name, value)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def send_json(self, status: HTTPStatus, data: object) -> None:
            self.send(status, json.dumps(data).encode(), "application/json")

        def refuse(self, status: HTTPStatus, message: str) -> None:
            self.send_json(status, {"error": message})

        def trusted(self) -> bool:
            if self.headers.get("Host", "") not in allowed_hosts:
                self.refuse(HTTPStatus.MISDIRECTED_REQUEST, "Unknown host.")
                return False
            origin = self.headers.get("Origin")
            if origin is not None and urlsplit(origin).netloc not in allowed_hosts:
                self.refuse(HTTPStatus.FORBIDDEN, "Cross-origin requests are not allowed.")
                return False
            return True

        def do_GET(self) -> None:
            if not self.trusted():
                return
            url = urlsplit(self.path)
            if url.path in STATIC:
                if url.path == "/" and not dashboard.authorized(parse_qs(url.query).get("token", [None])[0]):
                    self.send(HTTPStatus.FORBIDDEN, b"Open the address tuxcast ui printed in your terminal.",
                              "text/plain; charset=utf-8")
                    return
                name, kind = STATIC[url.path]
                body = resources.files("tuxcast.dashboard").joinpath("static", name).read_bytes()
                self.send(HTTPStatus.OK, body, kind, cache=url.path != "/")
                return
            if self.allowed("GET", url.path):
                self.api("GET", url.path, b"")

        def do_POST(self) -> None:
            if not self.trusted() or not self.allowed("POST", urlsplit(self.path).path):
                return
            # the body is only read once the request is known to come from the dashboard
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                length = -1
            if length < 0:
                self.refuse(HTTPStatus.BAD_REQUEST, "Invalid Content-Length.")
                return
            if length > MAX_UPLOAD:
                self.refuse(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "That file is too big for a profile.")
                return
            self.api("POST", urlsplit(self.path).path, self.rfile.read(length) if length else b"")

        def allowed(self, method: str, path: str) -> bool:
            if (method, path) not in dashboard.routes:
                self.refuse(HTTPStatus.NOT_FOUND, "Not found.")
                return False
            if not dashboard.authorized(self.headers.get("X-Tuxcast-Token")):
                self.refuse(HTTPStatus.FORBIDDEN, "Missing or wrong token.")
                return False
            return True

        def api(self, method: str, path: str, raw: bytes) -> None:
            route = dashboard.routes[(method, path)]
            try:
                if path == "/api/convert/preview":
                    filename = self.headers.get("X-Filename", "profile.streamDeckProfile")
                    body = {"_upload": dashboard.store_upload(filename, raw)}
                else:
                    body = json.loads(raw or b"{}")
                    if not isinstance(body, dict):
                        raise ApiError(HTTPStatus.BAD_REQUEST, "Expected a JSON object.")
                self.send_json(HTTPStatus.OK, route(body))
            except ApiError as exc:
                self.refuse(exc.status, str(exc))
            except (ValueError, UnicodeDecodeError):
                self.refuse(HTTPStatus.BAD_REQUEST, "Malformed request.")
            except OSError as exc:
                self.refuse(HTTPStatus.INTERNAL_SERVER_ERROR, f"{exc.strerror or exc}")

    return Handler


def serve(dashboard: Dashboard, port: int = 0) -> ThreadingHTTPServer:
    """Binds the dashboard to 127.0.0.1 (port 0 picks a free one); call serve_forever() on the result."""
    server = ThreadingHTTPServer(("127.0.0.1", port), BaseHTTPRequestHandler)
    actual = server.server_address[1]
    server.RequestHandlerClass = make_handler(dashboard, {f"127.0.0.1:{actual}", f"localhost:{actual}"})
    server.daemon_threads = True
    return server
