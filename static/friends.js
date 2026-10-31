// Freunde: alle sichtbaren Konten der Seite mit ihrem Partner. Besuchen (3D-Welt zeigt deren Digimon),
// einmal am Tag anfeuern, Jogress anfragen bzw. annehmen, oder Jogress mit einem eigenen Gegenstück aus der Ruhmeshalle.
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

function ago(ts, now) {
  const m = Math.max(0, (now - ts) / 60);
  if (m < 10) return "gerade eben";
  if (m < 60) return `vor ${Math.round(m)} Min.`;
  if (m < 48 * 60) return `vor ${Math.round(m / 60)} Std.`;
  return `vor ${Math.round(m / 1440)} Tagen`;
}

export function setupFriends(ctx) {
  const F = { data: null };

  async function load() {
    F.data = await ctx.api("/friends");
    render();
  }

  function jogressBox(state) {
    const p = state.pet, d = F.data;
    const parts = [];
    for (const r of d.requests.filter((x) => !x.mine))
      parts.push(`<li class="jog-item"><p><b>${esc(r.from_name)}</b> möchte Jogress mit dir.</p>
        <div class="row"><button class="btn btn--primary btn--small" data-jog="accept" data-id="${r.id}">Annehmen</button>
        <button class="btn btn--small" data-jog="decline" data-id="${r.id}">Ablehnen</button></div></li>`);
    for (const r of d.requests.filter((x) => x.mine))
      parts.push(`<li class="jog-item"><p>Anfrage an <b>${esc(r.to_name)}</b> ist unterwegs. Sobald angenommen, werden beide zu Paildramon.</p></li>`);
    if (p.waiting && p.jogress_partner) {
      const days = Math.max(1, Math.round((p.jogress_left ?? 0) / 24));
      const ready = d.friends.filter((f) => f.jogress);
      parts.push(`<li class="jog-item"><p>${esc(p.name)} wartet auf ein <b>${esc(p.jogress_partner)}</b>. Noch ${days} ${days === 1 ? "Tag" : "Tage"},
        dann geht es auf einen anderen Weg.</p>
        ${ready.length ? `<div class="row">${ready.map((f) => `<button class="btn btn--primary btn--small" data-jog="ask" data-name="${esc(f.name)}">Jogress mit ${esc(f.name)}</button>`).join("")}</div>`
          : `<p class="caption">Gerade hat kein Freund ein wartendes ${esc(p.jogress_partner)}.</p>`}
        ${d.hall.length ? `<div class="row">${d.hall.map((h) => `<button class="btn btn--small" data-jog="hall" data-id="${h.id}">Mit deinem ${esc(h.with)} aus der Ruhmeshalle (${esc(h.name)})</button>`).join("")}</div>` : ""}
      </li>`);
    }
    $("jog-box").hidden = !parts.length;
    $("jog-list").innerHTML = parts.join("");
  }

  function card(f, now) {
    const p = f.pet;
    const status = p.form === "egg" ? "Ein Digi-Ei" : p.asleep ? "Schläft" : f.fasting ? "Fastet gerade" : p.waiting ? "Wartet auf Jogress" : "Wach";
    return `<li class="friend">
      <div class="friend-top"><div><p class="label">${esc(f.name)}</p><b class="friend-pet">${esc(p.name)}</b></div>
        <span class="chip">${esc(status)}</span></div>
      <p class="caption">${p.form === "egg" ? "Schlüpft gleich" : `${esc(p.stage_label)}, Tag ${Math.floor(p.age_days) + 1}`} · zuletzt da ${ago(p.last_seen, now)}</p>
      <div class="mini"><span>Laune</span><span class="bar"><i style="width:${Math.round(f.mood)}%"></i></span><span class="num">${Math.round(f.mood)}</span></div>
      <p class="caption num">Wasser-Serie ${f.streak} ${f.streak === 1 ? "Tag" : "Tage"} · ${p.week.kraft + p.week.geist} Trainings diese Woche · ${f.trainings} insgesamt</p>
      <div class="row">
        <button class="btn btn--small" data-visit="${esc(f.name)}">Besuchen</button>
        <button class="btn btn--small" data-cheer="${esc(f.name)}" ${f.cheered ? "disabled" : ""}>${f.cheered ? "Heute angefeuert" : "Anfeuern"}</button>
      </div></li>`;
  }

  function render() {
    const state = ctx.state(), d = F.data;
    if (!state || !d) return;
    $("friends-sub").textContent = d.friends.length
      ? `${d.friends.length} ${d.friends.length === 1 ? "Freund" : "Freunde"} auf der Seite. Einmal am Tag anfeuern gibt ihrem Partner gute Laune.`
      : "Noch niemand hier. Lade Freunde ein (unter Mehr), dann siehst du ihre Partner.";
    $("friends-hidden").hidden = d.share;
    $("friends").innerHTML = d.friends.map((f) => card(f, state.now)).join("");
    jogressBox(state);
  }

  async function visit(name) {
    const f = F.data?.friends.find((x) => x.name === name);
    if (!f) return;
    await ctx.visit(f);
  }

  async function cheer(name, btn) {
    btn.disabled = true;
    try {
      const res = await ctx.api("/friends/cheer", "POST", { name });
      ctx.sfx.award();
      ctx.toast(`Du hast ${res.friend}s Partner angefeuert!`);
      await ctx.render(res);
      await load();
    } catch (err) { btn.disabled = false; ctx.toast(err.message, true); }
  }

  async function jog(b) {
    const what = b.dataset.jog;
    if (what === "accept" && !confirm("Jogress annehmen? Beide Partner werden zu Paildramon.")) return;
    if (what === "hall" && !confirm("Jogress mit deinem Partner aus der Ruhmeshalle? Dein Partner wird zu Paildramon.")) return;
    try {
      const res = await ctx.api("/jogress", "POST", { action: what, name: b.dataset.name, id: Number(b.dataset.id) || undefined });
      if (what === "ask") ctx.toast("Anfrage geschickt. Sobald dein Freund annimmt, passiert die Jogress.");
      if (what === "decline") ctx.toast("Abgelehnt.");
      if (what === "accept" || what === "hall") { await ctx.endVisit(); ctx.showTab("partner"); }
      await ctx.render(res);
      await load();
    } catch (err) { ctx.toast(err.message, true); }
  }

  $("tab-freunde").addEventListener("click", (e) => {
    const v = e.target.closest("[data-visit]"), c = e.target.closest("[data-cheer]"), j = e.target.closest("[data-jog]");
    if (v) visit(v.dataset.visit);
    if (c) cheer(c.dataset.cheer, c);
    if (j) jog(j);
  });

  return { load, refresh: render };
}
