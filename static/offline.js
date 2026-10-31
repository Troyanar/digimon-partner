// Offline-Betrieb: Eintragungen (Wasser, Essen, Fasten, Training) kommen mit Uhrzeit in eine Warteschlange,
// der letzte Stand vom Server wird gespeichert, und bis zum nächsten Sync rechnet eine Vorschau Hunger, Durst,
// Laune und Fasten weiter. Beim Sync (/api/sync) spielt der Server alles in der richtigen Reihenfolge nach und
// bleibt die Wahrheit – Digitationen, Pflegefehler und Erfolge entstehen erst dort.
// Die Werte unten entsprechen game.py (DECAY, GLASS, MEAL, COOKED); ändert man dort etwas, hier mitziehen.

const DECAY = { hunger: 6, thirst: 9, power: 0.6, mind: 0.6, disc: 0.3 };
const GLASS = 12.5, MEAL = 30, COOKED = 45, STEP = 600;

const read = (key, fallback) => { try { const v = localStorage.getItem(key); return v ? JSON.parse(v) : fallback; } catch { return fallback; } };
const write = (key, value) => { try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* Speicher voll oder gesperrt */ } };
const uid = () => (crypto.randomUUID ? crypto.randomUUID() : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`);

export const cachedMe = () => read("partner.me", null);
export const saveMe = (me) => write("partner.me", me);

const minutesOf = (hhmm) => Number(hhmm.slice(0, 2)) * 60 + Number(hhmm.slice(3, 5));
function asleepAt(ts, s) {
  const d = new Date(ts * 1000), m = d.getHours() * 60 + d.getMinutes();
  const a = minutesOf(s.sleep_start), b = minutesOf(s.sleep_end);
  return a < b ? a <= m && m < b : m >= a || m < b;
}
const dayOf = (ts) => { const d = new Date(ts * 1000); return `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`; };
const clockText = (ts) => {
  const d = new Date(ts * 1000), p = (n) => String(n).padStart(2, "0");
  return `${p(d.getDate())}.${p(d.getMonth() + 1)}. ${p(d.getHours())}:${p(d.getMinutes())}`;
};
const TEXT = {
  water: (e) => (e.data.glasses > 1 ? `${e.data.glasses} Gläser Wasser.` : "1 Glas Wasser."),
  eat: (e) => (e.data.cooked ? `Selbst gekocht: ${e.data.cooked}.` : "Etwas gegessen."),
  fast_start: () => "Fasten gestartet.", fast_stop: () => "Fasten beendet.",
  train: (e) => `Training: ${e.data.title || e.data.plan}.`,
};

export function setupOffline(user) {
  const QKEY = `partner.queue.${user}`, SKEY = `partner.state.${user}`;
  let queue = read(QKEY, []);

  const api = {
    pending: () => queue.length,
    saveState: (state) => { if (!state.offline) write(SKEY, { ...state, saved_at: Date.now() / 1000 }); },
    lastState: () => read(SKEY, null),

    push(kind, data, at) {
      queue.push({ id: uid(), kind, at, data: data || {} });
      write(QKEY, queue);
    },

    /** Warteschlange an den Server schicken; gibt den neuen Stand zurück (oder null, wenn nichts wartet). */
    async flush(call) {
      if (!queue.length) return null;
      const sending = queue.slice();
      const res = await call("/sync", "POST", { events: sending });
      const done = new Set(res.synced || []);
      queue = read(QKEY, []).filter((e) => !done.has(e.id));
      write(QKEY, queue);
      return res;
    },

    /** Vorschau ohne Server: letzter Stand + vergangene Zeit + wartende Eintragungen. */
    view(now) {
      const base = read(SKEY, null);
      if (!base) return null;
      const st = structuredClone(base), p = st.pet, s = st.settings, stats = p.stats;
      const events = queue.slice().sort((a, b) => a.at - b.at);
      let t = base.now, k = 0, day = dayOf(t);
      const apply = (e) => {
        const d = e.data;
        if (e.kind === "water") { stats.thirst += GLASS * (d.glasses || 1); stats.mood += 2; p.water_today += d.glasses || 1; }
        if (e.kind === "eat") { p.fasting = null; stats.hunger += d.cooked ? COOKED : MEAL; stats.mood += d.cooked ? 5 : 1; }
        if (e.kind === "fast_start" && !p.fasting) {
          const start = e.at - (d.minutes_ago || 0) * 60;
          p.fasting = { start, goal: s.fast_goal, goal_at: start + s.fast_goal * 3600, hours: 0 };
        }
        if (e.kind === "fast_stop" && p.fasting) {
          if ((e.at - p.fasting.start) / 3600 >= p.fasting.goal) { stats.disc += 15; stats.mood += 5; }
          p.fasting = null;
        }
        if (e.kind === "train") {
          const key = d.art === "geist" ? "mind" : "power";
          stats[key] += (d.minutes || 10) * 1.5; stats.hunger -= 5; stats.thirst -= 8; stats.mood += 6;
          p.week[d.art === "geist" ? "geist" : "kraft"] += 1;
        }
        for (const x in stats) stats[x] = Math.max(0, Math.min(100, stats[x]));
      };
      while (t < now) {
        const dt = Math.min(STEP, now - t);
        t += dt;
        while (k < events.length && events[k].at <= t) apply(events[k++]);
        if (dayOf(t) !== day) { day = dayOf(t); p.water_today = 0; }
        if (p.form !== "egg" && !asleepAt(t, s)) {
          const h = dt / 3600;
          for (const [x, rate] of Object.entries(DECAY)) stats[x] = Math.max(0, stats[x] - rate * h);
          const care = (stats.hunger + stats.thirst) / 2, fit = Math.min(100, stats.power + stats.mind);
          stats.mood += (care * 0.5 + fit * 0.3 + stats.disc * 0.2 - stats.mood) * Math.min(1, 0.15 * h * 6);
        }
      }
      while (k < events.length) apply(events[k++]);
      const passed = (now - base.now) / 3600;
      if (p.hours_left != null) p.hours_left = Math.max(0, p.hours_left - passed);
      if (p.fasting) p.fasting.hours = (now - p.fasting.start) / 3600;
      for (const x in stats) stats[x] = Math.round(stats[x] * 10) / 10;
      p.asleep = asleepAt(now, s);
      p.age_days += passed / 24;
      st.now = now; st.clock = clockText(now);
      st.offline = true; st.pending = queue.length; st.unlocked_now = []; st.jogress_in = [];
      // Wartende Eintragungen schon im Tagebuch zeigen
      st.diary = events.map((e) => ({ kind: "pending", text: `${TEXT[e.kind]?.(e) || e.kind} (wartet auf Sync)`, at: e.at }))
        .reverse().concat(st.diary || []);
      return st;
    },
  };
  return api;
}
