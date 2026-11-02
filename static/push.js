// Benachrichtigungen (Web-Push): Karte unter Mehr. Der Server entscheidet, wann sich das Digimon meldet (push.py).
// iPhone: geht nur in der Web-App vom Home-Bildschirm (ab iOS 16.4), nicht im Safari-Tab.

const isIos = () => /iPhone|iPad|iPod/.test(navigator.userAgent) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
const standalone = () => navigator.standalone === true || matchMedia("(display-mode: standalone)").matches;
const supported = () => "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;

function keyBytes(b64) {
  const s = atob((b64 + "=".repeat((4 - (b64.length % 4)) % 4)).replace(/-/g, "+").replace(/_/g, "/"));
  return Uint8Array.from(s, (c) => c.charCodeAt(0));
}

export function setupPush({ $, api, toast }) {
  let key = null, sub = null;

  async function current() {
    if (!supported()) return null;
    const reg = await navigator.serviceWorker.ready;
    return reg.pushManager.getSubscription();
  }

  function render() {
    const on = !!sub && Notification.permission === "granted";
    let text;
    if (!supported()) text = isIos() && !standalone()
      ? "Auf dem iPhone geht das nur, wenn die Seite als App auf dem Home-Bildschirm liegt:"
      : "Dieser Browser kann keine Benachrichtigungen.";
    else if (Notification.permission === "denied") text = isIos()
      ? "Abgelehnt. Erlauben unter iPhone-Einstellungen → Mitteilungen → Partner."
      : "Abgelehnt. Erlauben in den Website-Einstellungen des Browsers (Schloss neben der Adresse).";
    else text = on ? "An auf diesem Gerät." : "Aus auf diesem Gerät.";
    $("push-status").textContent = text;
    $("push-ios").hidden = supported() || !isIos() || standalone();
    $("push-on").hidden = !supported() || on || Notification.permission === "denied";
    $("push-test").hidden = !on;
    $("push-off").hidden = !on;
  }

  async function turnOn() {
    // Erst fragen (muss direkt aufs Antippen folgen, sonst blockt Safari), dann beim Server anmelden
    const perm = await Notification.requestPermission();
    if (perm !== "granted") { render(); return; }
    try {
      key = key || (await api("/push")).key;
      const reg = await navigator.serviceWorker.ready;
      const opts = { userVisibleOnly: true, applicationServerKey: keyBytes(key) };
      try { sub = await reg.pushManager.subscribe(opts); } catch (err) {
        // altes Abo mit anderem Server-Schlüssel: weg damit, neu anmelden
        const old = await reg.pushManager.getSubscription();
        if (!old) throw err;
        await old.unsubscribe();
        sub = await reg.pushManager.subscribe(opts);
      }
      await api("/push", "POST", sub.toJSON());
      toast("Benachrichtigungen sind an.");
    } catch (err) { sub = null; toast(`Einschalten ging nicht${err.message ? ` (${err.message})` : ""}.`, true); }
    render();
  }

  async function turnOff() {
    try {
      if (sub) { await api("/push", "DELETE", { endpoint: sub.endpoint }).catch(() => {}); await sub.unsubscribe(); }
      sub = null; toast("Benachrichtigungen sind aus.");
    } catch (err) { toast(err.message, true); }
    render();
  }

  async function test() {
    try { await api("/push/test", "POST", {}); toast("Geschickt – gleich sollte sie kommen."); } catch (err) { toast(err.message, true); }
  }

  $("push-on").addEventListener("click", turnOn);
  $("push-off").addEventListener("click", turnOff);
  $("push-test").addEventListener("click", test);

  (async () => {
    try {
      sub = await current();
      // Server auf Stand halten (z. B. nach neuem Anmelden auf diesem Gerät)
      if (sub && Notification.permission === "granted") await api("/push", "POST", sub.toJSON()).catch(() => {});
      if (supported()) key = (await api("/push")).key;
    } catch { /* offline: Karte zeigt trotzdem den Stand */ }
    render();
  })();
  render();

  // Beim Abmelden: dieses Gerät soll keine Meldungen für das alte Konto mehr bekommen
  return { async forget() { if (sub) await api("/push", "DELETE", { endpoint: sub.endpoint }).catch(() => {}); } };
}
