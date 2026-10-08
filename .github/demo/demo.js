"use strict";

// The website's demo of tuxcast ui: the real dashboard, answered by this file instead of a server.
// It starts from sample data (fixtures.json) and plays along: connect Discord, create the audio
// channels, move faders and apps, import the demo profile, apply a patch. Nothing leaves the page.
(function () {
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));
  const copy = (x) => JSON.parse(JSON.stringify(x));
  let fixtures = null;
  const loading = fetch("fixtures.json").then((r) => r.json()).then((data) => { fixtures = data; });

  const state = {
    discordFixed: false,
    channels: [],          // created sink keys
    volumes: {},
    muted: {},
    routes: { 1: "game", 2: "music", 3: "voice", 4: "alerts" },
    patchApplied: false,
    watching: false,
  };
  const APPS = { 1: "Elden Ring", 2: "Spotify", 3: "Discord", 4: "Firefox" };
  const LABELS = { game: "Game", music: "Music", voice: "Voice chat", alerts: "Alerts", browser: "Browser" };

  function doctor() {
    const topics = copy(fixtures.doctor);
    for (const topic of topics) {
      if (topic.topic === "discord" && state.discordFixed) {
        topic.findings = topic.findings.filter((f) => f.status !== "warn");
        topic.findings.push({ status: "ok", summary: "The Discord bridge is in place", detail: "", fix: "", action: "" });
      }
      if (topic.topic === "audio" && state.channels.length) {
        topic.findings = topic.findings.filter((f) => f.status !== "info");
        topic.findings.push({ status: "ok", summary: `${state.channels.length} tuxcast sinks`, detail: "", fix: "", action: "" });
      }
    }
    return topics;
  }

  function audio() {
    const strips = state.channels.map((key, i) => ({
      index: String(100 + i), name: `tuxcast_${key}`, ours: true, default: false, label: LABELS[key] || key,
      detail: `Stream · ${LABELS[key] || key}`, volume: state.volumes[key] ?? [85, 45, 70, 60, 50][i % 5],
      muted: !!state.muted[key],
      apps: Object.entries(state.routes).filter(([, sink]) => sink === key).map(([index]) => ({ index, application: APPS[index] })),
    }));
    strips.push({ index: "1", name: "alsa_output.usb-headset", ours: false, default: true, label: "Your output",
      detail: "USB headset", volume: state.volumes.output ?? 65, muted: !!state.muted.output,
      apps: state.channels.length ? Object.entries(state.routes).filter(([, s]) => !state.channels.includes(s))
        .map(([index]) => ({ index, application: APPS[index] }))
        : Object.keys(APPS).map((index) => ({ index, application: APPS[index] })) });
    return {
      configured: state.channels.map((k) => `tuxcast_${k}`), defaults: ["game", "music", "voice", "alerts"],
      descriptions: Object.fromEntries(Object.entries(LABELS).map(([k, v]) => [k, `Stream · ${v}`])),
      strips, elsewhere: [],
    };
  }

  function discord() {
    return {
      installs: ["Discord (snap)"], running: ["/run/user/1000/snap.discord/discord-ipc-0"],
      links: [{ path: "/run/user/1000/app/com.discordapp.Discord/discord-ipc-0", target: "/run/user/1000/snap.discord/discord-ipc-0",
        variant: "Discord (snap)", ok: state.discordFixed }],
      clients: [{ app: "com.core447.StreamController", missing: state.discordFixed ? [] : ["xdg-run/snap.discord"] }],
      service: state.discordFixed,
    };
  }

  function patches() {
    return {
      folder: "~/.config/tuxcast/patches", watching: state.watching,
      patches: [{ name: "twitch-oauth-port", file: "~/.var/app/com.core447.StreamController/data/plugins/com_imdevinc_StreamControllerTwitchPlugin/constants.py",
        watch: "~/.var/app/com.core447.StreamController/data/plugins", state: state.patchApplied ? "unchanged" : "applied", error: "" }],
    };
  }

  const sinkKey = (name) => name.startsWith("tuxcast_") ? name.slice(8) : "output";

  const routes = {
    "GET /api/overview": () => fixtures.overview,
    "GET /api/doctor": async () => { await wait(700); return doctor(); },
    "GET /api/deck": () => fixtures.deck,
    "POST /api/deck/reset": () => ({ results: [{ name: "Stream Deck Mini (v2)", ok: true }] }),
    "POST /api/convert/preview": async (body) => { await wait(500); return { ...copy(fixtures.preview), upload: "demo", file: body && body.name ? body.name : "Streaming.streamDeckProfile" }; },
    "POST /api/convert": async () => { await wait(400); return { ...copy(fixtures.preview), written: fixtures.preview.pages.map((p) => p.name), pagesDir: fixtures.deck.pagesDir }; },
    "GET /api/audio": () => audio(),
    "POST /api/audio/setup": async (body) => { await wait(400); state.channels = body.sinks.filter((k) => LABELS[k]); return { path: "~/.config/pipewire/pipewire.conf.d/tuxcast-sinks.conf", restarted: true }; },
    "POST /api/audio/remove": () => { state.channels = []; return { removed: true, restarted: true }; },
    "POST /api/audio/route": (body) => { const key = sinkKey(body.sink); state.routes[body.stream] = key === "output" ? "output" : key; return { ok: true }; },
    "POST /api/audio/volume": (body) => { state.volumes[sinkKey(body.sink)] = body.volume; return { ok: true }; },
    "POST /api/audio/mute": (body) => { state.muted[sinkKey(body.sink)] = body.muted; return { ok: true }; },
    "GET /api/discord": () => discord(),
    "POST /api/discord": async () => { await wait(500); state.discordFixed = true; return discord(); },
    "GET /api/patches": () => patches(),
    "POST /api/patches/apply": () => { state.patchApplied = true; return patches(); },
    "POST /api/patches/watch": (body) => { state.watching = !!body.enable; return patches(); },
  };

  window.TUXCAST_DEMO = async (method, path, body) => {
    await loading;
    await wait(120);
    const route = routes[`${method} ${path}`];
    if (!route) throw new Error("Not available in the demo.");
    return copy(await route(body));
  };
})();
