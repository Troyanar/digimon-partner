"""Digimon-Partner: Webserver (aiohttp). Start: python app.py"""

from __future__ import annotations

import asyncio
import contextlib
import base64
import copy
import hashlib
import json
import logging
import re
import secrets
import time
from datetime import date, timedelta
from urllib.parse import urlencode

import aiohttp
from aiohttp import web

import auth
import config
import db
import game
import lines as L
import progress
import push
import training
import nutrition

STATIC = config.BASE_DIR / "static"
log = logging.getLogger("partner")
store_key = web.AppKey("store", db.Store)
vapid_key = web.AppKey("vapid", object)
http_key = web.AppKey("http", object)
login_limit = auth.RateLimit(8, 15 * 60)
login_limit_all = auth.RateLimit(40, 15 * 60)
register_limit = auth.RateLimit(5, 60 * 60)
photo_limit = auth.RateLimit(20, 60 * 60)
step_limit = auth.RateLimit(20, 15 * 60)  # falsche Schritte-Schlüssel

ASSET_ID = re.compile(r"^(?:[a-g]\d{3}|egg\d{2})$")
ASSET_FILE = re.compile(r"^[A-Za-z0-9_()\-]+\.(fbx|png|json|obj)$")
NAME = re.compile(r"^[\wÄÖÜäöüß .\-]{2,24}$")


def _csp() -> str:
    """Die Importmap in index.html ist ein Inline-Script – per Hash erlauben statt 'unsafe-inline'."""
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    hashes = []
    for m in re.finditer(r'<script type="importmap">(.*?)</script>', html, re.S):
        digest = base64.b64encode(hashlib.sha256(m.group(1).encode()).digest()).decode()
        hashes.append(f"'sha256-{digest}'")
    return ("default-src 'self'; script-src 'self' https://unpkg.com " + " ".join(hashes) + "; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; "
            # connect-src: der Service Worker (sw.js) holt three.js und die Schriften selbst, um sie offline vorzuhalten
            "img-src 'self' data: blob:; connect-src 'self' https://unpkg.com https://fonts.googleapis.com https://fonts.gstatic.com; "
            "frame-ancestors 'none'; form-action 'self'; "
            "base-uri 'none'; object-src 'none'")


CSP = _csp()
SECURITY_HEADERS = {"X-Frame-Options": "DENY", "X-Content-Type-Options": "nosniff",
                    "Referrer-Policy": "same-origin", "Content-Security-Policy": CSP}


def store(request: web.Request) -> db.Store:
    return request.app[store_key]


def fail(status: int, message: str) -> web.Response:
    return web.json_response({"error": message}, status=status)


async def body(request: web.Request) -> dict:
    try:
        data = await request.json()
    except ValueError:
        raise web.HTTPBadRequest(text="Ungültiges JSON") from None
    if not isinstance(data, dict):
        raise web.HTTPBadRequest(text="Ungültiges JSON")
    return data


def is_https(request: web.Request) -> bool:
    return request.secure or request.headers.get("X-Forwarded-Proto") == "https"


def _now(s: db.Store, uid: int) -> float:
    """Spielzeit eines Kontos. Im Test-Modus kann pro Konto vorgespult werden."""
    if config.DEV and uid:
        return time.time() + float(s.settings(uid).get("dev_offset", 0))
    return time.time()


def _settings(s: db.Store, uid: int) -> dict:
    raw = s.settings(uid)
    return {**game.DEFAULT_SETTINGS, "tz": config.TZ, **{k: v for k, v in raw.items() if k in game.DEFAULT_SETTINGS}}


def now_of(request: web.Request, uid: int) -> float:
    return _now(store(request), uid)


def settings_of(request: web.Request, uid: int) -> dict:
    return _settings(store(request), uid)


def now_for(request: web.Request) -> float:
    return now_of(request, request.get("user"))


def user_settings(request: web.Request) -> dict:
    return settings_of(request, request["user"])


# --- Middleware --------------------------------------------------------------------------
# /api/steps meldet sich mit dem Schritte-Schlüssel statt mit dem Anmelde-Cookie (Kurzbefehl auf dem iPhone)
OPEN = {"/login", "/api/login", "/api/register", "/api/me", "/dev/login", "/sw.js", "/api/steps", "/manifest.webmanifest"}


@web.middleware
async def security_headers(request: web.Request, handler):
    try:
        resp = await handler(request)
    except web.HTTPException as exc:
        exc.headers.update(SECURITY_HEADERS)
        raise
    resp.headers.update(SECURITY_HEADERS)
    return resp


@web.middleware
async def require_login(request: web.Request, handler):
    request["user"] = store(request).session_user(request.cookies.get(auth.COOKIE), auth.SESSION_SECONDS)
    if request.method not in ("GET", "HEAD") and request.path.startswith("/api/") \
            and request.content_type != "application/json" and not (
                request.path == "/api/nutrition/photo" and request.content_type in {"image/jpeg", "image/png", "image/webp"}):
        return fail(415, "Nur JSON")
    if request["user"] or request.path in OPEN or request.path.startswith("/static/"):
        return await handler(request)
    if request.path.startswith("/api/") or request.path.startswith("/assets/"):
        return fail(401, "Bitte anmelden")
    # nach dem Anmelden dorthin zurück (z. B. "Gekocht!" von der Rezepte-Seite)
    if request.path == "/" and request.query_string:
        raise web.HTTPFound("/login?" + urlencode({"next": request.path_qs}))
    raise web.HTTPFound("/login")


# --- Anmeldung -----------------------------------------------------------------------------
def _start_session(request: web.Request, user_id: int) -> web.Response:
    token = secrets.token_urlsafe(32)
    store(request).add_session(token, user_id, auth.SESSION_SECONDS)
    resp = web.json_response({"ok": True})
    resp.set_cookie(auth.COOKIE, token, max_age=auth.SESSION_SECONDS, httponly=True, samesite="Lax", secure=is_https(request))
    return resp


async def login_page(request: web.Request) -> web.StreamResponse:
    return web.FileResponse(STATIC / "login.html", headers={"Cache-Control": "no-cache"})


async def login(request: web.Request) -> web.Response:
    ip = auth.client_ip(request.remote, request.headers, config.TRUSTED_PROXIES)
    if login_limit.blocked(ip) or login_limit_all.blocked("all"):
        return fail(429, "Zu viele Versuche. Bitte in 15 Minuten nochmal.")
    data = await body(request)
    row = store(request).user_by_name(str(data.get("name") or "").strip())
    ok = row is not None and await asyncio.to_thread(auth.verify_password, str(data.get("password") or ""), row["pw_hash"])
    if not ok:
        login_limit.hit(ip)
        login_limit_all.hit("all")
        return fail(400, "Name oder Passwort stimmt nicht.")
    login_limit.reset(ip)
    return _start_session(request, row["id"])


async def register(request: web.Request) -> web.Response:
    ip = auth.client_ip(request.remote, request.headers, config.TRUSTED_PROXIES)
    if register_limit.blocked(ip):
        return fail(429, "Zu viele Versuche. Bitte später nochmal.")
    data = await body(request)
    s = store(request)
    name = " ".join(str(data.get("name") or "").split())
    password = str(data.get("password") or "")
    code = str(data.get("code") or "")
    first = s.user_count() == 0  # wer als Erstes kommt, ist Admin und braucht keinen Code
    if not NAME.match(name):
        return fail(400, "Name: 2 bis 24 Zeichen, Buchstaben, Zahlen, Leerzeichen, Punkt oder Bindestrich.")
    if len(password) < auth.MIN_PASSWORD:
        return fail(400, f"Das Passwort braucht mindestens {auth.MIN_PASSWORD} Zeichen.")
    if not first and not s.invite_open(code):
        register_limit.hit(ip)
        return fail(400, "Dieser Einladungscode stimmt nicht oder wurde schon benutzt.")
    if s.user_by_name(name):
        return fail(400, "Den Namen gibt es schon.")
    user_id = s.add_user(name, await asyncio.to_thread(auth.hash_password, password), is_admin=first)
    if not first:
        s.use_invite(code, user_id)
    pet = game.new_pet(time.time())
    s.add_pet(user_id, pet)
    return _start_session(request, user_id)


async def logout(request: web.Request) -> web.Response:
    store(request).end_session(request.cookies.get(auth.COOKIE))
    resp = web.json_response({"ok": True})
    resp.del_cookie(auth.COOKIE)
    return resp


def _apk_info() -> dict | None:
    path = config.APK_PATH
    if not path.is_file():
        return None
    st = path.stat()
    return {"size_kb": max(1, round(st.st_size / 1024)), "built": st.st_mtime}


async def download_apk(request: web.Request) -> web.StreamResponse:
    """Geräte-App (Android) – nur angemeldet, wie die 3D-Daten."""
    if not config.APK_PATH.is_file():
        raise web.HTTPNotFound(text="Die Geräte-App ist noch nicht gebaut.")
    return web.FileResponse(config.APK_PATH, headers={
        "Content-Type": "application/vnd.android.package-archive",
        "Content-Disposition": 'attachment; filename="DigimonPartner.apk"',
        "Cache-Control": "no-cache"})


async def me(request: web.Request) -> web.Response:
    s = store(request)
    if not request["user"]:
        return web.json_response({"user": None, "first": s.user_count() == 0})
    row = s.user(request["user"])
    return web.json_response({"user": {"name": row["name"], "admin": bool(row["is_admin"])}, "dev": config.DEV,
                              "names": L.NAMES, "team_size": game.TEAM_SIZE, "apk": _apk_info(),
                              "lines": [{"key": k, "egg": v["egg"], "egg_model": v["egg_model"]} for k, v in L.LINES.items()]})


async def service_worker(request: web.Request) -> web.StreamResponse:
    """Unter /sw.js (nicht /static/), damit er die ganze Seite abdecken darf – für den Offline-Betrieb."""
    return web.FileResponse(STATIC / "sw.js", headers={"Cache-Control": "no-cache", "Content-Type": "text/javascript"})


MANIFEST = {
    "name": "Digimon-Partner", "short_name": "Partner", "lang": "de", "id": "/", "start_url": "/", "scope": "/",
    "display": "standalone", "orientation": "portrait", "background_color": "#0c0d0f", "theme_color": "#0c0d0f",
    "icons": [{"src": "/static/icons/icon-192.png", "sizes": "192x192", "type": "image/png"},
              {"src": "/static/icons/icon-512.png", "sizes": "512x512", "type": "image/png"},
              {"src": "/static/icons/maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"}],
}


async def manifest(request: web.Request) -> web.Response:
    """Macht die Seite installierbar ("Zum Home-Bildschirm") – auf dem iPhone Voraussetzung für Benachrichtigungen."""
    return web.json_response(MANIFEST, content_type="application/manifest+json")


async def index(request: web.Request) -> web.StreamResponse:
    resp = web.FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-cache"})
    resp.set_cookie(auth.COOKIE, request.cookies[auth.COOKIE], max_age=auth.SESSION_SECONDS, httponly=True,
                    samesite="Lax", secure=is_https(request))
    return resp


# --- Partner -------------------------------------------------------------------------------
QUIET = {"day", "week", "steps"}  # Ereignisse nur für Serien/Erfolge, nicht fürs Tagebuch


def _progress(request: web.Request, uid: int | None = None) -> dict:
    s, uid = store(request), uid or request["user"]
    p = s.progress(uid)
    if p is None:
        # Konto von vor den Erfolgen: aus dem Tagebuch nachrechnen
        p = progress.new_progress()
        old = progress.apply(p, s.diary_all(uid), time.time())
        s.save_progress(uid, p)
        if old:
            s.log(uid, None, old, time.time())
    return p


def _record(request: web.Request, pet_id: int, logs: list[dict], now: float, uid: int | None = None) -> list[dict]:
    """Ereignisse ins Tagebuch schreiben und in den Fortschritt einrechnen. Gibt neue Erfolge zurück.
    uid: anderes Konto (z. B. der Freund bei Jogress oder Anfeuern), sonst das angemeldete."""
    s, uid = store(request), uid or request["user"]
    p = _progress(request, uid)
    fresh = progress.apply(p, logs, now)
    s.save_progress(uid, p)
    for e in logs:
        if e["kind"] in ("fast_done", "fast_break") and "start" in e:
            s.add_fast(uid, e["start"], e["end"], e["goal"], e["kind"] == "fast_done")
    entries = [e for e in logs if e["kind"] not in QUIET] + fresh
    if entries:
        s.log(uid, pet_id, entries, now)
    if uid == request["user"]:
        request["fresh"] = request.get("fresh", []) + fresh
    return fresh


def _load(request: web.Request, uid: int | None = None, tick: bool = True) -> tuple[int, dict, float, dict]:
    """Partner laden und die vergangene Zeit nachrechnen (Ergebnis wird gespeichert).
    tick=False: ohne Nachrechnen (der Offline-Sync rechnet selbst bis zu jeder Eintragung)."""
    s, uid = store(request), uid or request["user"]
    now, settings = now_of(request, uid), settings_of(request, uid)
    found = s.active_pet(uid)
    if not found:
        pet_id = s.add_pet(uid, game.new_pet(now))
        found = (pet_id, s.active_pet(uid)[1])
    pet_id, pet = found
    if not tick:
        return pet_id, pet, now, settings
    _record(request, pet_id, game.tick(pet, now, settings), now, uid)
    s.save_pet(pet_id, pet)
    return pet_id, pet, now, settings


def _state(request: web.Request, pet: dict, now: float, settings: dict) -> dict:
    s, uid = store(request), request["user"]
    view = game.view(pet, now, settings)
    return {"pet": view, "pet_id": (s.active_pet(uid) or [None])[0], "now": now, "clock": game.local_now_text(now, settings),
            "diary": s.diary(uid), "hall": len(s.hall(uid)), "settings": settings,
            "progress": progress.view(_progress(request), view["water_today"], view["water_goal"],
                                      game.local_day(now, settings)),
            "fasts": s.fasts(uid, now - 15 * 86400), "share": _shares(s.settings(uid)),
            "jogress_in": [r for r in s.jogress_open(uid) if r["to_id"] == uid],
            "steps": _steps_view(request, uid, now, settings),
            "team": [{"id": tid, "active": status == "active", "form": p["form"], "name": L.name_of(p["form"]),
                      "stage_label": L.STAGE_LABEL[L.stage_of(p["form"])], "egg_model": L.LINES[p["line"]]["egg_model"],
                      "line": L.LINES[p["line"]]["egg"]} for tid, status, p in s.team(uid)],
            "unlocked_now": request.get("fresh", [])}


async def nutrition_settings(request):
    _admin(request)
    if request.method == "PUT":
        data = await body(request)
        name = str(data.get("provider") or "")
        if name not in {"gemini", "openai", "deepseek", "custom"}:
            return fail(400, "Unbekannter Anbieter.")
        if data.get("remove") is True:
            nutrition.save_provider(name, {})
        else:
            old = nutrition.providers().get(name, {})
            key = str(data.get("key") or old.get("key") or "").strip()
            model = str(data.get("model") or "").strip()
            url = str(data.get("url") or "").strip().rstrip("/")
            from urllib.parse import urlsplit
            parsed = urlsplit(url)
            if not key or len(key) > 512 or not re.fullmatch(r"[A-Za-z0-9_.:/-]{1,120}", model):
                return fail(400, "Bitte API-Schlüssel und einen gültigen Modellnamen eingeben.")
            if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
                return fail(400, "Bitte eine HTTPS-API-Adresse ohne Zugangsdaten oder Parameter eingeben.")
            nutrition.save_provider(name, {"key": key, "model": model, "url": url})
    return web.json_response({"providers": {name: {"model": p["model"], "url": p["url"], "has_key": bool(p["key"])}
                                            for name, p in nutrition.providers().items()}})


async def nutrition_providers(request):
    return web.json_response({"providers": list(nutrition.providers())})


async def nutrition_photo(request):
    user_id = str(request["user"])
    if photo_limit.blocked(user_id):
        return fail(429, "Zu viele Fotoanalysen. Bitte später erneut versuchen.")
    available = nutrition.providers()
    provider = available.get(request.query.get("provider", ""))
    if not provider:
        return fail(400, "Diesen Foto-Anbieter bitte zuerst auf dem Server konfigurieren.")
    mime = request.content_type
    if mime not in {"image/jpeg", "image/png", "image/webp"}:
        return fail(400, "Bitte JPEG, PNG oder WebP verwenden.")
    image = await request.read()
    if not image or len(image) > 4 * 1024 * 1024:
        return fail(400, "Das Foto darf höchstens 4 MB groß sein.")
    try:
        photo_limit.hit(user_id)
        result = await nutrition.analyze(provider, image, mime)
    except (ValueError, aiohttp.ClientError, asyncio.TimeoutError) as exc:
        return fail(400, str(exc) if isinstance(exc, ValueError) else "Fotoanalyse nicht erreichbar. Bitte erneut versuchen.")
    return web.json_response(result)


async def get_state(request: web.Request) -> web.Response:
    _, pet, now, settings = _load(request)
    return web.json_response(_state(request, pet, now, settings))


class ActionError(ValueError):
    pass


def _apply(pet: dict, kind: str, data: dict, at: float, settings: dict, when: float | None = None) -> list[dict]:
    """Eine Eintragung zum Zeitpunkt at anwenden (sofort oder beim Offline-Sync nachgeholt).
    when: die echte Uhrzeit der Eintragung, falls sie vor dem Stand des Servers liegt – Dauern von Fasten
    und Training zählen damit richtig, auch wenn der Zustand erst ab at weitergerechnet werden kann."""
    when = at if when is None else min(at, when)
    if pet["form"] == "egg" and kind != "fast_start":
        raise ActionError("Das Ei schlüpft gleich – noch einen Moment.")
    try:
        if kind == "water":
            if "ml" in data:
                ml = int(data["ml"])
                if isinstance(data["ml"], bool) or ml != float(data["ml"]) or not 1 <= ml <= 10000:
                    raise ActionError("Bitte 1 bis 10.000 ml eingeben.")
                return game.drink(pet, ml=ml)
            return game.drink(pet, max(1, min(4, int(data.get("glasses") or 1))))
        if kind == "eat":
            cooked = str(data.get("cooked") or "").strip()[:120] or None
            calories = data.get("calories")
            if calories is not None:
                kcal = int(calories)
                if isinstance(calories, bool) or kcal != float(calories) or not 1 <= kcal <= 20000:
                    raise ActionError("Bitte 1 bis 20.000 kcal eingeben.")
            logs = game.eat(pet, when, cooked, settings)
            if calories is not None:
                pet["calories_today"] = (pet.get("calories_today") or 0) + kcal
                meal = str(data.get("meal") or "Mahlzeit").strip()[:120] or "Mahlzeit"
                logs[-1].update(text=f"{meal}: {kcal} kcal.", calories=kcal)
            return logs
        if kind == "fast_start":
            ago = max(0.0, min(12 * 60, float(data.get("minutes_ago") or 0)))
            return game.start_fast(pet, at, settings, start=when - ago * 60)
        if kind == "fast_stop":
            return game.stop_fast(pet, max(when, (pet["fasting"] or {}).get("start", when)), settings)
        if kind == "train":
            # Offline-Training: Start und Ende kommen mit; gleiche Regel wie online (mindestens die Hälfte der Zeit)
            plan = str(data.get("plan") or "")
            if plan not in training.PLANS:
                raise ActionError("Unbekannter Plan")
            start = float(data.get("start") or 0)
            minutes = training.credit_minutes(plan, when - start) if start else None
            if minutes is None:
                raise ActionError("Das Training ging zu schnell.")
            title, art = training.PLANS[plan][0], training.PLANS[plan][1]
            return game.train(pet, art, minutes, title)
    except (TypeError, ValueError, OverflowError) as exc:
        if isinstance(exc, ActionError):
            raise
        raise ActionError("Bitte eine Zahl") from None
    raise ActionError("Unbekannte Aktion")


async def action(request: web.Request) -> web.Response:
    data = await body(request)
    pet_id, pet, now, settings = _load(request)
    kind = str(data.get("kind") or "")
    if kind == "train":
        return fail(400, "Unbekannte Aktion")
    try:
        logs = _apply(pet, kind, data, now, settings)
    except ActionError as exc:
        return fail(400, str(exc))
    _record(request, pet_id, logs, now)
    store(request).save_pet(pet_id, pet)
    return web.json_response({**_state(request, pet, now, settings), "done": logs})


SYNC_KINDS = {"water", "eat", "fast_start", "fast_stop", "train"}
MAX_SYNC = 200


async def sync(request: web.Request) -> web.Response:
    """Offline gesammelte Eintragungen nachholen: in zeitlicher Reihenfolge, jede zu ihrer eigenen Uhrzeit.
    Bis zu jeder Eintragung wird die Zeit nachgerechnet, danach bis jetzt. Jede Eintragung (id) zählt nur einmal.
    Liegt eine Eintragung vor dem letzten Stand des Servers (z. B. weil inzwischen im Browser etwas passiert ist),
    zählt sie zu diesem Zeitpunkt."""
    data = await body(request)
    events = data.get("events")
    if not isinstance(events, list) or len(events) > MAX_SYNC:
        return fail(400, "Ungültige Liste")
    s, uid = store(request), request["user"]
    pet_id, pet, now, settings = _load(request, tick=False)
    done, rejected = [], []
    clean = []
    for e in events:
        if not isinstance(e, dict) or not isinstance(e.get("id"), str) or not 8 <= len(e["id"]) <= 64:
            continue
        try:
            at = float(e.get("at"))
        except (TypeError, ValueError):
            continue
        clean.append((at, e))
    for at, e in sorted(clean, key=lambda x: x[0]):
        kind = str(e.get("kind") or "")
        if kind not in SYNC_KINDS or not s.mark_synced(uid, e["id"]):
            done.append(e["id"])  # unbekannt oder schon erledigt: nicht nochmal schicken
            continue
        when = min(now, at)
        at = max(pet["last_tick"], when)
        _record(request, pet_id, game.tick(pet, at, settings), at)
        try:
            logs = _apply(pet, kind, e.get("data") if isinstance(e.get("data"), dict) else {}, at, settings, when)
        except ActionError as exc:
            rejected.append({"id": e["id"], "error": str(exc)})
            logs = []
        _record(request, pet_id, logs, at)
        done.append(e["id"])
    _record(request, pet_id, game.tick(pet, now, settings), now)
    s.save_pet(pet_id, pet)
    return web.json_response({**_state(request, pet, now, settings), "synced": done, "rejected": rejected})


async def get_plans(request: web.Request) -> web.Response:
    return web.json_response(training.plan_list())


async def train(request: web.Request) -> web.Response:
    """step "start": Plan merken (Startzeit). step "finish": gutschreiben, wenn genug Zeit vergangen ist."""
    data = await body(request)
    pet_id, pet, now, settings = _load(request)
    plan = str(data.get("plan") or "")
    if plan not in training.PLANS:
        return fail(400, "Unbekannter Plan")
    if pet["form"] == "egg":
        return fail(400, "Das Ei schlüpft gleich – dann könnt ihr zusammen trainieren.")
    step = data.get("step")
    logs: list[dict] = []
    if step == "start":
        pet["training"] = {"plan": plan, "start": now}
    elif step == "cancel":
        pet["training"] = None
    elif step == "finish":
        run = pet.get("training")
        if not run or run["plan"] != plan:
            return fail(400, "Dieses Training wurde nicht gestartet.")
        minutes = training.credit_minutes(plan, now - run["start"])
        if minutes is None:
            return fail(400, "Das ging zu schnell – mindestens die Hälfte der Zeit musst du wirklich trainieren.")
        title, art = training.PLANS[plan][0], training.PLANS[plan][1]
        pet["training"] = None
        logs = game.train(pet, art, minutes, title)
    else:
        return fail(400, "Unbekannter Schritt")
    _record(request, pet_id, logs, now)
    store(request).save_pet(pet_id, pet)
    return web.json_response({**_state(request, pet, now, settings), "done": logs})


async def new_egg(request: web.Request) -> web.Response:
    """Neues Digi-Ei der gewählten Linie. retire: der aktive (fertige) Partner zieht in die Ruhmeshalle,
    sonst wird er pausiert – das Team hat höchstens TEAM_SIZE Partner."""
    data = await body(request)
    s, uid = store(request), request["user"]
    pet_id, pet, now, settings = _load(request)
    line = str(data.get("line") or "")
    if line not in L.LINES:
        return fail(400, "Bitte ein Ei aussuchen.")
    retire = bool(data.get("retire"))
    if retire:
        if not game.view(pet, now, settings)["end"]:
            return fail(400, "Dein Partner ist noch nicht fertig entwickelt.")
    elif len(s.team(uid)) >= game.TEAM_SIZE:
        return fail(400, f"Dein Team ist voll ({game.TEAM_SIZE}). Ein fertiger Partner kann erst in die Ruhmeshalle ziehen.")
    carry = game.pause(pet, now)
    s.save_pet(pet_id, pet)
    if retire:
        s.retire_pet(pet_id)
        text = f"{L.name_of(pet['form'])} zieht in die Ruhmeshalle. Ein neues {L.LINES[line]['egg']}-Ei!"
    else:
        s.set_pet_status(pet_id, "paused")
        text = f"{L.name_of(pet['form'])} macht Pause. Ein neues {L.LINES[line]['egg']}-Ei ist da!"
    new = game.new_pet(now, line=line)
    new.update(carry)
    new_id = s.add_pet(uid, new)
    s.log(uid, new_id, [{"kind": "egg", "text": text}], now)
    return web.json_response(_state(request, new, now, settings))


async def switch_partner(request: web.Request) -> web.Response:
    """Anderen Partner aus dem Team aktiv machen; der bisherige pausiert."""
    data = await body(request)
    s, uid = store(request), request["user"]
    pet_id, pet, now, settings = _load(request)
    target = int(data.get("id") or 0)
    other = next(((tid, p) for tid, status, p in s.team(uid) if tid == target and status == "paused"), None)
    if not other:
        return fail(400, "Diesen Partner gibt es in deinem Team nicht.")
    if pet.get("training"):
        return fail(400, "Erst das laufende Training beenden.")
    o_id, o_pet = other
    carry = game.pause(pet, now)
    game.resume(o_pet, now, carry)
    s.save_pet(pet_id, pet)
    s.set_pet_status(pet_id, "paused")
    s.save_pet(o_id, o_pet)
    s.set_pet_status(o_id, "active")
    s.log(uid, o_id, [{"kind": "switch", "text": f"{L.name_of(o_pet['form'])} ist wieder dein aktiver Partner, "
                                                 f"{L.name_of(pet['form'])} macht Pause."}], now)
    _, o_pet, now, settings = _load(request)
    return web.json_response(_state(request, o_pet, now, settings))


async def get_hall(request: web.Request) -> web.Response:
    out = []
    for h in store(request).hall(request["user"]):
        p = h["pet"]
        out.append({"form": p["form"], "name": L.name_of(p["form"]), "line": L.LINES[p["line"]]["egg"],
                    "forms": [{"id": f, "name": L.name_of(f)} for f in p["forms"]], "created": h["created"], "ended": h["ended"]})
    return web.json_response(out)



# --- Freunde: alle sichtbaren Konten auf dieser Seite (nur mit Einladung erreichbar) --------------
def _shares(settings: dict) -> bool:
    return settings.get("share", True) is not False


def _friend_view(request: web.Request, uid: int) -> tuple[dict, dict] | None:
    """Aktueller Stand eines fremden Partners, ohne ihn zu verändern (Kopie wird nachgerechnet)."""
    found = store(request).active_pet(uid)
    if not found:
        return None
    pet = copy.deepcopy(found[1])
    last = pet["last_tick"]
    now, settings = now_of(request, uid), settings_of(request, uid)
    game.tick(pet, now, settings)
    return pet, {**game.view(pet, now, settings), "last_seen": last}


def _jogress_ok(mine: dict, theirs: dict) -> bool:
    return game.can_jogress(mine) and game.can_jogress(theirs) and L.JOGRESS_FORMS[mine["form"]] == theirs["form"]


async def get_friends(request: web.Request) -> web.Response:
    s, me = store(request), request["user"]
    _, pet, now, settings = _load(request)
    day = game.local_day(now, settings)
    cheered = s.cheered(me, day)
    out = []
    for u in s.users():
        if u["id"] == me or not _shares(json.loads(u["settings"] or "{}")):
            continue
        fv = _friend_view(request, u["id"])
        if not fv:
            continue
        their_pet, v = fv
        pr = progress.view(s.progress(u["id"]) or progress.new_progress(), v["water_today"], v["water_goal"])
        out.append({
            "name": u["name"], "cheered": u["id"] in cheered, "jogress": _jogress_ok(pet, their_pet),
            "pet": {k: v[k] for k in ("form", "name", "stage", "stage_label", "stage_index", "egg_model", "asleep",
                                      "waiting", "age_days", "last_seen", "week", "mistakes")},
            "fasting": bool(v["fasting"]), "mood": v["stats"]["mood"], "streak": pr["streak"], "trainings": pr["trainings"],
        })
    # Eigene Gegenstücke aus der Ruhmeshalle (z. B. ein früheres Stingmon für ein wartendes ExVeemon)
    hall = []
    if game.can_jogress(pet):
        want = L.JOGRESS_FORMS[pet["form"]]
        hall = [{"id": h["id"], "name": L.name_of(h["pet"]["form"]), "with": L.name_of(want)}
                for h in s.hall(me) if want in h["pet"]["forms"]]
    reqs = [{**r, "mine": r["from_id"] == me} for r in s.jogress_open(me)]
    return web.json_response({"friends": out, "hall": hall, "requests": reqs, "share": _shares(s.settings(me))})


def _friend_id(request: web.Request, name: str) -> int:
    row = store(request).user_by_name(name)
    if not row or row["id"] == request["user"] or not _shares(json.loads(row["settings"] or "{}")):
        raise web.HTTPBadRequest(text="Diesen Freund gibt es nicht.")
    return row["id"]


async def cheer(request: web.Request) -> web.Response:
    data = await body(request)
    s, me = store(request), request["user"]
    fid = _friend_id(request, str(data.get("name") or ""))
    pet_id, pet, now, settings = _load(request)
    if not s.add_cheer(me, fid, game.local_day(now, settings)):
        return fail(400, "Heute hast du diesen Partner schon angefeuert.")
    my_name = s.user(me)["name"]
    f_pet_id, f_pet, f_now, _ = _load(request, fid)
    if f_pet["form"] != "egg":
        f_pet["stats"]["mood"] = min(100.0, f_pet["stats"]["mood"] + 10)
    _record(request, f_pet_id, [{"kind": "cheer", "text": f"{my_name} hat {L.name_of(f_pet['form'])} angefeuert!"}], f_now, fid)
    s.save_pet(f_pet_id, f_pet)
    friend = s.user(fid)["name"]
    _record(request, pet_id, [{"kind": "cheer_sent", "text": f"Du hast {friend}s {L.name_of(f_pet['form'])} angefeuert."}], now)
    return web.json_response({**_state(request, pet, now, settings), "friend": friend})


async def jogress(request: web.Request) -> web.Response:
    """ask: Anfrage an einen Freund · accept/decline: Antwort auf eine Anfrage · hall: mit eigenem Gegenstück."""
    data = await body(request)
    s, me = store(request), request["user"]
    what = data.get("action")
    pet_id, pet, now, settings = _load(request)
    if what == "ask":
        fid = _friend_id(request, str(data.get("name") or ""))
        fv = _friend_view(request, fid)
        if not fv or not _jogress_ok(pet, fv[0]):
            return fail(400, "Jogress geht nur, wenn beide Partner bereit sind und zusammenpassen.")
        s.add_jogress(me, fid)
        _record(request, pet_id, [{"kind": "wait", "text": f"Jogress-Anfrage an {s.user(fid)['name']} geschickt."}], now)
    elif what in ("accept", "decline"):
        req = s.jogress_get(int(data.get("id") or 0))
        if not req or req["to_id"] != me or req["status"] != "open":
            return fail(400, "Diese Anfrage gibt es nicht mehr.")
        if what == "decline":
            s.jogress_set(req["id"], "declined")
        else:
            o_pet_id, o_pet, o_now, _ = _load(request, req["from_id"])
            if not _jogress_ok(pet, o_pet):
                s.jogress_set(req["id"], "cancelled")
                return fail(400, "Einer der beiden Partner ist nicht mehr bereit für die Jogress.")
            mine, theirs = pet["form"], o_pet["form"]
            me_name, other = s.user(me)["name"], s.user(req["from_id"])["name"]
            _record(request, pet_id, game.jogress(pet, now, f"{other}s {L.name_of(theirs)}"), now)
            _record(request, o_pet_id, game.jogress(o_pet, o_now, f"{me_name}s {L.name_of(mine)}"), o_now, req["from_id"])
            s.save_pet(o_pet_id, o_pet)
            s.jogress_set(req["id"], "done")
    elif what == "hall":
        hid = int(data.get("id") or 0)
        h = next((x for x in s.hall(me) if x["id"] == hid), None)
        if not game.can_jogress(pet) or not h or L.JOGRESS_FORMS[pet["form"]] not in h["pet"]["forms"]:
            return fail(400, "Damit geht keine Jogress.")
        who = f"dein {L.name_of(L.JOGRESS_FORMS[pet['form']])} aus der Ruhmeshalle"
        _record(request, pet_id, game.jogress(pet, now, who), now)
    else:
        return fail(400, "Unbekannte Aktion")
    s.save_pet(pet_id, pet)
    return web.json_response(_state(request, pet, now, settings))

# --- Schritte vom iPhone (Kurzbefehl) oder aus der App "Health Auto Export" ---------------------
MAX_STEPS = 100_000
STEP_DAYS = 7  # so viele Tage zurück dürfen noch nachgemeldet werden
DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _day(text) -> str | None:
    text = str(text or "")[:10]
    try:
        return date.fromisoformat(text).isoformat() if DAY.match(text) else None
    except ValueError:
        return None


def _count(value) -> int | None:
    """Schrittzahl aus dem JSON: Zahl oder Text ("5432", "5.432", "5432,0")."""
    if isinstance(value, bool):
        return None
    if isinstance(value, str):
        value = value.strip().replace(" ", "").replace("\u00a0", "").split(",")[0]
        if re.fullmatch(r"\d{1,3}(\.\d{3})+", value):  # deutscher Tausenderpunkt
            value = value.replace(".", "")
        try:
            value = float(value)
        except ValueError:
            return None
    if not isinstance(value, (int, float)) or value != value or value < 0:
        return None
    return min(MAX_STEPS, int(value))


def _step_reports(data: dict, today: str) -> dict[str, int]:
    """Gemeldete Schritte je Tag. Zwei Formate:
    Kurzbefehl: {"key": "...", "heute": 5432, "gestern": 9876 (freiwillig), "datum": "2026-10-31" (freiwillig)}
    Health Auto Export: {"data": {"metrics": [{"name": "step_count", "data": [{"date": "2026-10-31 ...", "qty": 5432}]}]}}"""
    out: dict[str, int] = {}
    inner = data.get("data")
    if isinstance(inner, dict) and isinstance(inner.get("metrics"), list):
        for m in inner["metrics"]:
            if not isinstance(m, dict) or m.get("name") != "step_count" or not isinstance(m.get("data"), list):
                continue
            for row in m["data"]:  # mehrere Einträge am Tag (z. B. stündlich) werden zusammengezählt
                day = _day(row.get("date")) if isinstance(row, dict) else None
                n = _count(row.get("qty")) if day else None
                if n is not None:
                    out[day] = min(MAX_STEPS, out.get(day, 0) + n)
    else:
        base = _day(data.get("datum")) or today
        n = _count(data.get("heute", data.get("steps")))
        if n is not None:
            out[base] = n
        n = _count(data.get("gestern"))
        if n is not None:
            out[(date.fromisoformat(base) - timedelta(days=1)).isoformat()] = n
    t = date.fromisoformat(today)
    lo, hi = (t - timedelta(days=STEP_DAYS - 1)).isoformat(), (t + timedelta(days=1)).isoformat()
    return {d: n for d, n in out.items() if lo <= d <= hi}


def _steps_view(request: web.Request, uid: int, now: float, settings: dict) -> dict:
    s, today = store(request), game.local_day(now, settings)
    days = s.steps_since(uid, (date.fromisoformat(today) - timedelta(days=6)).isoformat())
    return {"today": next((d["steps"] for d in days if d["day"] == today), 0), "goal": settings["step_goal"],
            "days": days, "key": s.step_key_info(uid)}


async def post_steps(request: web.Request) -> web.Response:
    ip = auth.client_ip(request.remote, request.headers, config.TRUSTED_PROXIES)
    if step_limit.blocked(ip):
        return fail(429, "Zu viele falsche Schlüssel. Bitte in 15 Minuten nochmal.")
    data = await body(request)
    s = store(request)
    header = request.headers.get("Authorization", "")
    key = (header[7:] if header.lower().startswith("bearer ") else
           request.headers.get("X-Partner-Key") or str(data.get("key") or "")).strip()
    uid = s.step_key_user(key) if key else None
    if not uid:
        step_limit.hit(ip)
        return fail(401, "Der Schlüssel stimmt nicht. Unter Mehr → Schritte einen neuen erzeugen.")
    pet_id, pet, now, settings = _load(request, uid)
    today = game.local_day(now, settings)
    reports = _step_reports(data, today)
    if not reports:
        return fail(400, "Keine Schritte gefunden. Im Kurzbefehl muss das Feld \"heute\" heißen und eine Zahl sein.")
    goal, logs = settings["step_goal"], []
    for day in sorted(reports):
        before = s.steps_of(uid, day)
        s.set_steps(uid, day, reports[day], now)
        if reports[day] > before:
            new = game.walk(pet, day, before, reports[day], goal)
            if day != today:  # nachgemeldet (z. B. gestern Abend): Datum dazuschreiben
                for e in new:
                    if e["kind"] == "steps_goal":
                        e["text"] = e["text"].replace("Schrittziel", f"Schrittziel vom {day[8:10]}.{day[5:7]}.", 1)
            logs += new
    _record(request, pet_id, logs, now, uid)
    s.save_pet(pet_id, pet)
    n = s.steps_of(uid, today)
    return web.json_response({"ok": True, "heute": n, "ziel": goal,
                              "text": f"{n:,} von {goal:,} Schritten".replace(",", ".")})


async def step_key(request: web.Request) -> web.Response:
    """POST: neuen Schlüssel erzeugen (wird nur dieses eine Mal gezeigt). DELETE: Verbindung trennen."""
    s, uid = store(request), request["user"]
    if request.method == "DELETE":
        s.drop_step_key(uid)
        return web.json_response({"key": None, "info": None})
    return web.json_response({"key": s.new_step_key(uid), "info": s.step_key_info(uid)})


# --- Benachrichtigungen (Web-Push) -------------------------------------------------------------
B64URL = re.compile(r"^[A-Za-z0-9_\-]{16,200}={0,2}$")


def _push_check(s: db.Store, uid: int) -> list[dict]:
    """Was der Partner gerade melden möchte (nachgerechnet als Kopie, gespeichert wird nur, was gemeldet wurde)."""
    found = s.active_pet(uid)
    if not found:
        return []
    pet_id, pet = found[0], copy.deepcopy(found[1])
    now, settings = _now(s, uid), _settings(s, uid)
    game.tick(pet, now, settings)
    jog = [(r["id"], r["from_name"]) for r in s.jogress_open(uid) if r["to_id"] == uid]
    out, memo = push.due(game.view(pet, now, settings), s.push_memo(uid), now, jog, pet_id)
    s.save_push_memo(uid, memo)
    return out


async def _push_to(app: web.Application, uid: int, messages: list[dict]) -> int:
    """An alle Geräte des Kontos. Gibt zurück, auf wie vielen es angekommen ist."""
    s, ok_count = app[store_key], 0
    for sub in s.push_subs(uid):
        for m in messages:
            ok = await push.send(app[http_key], app[vapid_key], config.PUSH_CONTACT, sub, {**m, "url": "/"})
            if ok is False:            # Abo abgelaufen oder auf dem Gerät ausgeschaltet
                s.drop_push(sub["endpoint"])
                break
            if ok:
                s.push_used(sub["endpoint"])
                ok_count += 1
    return ok_count


async def _push_loop(app: web.Application) -> None:
    await asyncio.sleep(20)
    while True:
        s = app[store_key]
        for uid in s.push_users():
            try:
                messages = _push_check(s, uid)
                if messages:
                    await _push_to(app, uid, messages)
            except Exception:  # ein kaputtes Konto soll die anderen nicht aufhalten
                log.exception("Push-Prüfung für Konto %s fehlgeschlagen", uid)
        await asyncio.sleep(config.PUSH_EVERY)


async def _push_ctx(app: web.Application):
    app[vapid_key] = push.load_vapid(config.VAPID_PATH)
    app[http_key] = aiohttp.ClientSession()
    task = asyncio.create_task(_push_loop(app)) if config.PUSH_EVERY else None
    yield
    if task:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
    await app[http_key].close()


async def push_info(request: web.Request) -> web.Response:
    s, uid = store(request), request["user"]
    return web.json_response({"key": push.public_key(request.app[vapid_key]), "devices": len(s.push_subs(uid))})


async def push_subscribe(request: web.Request) -> web.Response:
    """POST: dieses Gerät meldet sich an (Daten aus pushManager.subscribe()). DELETE: abmelden."""
    data = await body(request)
    s, uid = store(request), request["user"]
    endpoint = str(data.get("endpoint") or "")
    if len(endpoint) > 1024 or not push.allowed_endpoint(endpoint):
        return fail(400, "Dieser Browser schickt an einen unbekannten Push-Dienst.")
    if request.method == "DELETE":
        s.drop_push(endpoint, uid)
        return web.json_response({"devices": len(s.push_subs(uid))})
    keys = data.get("keys") if isinstance(data.get("keys"), dict) else {}
    p256dh, auth_secret = str(keys.get("p256dh") or ""), str(keys.get("auth") or "")
    if not (B64URL.match(p256dh) and B64URL.match(auth_secret)):
        return fail(400, "Ungültiges Abo.")
    s.add_push(uid, endpoint, p256dh, auth_secret)
    _push_check(s, uid)   # merkt sich den jetzigen Stand, damit nicht sofort alte Dinge gemeldet werden
    return web.json_response({"devices": len(s.push_subs(uid))})


async def push_test(request: web.Request) -> web.Response:
    s, uid = store(request), request["user"]
    found = s.active_pet(uid)
    name = L.name_of(found[1]["form"]) if found else "Dein Digimon"
    sent = await _push_to(request.app, uid, [{"title": f"Hallo von {name}!", "tag": "test",
                                              "body": "So sehen meine Meldungen aus, wenn ich etwas brauche."}])
    if not sent:
        return fail(502, "Die Mitteilung kam nicht an. Schalte die Benachrichtigungen aus und wieder ein.")
    return web.json_response({"sent": sent})


# --- Einstellungen ---------------------------------------------------------------------------
TIME = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


async def put_settings(request: web.Request) -> web.Response:
    data = await body(request)
    s, uid = store(request), request["user"]
    cur = s.settings(uid)
    for key in ("sleep_start", "sleep_end"):
        if key in data:
            if not TIME.match(str(data[key])):
                return fail(400, "Uhrzeit bitte als HH:MM")
            cur[key] = data[key]
    for key, lo, hi in (("water_goal", 1, 20), ("fast_goal", 12, 23), ("week_kraft", 0, 7), ("week_geist", 0, 7),
                         ("step_goal", 1000, 50000)):
        if key in data:
            try:
                value = int(data[key])
            except (TypeError, ValueError):
                return fail(400, "Bitte eine Zahl")
            if not lo <= value <= hi:
                return fail(400, f"Bitte eine Zahl von {lo} bis {hi}")
            cur[key] = value
    if "share" in data:
        cur["share"] = bool(data["share"])
    s.save_settings(uid, cur)
    return web.json_response(user_settings(request))


async def change_password(request: web.Request) -> web.Response:
    data = await body(request)
    s, uid = store(request), request["user"]
    if not await asyncio.to_thread(auth.verify_password, str(data.get("current") or ""), s.user(uid)["pw_hash"]):
        return fail(400, "Das bisherige Passwort stimmt nicht.")
    new = str(data.get("new") or "")
    if len(new) < auth.MIN_PASSWORD:
        return fail(400, f"Das neue Passwort braucht mindestens {auth.MIN_PASSWORD} Zeichen.")
    s.set_password(uid, await asyncio.to_thread(auth.hash_password, new))
    return web.json_response({"ok": True})


# --- Einladungen (nur Admin) ----------------------------------------------------------------
def _admin(request: web.Request) -> None:
    if not store(request).user(request["user"])["is_admin"]:
        raise web.HTTPForbidden(text="Nur für Admins")


async def get_invites(request: web.Request) -> web.Response:
    _admin(request)
    return web.json_response(store(request).invites())


async def add_invite(request: web.Request) -> web.Response:
    _admin(request)
    return web.json_response({"code": store(request).new_invite(request["user"]), "all": store(request).invites()})


# --- Test-Werkzeuge (nur mit DEV=1) -----------------------------------------------------------
async def dev(request: web.Request) -> web.Response:
    if not config.DEV:
        raise web.HTTPNotFound()
    data = await body(request)
    s, uid = store(request), request["user"]
    what = request.match_info["what"]
    if what == "skip":
        cur = s.settings(uid)
        cur["dev_offset"] = float(cur.get("dev_offset", 0)) + max(0.0, min(24 * 30, float(data.get("hours") or 1))) * 3600
        s.save_settings(uid, cur)
        _, pet, now, settings = _load(request)
        return web.json_response(_state(request, pet, now, settings))
    pet_id, pet, now, settings = _load(request)
    if what == "train":
        logs = game.train(pet, "geist" if data.get("art") == "geist" else "kraft", int(data.get("minutes") or 30), "Test")
    elif what == "form":
        form = str(data.get("form") or "")
        if form not in L.NAMES:
            return fail(400, "Unbekannte Form")
        # passende Linie mitsetzen, sonst fehlen die Wege (z. B. Agumon in einem DemiDevimon-Ei)
        for key, line in L.LINES.items():
            if form in line["evo"] or any(form == dst for rules in line["evo"].values() for _, dst in rules):
                pet["line"] = key
                break
        logs = [game.evolve(pet, form, now)]
    elif what == "empty":
        pet["stats"].update(hunger=0, thirst=0)
        logs = []
    else:
        return fail(400, "?")
    _record(request, pet_id, logs, now)
    s.save_pet(pet_id, pet)
    return web.json_response({**_state(request, pet, now, settings), "done": logs})


async def dev_login(request: web.Request) -> web.StreamResponse:
    """Nur im Test-Modus: meldet ein Test-Konto direkt an (für Prüf-Browser, die kein Formular ausfüllen)."""
    if not config.DEV:
        raise web.HTTPNotFound()
    s = store(request)
    name = (request.query.get("name") or "Test")[:24]
    if not NAME.match(name):
        raise web.HTTPBadRequest(text="Ungültiger Name")
    row = s.user_by_name(name)
    user_id = row["id"] if row else s.add_user(name, auth.hash_password(secrets.token_urlsafe(16)), is_admin=s.user_count() == 0)
    if not row:
        s.add_pet(user_id, game.new_pet(time.time()))
    token = secrets.token_urlsafe(32)
    s.add_session(token, user_id, auth.SESSION_SECONDS)
    resp = web.HTTPFound("/")
    resp.set_cookie(auth.COOKIE, token, max_age=auth.SESSION_SECONDS, httponly=True, samesite="Lax")
    raise resp


# --- 3D-Daten (nur angemeldet) ----------------------------------------------------------------
TYPES = {".fbx": "application/octet-stream", ".png": "image/png", ".json": "application/json", ".obj": "text/plain"}


async def asset(request: web.Request) -> web.StreamResponse:
    mid, name = request.match_info["id"], request.match_info["file"]
    if not ASSET_ID.match(mid) or not ASSET_FILE.match(name):
        raise web.HTTPNotFound()
    path = config.ASSET_DIR / mid / name
    if not path.is_file():
        raise web.HTTPNotFound()
    headers = {"Cache-Control": "private, max-age=86400", "Content-Type": TYPES[path.suffix]}
    gz = path.with_name(path.name + ".gz")
    if gz.is_file() and "gzip" in request.headers.get("Accept-Encoding", ""):
        headers["Content-Encoding"] = "gzip"
        return web.FileResponse(gz, headers=headers)
    return web.FileResponse(path, headers=headers)


def make_app() -> web.Application:
    app = web.Application(middlewares=[security_headers, require_login], client_max_size=4 * 1024 * 1024)
    app[store_key] = db.Store(config.DB_PATH)
    app.cleanup_ctx.append(_push_ctx)
    app.add_routes([
        web.get("/", index),
        web.get("/login", login_page),
        web.get("/sw.js", service_worker),
        web.get("/manifest.webmanifest", manifest),
        web.post("/api/login", login),
        web.post("/api/register", register),
        web.post("/api/logout", logout),
        web.get("/api/me", me),
        web.get("/api/state", get_state),
        web.post("/api/action", action),
        web.get("/api/nutrition/providers", nutrition_providers),
        web.get("/api/nutrition/settings", nutrition_settings),
        web.put("/api/nutrition/settings", nutrition_settings),
        web.post("/api/nutrition/photo", nutrition_photo),
        web.post("/api/egg", new_egg),
        web.post("/api/team/switch", switch_partner),
        web.get("/api/plans", get_plans),
        web.post("/api/train", train),
        web.post("/api/sync", sync),
        web.get("/api/friends", get_friends),
        web.post("/api/friends/cheer", cheer),
        web.post("/api/jogress", jogress),
        web.get("/api/hall", get_hall),
        web.post("/api/steps", post_steps),
        web.post("/api/steps/key", step_key),
        web.delete("/api/steps/key", step_key),
        web.get("/api/push", push_info),
        web.post("/api/push", push_subscribe),
        web.delete("/api/push", push_subscribe),
        web.post("/api/push/test", push_test),
        web.put("/api/settings", put_settings),
        web.post("/api/password", change_password),
        web.get("/api/invites", get_invites),
        web.post("/api/invites", add_invite),
        web.post("/api/dev/{what}", dev),
        web.get("/dev/login", dev_login),
        web.get("/assets/{id}/{file}", asset),
        web.get("/download/DigimonPartner.apk", download_apk),
        web.static("/static", STATIC),
    ])
    return app


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if config.DEV:
        log.warning("TEST-MODUS (DEV=1): Zeit vorspulen und Test-Training sind an – nie auf dem Server benutzen!")
    web.run_app(make_app(), host=config.HOST, port=config.PORT,
                print=lambda _: log.info("Digimon-Partner läuft auf http://%s:%s",
                                         "localhost" if config.HOST == "127.0.0.1" else config.HOST, config.PORT))
