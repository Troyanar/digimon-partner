// Kurze Spiel-Töne, direkt im Browser erzeugt (Web Audio, keine Dateien). Abschaltbar, Wahl bleibt gespeichert.
const KEY = "partner.sound";
let ctx = null;
let on = (() => { try { return localStorage.getItem(KEY) !== "off"; } catch { return true; } })();

export const soundOn = () => on;
export function setSound(value) {
  on = value;
  try { localStorage.setItem(KEY, value ? "on" : "off"); } catch { /* egal */ }
}

// Browser erlauben Ton erst nach der ersten Berührung; davor still bleiben statt Warnungen zu erzeugen
let touched = false;
/** Im Geräte-Modus darf das Digimon sich auch ohne vorheriges Antippen melden (die App erlaubt Ton ohne Geste). */
export function allowSound() { touched = true; }
for (const ev of ["pointerdown", "keydown"]) addEventListener(ev, () => { touched = true; }, { once: true, capture: true });

function audio() {
  if (!on || !touched) return null;
  try {
    ctx ||= new AudioContext();
    if (ctx.state === "suspended") ctx.resume();
    return ctx;
  } catch { return null; }
}

/** Ein Ton: Frequenz (Hz), Start (s ab jetzt), Länge (s), Wellenform, Lautstärke */
function tone(a, freq, at, len, type = "square", vol = 0.06) {
  const t = a.currentTime + at;
  const o = a.createOscillator(), g = a.createGain();
  o.type = type; o.frequency.setValueAtTime(freq, t);
  g.gain.setValueAtTime(0, t);
  g.gain.linearRampToValueAtTime(vol, t + 0.01);
  g.gain.exponentialRampToValueAtTime(0.0001, t + len);
  o.connect(g).connect(a.destination);
  o.start(t); o.stop(t + len + 0.02);
}

const notes = (seq, type, vol) => { const a = audio(); if (!a) return; seq.forEach(([f, at, len]) => tone(a, f, at, len, type, vol)); };

export const sfx = {
  tap: () => notes([[880, 0, 0.06]], "square", 0.035),
  water: () => notes([[660, 0, 0.08], [990, 0.07, 0.12]], "triangle", 0.12),
  eat: () => notes([[392, 0, 0.08], [523, 0.08, 0.08], [659, 0.16, 0.14]], "square", 0.05),
  goal: () => notes([[523, 0, 0.1], [659, 0.1, 0.1], [784, 0.2, 0.1], [1047, 0.3, 0.32]], "square", 0.06),
  award: () => notes([[784, 0, 0.09], [988, 0.09, 0.09], [1175, 0.18, 0.09], [1568, 0.27, 0.4]], "triangle", 0.14),
  fast: () => notes([[440, 0, 0.1], [330, 0.1, 0.18]], "triangle", 0.1),
  evolve: () => notes(Array.from({ length: 12 }, (_, i) => [300 * 2 ** (i / 6), i * 0.11, 0.12]), "square", 0.045),
  go: () => notes([[784, 0, 0.08], [1175, 0.08, 0.16]], "square", 0.05),
  rest: () => notes([[587, 0, 0.12], [440, 0.12, 0.2]], "triangle", 0.1),
  alert: () => notes([[988, 0, 0.09], [784, 0.12, 0.09], [988, 0.24, 0.09], [1319, 0.36, 0.2]], "square", 0.07),
  poke: () => notes([[1200, 0, 0.05], [1500, 0.05, 0.07]], "square", 0.035),
};
