"use strict";
// Anmelden oder neues Konto (mit Einladungscode; das allererste Konto braucht keinen und wird Admin)
(async () => {
  const form = document.getElementById("form"), err = document.getElementById("err");
  let mode = "login", first = false;
  try { first = (await (await fetch("/api/me")).json()).first; } catch { /* egal */ }

  function setMode(m) {
    mode = m;
    document.querySelectorAll("[data-mode]").forEach((b) => (b.dataset.mode === m ? b.setAttribute("aria-current", "page") : b.removeAttribute("aria-current")));
    document.getElementById("codefield").hidden = m !== "register" || first;
    document.getElementById("pw-rule").hidden = m !== "register";
    form.elements.password.autocomplete = m === "register" ? "new-password" : "current-password";
    document.getElementById("hint").textContent = m === "login" ? "Melde dich an und schau, was dein Partner gerade braucht."
      : first ? "Das erste Konto wird Admin und braucht keinen Einladungscode."
      : "Du brauchst einen Einladungscode von einem Freund. Danach bekommst du dein erstes Digi-Ei.";
    err.textContent = "";
  }
  document.getElementById("tabs").addEventListener("click", (e) => { const b = e.target.closest("[data-mode]"); if (b) setMode(b.dataset.mode); });
  setMode(first ? "register" : "login");

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    err.textContent = "";
    const f = form.elements;
    const data = { name: f.name.value.trim(), password: f.password.value, code: f.code.value.trim() };
    const resp = await fetch(`/api/${mode}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) }).catch(() => null);
    if (!resp) { err.textContent = "Keine Verbindung zum Server."; return; }
    if (resp.ok) {
      // nur eigene Seiten als Ziel ("/…", nicht "//fremd.de")
      const next = new URLSearchParams(location.search).get("next") || "/";
      location.href = /^\/(?!\/)/.test(next) ? next : "/";
      return;
    }
    err.textContent = (await resp.json().catch(() => ({}))).error || `Fehler ${resp.status}`;
  });
})();
