// Service Worker: damit die Seite (und die Geräte-App) auch ohne Netz startet.
//  - Seite und eigene Dateien: erst Netz (immer aktuell), ohne Netz die gespeicherte Fassung
//  - 3D-Modelle (/assets): einmal geladen, bleiben sie auf dem Gerät (nur für angemeldete Nutzer erreichbar)
//  - three.js und Schriften von außen: einmal geladen, bleiben sie
//  - /api: nie aus dem Speicher – das übernimmt die Seite selbst (Warteschlange + Sync, siehe offline.js)
// Ausgeliefert unter /sw.js, damit er die ganze Seite abdeckt.
const VERSION = "partner-v1";
const SHELL = `${VERSION}-seite`, MODELS = "partner-modelle", EXTERN = "partner-extern";
const PRECACHE = [
  "/static/style.css", "/static/app.js", "/static/viewer.js", "/static/world.js", "/static/sound.js",
  "/static/train.js", "/static/friends.js", "/static/device.js", "/static/offline.js", "/static/favicon.svg",
  "https://unpkg.com/three@0.170.0/build/three.module.js",
  "https://unpkg.com/three@0.170.0/examples/jsm/loaders/FBXLoader.js",
  "https://unpkg.com/three@0.170.0/examples/jsm/loaders/OBJLoader.js",
  "https://unpkg.com/three@0.170.0/examples/jsm/controls/OrbitControls.js",
  "https://unpkg.com/three@0.170.0/examples/jsm/curves/NURBSCurve.js",
  "https://unpkg.com/three@0.170.0/examples/jsm/curves/NURBSUtils.js",
  "https://unpkg.com/three@0.170.0/examples/jsm/libs/fflate.module.js",
];
const NETWORK_WAIT = 4000;   // so lange auf den Server warten, dann die gespeicherte Fassung nehmen

self.addEventListener("install", (event) => {
  event.waitUntil((async () => {
    const shell = await caches.open(SHELL), ext = await caches.open(EXTERN);
    // einzeln, damit eine fehlende Datei nicht alles abbricht
    await Promise.allSettled(PRECACHE.map((url) => (url.startsWith("http") ? ext : shell).add(new Request(url, { cache: "reload" }))));
    await self.skipWaiting();
  })());
});

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    for (const key of await caches.keys())
      if (key.endsWith("-seite") && key !== SHELL) await caches.delete(key);
    await self.clients.claim();
  })());
});

function timeout(ms) { return new Promise((_, no) => setTimeout(() => no(new Error("timeout")), ms)); }

async function networkFirst(request, cacheName, key = request) {
  const cache = await caches.open(cacheName);
  try {
    const resp = await Promise.race([fetch(request), timeout(NETWORK_WAIT)]);
    if (resp.ok && !resp.redirected && resp.type !== "opaqueredirect") await cache.put(key, resp.clone());
    return resp;
  } catch {
    const hit = await cache.match(key);
    if (hit) return hit;
    throw new Error("offline");
  }
}

async function cacheFirst(request, cacheName) {
  const cache = await caches.open(cacheName);
  const hit = await cache.match(request);
  if (hit) return hit;
  const resp = await fetch(request);
  if (resp.ok || resp.type === "opaque") await cache.put(request, resp.clone());
  return resp;
}

const OFFLINE_PAGE = `<!doctype html><html lang="de"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Digimon-Partner</title><body style="margin:0;height:100vh;display:grid;place-items:center;background:#0c0d0f;color:#f4f5f6;font-family:sans-serif;text-align:center">
<div><p style="font-size:22px">Keine Verbindung zum Digimon …</p><p style="color:#a3a8b0">Einmal mit Netz öffnen, danach geht es auch offline.</p></div>`;

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin === location.origin) {
    if (url.pathname.startsWith("/api/") || url.pathname.startsWith("/dev/")) return;
    if (req.mode === "navigate") {
      // Startseite: die zuletzt geladene Fassung, falls kein Netz. Andere Seiten (Login) nur mit Netz.
      if (url.pathname !== "/") return;
      event.respondWith(networkFirst(req, SHELL, "/").catch(() =>
        new Response(OFFLINE_PAGE, { headers: { "Content-Type": "text/html; charset=utf-8" } })));
      return;
    }
    if (url.pathname.startsWith("/assets/")) { event.respondWith(cacheFirst(req, MODELS)); return; }
    if (url.pathname.startsWith("/static/")) { event.respondWith(networkFirst(req, SHELL)); return; }
    return;
  }
  if (url.hostname === "unpkg.com" || url.hostname.endsWith("fonts.googleapis.com") || url.hostname.endsWith("fonts.gstatic.com")) {
    event.respondWith(cacheFirst(req, EXTERN));
  }
});
