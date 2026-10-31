"""Spiel-Logik des Partners: Werte, Zeit, Pflegefehler, Digitation. Ohne Datenbank und Web –
alles arbeitet auf einem einfachen dict (dem Partner) und einer Uhrzeit, damit es gut testbar ist.

Zeit läuft "faul" weiter: Bei jedem Aufruf rechnet tick() die Zeit seit dem letzten Mal in
10-Minuten-Schritten nach (Schlafenszeit, Tageswechsel, Pflegefehler, Digitation).
"""

from __future__ import annotations

import random
from datetime import datetime
from zoneinfo import ZoneInfo

import lines as L

STEP = 600  # Sekunden je Rechenschritt
HOUR = 3600
DAY = 24 * HOUR

# Wie stark die Werte je wacher Stunde sinken (0–100)
DECAY = {"hunger": 6.0, "thirst": 9.0, "power": 0.6, "mind": 0.6, "disc": 0.3}
ZERO_HOURS = 2           # so lange darf Hunger/Durst leer sein, dann Pflegefehler
REPEAT_HOURS = 6         # danach frühestens der nächste Pflegefehler für denselben Wert
GLASS = 12.5             # ein Glas Wasser (bei Ziel 8 Gläsern füllt ein Tag den Durst)
MEAL, COOKED = 30.0, 45.0

DEFAULT_SETTINGS = {"sleep_start": "23:00", "sleep_end": "07:00", "water_goal": 8, "fast_goal": 16,
                    "week_kraft": 3, "week_geist": 2, "step_goal": 8000, "tz": "Europe/Berlin"}


def _settings(s: dict | None) -> dict:
    return {**DEFAULT_SETTINGS, **(s or {})}


def _local(ts: float, tz: str) -> datetime:
    return datetime.fromtimestamp(ts, ZoneInfo(tz))


def asleep(ts: float, settings: dict) -> bool:
    """Liegt die Uhrzeit im Schlaf-Fenster (auch über Mitternacht, z. B. 23:00–07:00)?"""
    s = _settings(settings)
    t = _local(ts, s["tz"])
    minutes = t.hour * 60 + t.minute
    a = int(s["sleep_start"][:2]) * 60 + int(s["sleep_start"][3:5])
    b = int(s["sleep_end"][:2]) * 60 + int(s["sleep_end"][3:5])
    return (a <= minutes < b) if a < b else (minutes >= a or minutes < b)


def _period() -> dict:
    return {"kraft_min": 0, "geist_min": 0, "sessions": 0, "mistakes": 0, "fasts": 0, "water_days": 0}


def _week(now: float) -> dict:
    return {"start": now, "mistakes": 0, "sessions": 0, "kraft": 0, "geist": 0, "water_days": 0}


def new_pet(now: float, line: str | None = None, avoid: str | None = None) -> dict:
    """Neues Digi-Ei. Die Linie ist zufällig (nicht dieselbe wie zuletzt, wenn möglich)."""
    choices = [k for k in L.LINES if k != avoid] or list(L.LINES)
    line = line or random.choice(choices)
    return {
        "line": line, "form": "egg", "born": now, "stage_since": now, "last_tick": now,
        "stats": {"hunger": 70.0, "thirst": 70.0, "power": 0.0, "mind": 0.0, "disc": 20.0, "mood": 70.0},
        "mistakes": 0, "period": _period(), "week": _week(now), "faul_origin": None, "wait_since": None,
        "zero_since": {"hunger": None, "thirst": None}, "fasting": None, "water_today": 0, "today": None,
        "forms": [], "training": None,
    }


def _log(kind: str, text: str, **extra) -> dict:
    return {"kind": kind, "text": text, **extra}


def _clamp(pet: dict) -> None:
    for k, v in pet["stats"].items():
        pet["stats"][k] = max(0.0, min(100.0, v))


def _mood_target(s: dict) -> float:
    care = (s["hunger"] + s["thirst"]) / 2
    fit = min(100.0, s["power"] + s["mind"])
    return care * 0.5 + fit * 0.3 + s["disc"] * 0.2


# --- Zeit vergehen lassen ---------------------------------------------------------------
def tick(pet: dict, now: float, settings: dict | None = None) -> list[dict]:
    s = _settings(settings)
    logs: list[dict] = []
    t = pet["last_tick"]
    while t < now:
        dt = min(STEP, now - t)
        t += dt
        logs += _step(pet, t, dt, s)
    pet["last_tick"] = now
    return logs


def _step(pet: dict, t: float, dt: float, s: dict) -> list[dict]:
    logs = []
    today = _local(t, s["tz"]).date().isoformat()
    if pet["today"] != today:
        if pet["today"] is not None:
            ok = pet["water_today"] >= s["water_goal"]
            if ok:
                pet["period"]["water_days"] += 1
                pet["week"]["water_days"] += 1
            # für Serien (progress.py); erscheint nicht im Tagebuch
            if pet["form"] != "egg":
                logs.append(_log("day", "", date=pet["today"], water_ok=ok))
        pet["today"], pet["water_today"] = today, 0

    if pet["form"] != "egg" and not asleep(t, s):
        h = dt / HOUR
        st = pet["stats"]
        for k, rate in DECAY.items():
            st[k] -= rate * h
        _clamp(pet)
        st["mood"] += (_mood_target(st) - st["mood"]) * min(1.0, 0.15 * h * 6)
        logs += _care_mistakes(pet, t)

    if t - pet["week"]["start"] >= 7 * DAY:
        logs += _end_of_week(pet, t, s)
    logs += _maybe_evolve(pet, t)
    return logs


def _care_mistakes(pet: dict, t: float) -> list[dict]:
    logs = []
    for key in ("hunger", "thirst"):
        empty = pet["stats"][key] <= 0
        if key == "hunger" and pet["fasting"]:
            empty = False  # beim Fasten zählt leerer Magen nicht
        since = pet["zero_since"][key]
        if not empty:
            pet["zero_since"][key] = None
        elif since is None:
            pet["zero_since"][key] = t
        elif t - since >= ZERO_HOURS * HOUR:
            pet["mistakes"] += 1
            pet["period"]["mistakes"] += 1
            pet["week"]["mistakes"] += 1
            # nächster Fehler für denselben Wert frühestens nach REPEAT_HOURS
            pet["zero_since"][key] = t + (REPEAT_HOURS - ZERO_HOURS) * HOUR
            what = "Hunger" if key == "hunger" else "Durst"
            logs.append(_log("mistake", f"{L.name_of(pet['form'])} hatte zu lange {what}. Pflegefehler!"))
    return logs


def perfect_week(pet: dict, s: dict) -> bool:
    w = pet["week"]
    trained = w["kraft"] >= s["week_kraft"] and w["geist"] >= s["week_geist"]
    return w["mistakes"] == 0 and trained and w["water_days"] >= 6


def _end_of_week(pet: dict, t: float, s: dict) -> list[dict]:
    perfect = pet["form"] != "egg" and perfect_week(pet, s)
    logs = [_log("week", "", perfect=perfect)]  # für Erfolge; erscheint nicht im Tagebuch
    target = L.FORM_CHANGE.get(pet["form"])
    if target and perfect:
        old = pet["form"]
        pet["form"] = target
        pet["forms"].append(target)
        logs.append(_log("formchange", f"Perfekte Woche! {L.name_of(old)} wechselt in den {L.name_of(target)}!",
                         old=old, new=target))
    pet["week"] = _week(t)
    return logs


# --- Digitation ---------------------------------------------------------------------------
def _sessions_per_week(pet: dict, stage: str) -> float:
    weeks = max(1.0, L.STAGE_HOURS.get(stage, 168) / 168)
    return pet["period"]["sessions"] / weeks


def _check(cond: str, pet: dict) -> bool:
    p = pet["period"]
    return {
        "immer": True,
        "kraft": p["kraft_min"] >= p["geist_min"],
        "geist": p["geist_min"] > p["kraft_min"],
        "wild": p["mistakes"] >= 2,
        "jogress": False,  # kommt mit der Freunde-Etappe
        "comeback": p["mistakes"] < 2 and p["sessions"] >= 2,
        "numemon": pet["faul_origin"] == "numemon",
    }.get(cond, False)


def next_form(pet: dict, preview: bool = False) -> str | None:
    """Welche Form käme jetzt? None = keine weitere Digitation (Endstufe).
    preview: ohne Faul-Abzweig – das Ziel, wenn du so weitermachst wie geplant (für die Vorschau)."""
    form = pet["form"]
    if form == "egg":
        return L.LINES[pet["line"]]["start"]
    stage = L.stage_of(form)
    faul = form in L.FAUL_EVO
    if preview:
        pass
    elif stage == "rookie":
        if pet["period"]["mistakes"] >= 4:
            return L.FAUL_PFLEGE
        if _sessions_per_week(pet, stage) < 2:
            return L.FAUL_TRAINING
    if not preview and stage == "champion" and not faul and _sessions_per_week(pet, stage) < 1:
        return L.FAUL_ULTIMATE
    rules = L.FAUL_EVO.get(form) or L.LINES[pet["line"]]["evo"].get(form) or []
    for cond, target in rules:
        if (preview and cond == "jogress") or _check(cond, pet):
            return target
    return None


def _maybe_evolve(pet: dict, t: float) -> list[dict]:
    form = pet["form"]
    stage = L.stage_of(form)
    hours = L.STAGE_HOURS.get(stage)
    if hours is None or t - pet["stage_since"] < hours * HOUR:
        return []
    # Ultimate zu faul zum Weiterdigitieren: noch eine Woche warten
    if stage == "ultimate" and form not in L.FAUL_EVO and _sessions_per_week(pet, stage) < 1:
        pet["stage_since"] += 7 * DAY
        return [_log("lazy", f"{L.name_of(form)} ist zu faul zum Digitieren. Noch eine Woche trainieren!")]
    # Jogress-Formen warten erst auf einen Partner
    if form in L.JOGRESS_FORMS:
        if pet["wait_since"] is None:
            pet["wait_since"] = t
            partner = L.name_of(L.JOGRESS_FORMS[form])
            return [_log("wait", f"{L.name_of(form)} wartet auf ein {partner} für die Jogress zu Paildramon.")]
        if t - pet["wait_since"] < L.JOGRESS_WAIT_HOURS * HOUR:
            return []
    target = next_form(pet)
    if target is None:
        return []
    return [evolve(pet, target, t)]


def evolve(pet: dict, target: str, t: float) -> dict:
    old = pet["form"]
    if target == L.FAUL_TRAINING:
        pet["faul_origin"] = "numemon"
    elif target == L.FAUL_PFLEGE:
        pet["faul_origin"] = "sukamon"
    pet["form"] = target
    pet["forms"].append(target)
    pet["stage_since"] = t
    pet["period"] = _period()
    pet["wait_since"] = None
    if old == "egg":
        return _log("hatch", f"Das Digi-Ei ist geschlüpft: {L.name_of(target)}!", old=old, new=target)
    return _log("evolve", f"{L.name_of(old)} digitiert zu {L.name_of(target)}!", old=old, new=target)


# --- Team: pausieren und wieder aktiv machen ----------------------------------------------
TEAM_SIZE = 3
# Was zu dir gehört und nicht zum Digimon: wandert beim Wechsel zum neuen aktiven Partner
CARRY = ("today", "water_today", "fasting", "training")


def pause(pet: dict, now: float) -> dict:
    """Partner pausieren: seine Zeit steht still. Gibt zurück, was der nächste aktive Partner übernimmt."""
    carry = {k: pet.get(k) for k in CARRY}
    pet.update(today=None, water_today=0, fasting=None, training=None, paused_at=now)
    return carry


def resume(pet: dict, now: float, carry: dict | None = None) -> None:
    """Pausierten Partner wieder aktiv machen: alle Zeitpunkte rücken um die Pause nach vorn,
    damit in der Pause nichts passiert ist (kein Hunger, keine Digitation, keine Wartezeit)."""
    gap = max(0.0, now - (pet.get("paused_at") or now))
    for key in ("last_tick", "stage_since", "born"):
        pet[key] += gap
    pet["week"]["start"] += gap
    if pet["wait_since"] is not None:
        pet["wait_since"] += gap
    for key, since in pet["zero_since"].items():
        if since is not None:
            pet["zero_since"][key] = since + gap
    pet["paused_at"] = None
    if carry:
        pet.update(carry)


def can_jogress(pet: dict) -> bool:
    """Wartet dieser Partner gerade auf einen Jogress-Partner (Stufe fertig, Wartezeit läuft)?"""
    return pet["form"] in L.JOGRESS_FORMS and pet["wait_since"] is not None


def jogress(pet: dict, t: float, who: str) -> list[dict]:
    """Jogress: dieser Partner verschmilzt mit dem Gegenstück zur Jogress-Form (Paildramon).
    who: wer das Gegenstück ist, für den Tagebuch-Text (z. B. "Marios Stingmon")."""
    old = pet["form"]
    log = evolve(pet, L.JOGRESS_TARGET, t)
    log["text"] = f"Jogress! {L.name_of(old)} und {who} werden zu {L.name_of(L.JOGRESS_TARGET)}!"
    log["jogress"] = True
    return [log]


# --- Aktionen ------------------------------------------------------------------------------
def drink(pet: dict, glasses: int = 1) -> list[dict]:
    pet["stats"]["thirst"] += GLASS * glasses
    pet["stats"]["mood"] += 2
    pet["water_today"] += glasses
    _clamp(pet)
    return [_log("water", f"{glasses} Glas Wasser." if glasses == 1 else f"{glasses} Gläser Wasser.", glasses=glasses)]


def eat(pet: dict, now: float, cooked: str | None = None, settings: dict | None = None) -> list[dict]:
    logs = []
    if pet["fasting"]:
        logs += stop_fast(pet, now, settings)
    pet["stats"]["hunger"] += COOKED if cooked else MEAL
    pet["stats"]["mood"] += 5 if cooked else 1
    _clamp(pet)
    logs.append(_log("eat", f"Selbst gekocht: {cooked}. Lecker!" if cooked else "Etwas gegessen.", cooked=bool(cooked)))
    return logs


def train(pet: dict, kind: str, minutes: int, plan: str = "") -> list[dict]:
    """kind: "kraft" (ohne Geräte) oder "geist" (Dehnen/Yoga)."""
    minutes = max(1, min(240, int(minutes)))
    st, p, w = pet["stats"], pet["period"], pet["week"]
    if kind == "geist":
        st["mind"] += minutes * 1.5
        p["geist_min"] += minutes
        w["geist"] += 1
    else:
        st["power"] += minutes * 1.5
        p["kraft_min"] += minutes
        w["kraft"] += 1
    p["sessions"] += 1
    w["sessions"] += 1
    st["hunger"] -= 5
    st["thirst"] -= 8
    st["mood"] += 6
    _clamp(pet)
    what = "Dehnen/Yoga" if kind == "geist" else "Krafttraining"
    return [_log("train", f"{what}{f' ({plan})' if plan else ''}: {minutes} Minuten.", art=kind, minutes=minutes)]


STEP_POWER = 1.5   # Kraft je 1000 Schritte (zum Vergleich: 30 Minuten Training geben 45)
STEP_MOOD = 0.5    # Laune je 1000 Schritte
STEP_CAP = 20000   # mehr Schritte an einem Tag bringen dem Partner nichts mehr


def walk(pet: dict, day: str, before: int, after: int, goal: int) -> list[dict]:
    """Neue Schritte eines Tages (vom Handy gemeldet, before → after). Kraft und Laune steigen mit;
    das Schrittziel zählt einmal am Tag wie ein Training (gegen den Faul-Weg), nicht für Kraft- oder Yoga-Ziele."""
    gain = max(0, min(after, STEP_CAP) - min(before, STEP_CAP)) / 1000
    st = pet["stats"]
    if pet["form"] != "egg" and gain:
        st["power"] += gain * STEP_POWER
        st["mood"] += gain * STEP_MOOD
        _clamp(pet)
    # für Summe und Serie (progress.py); erscheint nicht im Tagebuch
    logs = [_log("steps", "", day=day, steps=after, new=after - before)]
    if before < goal <= after:
        if pet["form"] != "egg":
            pet["period"]["sessions"] += 1
            pet["week"]["sessions"] += 1
        logs.append(_log("steps_goal", f"Schrittziel geschafft: {after:,} Schritte!".replace(",", "."), day=day, steps=after))
    return logs


MAX_BACKDATE = 12 * HOUR  # so weit darf der Fasten-Start zurückliegen ("letzte Mahlzeit war um …")


def start_fast(pet: dict, now: float, settings: dict | None = None, start: float | None = None) -> list[dict]:
    if pet["fasting"]:
        return []
    s = _settings(settings)
    goal = s["fast_goal"]
    start = now if start is None else max(now - MAX_BACKDATE, min(now, start))
    pet["fasting"] = {"start": start, "goal": goal}
    since = f", seit {_local(start, s['tz']).strftime('%H:%M')} Uhr" if now - start >= 60 else ""
    return [_log("fast", f"Fasten gestartet ({goal}:{24 - goal}){since}.")]


def stop_fast(pet: dict, now: float, settings: dict | None = None) -> list[dict]:
    f = pet["fasting"]
    if not f:
        return []
    pet["fasting"] = None
    hours = (now - f["start"]) / HOUR
    # für Verlauf und Fasten-Serie (Tag = Kalendertag, an dem das Fasten endet)
    info = {"start": f["start"], "end": now, "hours": round(hours, 2), "goal": f["goal"],
            "day": _local(now, _settings(settings)["tz"]).date().isoformat()}
    if hours >= f["goal"]:
        pet["stats"]["disc"] += 15
        pet["stats"]["mood"] += 5
        pet["period"]["fasts"] += 1
        _clamp(pet)
        return [_log("fast_done", f"Fasten geschafft: {hours:.1f} Stunden!", **info)]
    if hours >= 1:
        pet["stats"]["disc"] -= 5
        _clamp(pet)
    return [_log("fast_break", f"Fasten nach {hours:.1f} Stunden beendet (Ziel {f['goal']}).", **info)]


# --- Anzeige -------------------------------------------------------------------------------
def view(pet: dict, now: float, settings: dict | None = None) -> dict:
    s = _settings(settings)
    form = pet["form"]
    stage = L.stage_of(form)
    hours = L.STAGE_HOURS.get(stage)
    elapsed = (now - pet["stage_since"]) / HOUR
    p = pet["period"]
    tendency = None
    if stage in ("rookie", "champion"):
        tendency = "geist" if p["geist_min"] > p["kraft_min"] else "kraft" if p["kraft_min"] else None
    fast = None
    if pet["fasting"]:
        fast = {"start": pet["fasting"]["start"], "goal": pet["fasting"]["goal"],
                "goal_at": pet["fasting"]["start"] + pet["fasting"]["goal"] * HOUR,
                "hours": round((now - pet["fasting"]["start"]) / HOUR, 2)}
    return {
        "line": pet["line"], "egg": L.LINES[pet["line"]]["egg"], "egg_model": L.LINES[pet["line"]]["egg_model"],
        "form": form, "name": L.name_of(form),
        "stage": stage, "stage_label": L.STAGE_LABEL[stage],
        "stats": {k: round(v, 1) for k, v in pet["stats"].items()},
        "mistakes": pet["mistakes"], "period": p, "week": {k: v for k, v in pet["week"].items() if k != "start"},
        "progress": None if hours is None else min(1.0, elapsed / hours),
        "hours_left": None if hours is None else max(0.0, round(hours - elapsed, 1)),
        "waiting": pet["wait_since"] is not None, "tendency": tendency,
        "jogress_partner": L.name_of(L.JOGRESS_FORMS[form]) if form in L.JOGRESS_FORMS else None,
        "jogress_left": (round(max(0.0, L.JOGRESS_WAIT_HOURS - (now - pet["wait_since"]) / HOUR), 1)
                         if form in L.JOGRESS_FORMS and pet["wait_since"] is not None else None),
        # Endstufe (Mega oder ein Weg ohne Fortsetzung): dann darf ein neues Ei gelegt werden
        "end": form != "egg" and (hours is None or next_form(pet) is None),
        # Was käme jetzt als Nächstes (für die Schatten-Silhouette "???"); kann sich durchs Training noch ändern
        "next": None if hours is None else next_form(pet, preview=True),
        # Ab der Hälfte der Stufe warnen, wenn es gerade auf den Faul-Weg zuläuft
        "lazy_risk": (hours is not None and elapsed >= hours / 2 and form not in L.JOGRESS_FORMS
                      and next_form(pet) != next_form(pet, preview=True)),
        "stage_index": L.STAGES.index(stage),
        "training": pet.get("training"),
        "fasting": fast, "asleep": asleep(now, s), "water_today": pet["water_today"], "water_goal": s["water_goal"],
        "age_days": round((now - pet["born"]) / DAY, 1), "forms": pet["forms"],
        "perfect_week": perfect_week(pet, s) if form in L.FORM_CHANGE else None,
    }


def local_day(now: float, settings: dict | None = None) -> str:
    return _local(now, _settings(settings)["tz"]).date().isoformat()


def local_now_text(now: float, settings: dict | None = None) -> str:
    return _local(now, _settings(settings)["tz"]).strftime("%d.%m. %H:%M")
