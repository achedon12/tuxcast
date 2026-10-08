"use strict";

// The token arrives in the address tuxcast ui printed. It is kept for this tab only, then removed
// from the address bar. The website's demo has no server: demo.js answers instead (TUXCAST_DEMO).
const params = new URLSearchParams(location.search);
if (params.get("token")) {
  sessionStorage.setItem("tuxcast-token", params.get("token"));
  history.replaceState(null, "", location.pathname + location.hash);
}
const TOKEN = sessionStorage.getItem("tuxcast-token") || "";

// ------------------------------------------------------------------------------- helpers

// Builds elements from data. Text always goes through text nodes: profiles, page names and app
// names are not trusted, so nothing here ever becomes HTML.
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
  if (window.TUXCAST_DEMO) return window.TUXCAST_DEMO(method, path, body);
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
  document.getElementById("toasts").append(el);
  setTimeout(() => el.remove(), kind === "error" ? 8000 : 4500);
}

// Runs a button's action: disabled meanwhile, errors shown in a toast.
async function act(button, work, done) {
  if (button) button.disabled = true;
  try {
    const result = await work();
    if (done) toast(typeof done === "function" ? done(result) : done);
    return result;
  } catch (error) {
    toast(error.message, "error");
    return null;
  } finally {
    if (button) button.disabled = false;
  }
}

const $ = (id) => document.getElementById(id);
const fill = (id, ...children) => $(id).replaceChildren(...children.filter((c) => c !== null && c !== undefined && c !== false));
const worst = (states) => states.includes("fail") ? "fail" : states.includes("warn") ? "warn" : "ok";
const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;

function button(label, onclick, kind = "") {
  return h("button", { type: "button", class: `btn ${kind}`.trim(), onclick }, label);
}

// ------------------------------------------------------------------------------- drawer

let drawerReturn = null;
function openDrawer(title, ...content) {
  drawerReturn = document.activeElement;
  $("drawer-title").textContent = title;
  fill("drawer-body", ...content);
  $("drawer").hidden = false;
  $("scrim").hidden = false;
  $("drawer-close").focus();
}
function closeDrawer() {
  $("drawer").hidden = true;
  $("scrim").hidden = true;
  if (drawerReturn) drawerReturn.focus();
}
$("drawer-close").addEventListener("click", closeDrawer);
$("scrim").addEventListener("click", closeDrawer);
document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !$("drawer").hidden) closeDrawer(); });

// ------------------------------------------------------------------------------- tally and checks

const TALLY = { ok: "Ready to go live", warn: "Ready, with things to check", fail: "Not ready to go live" };
let topics = [];

async function loadChecks() {
  const tally = $("tally");
  tally.dataset.state = "";
  $("tally-text").textContent = "Checking your setup…";
  topics = await api("GET", "/api/doctor");
  const states = topics.flatMap((t) => t.findings.map((f) => f.status));
  const state = worst(states);
  const count = states.filter((s) => s === "warn" || s === "fail").length;
  tally.dataset.state = state;
  $("tally-text").textContent = state === "ok" ? TALLY.ok : `${TALLY[state]} (${count})`;

  // what to do next: problems first, then what tuxcast can set up for you
  const todo = topics.flatMap((t) => t.findings.filter((f) => f.status === "fail" || f.status === "warn" ||
    (f.status === "info" && ACTIONS[f.action])).map((f) => ({ ...f, topic: t.title })))
    .sort((a, b) => ["fail", "warn", "info"].indexOf(a.status) - ["fail", "warn", "info"].indexOf(b.status));
  const next = todo.length
    ? h("div", { class: "todo" }, h("h3", { class: "todo__title" }, "To do before going live"), todo.slice(0, 4).map(todoRow))
    : h("p", { class: "todo todo--done" }, "Nothing to fix. Have a good stream.");

  fill("checks", h("div", { class: "checks" }, topics.map((topic) => {
    const topicState = worst(topic.findings.map((f) => f.status));
    const flagged = topic.findings.find((f) => f.status === "fail") || topic.findings.find((f) => f.status === "warn");
    const skipped = topic.findings.every((f) => f.status === "skip");
    const summary = flagged ? flagged.summary : skipped ? topic.findings[0].summary : "All good";
    return h("button", { type: "button", class: "check-tile", dataset: { state: skipped ? "" : topicState },
        onclick: () => showTopic(topic) },
      h("span", { class: "check-tile__top" },
        h("span", { class: "led", dataset: { state: skipped ? "" : topicState } }), topic.title),
      h("span", { class: "check-tile__text" }, summary));
  })), next);
}

function todoRow(f) {
  const action = ACTIONS[f.action];
  let actionButton = null;
  if (action) {
    actionButton = h("button", { type: "button", class: `btn ${f.status === "info" ? "" : "btn--go"}` }, action[0]);
    actionButton.addEventListener("click", () => action[1](actionButton));
  }
  return h("div", { class: "todo__row" },
    h("span", { class: "led", dataset: { state: f.status } }),
    h("div", {}, h("div", { class: "todo__summary" }, f.summary),
      f.fix ? h("div", { class: "todo__fix" }, f.fix) : null),
    actionButton);
}

const ACTIONS = {
  audio: ["Set up the mixer", () => { closeDrawer(); setupSinks(); }],
  discord: ["Connect Discord", (b) => connectDiscord(b)],
  deck: ["Show the permission rule", () => { closeDrawer(); showUdev(); }],
  convert: ["Import a profile", () => { closeDrawer(); importProfile(); }],
};

function showTopic(topic) {
  openDrawer(topic.title, ...topic.findings.map((f) => {
    const action = ACTIONS[f.action];
    let actionButton = null;
    if (action && f.status !== "ok") {
      actionButton = h("button", { type: "button", class: "btn btn--go" }, action[0]);
      actionButton.addEventListener("click", () => action[1](actionButton));
    }
    return h("div", { class: "finding" },
      h("span", { class: "led", dataset: { state: f.status === "skip" ? "" : f.status } }),
      h("span", { class: "finding__summary" }, f.summary),
      f.detail ? h("p", { class: "finding__detail" }, f.detail) : null,
      f.fix ? h("p", { class: "finding__fix" }, "Fix: ", h("code", {}, f.fix)) : null,
      actionButton);
  }));
}

// ------------------------------------------------------------------------------- Stream Deck

let deckData = null;
let pageIndex = 0;
let preview = null;     // a dropped Elgato profile, converted in memory only
let selectedKey = null;
let importing = false;

async function loadDeck() {
  deckData = await api("GET", "/api/deck");
  const main = deckData.pages.findIndex((p) => p.name.toLowerCase() === "main");
  pageIndex = main >= 0 ? main : 0;
  renderDeck();
}

function grid() {
  const plugged = deckData.decks[0];
  if (preview) {
    const page = preview.pages[pageIndex] || preview.pages[0];
    return { columns: Math.max(page.columns, plugged ? plugged.columns : 0), rows: Math.max(page.rows, plugged ? plugged.rows : 0) };
  }
  if (plugged) return { columns: plugged.columns, rows: plugged.rows };
  return { columns: 5, rows: 3 };
}

function renderDeck() {
  const plugged = deckData.decks[0];
  const { columns, rows } = grid();
  const pages = preview ? preview.pages : deckData.pages;
  const page = pages[pageIndex] || { keys: [] };
  const byPosition = new Map(page.keys.map((k) => [`${k.column},${k.row}`, k]));

  const keys = h("div", { class: "device__keys" });
  keys.style.setProperty("--cols", columns);
  for (let row = 0; row < rows; row++) {
    for (let column = 0; column < columns; column++) {
      const key = byPosition.get(`${column},${row}`);
      const label = key ? (key.title ?? key.label ?? "") : "";
      const content = [key && key.image ? h("img", { src: key.image, alt: "" }) : null, label ? h("span", {}, label) : null];
      if (preview && key) {
        keys.append(h("button", { type: "button", class: "key", dataset: { status: key.status },
          "aria-pressed": selectedKey === key ? "true" : "false",
          "aria-label": `${label || "Untitled key"}: ${STATUS[key.status] || key.status}`,
          onclick: () => { selectedKey = key; renderDeck(); } }, content));
      } else {
        keys.append(h("div", { class: "key", "aria-label": label || undefined }, content));
      }
    }
  }

  const body = h("div", { class: "device__body" }, keys);
  if (importing) body.append(dropZone());

  const chips = h("div", { class: "chips", role: "group", "aria-label": "Pages" }, pages.map((p, i) =>
    h("button", { type: "button", class: "chip", "aria-pressed": i === pageIndex ? "true" : "false",
      onclick: () => { pageIndex = i; selectedKey = null; renderDeck(); } }, p.name)));

  const label = plugged
    ? h("div", { class: "device__label" }, h("span", { class: "led", dataset: { state: plugged.accessible ? "ok" : "fail" } }),
        `${plugged.name} · ${plugged.accessible ? "connected" : "no permission"}`)
    : h("div", { class: "device__label" }, h("span", { class: "led" }), "No Stream Deck plugged in");

  fill("deck", h("div", { class: "device" }, label, body,
    pages.length ? chips : h("p", { class: "note" }, "No StreamController page yet."),
    preview ? previewBar() : null));

  $("deck-meta").textContent = preview ? "Preview, nothing written yet" : `${plural(deckData.pages.length, "page")} in StreamController`;
  const tools = [];
  if (!preview && !importing) tools.push(button("Import Elgato profile", importProfile));
  if (plugged && !preview) tools.push(button("Reset", resetDeck, "btn--ghost"));
  if (plugged && !plugged.accessible) tools.push(button("Permission rule", showUdev, "btn--ghost"));
  fill("deck-tools", ...tools);
}

const STATUS = { converted: "Converted", partial: "Converted, check it", manual: "Redo by hand", added: "Added by tuxcast" };

function importProfile() {
  importing = true;
  preview = null;
  renderDeck();
  const input = document.querySelector(".dropzone input");
  if (input) input.closest(".dropzone").focus();
}

function dropZone() {
  const input = h("input", { type: "file", accept: ".streamDeckProfile,.streamDeckProfilesBackup,.zip", hidden: true });
  const zone = h("div", { class: "dropzone", tabindex: "0", role: "button", "aria-label": "Choose an Elgato profile" },
    h("div", {}, h("strong", {}, "Drop your .streamDeckProfile"), "or click to choose it",
      h("div", { class: "row", style: undefined }, button("Cancel", (e) => { e.stopPropagation(); importing = false; renderDeck(); }, "btn--ghost"))),
    input);
  const pick = () => input.click();
  zone.addEventListener("click", pick);
  zone.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); pick(); } });
  zone.addEventListener("dragover", (e) => { e.preventDefault(); zone.dataset.over = ""; });
  zone.addEventListener("dragleave", () => { delete zone.dataset.over; });
  zone.addEventListener("drop", (e) => { e.preventDefault(); delete zone.dataset.over; if (e.dataTransfer.files[0]) readProfile(e.dataTransfer.files[0]); });
  input.addEventListener("change", () => { if (input.files[0]) readProfile(input.files[0]); });
  return zone;
}

async function readProfile(file) {
  try {
    preview = await api("POST", "/api/convert/preview", file, { "X-Filename": file.name });
    importing = false;
    pageIndex = 0;
    selectedKey = null;
  } catch (error) {
    toast(error.message, "error");
  }
  renderDeck();
}

function previewBar() {
  const name = h("input", { type: "text", "aria-label": "Name of the pages", value: preview.pages[0].name.replace(/ \d+$/, "") });
  const layout = h("select", { "aria-label": "Keyboard layout the hotkeys were recorded with" },
    (overview.layouts || ["us"]).map((l) => h("option", { value: l, selected: l === overview.layout || undefined }, `Keyboard ${l}`)));
  const overwrite = h("input", { type: "checkbox" });
  const convert = h("button", { type: "button", class: "btn btn--go" }, `Convert ${plural(preview.pages.length, "page")}`);
  convert.addEventListener("click", () => act(convert, () => api("POST", "/api/convert",
    { upload: preview.upload, name: name.value, layout: layout.value, force: overwrite.checked }),
  (r) => `Wrote ${plural(r.written.length, "page")} to StreamController. Restart it to see them.`).then((r) => {
    if (!r) return;
    preview = null;
    loadDeck();
  }));
  const cancel = button("Cancel", () => { preview = null; renderDeck(); }, "btn--ghost");
  const toRedo = preview.pages.reduce((n, p) => n + p.keys.filter((k) => k.status === "manual").length, 0);

  return h("div", { class: "preview-bar" },
    h("div", { class: "preview-bar__line" },
      h("span", {}, h("span", { class: "preview-bar__score" }, `${preview.converted}/${preview.total}`), " keys convert"),
      h("span", { class: "note" }, preview.file)),
    selectedKey
      ? h("div", { class: "note" }, h("strong", {}, `${selectedKey.title || "Untitled key"}: ${STATUS[selectedKey.status]}. `),
          selectedKey.notes.join(" "))
      : h("div", { class: "note" }, toRedo
          ? `${plural(toRedo, "key")} outlined in red need an action picked in StreamController. Select a key to see why.`
          : "Select a key to see how it converts."),
    h("div", { class: "row" }, name, layout, h("label", { class: "check" }, overwrite, "Overwrite"), convert, cancel));
}

async function resetDeck(event) {
  await act(event.currentTarget, () => api("POST", "/api/deck/reset"),
    (r) => r.results.map((x) => x.ok ? `${x.name} was reset. Restart StreamController.` : `${x.name}: ${x.error}`).join(" "));
}

function showUdev() {
  const commands = `sudo tee ${deckData.udevPath} <<'EOF'\n${deckData.udev}EOF\nsudo udevadm control --reload && sudo udevadm trigger`;
  const copy = button("Copy the commands", async () => {
    await navigator.clipboard.writeText(commands);
    copy.textContent = "Copied";
  });
  openDrawer("Stream Deck permission",
    h("p", {}, "Linux only lets root open USB devices unless a rule allows your user. Run this once in a terminal:"),
    h("pre", { class: "block" }, commands), copy);
}

// ------------------------------------------------------------------------------- mixer

let audioData = null;
let dragged = null;

async function loadAudio() {
  audioData = await api("GET", "/api/audio");
  const ours = audioData.strips.filter((s) => s.ours);
  $("mixer-meta").textContent = ours.length ? `${plural(ours.length, "channel")} for OBS` : "One mix: everything reaches OBS together";
  fill("mixer-tools", button(ours.length ? "Channels" : "Set up", setupSinks), button("Refresh", loadAudio, "btn--ghost"));

  if (!ours.length && !audioData.configured.length) {
    fill("mixer", h("div", { class: "setup" },
      h("div", { class: "empty" }, h("strong", {}, "Give each sound its own fader in OBS"),
        "Create a channel for the game, the music, voice chat and alerts. You keep hearing everything; OBS gets each one separately."),
      sinkPicker()));
    return;
  }
  const strips = audioData.strips.map(strip);
  const elsewhere = audioData.elsewhere.length
    ? h("p", { class: "mixer-hint" }, "Playing elsewhere: ", audioData.elsewhere.map((a) => a.application).join(", "))
    : null;
  const pending = audioData.configured.length > ours.length
    ? h("p", { class: "mixer-hint" }, "Some channels appear after PipeWire restarts (Channels, then restart).") : null;
  fill("mixer", h("div", { class: "mixer" }, strips),
    h("p", { class: "mixer-hint" }, "Drag an app onto a channel to send its sound there."), elsewhere, pending);
}

function strip(data) {
  let timer = null;
  const value = h("span", { class: "strip__value" }, `${data.volume}%`);
  const fader = h("input", { type: "range", min: "0", max: "150", step: "1", value: String(data.volume),
    "aria-label": `${data.label} volume` });
  fader.addEventListener("input", () => {
    value.textContent = `${fader.value}%`;
    clearTimeout(timer);
    timer = setTimeout(() => api("POST", "/api/audio/volume", { sink: data.name, volume: Number(fader.value) })
      .catch((e) => toast(e.message, "error")), 120);
  });
  const mute = h("button", { type: "button", class: "mute", "aria-pressed": data.muted ? "true" : "false" }, "Mute");
  mute.addEventListener("click", async () => {
    const muted = mute.getAttribute("aria-pressed") !== "true";
    mute.setAttribute("aria-pressed", muted ? "true" : "false");
    try { await api("POST", "/api/audio/mute", { sink: data.name, muted }); }
    catch (e) { mute.setAttribute("aria-pressed", muted ? "false" : "true"); toast(e.message, "error"); }
  });
  const apps = h("div", { class: "apps" }, data.apps.map((app) =>
    h("div", { class: "app", draggable: "true", title: app.application,
      ondragstart: (e) => { dragged = app; e.dataTransfer.setData("text/plain", app.application); } }, app.application)));

  const el = h("div", { class: `strip${data.default ? " strip--master" : ""}`, title: data.detail },
    h("div", { class: "strip__name" }, data.label),
    h("div", { class: "fader" }, h("div", { class: "fader__scale", "aria-hidden": "true" },
      h("span", {}, "150"), h("span", {}, "100"), h("span", {}, "50"), h("span", {}, "0")), fader),
    value, mute, apps);
  el.addEventListener("dragover", (e) => { if (dragged) { e.preventDefault(); el.dataset.drop = ""; } });
  el.addEventListener("dragleave", () => { delete el.dataset.drop; });
  el.addEventListener("drop", async (e) => {
    e.preventDefault();
    delete el.dataset.drop;
    if (!dragged) return;
    const app = dragged;
    dragged = null;
    await act(null, () => api("POST", "/api/audio/route", { stream: app.index, sink: data.name }),
      `${app.application} now plays into ${data.label}.`);
    loadAudio();
  });
  return el;
}

function sinkPicker() {
  const configured = new Set(audioData.configured.map((n) => n.replace(/^tuxcast_/, "")));
  const keys = [...new Set([...Object.keys(audioData.descriptions), ...configured])];
  const boxes = keys.map((key) => h("input", { type: "checkbox", value: key,
    checked: (configured.size ? configured.has(key) : audioData.defaults.includes(key)) || undefined }));
  const restart = h("input", { type: "checkbox", checked: true });
  const save = h("button", { type: "button", class: "btn btn--go" }, configured.size ? "Save channels" : "Create channels");
  save.addEventListener("click", () => {
    const sinks = boxes.filter((b) => b.checked).map((b) => b.value);
    act(save, () => api("POST", "/api/audio/setup", { sinks, restart: restart.checked }),
      (r) => r.restarted ? "Channels created. Add each one to OBS as an Audio Output Capture." : "Saved. The channels appear after PipeWire restarts.")
      .then((r) => { if (r) { closeDrawer(); loadAudio(); loadChecks(); } });
  });
  return h("div", { class: "setup" },
    h("div", { class: "sink-pick" }, boxes.map((box, i) => h("label", {}, box, (audioData.descriptions[keys[i]] || keys[i]).replace("Stream · ", "")))),
    h("label", { class: "check" }, restart, "Restart PipeWire now (sound cuts for a second)"),
    h("div", { class: "row" }, save,
      configured.size ? button("Remove all channels", (e) => act(e.currentTarget,
        () => api("POST", "/api/audio/remove", { restart: restart.checked }), "Channels removed.")
        .then((r) => { if (r) { closeDrawer(); loadAudio(); } }), "btn--ghost") : null));
}

function setupSinks() {
  openDrawer("Audio channels",
    h("p", {}, "Each channel is a sound output you can pick in an app, and a separate source in OBS (Audio Output Capture). You keep hearing everything."),
    sinkPicker());
}

// ------------------------------------------------------------------------------- Discord

async function loadDiscord() {
  const data = await api("GET", "/api/discord");
  const linksOk = data.links.every((l) => l.ok);
  const clientsOk = data.clients.every((c) => !c.missing.length);
  if (!data.installs.length) {
    fill("discord", h("p", { class: "empty" }, h("strong", {}, "Discord is not installed"), "Nothing to connect."));
    return;
  }
  const connect = h("button", { type: "button", class: `btn ${linksOk && clientsOk ? "" : "btn--go"}` },
    linksOk && clientsOk ? "Repair" : "Connect Discord");
  connect.addEventListener("click", () => connectDiscord(connect));
  $("discord").replaceWith(h("div", { id: "discord" },
    h("div", { class: "dock__body" },
      h("div", { class: "status-line" }, h("span", { class: "led", dataset: { state: "ok" } }), data.installs.join(", "),
        h("span", {}, data.running.length ? "running" : "not running")),
      h("div", { class: "status-line" }, h("span", { class: "led", dataset: { state: linksOk ? "ok" : "warn" } }),
        linksOk ? "Socket visible where clients look" : "Socket hidden from clients",
        h("span", {}, data.links.length ? plural(data.links.length, "link") : "no link needed")),
      ...data.clients.map((c) => h("div", { class: "status-line" },
        h("span", { class: "led", dataset: { state: c.missing.length ? "warn" : "ok" } }),
        c.app.replace("com.core447.", ""), h("span", {}, c.missing.length ? "cannot reach Discord" : "can reach Discord"))),
      h("div", { class: "status-line" }, h("span", { class: "led", dataset: { state: data.service ? "ok" : "" } }),
        "Kept after reboot", h("span", {}, data.service ? "yes" : "not yet"))),
    h("div", { class: "dock__foot" }, connect)));
}

async function connectDiscord(btn) {
  const r = await act(btn, () => api("POST", "/api/discord", { install: true }),
    "Discord is connected. Restart StreamController to use it.");
  if (r) { closeDrawer(); loadDiscord(); loadChecks(); }
}

// ------------------------------------------------------------------------------- patches

const PATCH = { unchanged: ["ok", "applied"], applied: ["warn", "needs applying"], missing: ["", "file not found"],
  "no-match": ["fail", "pattern not found"], error: ["fail", "error"] };

async function loadPatches() {
  const data = await api("GET", "/api/patches");
  if (!data.patches.length) {
    fill("patches", h("p", { class: "empty" }, h("strong", {}, "No patches yet"),
      "A patch re-applies a small fix to an app file after every update. Add one to ", h("code", {}, data.folder), "."));
    return;
  }
  const apply = button("Apply now", (e) => act(e.currentTarget, () => api("POST", "/api/patches/apply"), "Patches applied.").then(loadPatches));
  const watch = button(data.watching ? "Stop watching" : "Re-apply after updates", (e) => act(e.currentTarget,
    () => api("POST", "/api/patches/watch", { enable: !data.watching }),
    data.watching ? "Patches are no longer watched." : "Patches now come back after every update.").then(loadPatches),
    data.watching ? "btn--ghost" : "btn--go");
  $("patches").replaceWith(h("div", { id: "patches" },
    h("div", { class: "dock__body" }, data.patches.map((p) => {
      const [state, label] = PATCH[p.state] || ["", p.state];
      return h("div", { class: "status-line", title: p.file }, h("span", { class: "led", dataset: { state } }), p.name,
        h("span", {}, p.error || label));
    }), h("div", { class: "status-line" }, h("span", { class: "led", dataset: { state: data.watching ? "ok" : "" } }),
      "Re-applied after updates", h("span", {}, data.watching ? "yes" : "no"))),
    h("div", { class: "dock__foot" }, apply, watch)));
}

// ------------------------------------------------------------------------------- start

let overview = {};

function guard(id, task) {
  return task().catch((error) => fill(id, h("p", { class: "empty" }, h("strong", {}, "This part could not load"), error.message)));
}

$("recheck").addEventListener("click", (e) => act(e.currentTarget, loadChecks));

api("GET", "/api/overview").then((data) => {
  overview = data;
  $("version").textContent = `v${data.version}`;
  guard("checks", loadChecks);
  guard("deck", loadDeck);
  guard("mixer", loadAudio);
  guard("discord", loadDiscord);
  guard("patches", loadPatches);
}).catch(() => {
  $("tally-text").textContent = "Open the address tuxcast ui printed";
  fill("checks", h("p", { class: "empty" }, h("strong", {}, "This page needs its token"),
    "Run tuxcast ui in a terminal and open the address it prints."));
});
