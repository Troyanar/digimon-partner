// Digimon-Partner – Digivice: die Begrüßung beantwortet "Was braucht mein Digimon gerade?", darunter die passende Aktion,
// Stufen-Leiste mit Schatten der nächsten Form, Tageswerte, Serien und Erfolge. Das Digimon spricht in einer Sprechblase,
// jede Eintragung hat eine kleine Belohnung (Balken laufen, Zahlen zählen hoch, Ton, Jubel).
import { Viewer, silhouette, snapshot } from "/static/viewer.js";
import { sfx, soundOn, setSound, allowSound } from "/static/sound.js";
import { isDevice, setupDevice } from "/static/device.js";
import { setupOffline, cachedMe, saveMe } from "/static/offline.js";
import { setupTraining } from "/static/train.js";
import { setupFriends } from "/static/friends.js";

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const wait = (ms) => new Promise((ok) => setTimeout(ok, ms));
const pick = (list) => list[Math.floor(Math.random() * list.length)];
const REDUCED = matchMedia("(prefers-reduced-motion: reduce)").matches;

const STATS = [["hunger", "Hunger"], ["thirst", "Durst"], ["power", "Kraft"], ["mind", "Geist"], ["disc", "Disziplin"], ["mood", "Laune"]];
const LOW = 20;
// Rot nur, wo es um Pflege geht: leere Kraft oder Geist am Anfang sind normal, kein Alarm
const CARE = new Set(["hunger", "thirst", "mood"]);
const LADDER = [["egg", "Ei"], ["baby", "Baby"], ["intraining", "In-Training"], ["rookie", "Rookie"], ["champion", "Champion"], ["ultimate", "Ultimate"], ["mega", "Mega"]];
const PREFIX = { a: "baby", b: "intraining", c: "rookie", d: "champion", e: "ultimate", f: "mega", g: "mega" };
const ui = { me: null, state: null, shown: null, busy: false, clockOffset: 0, storeKey: "", nextId: null, shadows: new Map() };
let NAMES = {};

async function api(path, method = "GET", data) {
  const opts = { method, headers: { "Content-Type": "application/json" } };
  if (data !== undefined) opts.body = JSON.stringify(data);
  let resp;
  const offline = (text) => Object.assign(new Error(text), { offline: true });
  try { resp = await fetch("/api" + path, opts); } catch { throw offline("Keine Verbindung zum Server."); }
  if (resp.status >= 502 && resp.status <= 504) throw offline("Der Server ist gerade nicht erreichbar.");
  if (resp.status === 401) { location.href = "/login"; throw new Error("Bitte anmelden"); }
  const json = await resp.json().catch(() => ({}));
  if (!resp.ok) throw new Error(json.error || `Fehler ${resp.status}`);
  return json;
}

let toastTimer;
function toast(text, err = false) {
  const el = $("toast");
  el.textContent = text; el.classList.toggle("err", err); el.classList.add("show");
  clearTimeout(toastTimer); toastTimer = setTimeout(() => el.classList.remove("show"), err ? 5000 : 2600);
}

const nameOf = (form) => (form === "egg" ? "Digi-Ei" : NAMES[form] || form);
const days = (h) => Math.max(1, Math.round(h / 24));
const head = () => ui.viewer?.headPoint() || { x: 0.5, y: 0.3 };

// --- Effekte ----------------------------------------------------------------------------------
/** Kurzer Hinweis über dem Digimon */
function fx(text, cls = "") {
  const el = document.createElement("span"), h = head();
  el.className = "fx " + cls; el.textContent = text;
  el.style.left = `${Math.min(85, Math.max(15, h.x * 100))}%`;
  el.style.top = `${Math.min(70, Math.max(14, h.y * 100 + 6))}%`;
  $("fx").appendChild(el);
  el.addEventListener("animationend", () => el.remove());
}

/** Daten-Splitter fliegen vom Digimon weg (großer Moment: Ziel erreicht, Erfolg, Digitation) */
function burst(count = 28) {
  if (REDUCED) return;
  const h = head(), colors = ["#ffffff", "#3fb6ff", "#f0b43c", "#ffffff"];
  for (let i = 0; i < count; i++) {
    const el = document.createElement("i"), a = Math.random() * Math.PI * 2, d = 120 + Math.random() * 220;
    el.className = "bit";
    el.style.left = `${h.x * 100}%`; el.style.top = `${Math.min(75, h.y * 100 + 12)}%`;
    el.style.setProperty("--dx", `${Math.cos(a) * d}px`); el.style.setProperty("--dy", `${Math.sin(a) * d - 60}px`);
    el.style.setProperty("--r", `${Math.random() * 540 - 270}deg`); el.style.setProperty("--c", pick(colors));
    el.style.setProperty("--t", `${0.8 + Math.random() * 0.6}s`);
    $("fx").appendChild(el);
    el.addEventListener("animationend", () => el.remove());
  }
}

function banner(text, big = false) {
  $("banner").innerHTML = `<span class="${big ? "big" : ""}">${esc(text)}</span>`;
  requestAnimationFrame(() => $("banner").firstChild.classList.add("in"));
}

function flash() { const f = $("flash"); f.classList.remove("go"); void f.offsetWidth; f.classList.add("go"); }

/** Zahl hochzählen statt springen */
function countTo(el, to, fmt = (v) => String(v)) {
  const from = Number(el.dataset.v ?? to);
  el.dataset.v = to;
  if (from === to || REDUCED) { el.textContent = fmt(to); return; }
  const start = performance.now(), len = Math.min(900, 250 + Math.abs(to - from) * 60);
  const step = (t) => {
    const k = Math.min(1, (t - start) / len), e = 1 - (1 - k) ** 3;
    el.textContent = fmt(Math.round(from + (to - from) * e));
    if (k < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
  if (to > from) { el.classList.remove("bump"); void el.offsetWidth; el.classList.add("bump"); }
}

function hex(on) {
  return on
    ? `<svg viewBox="0 0 48 48" aria-hidden="true"><path class="hex-on" d="M24 2l19 11v22L24 46 5 35V13z"/><path class="hex-on-ink" d="M20.5 31.5l-7-7 2.8-2.8 4.2 4.2 11.2-11.2 2.8 2.8z"/></svg>`
    : `<svg viewBox="0 0 48 48" aria-hidden="true"><path class="hex-off" d="M24 2l19 11v22L24 46 5 35V13z"/><path class="hex-off-ink" d="M24 14l9 5.2v10.4L24 34.8l-9-5.2V19.2zm0 3.5l-6 3.5v7l6 3.5 6-3.5v-7z"/></svg>`;
}

/** Erfolge nacheinander einblenden */
async function showAwards(list) {
  for (const a of list || []) {
    const el = document.createElement("div");
    el.className = "award";
    el.innerHTML = `${hex(true)}<small>Erfolg freigeschaltet</small><b>${esc(a.title)}</b>`;
    $("awards").appendChild(el);
    el.addEventListener("animationend", () => el.remove());
    sfx.award(); burst(18);
    say(pick(LINES.award));
    await wait(1100);
  }
}

// --- Das Digimon spricht ----------------------------------------------------------------------
const LINES = {
  egg: ["*wackel, wackel*", "*klopf, klopf*", "*knack …*"],
  asleep: ["Zzz …", "Zzz … noch fünf Minuten …", "Mmh … Fleisch …"],
  fasting: ["Wir schaffen das zusammen!", "Mein Magen knurrt, aber ich halte durch!", "Wasser ist erlaubt, oder?"],
  thirst: ["Ich hab sooo Durst!", "Wasser! Bitte, bitte!", "Meine Zunge ist ganz trocken."],
  hunger: ["Mein Bauch knurrt …", "Gibt's bald was zu essen?", "Ich könnte ein ganzes Fleisch verdrücken!"],
  sad: ["Mir ist irgendwie langweilig …", "Hast du mich vergessen?", "Ein bisschen Pflege wär schön …"],
  end: ["Ich bin jetzt richtig stark!", "Danke, dass du immer für mich da warst.", "Schau mal, wie groß ich geworden bin!"],
  good: ["Heute fühl ich mich super!", "Lass uns heute was schaffen!", "Wie viel Wasser hattest du heute schon?", "Ich will stärker werden!",
    "Ich spür, dass bald was passiert …", "Hey! Schön, dass du da bist."],
  water: ["Ahh, erfrischend!", "Gluck, gluck, gluck!", "Danke! Mehr davon!", "Wasser ist das Beste!"],
  goal: ["Wasserziel geschafft! Du bist super!", "Alle Gläser voll! Juhu!"],
  eat: ["Mmmh, lecker!", "Danke fürs Essen!", "Satt und glücklich!"],
  cooked: ["Selbst gekocht schmeckt am besten!", "Mmmh, das hast du gemacht? Super!", "Das war das Beste heute!"],
  fastStart: ["Okay, ab jetzt wird gefastet!", "Fasten? Na gut … für dich!"],
  fastDone: ["Geschafft! Wir sind so diszipliniert!"],
  fastBreak: ["Nicht schlimm, nächstes Mal klappt's!"],
  poke: ["Hey, das kitzelt!", "Was gibt's?", "Hihi!", "Ich bin bereit!", "Huch!"],
  award: ["Ein Erfolg! Wir sind ein Super-Team!", "Juhu, freigeschaltet!"],
};

function mood(state) {
  const p = state.pet, s = p.stats;
  if (p.form === "egg") return "egg";
  if (p.asleep) return "asleep";
  if (p.fasting) return "fasting";
  if (s.thirst < 35) return "thirst";
  if (s.hunger < 35) return "hunger";
  if (p.end) return "end";
  if (s.mood < 35) return "sad";
  return "good";
}

let bubbleTimer, bubbleFrame;
function say(text, ms = 4200) {
  const b = $("bubble");
  $("bubble-text").textContent = text;
  b.hidden = false;
  b.classList.remove("pop"); void b.offsetWidth; b.classList.add("pop");
  cancelAnimationFrame(bubbleFrame);
  const follow = () => {
    const h = head(), world = $("world");
    const minTop = (b.offsetHeight + 16) / world.clientHeight;
    b.style.left = `${Math.min(80, Math.max(20, h.x * 100))}%`;
    b.style.top = `${Math.min(0.62, Math.max(minTop, h.y - 0.02)) * 100}%`;
    bubbleFrame = requestAnimationFrame(follow);
  };
  follow();
  clearTimeout(bubbleTimer);
  bubbleTimer = setTimeout(() => { b.hidden = true; cancelAnimationFrame(bubbleFrame); }, ms);
}
const chatter = () => { if (!ui.busy && !ui.visiting && ui.state && document.visibilityState === "visible") say(pick(LINES[mood(ui.state)])); };

// --- Die eine Frage: was braucht es gerade? -------------------------------------------------
/** Liefert Titel, Unterzeile und die Aktion, die gerade am meisten hilft (oder null). */
function need(state) {
  const p = state.pet, s = p.stats, n = p.name;
  if (p.form === "egg") return { title: "Dein Digi-Ei wackelt.", sub: "Gleich schlüpft es. Bleib in der Nähe.", act: null };
  if (p.asleep) return { title: `${n} schläft.`, sub: `Bis ${state.settings.sleep_end} Uhr sinkt nichts.`, act: null };
  if (p.fasting) {
    const h = p.fasting.hours, goal = p.fasting.goal;
    if (h >= goal) return { title: "Fastenziel geschafft!", sub: `${n} ist stolz auf dich. Du kannst jetzt essen – oder noch weiter fasten.`, act: "eat" };
    return { title: `${n} fastet mit dir.`, sub: `${Math.floor(h)} von ${goal} Stunden geschafft. Wasser trinken ist erlaubt.`, act: "water" };
  }
  if (s.thirst < 35) return { title: `${n} hat Durst.`, sub: `${p.water_today} von ${p.water_goal} Gläsern heute.`, act: "water" };
  if (s.hunger < 35) return { title: `${n} hat Hunger.`, sub: "Trag ein, wenn du gegessen hast.", act: "eat" };
  if (p.waiting && p.jogress_partner)
    return { title: `${n} wartet auf ein ${p.jogress_partner}.`, sub: "Für die Jogress zu Paildramon. Schau bei Freunde, wer gerade eins hat.", act: null };
  if (p.end) return { title: `${n} ist ganz ausgewachsen.`, sub: "Es kann in die Ruhmeshalle ziehen, dann bekommst du ein neues Ei.", act: null };
  // "will trainieren" erst, wenn es die Trainingsseite gibt – die Begrüßung nennt nur, was man auch tun kann
  {
    const goal = state.settings.week_kraft + state.settings.week_geist;
    if (p.week.kraft + p.week.geist < goal && (s.power < 30 || s.mind < 30))
      return { title: `${n} will trainieren.`, sub: `${p.week.kraft + p.week.geist} von ${goal} Trainings diese Woche.`, act: "train" };
  }
  if (s.mood < 35) return { title: `${n} ist schlecht gelaunt.`, sub: "Etwas Wasser und Essen helfen.", act: "water" };
  if (p.water_today < p.water_goal)
    return { title: `${n} geht es gut.`, sub: `Noch ${p.water_goal - p.water_today} Gläser bis zum Wasserziel, dann wächst deine Serie.`, act: "water" };
  return { title: `${n} geht es super.`, sub: "Wasserziel für heute geschafft.", act: null };
}

// --- Darstellung ------------------------------------------------------------------------------
function buildStats() {
  $("stats").innerHTML = STATS.map(([key, label]) =>
    `<li data-k="${key}"><span>${label}</span><span class="bar"><i></i></span><span class="v num">0</span></li>`).join("");
}

function renderStats(p) {
  for (const [key] of STATS) {
    const li = $("stats").querySelector(`[data-k="${key}"]`), v = Math.round(p.stats[key]);
    li.classList.toggle("low", v <= LOW && CARE.has(key));
    li.querySelector("i").style.width = `${v}%`;
    countTo(li.querySelector(".v"), v);
  }
}

function renderWater(p) {
  const box = $("glasses"), goal = p.water_goal;
  if (box.children.length !== goal) {
    box.style.setProperty("--n", goal);
    box.innerHTML = Array.from({ length: goal }, () => "<i></i>").join("");
  }
  [...box.children].forEach((cell, i) => {
    const on = i < p.water_today;
    if (on && !cell.classList.contains("on") && ui.state?.pet) { cell.classList.remove("pop"); void cell.offsetWidth; cell.classList.add("pop"); }
    cell.classList.toggle("on", on);
  });
  countTo($("t-water"), p.water_today);
  $("t-water-goal").textContent = ` von ${goal} ${goal === 1 ? "Glas" : "Gläsern"}`;
  document.querySelector(".tile--water").classList.toggle("goal", p.water_today >= goal);
}

function renderTiles(state) {
  const p = state.pet, s = state.settings, pr = state.progress;
  renderWater(p);
  countTo($("t-streak"), pr.streak);
  $("t-streak-unit").textContent = pr.streak === 1 ? " Tag" : " Tage";
  $("t-streak-cap").textContent = pr.today_ok ? `Heute geschafft. Beste Serie: ${pr.best_streak}`
    : pr.streak ? `Heute noch ${p.water_goal - p.water_today} Gläser, sonst reißt sie.` : "Schaff heute dein Wasserziel, dann startet sie.";
  const goal = s.week_kraft + s.week_geist;
  countTo($("t-train"), p.week.kraft + p.week.geist);
  $("t-train-goal").textContent = ` von ${goal}`;
  $("t-train-cap").textContent = `Kraft ${p.week.kraft}/${s.week_kraft} · Dehnen und Yoga ${p.week.geist}/${s.week_geist}`;
  countTo($("t-mistakes"), p.mistakes);
}

// --- Schritte (vom iPhone) -----------------------------------------------------------------------------
const num = (n) => Number(n || 0).toLocaleString("de-DE");
const WD = ["So", "Mo", "Di", "Mi", "Do", "Fr", "Sa"];
function isoDay(d) { return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`; }

// Meldezeit (echte Uhrzeit des Servers): heute nur die Uhrzeit, sonst mit Datum
function whenText(ts) {
  const d = new Date(ts * 1000), hm = d.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
  return d.toDateString() === new Date().toDateString() ? `${hm} Uhr` : `${d.toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" })}, ${hm} Uhr`;
}

function renderSteps(state) {
  const st = state.steps, pr = state.progress;
  if (!st) return;
  const on = !!st.key || st.days.length > 0;
  $("steptile").hidden = !on;
  renderStepsBox(st);
  if (!on) return;
  const goal = st.goal, ok = st.today >= goal;
  countTo($("t-steps"), st.today, num);
  $("t-steps-goal").textContent = ` von ${num(goal)}`;
  $("step-bar").style.width = `${Math.min(100, Math.round((st.today / goal) * 100))}%`;
  $("steptile").classList.toggle("goal", ok);
  const last = st.key?.used;
  const ago = last ? `zuletzt gemeldet ${whenText(last)}` : "noch nichts gemeldet";
  const streak = pr.step_streak ? `Serie ${pr.step_streak} ${pr.step_streak === 1 ? "Tag" : "Tage"} · ` : "";
  $("t-steps-cap").textContent = ok ? `Ziel geschafft! ${streak}${ago}` : `Noch ${num(goal - st.today)} bis zum Ziel. ${streak}${ago}`;
  // die letzten 7 Tage, heute rechts; Höhe relativ zum größeren Wert aus Ziel und bestem Tag
  const by = Object.fromEntries(st.days.map((d) => [d.day, d.steps]));
  const today = new Date(state.now * 1000);
  const days = [...Array(7)].map((_, i) => { const d = new Date(today); d.setDate(d.getDate() - 6 + i); return d; });
  const top = Math.max(goal, ...days.map((d) => by[isoDay(d)] || 0)) * 1.05;
  $("step-bars").innerHTML = days.map((d, i) => {
    const n = by[isoDay(d)] || 0, label = `${WD[d.getDay()]} ${d.getDate()}.${d.getMonth() + 1}.: ${num(n)} Schritte`;
    return `<span class="sb${n >= goal ? " ok" : ""}${i === 6 ? " today" : ""}" role="listitem" title="${label}" aria-label="${label}">
      <i style="height:${Math.round((n / top) * 100)}%"></i><b>${WD[d.getDay()]}</b></span>`;
  }).join("") + `<span class="goalline" style="bottom:${Math.round((goal / top) * 100)}%" aria-hidden="true"></span>`;
}

function renderStepsBox(st) {
  const k = st.key;
  $("steps-status").textContent = !k ? "Noch nicht verbunden."
    : k.used ? `Verbunden · zuletzt gemeldet ${whenText(k.used)}` : "Schlüssel erzeugt · wartet auf die erste Meldung vom iPhone";
  $("steps-new").textContent = k ? "Neuen Schlüssel erzeugen" : "Schlüssel erzeugen";
  $("steps-drop").hidden = !k;
  $("steps-url").textContent = `${location.origin}/api/steps`;
  if (!k) $("steps-keybox").hidden = true;
}

async function newStepKey() {
  if (ui.state?.steps?.key && !confirm("Neuer Schlüssel? Der alte im Kurzbefehl funktioniert dann nicht mehr.")) return;
  try {
    const res = await api("/steps/key", "POST", {});
    $("steps-key").textContent = res.key;
    $("steps-keybox").hidden = false;
    $("steps-howto").open = true;
    ui.state.steps.key = res.info;
    renderSteps(ui.state);
    $("steps-keybox").hidden = false;
  } catch (err) { toast(err.message, true); }
}

async function dropStepKey() {
  if (!confirm("Verbindung zum iPhone trennen? Der Kurzbefehl kann dann nichts mehr schicken.")) return;
  try { await api("/steps/key", "DELETE", {}); ui.state.steps.key = null; renderSteps(ui.state); toast("Getrennt."); } catch (err) { toast(err.message, true); }
}

async function copy(text) {
  try { await navigator.clipboard.writeText(text); toast("Kopiert."); } catch { toast("Kopieren ging nicht – bitte von Hand markieren.", true); }
}

function renderEvo(p) {
  const idx = p.stage_index;
  const seen = {};
  for (const f of p.forms) seen[PREFIX[f[0]]] = f;
  $("evo-name").textContent = p.form === "egg" ? "Digi-Ei" : p.name;
  $("evo-stage").textContent = `${p.stage_label} · Stufe ${idx + 1} von 7`;
  $("evo-bar").style.width = `${Math.round((p.end ? 1 : p.progress ?? 1) * 100)}%`;
  let left;
  if (p.form === "egg") left = "Schlüpft gleich";
  else if (p.end) left = "Endstufe erreicht";
  else if (p.waiting) left = "Wartet auf einen Jogress-Partner";
  else { const d = days(p.hours_left); left = `Noch ${d} ${d === 1 ? "Tag" : "Tage"} bis zur Digitation`; }
  $("evo-left").textContent = left;
  $("ladder").innerHTML = LADDER.map(([key, label], i) => {
    const cls = i < idx ? "done" : i === idx ? "now" : "";
    const who = key === "egg" ? "Digi-Ei" : seen[key] ? nameOf(seen[key]) : "";
    return `<li class="${cls}"${who ? ` title="${esc(who)}"` : ""}><i></i><span>${label}</span></li>`;
  }).join("");
  // Schatten der nächsten Form ("???"); bei der Endstufe nicht
  const nextId = p.end ? null : p.next;
  $("next").hidden = !nextId;
  $("next-cap").textContent = p.jogress_partner ? `Per Jogress mit einem ${p.jogress_partner}`
    : p.lazy_risk ? "Zu wenig Training! Sonst wird es etwas anderes …"
    : p.tendency === "geist" ? "Richtung Geist-Weg" : p.tendency === "kraft" ? "Richtung Kraft-Weg" : "Nächste Form";
  $("next-cap").classList.toggle("warn", !!p.lazy_risk);
  if (nextId && nextId !== ui.nextId) loadShadow(nextId);
  ui.nextId = nextId;
}

async function loadShadow(id) {
  const img = $("next-img");
  img.hidden = true; $("next-q").hidden = false;
  if (!ui.shadows.has(id)) ui.shadows.set(id, silhouette(id));
  const url = await ui.shadows.get(id);
  if (ui.nextId !== id || !url) return;
  img.src = url; img.hidden = false; $("next-q").hidden = true;
}

function renderActions(state, act) {
  const p = state.pet;
  $("act-fast").textContent = p.fasting ? "Fasten beenden" : "Fasten starten";
  for (const [id, kind] of [["act-water", "water"], ["act-eat", "eat"], ["act-fast", "fast"], ["act-train", "train"]])
    $(id).classList.toggle("btn--primary", act === kind);
  $("actions").hidden = p.form === "egg";
}

function renderAchievements(pr) {
  $("ach-sub").textContent = `${pr.unlocked} von ${pr.total} freigeschaltet. Erfolge bleiben, auch wenn dein Partner in die Ruhmeshalle zieht.`;
  countTo($("k-streak"), pr.streak);
  countTo($("k-best"), pr.best_streak);
  countTo($("k-glasses"), pr.glasses);
  $("k-more").textContent = `${pr.fasts} Fastenfenster, ${pr.evolutions} ${pr.evolutions === 1 ? "Digitation" : "Digitationen"}`;
  const date = (ts) => new Date(ts * 1000 - ui.clockOffset * 1000).toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric" });
  const items = [...pr.achievements].sort((a, b) => (!!b.unlocked - !!a.unlocked) || (b.value / b.goal - a.value / a.goal));
  $("badges").innerHTML = items.map((a) => `<li class="badge ${a.unlocked ? "" : "locked"}">${hex(!!a.unlocked)}
    <b>${esc(a.title)}</b><p>${esc(a.text)}</p>
    ${a.unlocked ? `<p class="got num">Freigeschaltet am ${date(a.unlocked)}</p>`
      : `<div><div class="meter"><i style="width:${Math.round((a.value / a.goal) * 100)}%"></i></div><p class="num">${num(a.value)} von ${num(a.goal)}</p></div>`}</li>`).join("");
}

function baseRole(p) {
  if (p.asleep) return "sleep";
  if (p.stats.hunger < 15 || p.stats.thirst < 15) return "hungry";
  if (p.stats.mood < 35) return "sad";
  return "idle";
}

let zzTimer;
async function render(state, { animate = true } = {}) {
  ui.clockOffset = state.now - Date.now() / 1000;
  if (!state.offline) off?.saveState(state);
  renderNet(state);
  const p = state.pet, n = need(state);
  ui.viewer.setTime(p.asleep ? "night" : Number(state.clock.slice(7, 9)) >= 19 ? "dusk" : "day");
  $("clock").textContent = state.clock.slice(7);
  $("greeting").textContent = n.title;
  $("sub").textContent = n.sub;
  renderActions(state, n.act);
  renderTiles(state);
  renderSteps(state);
  renderStats(p);
  renderEvo(p);
  renderAchievements(state.progress);
  ui.state = state;
  renderFasting(state);
  $("newegg").hidden = !p.end;
  renderDiary(state.diary);
  $("tab-count").textContent = ` ${state.progress.unlocked}/${state.progress.total}`;
  clearInterval(zzTimer);
  if (p.asleep) zzTimer = setInterval(() => fx("z", "zz"), 1300);
  tickFast();
  trainer.refresh();
  renderJogressCard(state);
  renderTeam(state);
  showAwards(state.unlocked_now);
  // Anderer Partner aktiv (Wechsel oder neues Ei): eigene Form-Erinnerung je Partner, keine Digitations-Sequenz
  const switched = ui.petId !== undefined && ui.petId !== state.pet_id;
  if (switched) ui.shown = null;
  ui.petId = state.pet_id;
  ui.storeKey = `partner.form.${ui.me.user.name}.${state.pet_id}`;
  if (ui.visiting) return;
  await showForm(p, animate);
  if (!ui.training) ui.viewer.setBase(baseRole(p));
  device?.update(state, mood(state));   // nach einer Digitations-Sequenz melden, nicht mittendrin
  if (switched) {
    flash(); sfx.go();
    banner(p.form === "egg" ? "Ein neues Digi-Ei!" : `${p.name}, du bist dran!`, true);
    setTimeout(() => say(p.form === "egg" ? "*wackel, wackel*" : pick(["Ich bin wieder da!", "Endlich wieder ich!", "Hat mir gefehlt!"])), 900);
  }
}

/** Neue Form anzeigen – mit Digitations-Sequenz, wenn sie sich seit dem letzten Besuch geändert hat. */
async function showForm(p, animate) {
  if (ui.shown === p.form) return;
  let prev = ui.shown;
  try {
    // ältere Fassung merkte sich die Form pro Konto statt pro Partner
    prev ??= localStorage.getItem(ui.storeKey) ?? localStorage.getItem(`partner.form.${ui.me.user.name}`);
  } catch { /* ohne Speicher keine Sequenz nach dem Neuladen */ }
  const first = ui.shown === null;
  ui.shown = p.form;
  if (animate && prev && prev !== p.form && (NAMES[prev] || prev === "egg")) {
    if (first) await ui.viewer.show(prev, p.egg_model);
    $("loading").hidden = true;
    await evolveSequence(prev, p);
  } else {
    const ok = await ui.viewer.show(p.form, p.egg_model);
    $("loading").hidden = ok;
    if (!ok) $("loading").textContent = `Das Modell für ${p.name} fehlt noch.`;
    if (first) setTimeout(() => { if (!p.asleep && p.form !== "egg") ui.viewer.play("greet"); chatter(); }, 900);
  }
  try { localStorage.setItem(ui.storeKey, p.form); } catch { /* egal */ }
}

async function evolveSequence(from, p) {
  ui.busy = true;
  $("bubble").hidden = true;
  $("world").classList.add("rush");
  const jog = p.form === "e009" && (from === "d009" || from === "d011");
  banner(from === "egg" ? "Das Digi-Ei schlüpft …" : p.form === "g013" ? "Formwechsel …" : jog ? "Jogress …" : `${nameOf(from)} digitiert zu …`);
  sfx.evolve();
  await wait(400);
  await ui.viewer.digivolve(p.form, p.egg_model, { onFlash: flash });
  $("world").classList.remove("rush");
  banner(`${p.name}!`, true);
  sfx.goal(); burst(36);
  ui.busy = false;
  setTimeout(() => say(from === "egg" ? "Hallo! Ich bin's, dein Partner!" : `Ich bin jetzt ${p.name}!`), 1200);
}

function renderDiary(entries) {
  const fmt = (at) => new Date(at * 1000 - ui.clockOffset * 1000).toLocaleString("de-DE", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
  $("diary").innerHTML = entries.length
    ? entries.map((e) => `<li class="${e.kind}"><time class="num">${fmt(e.at)}</time><span>${esc(e.text)}</span></li>`).join("")
    : `<li><span></span><span>Noch nichts passiert. Trink ein Glas Wasser, dann steht hier der erste Eintrag.</span></li>`;
}

async function renderHall() {
  const hall = await api("/hall");
  $("hall").innerHTML = hall.length ? hall.map((h) => `<div class="hallcard"><b>${esc(h.name)}</b>
    <p>Ei: ${esc(h.line)}. ${h.forms.map((f) => esc(f.name)).join(" → ")}</p>
    <p class="num">${new Date(h.created * 1000).toLocaleDateString("de-DE")} bis ${new Date(h.ended * 1000).toLocaleDateString("de-DE")}</p></div>`).join("")
    : `<p class="caption">Noch leer. Hat dein Partner seine Endstufe erreicht, kann er hier einziehen.</p>`;
}

// --- Aktionen ---------------------------------------------------------------------------------------
async function act(kind) {
  if (ui.busy) return;
  const p = ui.state.pet;
  try {
    if (kind === "water") {
      const before = p.water_today;
      const res = await record("water", { glasses: 1 });
      const reached = before < res.pet.water_goal && res.pet.water_today >= res.pet.water_goal;
      sfx.water(); fx("+1 Glas");
      await render(res);
      if (reached) {
        ui.viewer.play("cheer"); sfx.goal(); burst(); banner("Wasserziel geschafft!", true);
        say(pick(LINES.goal));
      } else { ui.viewer.play("happy"); say(pick(LINES.water), 2600); }
    } else if (kind === "eat") {
      const res = await record("eat");
      sfx.eat(); ui.viewer.play("eat"); fx("Lecker!");
      await render(res);
      say(pick(LINES.eat), 2600);
    } else if (kind === "fast") {
      if (!p.fasting) { openFastStart(); return; }
      const res = await record("fast_stop");
      if (res.offline) {   // ohne Server: selbst sagen, ob das Ziel geschafft war
        const done = (gameNow() - p.fasting.start) / 3600 >= p.fasting.goal;
        res.done = [{ kind: done ? "fast_done" : "fast_break", text: done ? "Fasten geschafft!" : "Fasten beendet." }];
      }
      res.done.forEach((d) => toast(d.text));
      await render(res);
      if (res.done.some((d) => d.kind === "fast_done")) {
        ui.viewer.play("cheer"); sfx.goal(); burst(); banner("Fasten geschafft!", true); say(pick(LINES.fastDone));
      } else if (res.done.some((d) => d.kind === "fast_break")) { sfx.fast(); ui.viewer.play("down"); say(pick(LINES.fastBreak)); }
      else { sfx.fast(); say(pick(LINES.fastStart)); }
    } else if (kind === "train") {
      sfx.tap(); showTab("training");
    }
  } catch (err) { toast(err.message, true); }
}

function poke() {
  if (ui.busy || !ui.state || ui.state.pet.asleep) return;
  sfx.poke();
  if (ui.state.pet.form !== "egg") ui.viewer.play(pick(["happy", "happy", "confused"]));
  say(pick(ui.state.pet.form === "egg" ? LINES.egg : LINES.poke), 2400);
}

// --- Fasten ---------------------------------------------------------------------------------------
const hm = (h) => `${Math.floor(h)}:${String(Math.floor((h % 1) * 60)).padStart(2, "0")}`;
const timeOf = (ts) => new Date(ts * 1000).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
const dayKey = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const WEEKDAY = ["So", "Mo", "Di", "Mi", "Do", "Fr", "Sa"];

function fastPhase(h, goal) {
  if (h >= goal) return "Ziel erreicht. Jede weitere Stunde ist Bonus.";
  if (h < 4) return "Die letzte Mahlzeit wird noch verdaut.";
  if (h < 12) return "Der Magen ist leer, dein Körper lebt jetzt von seinen Speichern.";
  return "Endspurt: Der Körper greift jetzt stärker auf seine Fettreserven zurück.";
}

function openFastStart() {
  const now = new Date((Date.now() / 1000 + ui.clockOffset) * 1000);
  $("fast-at").value = `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`;
  $("fast-start").hidden = false; $("fast-idle").hidden = true;
  $("fastcard").scrollIntoView({ behavior: REDUCED ? "auto" : "smooth", block: "nearest" });
}

async function startFast(minutesAgo) {
  try {
    const res = await record("fast_start", { minutes_ago: minutesAgo });
    $("fast-start").hidden = true;
    res.done.forEach((d) => toast(d.text));
    await render(res);
    sfx.fast(); say(pick(LINES.fastStart));
  } catch (err) { toast(err.message, true); }
}

function renderFasting(state) {
  const p = state.pet, f = p.fasting, goal = state.settings.fast_goal, pr = state.progress;
  $("fast-rhythm").textContent = `${goal}:${24 - goal}`;
  $("fast-run").hidden = !f;
  if (f) {
    $("fast-start").hidden = true;
    $("fast-from").textContent = timeOf(f.start);
    $("fastgoal").textContent = `Ziel ${timeOf(f.goal_at)} Uhr`;
    $("fast-tick12").hidden = f.goal <= 12;
    $("fast-tick12").style.left = `${(12 / f.goal) * 100}%`;
  }
  // Ohne laufendes Fasten: Essfenster nach dem letzten geschafften Fasten
  const last = [...state.fasts].reverse().find((x) => x.done);
  let idle = "Kein Fasten aktiv. Starte es nach deiner letzten Mahlzeit, auch rückwirkend.";
  if (last && state.now - last.end < (24 - last.goal) * 3600)
    idle = `Essfenster offen bis ${timeOf(last.end + (24 - last.goal) * 3600)} Uhr. Danach am besten wieder fasten.`;
  $("fast-idle").textContent = idle;
  $("fast-idle").hidden = !!f || !$("fast-start").hidden;
  countTo($("f-streak"), pr.fast_streak, (v) => `${v} ${v === 1 ? "Tag" : "Tage"}`);
  $("f-longest").textContent = `${String(pr.longest_fast).replace(".", ",")} Std.`;
  renderFastChart(state);
}

/** Säulen: pro Tag das längste Fasten, das an diesem Tag endete. Gestrichelte Linie = Ziel. */
function renderFastChart(state) {
  const goal = state.settings.fast_goal, today = new Date(state.now * 1000);
  const days = Array.from({ length: 14 }, (_, i) => { const d = new Date(today); d.setDate(d.getDate() - 13 + i); return d; });
  const best = {};
  for (const x of state.fasts) {
    const k = dayKey(new Date(x.end * 1000)), hours = (x.end - x.start) / 3600;
    if (!best[k] || hours > best[k].hours) best[k] = { hours, done: x.done };
  }
  const plot = $("fchart");
  plot.querySelectorAll(".fbar, .fchart-goal").forEach((el) => el.remove());
  plot.insertAdjacentHTML("beforeend", `<div class="fchart-goal" style="bottom:${(goal / 24) * 100}%"><span>Ziel ${goal} Std.</span></div>`);
  let count = 0;
  days.forEach((d) => {
    const k = dayKey(d), b = best[k], label = `${WEEKDAY[d.getDay()]} ${d.getDate()}.${d.getMonth() + 1}.`;
    if (b?.done) count++;
    const text = b ? `${label}: ${hm(b.hours)} Std., ${b.done ? "Ziel erreicht" : "vorher beendet"}` : `${label}: kein Fasten`;
    const el = document.createElement("button");
    el.className = `fbar ${b ? (b.done ? "" : "short") : "none"}`;
    el.setAttribute("aria-label", text); el.dataset.tip = text;
    el.innerHTML = `<i style="height:${b ? Math.min(100, (b.hours / 24) * 100) : 0}%"></i>`;
    plot.appendChild(el);
  });
  countTo($("f-count"), count);
  // Ohne ein einziges Fasten in 14 Tagen: keine leere Fläche, sondern ein kurzer Hinweis
  const empty = !state.fasts.length;
  $("fchart").closest(".fchart").hidden = empty;
  $("fchart-empty").hidden = !empty;
  $("fchart-days").innerHTML = days.map((d, i) => `<span class="${i === 13 ? "today" : ""}">${i === 13 ? "Heute" : WEEKDAY[d.getDay()]}</span>`).join("");
}

function showTip(el) {
  // direkt über der Säule (bei leeren Tagen über der Grundlinie), nie über den Rand hinaus
  const tip = $("ftip"), fig = tip.parentElement.getBoundingClientRect(), r = el.getBoundingClientRect();
  const top = el.querySelector("i").getBoundingClientRect().top || r.bottom;
  tip.textContent = el.dataset.tip; tip.hidden = false;
  const x = r.left + r.width / 2 - fig.left;
  tip.style.left = `${Math.min(fig.width - tip.offsetWidth / 2, Math.max(tip.offsetWidth / 2, x))}px`;
  tip.style.bottom = `${fig.bottom - top + 8}px`;
}

function tickFast() {
  const f = ui.state?.pet.fasting;
  if (!f) return;
  const now = Date.now() / 1000 + ui.clockOffset;
  const h = Math.max(0, (now - f.start) / 3600);
  const bonus = h >= f.goal;
  $("fasttime").innerHTML = bonus
    ? `${hm(h)}<span class="unit"> Stunden, Ziel geschafft</span>`
    : `${hm(h)}<span class="unit"> von ${f.goal} Stunden</span>`;
  $("fast-phase").textContent = fastPhase(h, f.goal);
  $("fastbar").style.width = `${Math.min(100, (h / f.goal) * 100)}%`;
  $("fastcard").classList.toggle("bonus", bonus);
  // Ziel erreicht: einmal pro Fasten feiern (auch wenn man erst später wieder reinschaut)
  const key = `partner.fastgoal.${f.start}`;
  let seen = true;
  try { seen = !!localStorage.getItem(key); } catch { /* ohne Speicher lieber nicht wiederholen */ }
  if (bonus && !seen && !ui.busy) {
    try { localStorage.setItem(key, "1"); } catch { /* egal */ }
    ui.viewer.play("cheer"); sfx.goal(); burst(); banner("Fastenziel erreicht!", true);
    say(pick(LINES.fastDone));
  }
}

// --- Einstellungen ----------------------------------------------------------------------------------
const FIELDS = ["sleep_start", "sleep_end", "water_goal", "fast_goal", "step_goal", "week_kraft", "week_geist"];
function fillSettings(s, share) {
  const f = $("settings");
  for (const key of FIELDS) f.elements[key].value = s[key];
  if (share !== undefined) f.elements.share.checked = share;
}

async function renderInvites() {
  const list = await api("/invites");
  $("invites").innerHTML = list.map((i) => `<li><code>${esc(i.code)}</code> ${i.used_by ? `benutzt von ${esc(i.used_by)}` : "noch frei"}</li>`).join("");
}

function showTab(name) {
  document.querySelectorAll("#tabs button").forEach((x) => (x.dataset.tab === name ? x.setAttribute("aria-current", "page") : x.removeAttribute("aria-current")));
  document.querySelectorAll(".view").forEach((t) => { t.hidden = t.id !== `tab-${name}`; });
  if (name === "training") trainer.load().catch((err) => toast(err.message, true));
  if (name === "erfolge") renderHall().catch((err) => toast(err.message, true));
  if (name === "freunde") friends.load().catch((err) => toast(err.message, true));
  if (name === "einstellungen" && ui.me.user.admin) renderInvites().catch(() => {});
}

function renderSound() {
  const on = soundOn();
  $("sound").textContent = on ? "Ton an" : "Ton aus";
  $("sound").setAttribute("aria-pressed", String(on));
}

// --- Gekocht! (Link von der Rezepte-Seite: /?gekocht=Rezeptname) ----------------------------------
const cookedName = (new URLSearchParams(location.search).get("gekocht") || "").trim().slice(0, 120);

function showCook(state) {
  if (!cookedName) return;
  const p = state.pet;
  $("cook-name").textContent = cookedName;
  $("cook-text").textContent = p.form === "egg" ? "Dein Digi-Ei schlüpft gleich. Danach kannst du es füttern."
    : `Füttere ${p.name} mit deinem selbst gekochten Gericht. Das macht satter und froher als normales Essen.`;
  $("cook-go").hidden = p.form === "egg";
  $("cook").hidden = false;
  showTab("partner");
}

function closeCook() {
  $("cook").hidden = true;
  history.replaceState(null, "", "/");  // Neuladen füttert nicht nochmal
}

async function feedCooked() {
  if (ui.busy) return;
  try {
    const res = await record("eat", { cooked: cookedName });
    closeCook();
    sfx.eat(); ui.viewer.play("eat"); fx("Selbst gekocht!");
    await render(res);
    setTimeout(() => { ui.viewer.play("cheer"); sfx.goal(); burst(); banner("Selbst gekocht!", true); say(pick(LINES.cooked)); }, 1600);
  } catch (err) { toast(err.message, true); }
}

// --- Team: bis zu 3 Partner, einer aktiv; neue Eier selbst aussuchen ----------------------------------
const pics = new Map();
function pic(id, eggModel, img) {
  const key = `${id}|${eggModel}`;
  if (!pics.has(key)) pics.set(key, snapshot(id, eggModel));
  pics.get(key).then((url) => { if (url && img.isConnected) { img.src = url; img.hidden = false; } });
}

function renderTeam(state) {
  const size = ui.me.team_size || 3, team = state.team || [];
  const list = $("team");
  list.style.setProperty("--slots", size);
  const html = team.map((t) => `<li><button class="slot ${t.active ? "on" : ""}" data-switch="${t.id}" ${t.active ? 'aria-current="true"' : ""}>
      <span class="pic"><img alt="" hidden data-pic="${esc(t.form)}" data-egg="${esc(t.egg_model)}"></span>
      <b>${esc(t.name)}</b><small>${t.active ? "Aktiv" : `${esc(t.stage_label)} · pausiert`}</small></button></li>`);
  for (let i = team.length; i < size; i++)
    html.push(`<li><button class="slot add" data-newegg="1"><span class="pic">+</span><b>Neues Ei</b><small>Platz frei</small></button></li>`);
  const sig = JSON.stringify(team.map((t) => [t.id, t.form, t.active]));
  if (list.dataset.sig === sig) return;  // unverändert: Bilder nicht neu laden
  list.dataset.sig = sig;
  list.innerHTML = html.join("");
  list.querySelectorAll("img[data-pic]").forEach((img) => pic(img.dataset.pic, img.dataset.egg, img));
}

function openEggPick(retire) {
  ui.eggRetire = retire;
  $("egg-note").textContent = retire
    ? `${ui.state.pet.name} zieht in die Ruhmeshalle. Such dir das nächste Ei aus.`
    : `${ui.state.pet.name} macht solange Pause, seine Zeit steht still. Du kannst jederzeit zurückwechseln.`;
  $("eggs").innerHTML = (ui.me.lines || []).map((l) => `<li><button class="egg" data-line="${esc(l.key)}">
      <span class="pic"><img alt="" hidden data-pic="egg" data-egg="${esc(l.egg_model)}"></span><b>${esc(l.egg)}</b></button></li>`).join("");
  $("eggs").querySelectorAll("img[data-pic]").forEach((img) => pic("egg", img.dataset.egg, img));
  $("eggpick").hidden = false;
  $("eggpick").scrollIntoView({ behavior: REDUCED ? "auto" : "smooth", block: "nearest" });
}

async function takeEgg(line) {
  if (ui.busy) return;
  try {
    const res = await api("/egg", "POST", { line, retire: !!ui.eggRetire });
    $("eggpick").hidden = true;
    await render(res);
  } catch (err) { toast(err.message, true); }
}

async function switchTo(id) {
  if (ui.busy || ui.training) { if (ui.training) toast("Erst das laufende Training beenden.", true); return; }
  if (ui.visiting) await endVisit();
  try { await render(await api("/team/switch", "POST", { id })); } catch (err) { toast(err.message, true); }
}

// --- Freunde und Jogress ---------------------------------------------------------------------------
function renderJogressCard(state) {
  const req = state.jogress_in || [];
  $("jog-card").hidden = !req.length;
  if (req.length) $("jog-h").textContent = `${req[0].from_name} möchte Jogress mit dir!`;
  $("friend-count").textContent = req.length ? ` ${req.length}` : "";
}

/** Freund besuchen: die Welt zeigt dessen Digimon, bis man zurückgeht */
async function visitFriend(f) {
  ui.visiting = f;
  $("bubble").hidden = true;
  $("visit-text").textContent = `Besuch bei ${f.name}`;
  $("visit").hidden = false;
  const ok = await ui.viewer.show(f.pet.form, f.pet.egg_model);
  if (!ok) { toast(`Das Modell für ${f.pet.name} fehlt noch.`, true); }
  ui.viewer.setBase(f.pet.asleep ? "sleep" : "idle");
  sfx.poke();
  if (!f.pet.asleep) { ui.viewer.play("greet"); setTimeout(() => say(f.pet.form === "egg" ? "*wackel*" : `Hallo! Ich bin ${f.name}s ${f.pet.name}!`), 700); }
  else say("Zzz …");
  $("world").scrollIntoView({ behavior: REDUCED ? "auto" : "smooth", block: "nearest" });
}

async function endVisit() {
  if (!ui.visiting) return;
  ui.visiting = null;
  $("visit").hidden = true;
  $("bubble").hidden = true;
  const p = ui.state.pet;
  await ui.viewer.show(p.form, p.egg_model);
  ui.viewer.setBase(baseRole(p));
  say(pick(["Da bist du ja wieder!", "Wie war's bei deinem Freund?", "Hast du mich vermisst?"]), 2600);
}

const friends = setupFriends({
  api, toast, sfx, showTab, state: () => ui.state, visit: visitFriend,
  render: (s) => render(s), endVisit,
});

// --- Offline: Warteschlange und Sync (siehe offline.js) -------------------------------------------------
let off = null;
const gameNow = () => Date.now() / 1000 + ui.clockOffset;

/** Eintragung: mit Netz sofort, sonst in die Warteschlange – der Server holt sie beim Sync zur richtigen Uhrzeit nach. */
async function record(kind, data = {}) {
  if (off.pending()) { try { await off.flush(api); } catch (e) { if (!e.offline) throw e; } }
  if (!off.pending()) {
    try { return await api("/action", "POST", { kind, ...data }); } catch (e) { if (!e.offline) throw e; }
  }
  off.push(kind, data, gameNow());
  return { ...off.view(gameNow()), done: [] };
}

async function syncNow() {
  const res = await off.flush(api);
  if (!res) return null;
  (res.rejected || []).forEach((r) => toast(`Nicht übernommen: ${r.error}`, true));
  const n = res.synced.length;
  if (n) toast(`Synchronisiert: ${n} ${n === 1 ? "Eintrag" : "Einträge"}.`);
  await render(res);
  return res;
}

/** Regelmäßig und wenn das Netz zurückkommt: erst Wartendes schicken, sonst neuen Stand holen. */
async function refresh() {
  if (ui.busy || !off) return;
  try {
    if (off.pending()) await syncNow();
    else await render(await api("/state"));
  } catch (e) {
    if (e.offline && off.lastState()) render(off.view(gameNow()));
  }
}

function renderNet(state) {
  const n = off?.pending() || 0;
  $("net").hidden = !state.offline && !n;
  $("net").textContent = state.offline
    ? `Offline${n ? ` · ${n} ${n === 1 ? "Eintrag wartet" : "Einträge warten"} auf Sync` : ""}`
    : `Synchronisiere ${n} …`;
}

// --- Training ---------------------------------------------------------------------------------------
function celebrate(text) {
  ui.viewer.play("cheer"); sfx.goal(); burst(); banner(text, true);
  say(pick(["Wir werden immer stärker!", "Super Training!", "Das hat Spaß gemacht!"]));
}
const trainer = setupTraining({
  api, toast, say, sfx, celebrate, render: (s) => render(s, { animate: true }),
  state: () => ui.state, get viewer() { return ui.viewer; },
  setTraining: (on) => { ui.training = on; if (!on && ui.state) ui.viewer.setBase(baseRole(ui.state.pet)); },
  gameNow,
  queueTrain: (plan, start, end) => {
    off.push("train", { plan: plan.id, start, title: plan.title, art: plan.art, minutes: plan.minutes }, end);
    return { ...off.view(gameNow()), done: [] };
  },
  rerender: () => ui.state && trainer.refresh(),
});

// --- Geräte-Modus ------------------------------------------------------------------------------------
let device = null;
function startDevice() {
  allowSound();
  device = setupDevice({
    showTab, clockOffset: () => ui.clockOffset, busy: () => ui.busy || ui.training || !!ui.visiting,
    alert: (text) => { sfx.alert(); ui.viewer.play("down"); say(text, 6000); },
  });
}

// --- Start ------------------------------------------------------------------------------------------
async function main() {
  try {
    ui.me = await api("/me");
    if (ui.me.user) saveMe(ui.me);
  } catch (e) {
    if (!e.offline || !cachedMe()) throw e;
    ui.me = cachedMe();   // offline: letzter bekannter Stand
  }
  if (!ui.me.user) { location.href = "/login"; return; }
  off = setupOffline(ui.me.user.name);
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => {});
  NAMES = ui.me.names || {};
  $("who").textContent = ui.me.user.name;
  $("dev").hidden = !ui.me.dev;
  $("invitebox").hidden = !ui.me.user.admin;
  renderSound();
  buildStats();
  if (isDevice()) startDevice();
  $("devicebox").hidden = !window.Geraet;
  $("stepsbox").hidden = !!window.Geraet;   // eingerichtet wird auf dem iPhone, nicht auf dem Digimon-Gerät
  // Download der Geräte-App – nicht in der App selbst, und nur wenn sie gebaut ist
  $("apkbox").hidden = !!window.Geraet || !ui.me.apk;
  if (ui.me.apk) {
    $("apk-link").textContent = `App herunterladen (${ui.me.apk.size_kb} KB)`;
    $("apk-meta").textContent = `Stand ${new Date(ui.me.apk.built * 1000).toLocaleDateString("de-DE")} · Android 7 oder neuer`;
  }
  ui.viewer = new Viewer($("stage3d"));
  if (ui.me.dev) window.__viewer = ui.viewer;
  let state;
  try {
    state = (off.pending() && await off.flush(api)) || await api("/state");
  } catch (e) {
    const last = off.lastState();
    if (!e.offline || !last) throw e;
    ui.clockOffset = last.now - (last.saved_at || last.now);
    state = off.view(gameNow());
  }
  await render(state);
  fillSettings(state.settings, state.share);
  showCook(state);
  setInterval(tickFast, 1000);
  setInterval(refresh, 60_000);
  addEventListener("online", refresh);
  setInterval(chatter, 32_000);
}

document.querySelectorAll("[data-act]").forEach((b) => b.addEventListener("click", () => act(b.dataset.act)));
$("tabs").addEventListener("click", (e) => { const b = e.target.closest("[data-tab]"); if (b) { sfx.tap(); showTab(b.dataset.tab); } });
$("sound").addEventListener("click", () => { setSound(!soundOn()); renderSound(); sfx.tap(); });
// Antippen (ohne Ziehen) = anstupsen; Ziehen dreht weiterhin die Kamera
let down = null;
$("stage3d").addEventListener("pointerdown", (e) => { down = { x: e.clientX, y: e.clientY, t: performance.now() }; });
$("stage3d").addEventListener("pointerup", (e) => {
  if (down && Math.hypot(e.clientX - down.x, e.clientY - down.y) < 6 && performance.now() - down.t < 350) poke();
  down = null;
});
$("cook-go").addEventListener("click", feedCooked);
$("steps-new").addEventListener("click", newStepKey);
$("steps-drop").addEventListener("click", dropStepKey);
$("steps-copy").addEventListener("click", () => copy($("steps-key").textContent));
$("steps-url-copy").addEventListener("click", () => copy($("steps-url").textContent));
$("visit-back").addEventListener("click", endVisit);
$("dev-home").addEventListener("click", () => window.Geraet?.chooseHome());
$("dev-settings").addEventListener("click", () => window.Geraet?.openSettings());
$("jog-open").addEventListener("click", () => showTab("freunde"));
$("cook-no").addEventListener("click", closeCook);
$("fast-start").addEventListener("click", (e) => {
  const b = e.target.closest("[data-ago]");
  if (b) startFast(Number(b.dataset.ago));
});
$("fast-at-go").addEventListener("click", () => {
  const [hh, mm] = ($("fast-at").value || "").split(":").map(Number);
  if (Number.isNaN(hh)) { toast("Bitte eine Uhrzeit wählen.", true); return; }
  const now = new Date((Date.now() / 1000 + ui.clockOffset) * 1000), at = new Date(now);
  at.setHours(hh, mm || 0, 0, 0);
  if (at > now) at.setDate(at.getDate() - 1);  // 23:00 am Morgen eingegeben = gestern Abend
  const ago = (now - at) / 60000;
  if (ago > 12 * 60) { toast("Höchstens 12 Stunden zurück.", true); return; }
  startFast(Math.round(ago));
});
$("fast-start-close").addEventListener("click", () => { $("fast-start").hidden = true; renderFasting(ui.state); });
$("fchart").addEventListener("pointerover", (e) => { const b = e.target.closest(".fbar"); if (b) showTip(b); });
$("fchart").addEventListener("pointerleave", () => { $("ftip").hidden = true; });
$("fchart").addEventListener("focusin", (e) => { const b = e.target.closest(".fbar"); if (b) showTip(b); });
$("fchart").addEventListener("focusout", () => { $("ftip").hidden = true; });
$("newegg").addEventListener("click", () => openEggPick(true));
$("team").addEventListener("click", (e) => {
  const s = e.target.closest("[data-switch]"), n = e.target.closest("[data-newegg]");
  if (s && !s.classList.contains("on")) switchTo(Number(s.dataset.switch));
  if (n) openEggPick(false);
});
$("eggs").addEventListener("click", (e) => { const b = e.target.closest("[data-line]"); if (b) takeEgg(b.dataset.line); });
$("egg-close").addEventListener("click", () => { $("eggpick").hidden = true; });
$("settings").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = e.currentTarget.elements, data = {};
  for (const key of FIELDS) data[key] = f[key].value.trim();
  data.share = f.share.checked;
  try { fillSettings(await api("/settings", "PUT", data)); toast("Gespeichert."); render(await api("/state"), { animate: false }); } catch (err) { toast(err.message, true); }
});
$("password").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = e.currentTarget.elements;
  try { await api("/password", "POST", { current: f.current.value, new: f.new.value }); e.currentTarget.reset(); toast("Passwort geändert."); } catch (err) { toast(err.message, true); }
});
$("newinvite").addEventListener("click", async () => {
  try { const res = await api("/invites", "POST", {}); toast(`Neuer Code: ${res.code}`); renderInvites(); } catch (err) { toast(err.message, true); }
});
$("logout").addEventListener("click", async () => {
  if (off?.pending() && !confirm("Es warten noch Eintragungen auf den Sync. Trotzdem abmelden? Sie werden beim nächsten Anmelden geschickt.")) return;
  await api("/logout", "POST", {}).catch(() => {});
  try { localStorage.removeItem("partner.me"); localStorage.removeItem(`partner.state.${ui.me.user.name}`); } catch { /* egal */ }
  location.href = "/login";
});
$("dev").addEventListener("click", async (e) => {
  const b = e.target.closest("[data-dev]"); if (!b) return;
  const what = b.dataset.dev;
  const data = what === "skip" ? { hours: Number(b.dataset.hours) } : what === "train" ? { art: b.dataset.art, minutes: 30 } : what === "form" ? { form: $("devform").value.trim() } : {};
  try {
    const res = await api(`/dev/${what}`, "POST", data);
    if (what === "train") { ui.viewer.play("train"); fx(b.dataset.art === "geist" ? "+30 Min. Yoga" : "+30 Min. Kraft"); }
    await render(res);
  } catch (err) { toast(err.message, true); }
});

main().catch((err) => { $("loading").textContent = err.message; });
