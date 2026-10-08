"use strict";

// The token arrives in the address tuxcast printed. Keep it for reloads, then drop it from the URL bar.
const params = new URLSearchParams(location.search);
if (params.get("token")) {
  sessionStorage.setItem("tuxcast-token", params.get("token"));
  history.replaceState(null, "", "/" + location.hash);
}
const TOKEN = sessionStorage.getItem("tuxcast-token") || "";

// ------------------------------------------------------------------------------- helpers

// Builds elements from data. Text always goes through textContent: profiles and app names are
// untrusted, so nothing here ever becomes HTML.
function h(tag, attrs, ...children) {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    if (value === undefined || value === null || value === false) continue;
    if (key.startsWith("on")) el.addEventListener(key.slice(2), value);
    else if (key === "dataset") Object.assign(el.dataset, value);
    else el.setAttribute(key, value === true ? "" : value);
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    el.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return el;
}

async function api(method, path, body, headers = {}) {
  const options = { method, headers: { "X-Tuxcast-Token": TOKEN, ...headers } };
  if (body instanceof Blob) options.body = body;
  else if (body !== undefined) {
    options.body = JSON.stringify(body);
    options.headers["Content-Type"] = "application/json";
  }
  const response = await fetch(path, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || `The dashboard answered ${response.status}.`);
  return data;
}

function toast(message, kind = "ok") {
  const el = h("div", { class: "toast", dataset: { kind } }, message);
  document.getElementById("toast").append(el);
  setTimeout(() => el.remove(), kind === "error" ? 9000 : 5000);
}

// Runs an action from a button: disables it meanwhile, reports errors in a toast.
async function act(button, work, done) {
  button.disabled = true;
  try {
    const result = await work();
    if (done) toast(typeof done === "function" ? done(result) : done);
    return result;
  } catch (error) {
    toast(error.message, "error");
    return null;
  } finally {
    button.disabled = false;
  }
}

function copyButton(text, label = "Copy") {
  const button = h("button", {
    type: "button", class: "quiet",
    onclick: async () => {
      await navigator.clipboard.writeText(text);
      button.textContent = "Copied";
      setTimeout(() => { button.textContent = label; }, 1500);
    },
  }, label);
  return button;
}

const view = () => document.getElementById("view");
function show(...children) {
  view().replaceChildren(...children);
}

const worst = (statuses) => statuses.includes("fail") ? "fail" : statuses.includes("warn") ? "warn" : "ok";

// ------------------------------------------------------------------------------- overview

const TOPIC_VIEW = { audio: "audio", discord: "discord", streamdeck: "deck" };
const ACTIONS = {
  audio: ["Set up audio", () => go("audio")],
  discord: ["Connect Discord", null],
  deck: ["Open Stream Deck", () => go("deck")],
  convert: ["Convert a profile", () => go("deck")],
};

async function overview() {
  show(h("h1", {}, "Ready to go live?"), h("p", { class: "lede loading" }, "Checking your setup…"));
  const topics = await api("GET", "/api/doctor");
  const statuses = topics.flatMap((t) => t.findings.map((f) => f.status));
  const state = worst(statuses);
  const problems = statuses.filter((s) => s === "fail").length;
  const warnings = statuses.filter((s) => s === "warn").length;

  for (const topic of topics) {
    const name = TOPIC_VIEW[topic.topic];
    if (name) setDot(name, worst(topic.findings.map((f) => f.status)));
  }
  setDot("overview", state);

  const headline = state === "ok" ? "Everything looks ready to go live."
    : [problems && `${problems} problem${problems > 1 ? "s" : ""} to fix`,
       warnings && `${warnings} warning${warnings > 1 ? "s" : ""} to look at`].filter(Boolean).join(" and ") + ".";
  const again = h("button", { type: "button", onclick: () => overview() }, "Check again");

  show(
    h("h1", {}, "Ready to go live?"),
    h("p", { class: "lede" }, "Eight checks of your streaming setup. Each problem comes with its fix, and a button when tuxcast can apply it for you."),
    h("section", { class: "verdict", dataset: { state } },
      h("div", { class: "verdict__key", "aria-hidden": "true" }, state === "ok" ? "Go live" : "Wait"),
      h("div", {}, h("h2", {}, headline), h("p", {}, "The doctor only reads your system: running it changes nothing.")),
      again),
    ...topics.map(topicSection),
  );
}

function topicSection(topic) {
  return h("section", { class: "topic" },
    h("h3", {}, topic.title),
    h("ul", { class: "findings" }, topic.findings.map(findingItem)));
}

function findingItem(finding) {
  let button = null;
  const action = ACTIONS[finding.action];
  if (action && finding.status !== "ok") {
    const [label, handler] = action;
    button = h("button", { type: "button", class: finding.status === "info" ? "" : "primary" }, label);
    button.addEventListener("click", handler || (() => act(button, () => api("POST", "/api/discord", { install: true }),
      "Discord is connected. Restart StreamController to use it.").then((r) => r && overview())));
  }
  return h("li", { class: "finding", dataset: { status: finding.status } },
    h("span", { class: "dot", "aria-hidden": "true" }),
    h("span", { class: "finding__summary" }, finding.summary,
      h("span", { class: "skip" }, ` (${finding.status})`)),
    finding.detail && finding.status !== "ok" ? h("p", { class: "finding__detail" }, finding.detail) : null,
    finding.fix ? h("p", { class: "finding__fix" }, "Fix: ", h("code", {}, finding.fix)) : null,
    button);
}

// ------------------------------------------------------------------------------- Stream Deck

let conversion = null; // the last preview: { upload, file, pages, ... }
let selectedPage = 0;
let selectedKey = null;

async function deckView() {
  show(h("h1", {}, "Stream Deck"), h("p", { class: "lede loading" }, "Looking for decks…"));
  const [info, overviewData] = await Promise.all([api("GET", "/api/deck"), api("GET", "/api/overview")]);
  setDot("deck", info.decks.length === 0 ? "" : info.decks.every((d) => d.accessible) ? "ok" : "fail");

  const decks = info.decks.length
    ? h("table", {},
        h("thead", {}, h("tr", {}, h("th", {}, "Model"), h("th", {}, "USB"), h("th", {}, "Access"))),
        h("tbody", {}, info.decks.map((d) => h("tr", {},
          h("td", {}, d.name), h("td", {}, h("code", {}, d.node)),
          h("td", {}, h("span", { class: "state", dataset: { state: d.accessible ? "ok" : "fail" } },
            d.accessible ? "Ready" : "No permission"))))))
    : h("p", { class: "muted" }, "No Stream Deck plugged in.");

  const reset = h("button", { type: "button" }, "Reset frozen deck");
  reset.addEventListener("click", () => act(reset, () => api("POST", "/api/deck/reset"), (r) =>
    r.results.map((x) => x.ok ? `${x.name} was reset. Restart StreamController.` : `${x.name}: ${x.error}`).join(" ")));

  const needsRule = info.decks.some((d) => !d.accessible);
  const rule = h("details", { open: needsRule || undefined },
    h("summary", {}, "Permission rule (udev)"),
    h("p", { class: "muted small" }, `Without it, only root can open the deck. Install it once, in a terminal:`),
    h("pre", { class: "block" }, `sudo tee ${info.udevPath} <<'EOF'\n${info.udev}EOF\nsudo udevadm control --reload && sudo udevadm trigger`),
    copyButton(`sudo tee ${info.udevPath} <<'EOF'\n${info.udev}EOF\nsudo udevadm control --reload && sudo udevadm trigger`, "Copy commands"));

  show(
    h("h1", {}, "Stream Deck"),
    h("p", { class: "lede" }, "Bring your Elgato profiles over to StreamController, and keep your decks working."),
    h("h2", {}, "Convert an Elgato profile"),
    conversion ? conversionPanel(overviewData) : dropZone(overviewData),
    h("h2", {}, "Your decks"),
    h("div", { class: "panel" }, decks, h("div", { class: "row" }, info.decks.length ? reset : null), rule),
  );
}

function dropZone(overviewData) {
  const input = h("input", { type: "file", accept: ".streamDeckProfile,.streamDeckProfilesBackup,.zip", hidden: true });
  const zone = h("div", { class: "drop", tabindex: "0", role: "button",
      "aria-label": "Choose an Elgato profile to convert" },
    h("strong", {}, "Drop your .streamDeckProfile here"),
    h("span", { class: "muted" }, "or click to choose it. In the Stream Deck app: Preferences, Profiles, then Export."),
    input);
  const pick = () => input.click();
  zone.addEventListener("click", pick);
  zone.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); pick(); } });
  zone.addEventListener("dragover", (e) => { e.preventDefault(); zone.dataset.over = ""; });
  zone.addEventListener("dragleave", () => { delete zone.dataset.over; });
  zone.addEventListener("drop", (e) => {
    e.preventDefault();
    delete zone.dataset.over;
    if (e.dataTransfer.files[0]) preview(e.dataTransfer.files[0], zone);
  });
  input.addEventListener("change", () => { if (input.files[0]) preview(input.files[0], zone); });
  return zone;
}

async function preview(file, zone) {
  zone.replaceChildren(h("strong", {}, `Reading ${file.name}…`));
  try {
    conversion = await api("POST", "/api/convert/preview", file, { "X-Filename": file.name });
    selectedPage = 0;
    selectedKey = null;
  } catch (error) {
    toast(error.message, "error");
  }
  deckView();
}

function conversionPanel(overviewData) {
  const page = conversion.pages[selectedPage];
  const keys = new Map(page.keys.map((k) => [`${k.column},${k.row}`, k]));
  const grid = h("div", { class: "keys" });
  grid.style.setProperty("--cols", page.columns);
  for (let row = 0; row < page.rows; row++) {
    for (let column = 0; column < page.columns; column++) {
      const key = keys.get(`${column},${row}`);
      if (!key) {
        grid.append(h("div", { class: "key", "data-empty": "", "aria-hidden": "true" }));
        continue;
      }
      const isSelected = selectedKey === key;
      grid.append(h("button", {
          type: "button", class: "key", dataset: { status: key.status },
          "aria-pressed": isSelected ? "true" : "false",
          "aria-label": `${key.title || "Untitled key"}: ${statusLabel(key.status)}`,
          onclick: () => { selectedKey = key; deckView(); },
        },
        key.image ? h("img", { src: key.image, alt: "" }) : null,
        h("span", {}, key.title)));
    }
  }

  const tabs = h("div", { class: "tabs", role: "tablist" }, conversion.pages.map((p, i) =>
    h("button", { type: "button", role: "tab", "aria-selected": i === selectedPage ? "true" : "false",
      onclick: () => { selectedPage = i; selectedKey = null; deckView(); } }, p.name)));

  const name = h("input", { type: "text", placeholder: "Profile name", value: conversion.pages[0].name.replace(/ \d+$/, ""),
    "aria-label": "Name of the pages" });
  const layout = h("select", { "aria-label": "Keyboard layout the hotkeys were recorded with" },
    overviewData.layouts.map((l) => h("option", { value: l, selected: l === overviewData.layout || undefined }, `Keyboard: ${l}`)));
  const force = h("input", { type: "checkbox" });
  const go = h("button", { type: "button", class: "primary" },
    `Convert ${conversion.pages.length} page${conversion.pages.length > 1 ? "s" : ""}`);
  go.addEventListener("click", () => act(go, () => api("POST", "/api/convert", {
      upload: conversion.upload, name: name.value, layout: layout.value, force: force.checked }),
    (r) => `Wrote ${r.written.length} pages to StreamController. Restart it, then pick a page.`)
    .then((r) => { if (r) { conversion = { ...r, upload: conversion.upload, file: conversion.file, done: true }; deckView(); } }));
  const other = h("button", { type: "button", class: "quiet", onclick: () => { conversion = null; deckView(); } },
    "Choose another file");

  const toRedo = conversion.pages.flatMap((p) => p.keys.filter((k) => k.status === "manual" || k.status === "partial")
    .map((k) => ({ page: p.name, ...k })));

  const aside = h("aside", { class: "aside panel" },
    h("div", { class: "stat" }, `${conversion.converted}/${conversion.total}`),
    h("p", { class: "muted" }, "keys converted"),
    selectedKey
      ? h("div", {}, h("h3", {}, selectedKey.title || "Untitled key"),
          h("p", { class: "muted small" }, statusLabel(selectedKey.status)),
          selectedKey.notes.length ? h("ul", {}, selectedKey.notes.map((n) => h("li", {}, n))) : null)
      : h("p", { class: "muted small" }, "Select a key to see how it converts."),
    conversion.plugins.length ? h("p", { class: "small" }, "Plugins needed: ", conversion.plugins.join(", ")) : null,
    toRedo.length ? h("p", { class: "small muted" }, `${toRedo.length} key${toRedo.length > 1 ? "s" : ""} to finish by hand in StreamController.`) : null);

  return h("div", { class: "convert" },
    h("div", {},
      h("p", { class: "muted" }, conversion.done ? `Converted ${conversion.file}.` : `Preview of ${conversion.file}. Nothing is written yet.`),
      tabs,
      h("div", { class: "deck" }, grid),
      h("div", { class: "legend" },
        h("span", {}, h("i", { class: "l-ok" }), "Converted"),
        h("span", {}, h("i", { class: "l-partial" }), "Converted, check it"),
        h("span", {}, h("i", { class: "l-manual" }), "Redo by hand")),
      conversion.done
        ? h("div", { class: "row" },
            h("span", { class: "state", dataset: { state: "ok" } }, `Written to ${conversion.pagesDir}`), other)
        : h("div", { class: "row" }, name, layout,
            h("label", { class: "check" }, force, "Overwrite existing pages"), go, other)),
    aside);
}

function statusLabel(status) {
  return { converted: "Converted", partial: "Converted, check it", manual: "Redo by hand in StreamController",
    added: "Added by tuxcast" }[status] || status;
}

// ------------------------------------------------------------------------------- audio

async function audioView() {
  show(h("h1", {}, "Audio"), h("p", { class: "lede loading" }, "Reading PipeWire…"));
  const data = await api("GET", "/api/audio");
  const configured = new Set(data.configured.map((n) => n.replace(/^tuxcast_/, "")));
  const live = new Set(data.live);
  const keys = [...new Set([...Object.keys(data.descriptions), ...configured])];
  setDot("audio", configured.size === 0 ? "warn" : [...configured].every((k) => live.has(`tuxcast_${k}`)) ? "ok" : "warn");

  const boxes = keys.map((key) => {
    const box = h("input", { type: "checkbox", value: key, checked: (configured.size ? configured.has(key) : data.defaults.includes(key)) || undefined });
    return h("label", { class: "sink", "data-live": live.has(`tuxcast_${key}`) || undefined }, box,
      h("span", {}, data.descriptions[key] || `Stream · ${key}`),
      h("small", {}, live.has(`tuxcast_${key}`) ? "live" : configured.has(key) ? "after restart" : ""));
  });
  const custom = h("input", { type: "text", placeholder: "Another sink, e.g. browser", "aria-label": "Name of another sink" });
  const restart = h("input", { type: "checkbox", checked: true });
  const save = h("button", { type: "button", class: "primary" }, "Save sinks");
  save.addEventListener("click", () => {
    const sinks = boxes.map((b) => b.querySelector("input")).filter((b) => b.checked).map((b) => b.value);
    if (custom.value.trim()) sinks.push(custom.value.trim().toLowerCase());
    act(save, () => api("POST", "/api/audio/setup", { sinks, restart: restart.checked }),
      (r) => r.restarted ? "Sinks created. Add each one to OBS as an Audio Output Capture." : "Saved. They appear after PipeWire restarts.")
      .then((r) => r && audioView());
  });
  const remove = h("button", { type: "button", class: "quiet" }, "Remove all sinks");
  remove.addEventListener("click", () => act(remove, () => api("POST", "/api/audio/remove", { restart: restart.checked }),
    "Sinks removed.").then((r) => r && audioView()));

  const streams = data.streams.length
    ? h("table", {},
        h("thead", {}, h("tr", {}, h("th", {}, "App playing now"), h("th", {}, "Plays into"))),
        h("tbody", {}, data.streams.map((stream) => {
          const select = h("select", { "aria-label": `Where ${stream.application} plays` },
            data.sinks.map((s) => h("option", { value: s.name, selected: s.index === stream.sink || undefined }, s.label)));
          select.addEventListener("change", async () => {
            select.disabled = true;
            try {
              await api("POST", "/api/audio/route", { stream: stream.index, sink: select.value });
              toast(`${stream.application} now plays into ${select.selectedOptions[0].textContent}.`);
            } catch (error) { toast(error.message, "error"); }
            select.disabled = false;
          });
          return h("tr", {}, h("td", {}, stream.application), h("td", {}, select));
        })))
    : h("p", { class: "muted" }, "No app is playing sound. Start the game or the music, then refresh.");

  show(
    h("h1", {}, "Audio"),
    h("p", { class: "lede" }, "Give the game, the music, voice chat and alerts their own sink, so each one is its own source in OBS. You keep hearing everything."),
    h("div", { class: "panel" },
      h("h3", {}, "Sinks"),
      h("div", { class: "sinks" }, boxes),
      h("div", { class: "row" }, custom, h("label", { class: "check" }, restart, "Restart PipeWire now (sound cuts for a second)")),
      h("div", { class: "row" }, save, remove)),
    h("h2", {}, "Send apps to a sink"),
    h("div", { class: "panel" }, streams,
      h("div", { class: "row" }, h("button", { type: "button", class: "quiet", onclick: () => audioView() }, "Refresh"))),
  );
}

// ------------------------------------------------------------------------------- Discord

async function discordView() {
  show(h("h1", {}, "Discord"), h("p", { class: "lede loading" }, "Looking for Discord…"));
  const data = await api("GET", "/api/discord");
  const broken = data.links.some((l) => !l.ok) || data.clients.some((c) => c.missing.length);
  setDot("discord", data.installs.length === 0 ? "" : broken ? "warn" : "ok");

  const connect = h("button", { type: "button", class: broken ? "primary" : "" }, broken ? "Connect Discord" : "Repair the connection");
  connect.addEventListener("click", () => act(connect, () => api("POST", "/api/discord", { install: true }),
    "Discord is connected. Restart StreamController to use it.").then((r) => r && discordView()));

  show(
    h("h1", {}, "Discord"),
    h("p", { class: "lede" }, "Stream Deck mute keys and rich presence talk to Discord through a socket that Flatpak and snap hide from each other. tuxcast links it where every client looks."),
    h("div", { class: "panel" },
      h("h3", {}, "Installed"),
      h("p", { class: "muted" }, data.installs.length ? data.installs.join(", ") : "Discord is not installed."),
      h("p", { class: "muted small" }, data.running.length ? "Running now." : "Not running: the connection is prepared and works as soon as it starts."),
      data.links.length ? h("table", {},
        h("thead", {}, h("tr", {}, h("th", {}, "Bridge"), h("th", {}, "State"))),
        h("tbody", {}, data.links.map((l) => h("tr", {},
          h("td", {}, l.variant, h("br"), h("code", { class: "small muted" }, l.path)),
          h("td", {}, h("span", { class: "state", dataset: { state: l.ok ? "ok" : "warn" } }, l.ok ? "Linked" : "Missing")))))) : null,
      data.clients.map((c) => h("p", {},
        h("span", { class: "state", dataset: { state: c.missing.length ? "warn" : "ok" } },
          c.missing.length ? `${c.app} cannot see Discord yet` : `${c.app} can reach Discord`))),
      h("p", { class: "muted small" }, data.service ? "Recreated at every login." : "Not recreated at login yet."),
      h("div", { class: "row" }, connect)),
  );
}

// ------------------------------------------------------------------------------- patches

const PATCH_STATES = { unchanged: ["ok", "Applied"], applied: ["warn", "Needs applying"], missing: ["", "File not found"],
  "no-match": ["fail", "Pattern not found"], error: ["fail", "Error"] };

async function patchesView() {
  show(h("h1", {}, "Patches"), h("p", { class: "lede loading" }, "Reading patches…"));
  const data = await api("GET", "/api/patches");
  setDot("patches", data.patches.length === 0 ? "" : data.patches.every((p) => p.state === "unchanged") ? "ok" : "warn");

  const apply = h("button", { type: "button", class: "primary" }, "Apply now");
  apply.addEventListener("click", () => act(apply, () => api("POST", "/api/patches/apply"), "Patches applied.").then((r) => r && patchesView()));
  const watch = h("button", { type: "button" }, data.watching ? "Stop re-applying after updates" : "Re-apply after every update");
  watch.addEventListener("click", () => act(watch, () => api("POST", "/api/patches/watch", { enable: !data.watching }),
    data.watching ? "Patches are no longer watched." : "Patches now come back after every update.").then((r) => r && patchesView()));

  show(
    h("h1", {}, "Patches"),
    h("p", { class: "lede" }, "Small fixes to app files that updates keep wiping, re-applied for you."),
    data.patches.length
      ? h("div", { class: "panel" },
          h("table", {},
            h("thead", {}, h("tr", {}, h("th", {}, "Patch"), h("th", {}, "File"), h("th", {}, "State"))),
            h("tbody", {}, data.patches.map((p) => {
              const [state, label] = PATCH_STATES[p.state] || ["", p.state];
              return h("tr", {}, h("td", {}, p.name), h("td", {}, h("code", { class: "small" }, p.file)),
                h("td", {}, h("span", { class: "state", dataset: { state } }, label), p.error ? h("div", { class: "small muted" }, p.error) : null));
            }))),
          h("div", { class: "row" }, apply, watch))
      : h("div", { class: "panel" },
          h("p", {}, "No patches yet."),
          h("p", { class: "muted" }, "Add a patch file to ", h("code", {}, data.folder), ". The guide has a ready-made one for StreamController's Twitch plugin."),
          h("a", { href: "https://achedon12.github.io/tuxcast/commands/patch/", target: "_blank", rel: "noreferrer" }, "How to write a patch")),
  );
}

// ------------------------------------------------------------------------------- router

const VIEWS = { overview, deck: deckView, audio: audioView, discord: discordView, patches: patchesView };

function setDot(name, state) {
  const dot = document.querySelector(`.dot[data-for="${name}"]`);
  if (dot) dot.dataset.state = state;
}

function go(name) {
  if (location.hash !== `#${name}`) location.hash = name;
  else route();
}

async function route() {
  const name = location.hash.slice(1) in VIEWS ? location.hash.slice(1) : "overview";
  for (const link of document.querySelectorAll(".nav a")) {
    if (link.dataset.view === name) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  }
  try {
    await VIEWS[name]();
  } catch (error) {
    show(h("h1", {}, "Something went wrong"), h("p", { class: "lede" }, error.message),
      h("button", { type: "button", onclick: () => route() }, "Try again"));
  }
}

window.addEventListener("hashchange", () => { route(); document.getElementById("main").focus(); });
api("GET", "/api/overview").then((data) => {
  document.getElementById("version").textContent = `v${data.version}`;
}).catch(() => {
  show(h("h1", {}, "Open the dashboard from your terminal"),
    h("p", { class: "lede" }, "This page needs the address tuxcast ui printed, with its token. Run tuxcast ui again if you closed it."));
});
route();
