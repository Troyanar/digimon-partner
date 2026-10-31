// Trainingsseite: feste Pläne, geführt Übung für Übung mit Countdown. Der Partner trainiert im 3D-Bild mit
// und feuert in der Sprechblase an. Gutgeschrieben wird am Ende über den Server (der prüft die echte Zeit).
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const pick = (list) => list[Math.floor(Math.random() * list.length)];
const clock = (sec) => `${Math.floor(sec / 60)}:${String(Math.floor(sec % 60)).padStart(2, "0")}`;

const CHEER = {
  kraft: { start: ["Los geht's!", "Zeig, was du kannst!", "Gemeinsam schaffen wir das!", "Volle Power!"],
           ten: ["Noch 10 Sekunden!", "Gleich geschafft!", "Durchhalten!"],
           rest: ["Kurz durchatmen …", "Puh! Weiter gleich!", "Trink ruhig einen Schluck."] },
  geist: { start: ["Ganz ruhig atmen …", "Schön locker bleiben.", "Spür mal rein.", "Langsam und gleichmäßig."],
           ten: ["Noch ein paar Atemzüge.", "Gleich lösen …"],
           rest: ["Sanft weiter …", "Gut gemacht."] },
};

export function setupTraining(ctx) {
  const T = { plans: [], run: null };

  async function load() {
    if (!T.plans.length) T.plans = await ctx.api("/plans");
    renderPlans();
  }

  function weekText(state) {
    const w = state.pet.week, s = state.settings;
    return `Diese Woche: Kraft ${w.kraft} von ${s.week_kraft}, Dehnen und Yoga ${w.geist} von ${s.week_geist}.`;
  }

  function renderPlans() {
    const state = ctx.state();
    if (!state || T.run) return;
    $("train-sub").textContent = weekText(state);
    // Empfehlung: die Art, bei der das Wochenziel noch am weitesten weg ist
    const w = state.pet.week, s = state.settings;
    const want = s.week_kraft - w.kraft >= s.week_geist - w.geist ? "kraft" : "geist";
    const best = T.plans.find((p) => p.art === want)?.id;
    const card = (p) => {
      const names = [...new Set(p.steps.map((x) => x.name))];
      return `<li class="plan"><div><b>${esc(p.title)}</b><p class="num">${p.minutes} Min. · ${p.steps.length} Übungen</p></div>
        <p>${esc(p.text)}</p><p class="caption">${esc(names.join(", "))}</p>
        <button class="btn ${p.id === best ? "btn--primary" : ""}" data-plan="${p.id}">Starten</button></li>`;
    };
    $("plans-kraft").innerHTML = T.plans.filter((p) => p.art === "kraft").map(card).join("");
    $("plans-geist").innerHTML = T.plans.filter((p) => p.art === "geist").map(card).join("");
  }

  // --- Ablauf ---------------------------------------------------------------------------------
  function phases(plan) {
    const out = [];
    plan.steps.forEach((step, i) => {
      out.push({ type: "work", step, seconds: step.seconds, index: i });
      if (i < plan.steps.length - 1 && plan.rest) out.push({ type: "rest", seconds: plan.rest, next: plan.steps[i + 1], index: i });
    });
    return out;
  }

  async function start(planId) {
    const plan = T.plans.find((p) => p.id === planId);
    if (!plan || T.run) return;
    let local = false;   // ohne Netz: Start nur hier merken, eingetragen wird beim Sync
    try { await ctx.api("/train", "POST", { plan: planId, step: "start" }); } catch (err) {
      if (!err.offline) { ctx.toast(err.message, true); return; }
      local = true;
    }
    T.run = { plan, local, startAt: ctx.gameNow(), list: phases(plan), at: -1, end: 0, pausedLeft: null, timer: null, anim: null, said10: false, saidHalf: false,
              total: plan.steps.reduce((a, x) => a + x.seconds, 0) + plan.rest * (plan.steps.length - 1), started: performance.now() };
    ctx.setTraining(true);
    try { T.run.lock = await navigator.wakeLock?.request("screen"); } catch { /* Bildschirm darf trotzdem ausgehen */ }
    $("plans").hidden = true; $("train-result").hidden = true; $("session").hidden = false;
    $("train-title").textContent = plan.title;
    ctx.sfx.go();
    next();
    T.run.timer = setInterval(tick, 200);
  }

  function next() {
    const r = T.run;
    r.at++;
    if (r.at >= r.list.length) { finish(); return; }
    const ph = r.list[r.at];
    r.end = performance.now() + ph.seconds * 1000;
    r.said10 = false; r.saidHalf = false;
    const steps = r.plan.steps.length, art = r.plan.art;
    clearInterval(r.anim);
    if (ph.type === "work") {
      $("ses-label").textContent = `Übung ${ph.index + 1} von ${steps}`;
      $("ses-name").textContent = ph.step.name;
      $("ses-text").textContent = ph.step.text;
      const nxt = r.plan.steps[ph.index + 1];
      $("ses-next").textContent = nxt ? `Als Nächstes: ${nxt.name}` : "Letzte Übung!";
      $("session").classList.remove("resting");
      if (art === "kraft") { ctx.viewer.play("train"); r.anim = setInterval(() => ctx.viewer.play("train"), 2600); }
      else ctx.viewer.setBase("sleep");
      ctx.say(pick(CHEER[art].start), 2600);
      if (ph.index > 0) ctx.sfx.go();
    } else {
      $("ses-label").textContent = "Pause";
      $("ses-name").textContent = `Gleich: ${ph.next.name}`;
      $("ses-text").textContent = ph.next.text;
      $("ses-next").textContent = `Nach Übung ${ph.index + 1} von ${steps}`;
      $("session").classList.add("resting");
      ctx.viewer.setBase("idle");
      ctx.sfx.rest();
      ctx.say(pick(CHEER[art].rest), 2200);
    }
    tick();
  }

  function tick() {
    const r = T.run;
    if (!r || r.at >= r.list.length) return;
    const ph = r.list[r.at];
    const left = r.pausedLeft ?? Math.max(0, (r.end - performance.now()) / 1000);
    const shown = Math.ceil(left);
    if ($("ses-time").textContent !== String(shown)) {
      $("ses-time").textContent = shown;
      if (r.pausedLeft === null && shown <= 3 && shown > 0) ctx.sfx.tap();
    }
    $("ses-bar").style.width = `${(1 - left / ph.seconds) * 100}%`;
    // Fortschritt über den ganzen Plan
    const before = r.list.slice(0, r.at).reduce((a, x) => a + x.seconds, 0);
    const doneSec = before + (ph.seconds - left);
    $("ses-total").textContent = `${clock(doneSec)} von ${clock(r.total)}`;
    $("ses-all").style.width = `${(doneSec / r.total) * 100}%`;
    if (r.pausedLeft !== null) return;
    if (ph.type === "work") {
      if (!r.saidHalf && /Halbzeit/.test(ph.step.text) && left <= ph.seconds / 2) { r.saidHalf = true; ctx.sfx.go(); ctx.say("Seite wechseln!", 2200); }
      if (!r.said10 && ph.seconds >= 30 && left <= 10) { r.said10 = true; ctx.say(pick(CHEER[r.plan.art].ten), 2200); }
    }
    if (left <= 0) next();
  }

  function pause() {
    const r = T.run; if (!r) return;
    if (r.pausedLeft === null) {
      r.pausedLeft = Math.max(0, (r.end - performance.now()) / 1000);
      $("ses-pause").textContent = "Weiter";
      clearInterval(r.anim);
      ctx.say("Ich warte auf dich!", 2000);
    } else {
      r.end = performance.now() + r.pausedLeft * 1000;
      r.pausedLeft = null;
      $("ses-pause").textContent = "Pause";
      if (r.list[r.at].type === "work" && r.plan.art === "kraft") r.anim = setInterval(() => ctx.viewer.play("train"), 2600);
    }
    tick();
  }

  function skip() {
    const r = T.run; if (!r) return;
    if (r.pausedLeft !== null) pause();
    next();
  }

  function stop() {
    const r = T.run;
    if (!r) return;
    clearInterval(r.timer); clearInterval(r.anim);
    r.lock?.release?.().catch(() => {});
    T.run = null;
    ctx.setTraining(false);
    $("ses-pause").textContent = "Pause";
  }

  async function cancel() {
    if (!T.run || !confirm("Training abbrechen? Es wird dann nicht eingetragen.")) return;
    const plan = T.run.plan.id;
    stop();
    ctx.api("/train", "POST", { plan, step: "cancel" }).catch(() => {});
    $("session").hidden = true; $("plans").hidden = false;
    ctx.viewer.play("down");
    ctx.say("Schade … beim nächsten Mal!", 2400);
    ctx.rerender();
  }

  async function finish() {
    const r = T.run, plan = r.plan, before = ctx.state().pet.stats;
    stop();
    $("session").hidden = true;
    try {
      let res, queued = false;
      try {
        if (r.local) throw Object.assign(new Error("offline"), { offline: true });
        res = await ctx.api("/train", "POST", { plan: plan.id, step: "finish" });
      } catch (err) {
        if (!err.offline) throw err;
        const end = ctx.gameNow();
        if (end - r.startAt < r.total * 0.5) throw new Error("Das ging zu schnell – mindestens die Hälfte der Zeit musst du wirklich trainieren.");
        res = ctx.queueTrain(plan, r.startAt, end);
        queued = true;
      }
      const key = plan.art === "geist" ? "mind" : "power", gain = Math.round(res.pet.stats[key] - before[key]);
      const minutes = res.done[0]?.minutes ?? plan.minutes;
      $("res-text").textContent = `${plan.title}: ${minutes} Minuten ${plan.art === "geist" ? "Dehnen und Yoga" : "Krafttraining"}.`;
      $("res-gain").textContent = `+${gain} ${plan.art === "geist" ? "Geist" : "Kraft"}`;
      $("res-week").textContent = queued ? "Ohne Netz gespeichert – wird beim nächsten Sync eingetragen." : weekText(res);
      $("train-result").hidden = false;
      await ctx.render(res);
      ctx.celebrate("Training geschafft!");
    } catch (err) {
      ctx.toast(err.message, true);
      ctx.viewer.play("confused");
      $("plans").hidden = false;
      ctx.rerender();
    }
  }

  // --- Ereignisse -----------------------------------------------------------------------------
  $("tab-training").addEventListener("click", (e) => {
    const b = e.target.closest("[data-plan]");
    if (b) start(b.dataset.plan);
  });
  $("ses-pause").addEventListener("click", pause);
  $("ses-skip").addEventListener("click", skip);
  $("ses-cancel").addEventListener("click", cancel);
  $("res-back").addEventListener("click", () => { $("train-result").hidden = true; $("plans").hidden = false; renderPlans(); });
  document.addEventListener("visibilitychange", async () => {
    // Bildschirmsperre wird beim Zurückkommen wieder angefordert
    if (T.run && document.visibilityState === "visible") { try { T.run.lock = await navigator.wakeLock?.request("screen"); } catch { /* egal */ } }
  });

  return { load, refresh: renderPlans, active: () => !!T.run };
}
