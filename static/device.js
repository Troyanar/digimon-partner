// Geräte-Modus: ein eigenes Android-Handy als Digimon-Gerät (wie ein Tamagotchi auf dem Tisch).
// Aktiv in der Geräte-App (User-Agent "DigimonGeraet") oder mit ?geraet in der Adresse (?geraet=0 schaltet ab).
// Große Knöpfe, Uhr im Bild, nachts dunkel, das Digimon meldet sich von selbst, gegen Einbrennen wandert die Anzeige leicht.
// Die App stellt window.Geraet bereit (vibrate, setBrightness); im normalen Browser fehlt es einfach.
const $ = (id) => document.getElementById(id);
const ALERT_EVERY = 30 * 60 * 1000;   // dieselbe Bitte frühestens nach 30 Minuten wiederholen
const BACK_HOME = 2 * 60 * 1000;      // nach 2 Minuten ohne Berührung zurück zum Partner
const WAKE_FOR = 30 * 1000;           // nachts: Antippen macht den Bildschirm 30 Sekunden hell

export function isDevice() {
  const q = new URLSearchParams(location.search).get("geraet");
  try {
    if (q === "0") localStorage.removeItem("partner.geraet");
    else if (q !== null) localStorage.setItem("partner.geraet", "1");
  } catch { /* ohne Speicher nur für diesen Besuch */ }
  if (/DigimonGeraet/.test(navigator.userAgent)) return true;
  if (q !== null) return q !== "0";
  try { return localStorage.getItem("partner.geraet") === "1"; } catch { return false; }
}

const bridge = (name, ...args) => { try { window.Geraet?.[name]?.(...args); } catch { /* nur in der App */ } };
const vibrate = (pattern) => {
  if (window.Geraet) bridge("vibrate", JSON.stringify([].concat(pattern)));
  else if (navigator.userActivation?.hasBeenActive) navigator.vibrate?.(pattern);   // Browser: erst nach einer Berührung
};

export function setupDevice(ctx) {
  document.body.classList.add("device");
  const D = { lastAlert: "", lastAt: 0, awakeUntil: 0, idle: null, night: false };

  // --- Uhr im Bild -------------------------------------------------------------------------------
  function clock() {
    const now = new Date(Date.now() + (ctx.clockOffset() || 0) * 1000);
    const t = `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`;
    $("devclock").textContent = t;
    $("night-clock").textContent = t;
  }
  $("devclock").hidden = false;
  setInterval(clock, 5000);

  // --- Gegen Einbrennen: alles wandert alle zwei Minuten um ein paar Pixel ------------------------
  setInterval(() => {
    const dx = Math.round(Math.random() * 6 - 3), dy = Math.round(Math.random() * 6 - 3);
    document.documentElement.style.setProperty("--shift", `translate(${dx}px, ${dy}px)`);
    const n = $("night-box");
    n.style.left = `${15 + Math.random() * 50}%`; n.style.top = `${20 + Math.random() * 50}%`;
  }, 2 * 60 * 1000);

  // --- Nacht: Bildschirm dunkel, Antippen weckt ihn kurz ---------------------------------------------
  function applyNight() {
    const dark = D.night && Date.now() > D.awakeUntil;
    $("night").hidden = !dark;
    bridge("setBrightness", dark ? 0.01 : -1);   // -1 = Helligkeit wie im System eingestellt
  }
  $("night").addEventListener("pointerdown", (e) => {
    e.preventDefault();
    D.awakeUntil = Date.now() + WAKE_FOR;
    applyNight();
    setTimeout(applyNight, WAKE_FOR + 200);
  });

  // --- Zurück zum Partner, wenn niemand mehr tippt ---------------------------------------------------
  const poke = () => {
    clearTimeout(D.idle);
    D.idle = setTimeout(() => { if (!ctx.busy()) ctx.showTab("partner"); }, BACK_HOME);
  };
  addEventListener("pointerdown", poke, { capture: true });
  poke();

  // --- Das Digimon meldet sich, wenn es etwas braucht -----------------------------------------------
  const ALERTS = { thirst: "Ich hab Durst! Ein Glas Wasser bitte!", hunger: "Mein Bauch knurrt … Hast du schon gegessen?",
                   sad: "Mir ist langweilig … Kümmerst du dich um mich?" };

  function update(state, mood) {
    clock();
    D.night = !!state.pet.asleep;
    applyNight();
    $("night-text").textContent = `${state.pet.name} schläft. Tippen macht den Bildschirm kurz hell.`;
    if (D.night || ctx.busy()) return;
    const want = ALERTS[mood] ? mood : "";
    if (!want) { D.lastAlert = ""; return; }
    if (want === D.lastAlert && Date.now() - D.lastAt < ALERT_EVERY) return;
    D.lastAlert = want; D.lastAt = Date.now();
    ctx.alert(ALERTS[want]);
    vibrate([220, 120, 220]);
  }

  return { update, vibrate };
}
