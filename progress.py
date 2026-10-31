"""Fortschritt über alle Partner hinweg: Serien, Summen und Erfolge.

Wird aus den Ereignissen gefüttert, die game.py liefert (Wasser, Essen, Fasten, Digitation, Tageswechsel,
Wochenende). Gehört zum Konto, nicht zum einzelnen Digimon: eine Wasser-Serie läuft auch über ein neues Ei weiter.
"""

from __future__ import annotations

from datetime import date, timedelta

STAGE_RANK = {"a": 1, "b": 2, "c": 3, "d": 4, "e": 5, "f": 6, "g": 6}


def new_progress() -> dict:
    return {"glasses": 0, "meals": 0, "cooked": 0, "fasts": 0, "evolutions": 0, "best_rank": 0,
            "trainings": 0, "kraft": 0, "geist": 0, "train_minutes": 0,
            "fast_streak": 0, "best_fast_streak": 0, "last_fast_day": None, "longest_fast": 0.0,
            "cheers": 0, "jogress": 0,
            "steps_total": 0, "step_days": 0, "step_streak": 0, "best_step_streak": 0, "last_step_day": None,
            "streak": 0, "best_streak": 0, "perfect_weeks": 0, "unlocked": {}}


# (Schlüssel, Titel, Beschreibung, Wert aus dem Fortschritt, Ziel)
ACHIEVEMENTS = [
    ("erstes_glas", "Erster Schluck", "Das erste Glas Wasser eingetragen.", "glasses", 1),
    ("serie_3", "Drei Tage durch", "Drei Tage hintereinander das Wasserziel geschafft.", "best_streak", 3),
    ("serie_7", "Eine ganze Woche", "Sieben Tage hintereinander das Wasserziel geschafft.", "best_streak", 7),
    ("serie_30", "Monatsserie", "30 Tage hintereinander das Wasserziel geschafft.", "best_streak", 30),
    ("glaeser_100", "Wasserdrache", "100 Gläser Wasser getrunken.", "glasses", 100),
    ("erstes_training", "Erstes Training", "Das erste Training mit deinem Partner geschafft.", "trainings", 1),
    ("training_10", "Trainingspartner", "Zehn Trainings geschafft.", "trainings", 10),
    ("training_50", "Unermüdlich", "50 Trainings geschafft.", "trainings", 50),
    ("kraftpaket", "Kraftpaket", "Zehn Krafttrainings geschafft.", "kraft", 10),
    ("yogi", "Yogi", "Zehn Mal Dehnen oder Yoga geschafft.", "geist", 10),
    ("erste_mahlzeit", "Guten Appetit", "Die erste Mahlzeit eingetragen.", "meals", 1),
    ("koch", "Selbst gekocht", "Ein Rezept nachgekocht und deinen Partner damit gefüttert.", "cooked", 1),
    ("fasten_1", "Erstes Fasten", "Ein Fastenfenster bis zum Ziel durchgehalten.", "fasts", 1),
    ("fasten_serie_3", "Drei Tage diszipliniert", "An drei Tagen hintereinander ein Fastenfenster geschafft.", "best_fast_streak", 3),
    ("fasten_serie_7", "Fastenwoche", "Sieben Tage hintereinander ein Fastenfenster geschafft.", "best_fast_streak", 7),
    ("fasten_20", "Langer Atem", "Einmal 20 Stunden oder länger gefastet.", "longest_fast", 20),
    ("fasten_10", "Fastenmeister", "Zehn Fastenfenster bis zum Ziel durchgehalten.", "fasts", 10),
    ("digitation_1", "Erste Digitation", "Dein Partner hat sich zum ersten Mal entwickelt.", "evolutions", 1),
    ("champion", "Champion", "Ein Partner hat die Stufe Champion erreicht.", "best_rank", 4),
    ("ultimate", "Ultimate", "Ein Partner hat die Stufe Ultimate erreicht.", "best_rank", 5),
    ("mega", "Mega", "Ein Partner hat die Stufe Mega erreicht.", "best_rank", 6),
    ("schritte_ziel", "Erster Spaziergang", "Zum ersten Mal das Schrittziel geschafft.", "step_days", 1),
    ("schritte_serie_7", "Wandertage", "Sieben Tage hintereinander das Schrittziel geschafft.", "best_step_streak", 7),
    ("schritte_100k", "Hunderttausend", "100.000 Schritte gesammelt.", "steps_total", 100_000),
    ("schritte_1m", "Weltenbummler", "Eine Million Schritte gesammelt.", "steps_total", 1_000_000),
    ("anfeuern_1", "Gute Freunde", "Zum ersten Mal den Partner eines Freundes angefeuert.", "cheers", 1),
    ("anfeuern_10", "Cheerleader", "Zehn Mal Freunde angefeuert.", "cheers", 10),
    ("jogress", "Jogress!", "Zwei Partner sind zu einem verschmolzen.", "jogress", 1),
    ("perfekte_woche", "Perfekte Woche", "Eine Woche ohne Pflegefehler, mit Wochenziel im Training und Wasser an sechs Tagen.", "perfect_weeks", 1),
]


def _fill(progress: dict) -> dict:
    """Ältere gespeicherte Stände um neue Felder ergänzen."""
    for key, value in new_progress().items():
        progress.setdefault(key, value)
    return progress


def _fast_day(progress: dict, day: str | None) -> None:
    """Fasten-Serie: ein geschafftes Fasten pro Kalendertag zählt; ein ausgelassener Tag beendet die Serie."""
    if not day:  # alte Einträge ohne Datum zählen nur in der Summe
        return
    last = progress["last_fast_day"]
    if last == day:
        return
    yesterday = (date.fromisoformat(day) - timedelta(days=1)).isoformat()
    progress["fast_streak"] = progress["fast_streak"] + 1 if last == yesterday else 1
    progress["best_fast_streak"] = max(progress["best_fast_streak"], progress["fast_streak"])
    progress["last_fast_day"] = day


def _step_day(progress: dict, day: str) -> None:
    """Schritt-Serie: Tage mit Schrittziel am Stück. Ein nachgemeldeter älterer Tag ändert die Serie nicht mehr."""
    last = progress["last_step_day"]
    if last is not None and day <= last:
        return
    yesterday = (date.fromisoformat(day) - timedelta(days=1)).isoformat()
    progress["step_streak"] = progress["step_streak"] + 1 if last == yesterday else 1
    progress["best_step_streak"] = max(progress["best_step_streak"], progress["step_streak"])
    progress["last_step_day"] = day


def apply(progress: dict, logs: list[dict], now: float) -> list[dict]:
    """Ereignisse einrechnen. Gibt neu freigeschaltete Erfolge als Tagebuch-Einträge zurück."""
    _fill(progress)
    for e in logs:
        kind = e["kind"]
        if kind == "water":
            progress["glasses"] += e.get("glasses", 1)
        elif kind == "eat":
            progress["meals"] += 1
            if e.get("cooked"):
                progress["cooked"] += 1
        elif kind == "train":
            progress["trainings"] += 1
            progress["geist" if e.get("art") == "geist" else "kraft"] += 1
            progress["train_minutes"] += int(e.get("minutes") or 0)
        elif kind in ("fast_done", "fast_break"):
            progress["longest_fast"] = max(progress["longest_fast"], float(e.get("hours") or 0))
            if kind == "fast_done":
                progress["fasts"] += 1
                _fast_day(progress, e.get("day"))
        elif kind == "steps":
            progress["steps_total"] += max(0, int(e.get("new") or 0))
        elif kind == "steps_goal":
            progress["step_days"] += 1
            _step_day(progress, e["day"])
        elif kind == "cheer_sent":
            progress["cheers"] += 1
        elif kind in ("evolve", "formchange", "hatch"):
            if kind == "evolve":
                progress["evolutions"] += 1
            if e.get("jogress"):
                progress["jogress"] += 1
            new = e.get("new") or ""
            progress["best_rank"] = max(progress["best_rank"], STAGE_RANK.get(new[:1], 0))
        elif kind == "day":
            progress["streak"] = progress["streak"] + 1 if e.get("water_ok") else 0
            progress["best_streak"] = max(progress["best_streak"], progress["streak"])
        elif kind == "week" and e.get("perfect"):
            progress["perfect_weeks"] += 1
    fresh = []
    for key, title, text, field, goal in ACHIEVEMENTS:
        if key not in progress["unlocked"] and progress[field] >= goal:
            progress["unlocked"][key] = now
            fresh.append({"kind": "achievement", "text": f"Erfolg freigeschaltet: {title}", "key": key, "title": title})
    return fresh


def view(progress: dict, water_today: int, water_goal: int, today: str | None = None) -> dict:
    """Für die Anzeige: die laufende Serie zählt heute mit, sobald das Wasserziel erreicht ist."""
    _fill(progress)
    today_ok = water_today >= water_goal
    streak = progress["streak"] + (1 if today_ok else 0)
    items = []
    for key, title, text, field, goal in ACHIEVEMENTS:
        items.append({"key": key, "title": title, "text": text, "goal": goal,
                      "value": round(min(progress[field], goal), 1), "unlocked": progress["unlocked"].get(key)})
    # Fasten-Serie gilt, solange das letzte geschaffte Fasten heute oder gestern war
    fast_streak = 0
    if today and progress["last_fast_day"]:
        yesterday = (date.fromisoformat(today) - timedelta(days=1)).isoformat()
        if progress["last_fast_day"] in (today, yesterday):
            fast_streak = progress["fast_streak"]
    step_streak = 0
    if today and progress["last_step_day"]:
        yesterday = (date.fromisoformat(today) - timedelta(days=1)).isoformat()
        if progress["last_step_day"] in (today, yesterday):
            step_streak = progress["step_streak"]
    return {"streak": streak, "today_ok": today_ok, "best_streak": max(progress["best_streak"], streak),
            "glasses": progress["glasses"], "fasts": progress["fasts"], "evolutions": progress["evolutions"],
            "trainings": progress["trainings"], "train_minutes": progress["train_minutes"],
            "fast_streak": fast_streak, "best_fast_streak": progress["best_fast_streak"],
            "step_streak": step_streak, "steps_total": progress["steps_total"],
            "fast_today": progress["last_fast_day"] == today, "longest_fast": round(progress["longest_fast"], 1),
            "achievements": items, "unlocked": len(progress["unlocked"]), "total": len(ACHIEVEMENTS)}
