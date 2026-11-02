"""Web-Push: das Digimon meldet sich von selbst, auch wenn die Seite zu ist.

Auf dem iPhone nur als Web-App vom Home-Bildschirm (ab iOS 16.4), auf Android/PC in jedem Browser.
Der Server prüft regelmäßig jeden Partner (als Kopie, nichts wird gespeichert) und schickt eine Mitteilung,
wenn sich etwas Neues ergibt. Damit es nicht nervt: jeder Grund höchstens alle paar Stunden, nachts nie.
"""

from __future__ import annotations

import base64
import json
import logging
from pathlib import Path
from urllib.parse import urlparse

import aiohttp
from cryptography.hazmat.primitives import serialization
from py_vapid import Vapid01
from pywebpush import WebPushException, webpush_async

log = logging.getLogger("partner.push")
HOUR = 3600.0
TTL = 4 * 3600      # nicht zugestellt (Handy aus)? Nach 4 Std. ist die Meldung veraltet und verfällt

# Nur an diese Push-Dienste wird gesendet (die Adresse kommt vom Browser – sonst könnte man den Server
# beliebige Adressen anfragen lassen)
PUSH_HOSTS = ("push.apple.com", "fcm.googleapis.com", "push.services.mozilla.com", "notify.windows.com")

LOW = 35            # wie in app.js: ab hier "hat Durst/Hunger/ist schlecht gelaunt"
REPEAT = {"thirst": 3 * HOUR, "hunger": 4 * HOUR, "sad": 6 * HOUR}


def allowed_endpoint(url: str) -> bool:
    u = urlparse(url)
    host = (u.hostname or "").lower()
    return u.scheme == "https" and any(host == h or host.endswith("." + h) for h in PUSH_HOSTS)


# --- Schlüssel (VAPID) --------------------------------------------------------------------------
def load_vapid(path: Path) -> Vapid01:
    """Schlüsselpaar des Servers; wird beim ersten Start erzeugt und bleibt im Datenordner.
    Geht er verloren, müssen alle Geräte die Benachrichtigungen neu einschalten."""
    if path.exists():
        return Vapid01.from_file(str(path))
    v = Vapid01()
    v.generate_keys()
    path.parent.mkdir(parents=True, exist_ok=True)
    v.save_key(str(path))
    path.chmod(0o600)   # privater Schlüssel: nur der Server-Nutzer darf ihn lesen
    return v


def public_key(v: Vapid01) -> str:
    raw = v.public_key.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


# --- Wann meldet es sich? -----------------------------------------------------------------------
def due(view: dict, memo: dict, now: float, jogress_from: list[tuple[int, str]],
        pet_id: int | None = None) -> tuple[list[dict], dict]:
    """Welche Mitteilungen jetzt fällig sind. view = game.view() des Partners, memo = was schon geschickt wurde.
    jogress_from = offene Jogress-Anfragen an dieses Konto als (id, Name des Freundes).
    Gibt die Mitteilungen und das neue memo zurück."""
    memo = {"sent": {}, **memo}
    if memo.get("pet") != pet_id:       # anderer Partner aktiv (Team, neues Ei): das ist keine Digitation
        memo["pet"], memo["form"] = pet_id, None
    sent, out = dict(memo["sent"]), []
    n = view["name"]

    def note(key: str, title: str, body: str) -> None:
        out.append({"title": title, "body": body, "tag": key.split(":")[0]})
        sent[key] = now

    # Nachts ist Ruhe – was dann passiert (z. B. Digitation), kommt morgens
    if view["asleep"]:
        return [], memo

    form = view["form"]
    if memo.get("form") and memo["form"] != form:
        if memo["form"] == "egg":
            note("evolve", "Dein Ei ist geschlüpft!", f"Sag hallo zu {n}.")
        else:
            note("evolve", "Digitation!", f"Dein Partner ist jetzt {n}. Komm schauen!")
    memo["form"] = form

    if form != "egg":
        st = view["stats"]
        fast = view["fasting"]
        # Beim Fasten ist Hunger gewollt – dann nur Durst melden
        if st["thirst"] < LOW:
            body = ("Leer! Ohne Wasser gibt's gleich einen Pflegefehler." if st["thirst"] <= 0
                    else f"{view['water_today']} von {view['water_goal']} Gläsern heute.")
            if _repeat(sent, "thirst", now):
                note("thirst", f"{n} hat Durst.", body)
        else:
            sent.pop("thirst", None)            # wieder gut: beim nächsten Mal sofort melden
        if st["hunger"] < LOW and not fast:
            body = ("Leer! Iss bald etwas, sonst gibt's einen Pflegefehler." if st["hunger"] <= 0
                    else "Trag ein, wenn du gegessen hast.")
            if _repeat(sent, "hunger", now):
                note("hunger", f"{n} hat Hunger.", body)
        else:
            sent.pop("hunger", None)
        if st["mood"] < LOW and st["thirst"] >= LOW and (st["hunger"] >= LOW or fast):
            if _repeat(sent, "sad", now):
                note("sad", f"{n} ist schlecht gelaunt.", "Hast du mich vergessen? Ein bisschen Pflege wär schön …")
        elif st["mood"] >= LOW:
            sent.pop("sad", None)
        if fast and fast["hours"] >= fast["goal"]:
            key = f"fast:{int(fast['start'])}"
            if key not in sent:
                note(key, "Fastenziel geschafft!", f"{fast['goal']} Stunden – {n} ist stolz auf dich.")

    for jid, who in jogress_from:
        key = f"jogress:{jid}"
        if key not in sent:
            note(key, f"{who} möchte Jogress!", "Zusammen werdet ihr zu Paildramon. Schau bei Freunde.")

    # alte Einmal-Meldungen (Fasten, Jogress) nach einer Woche vergessen
    memo["sent"] = {k: t for k, t in sent.items() if ":" not in k or now - t < 7 * 24 * HOUR}
    return out, memo


def _repeat(sent: dict, key: str, now: float) -> bool:
    return key not in sent or now - sent[key] >= REPEAT[key]


# --- Senden -------------------------------------------------------------------------------------
async def send(session: aiohttp.ClientSession, vapid: Vapid01, contact: str, sub: dict, message: dict) -> bool | None:
    """True = angekommen, False = Abo gibt es nicht mehr (löschen), None = anderer Fehler (später nochmal)."""
    info = {"endpoint": sub["endpoint"], "keys": {"p256dh": sub["p256dh"], "auth": sub["auth"]}}
    try:
        await webpush_async(info, json.dumps(message), vapid_private_key=vapid, vapid_claims={"sub": contact},
                            ttl=TTL, timeout=10, aiohttp_session=session)
        return True
    except WebPushException as exc:
        status = exc.status_code
        if status in (404, 410):
            return False
        log.warning("Push fehlgeschlagen (%s): %s", status, str(exc).splitlines()[0])
        return None
    except (aiohttp.ClientError, TimeoutError) as exc:
        log.warning("Push-Dienst nicht erreichbar: %s", exc)
        return None
