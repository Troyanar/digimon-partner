"""Trainingspläne: Heimtraining ohne Geräte ("kraft") und Dehnen/Yoga ("geist").

Jeder Plan ist eine feste Folge von Übungen mit Dauer in Sekunden; dazwischen kurze Pausen.
Die Seite führt Übung für Übung mit Timer durch. Gutgeschrieben wird erst am Ende – und nur, wenn
seit dem Start mindestens die Hälfte der Plan-Zeit wirklich vergangen ist (Überspringen ist erlaubt,
Durchklicken zählt nicht).
"""

from __future__ import annotations

EXERCISES = {
    # Kraft
    "hampelmann": ("Hampelmann", "Arme und Beine gleichzeitig öffnen und schließen, locker federn."),
    "kniebeugen": ("Kniebeugen", "Füße hüftbreit, Po nach hinten absenken, Knie über den Füßen, Rücken gerade."),
    "liegestuetze": ("Liegestütze", "Hände unter den Schultern, Körper gerade, Brust zum Boden. Auf den Knien ist auch gut."),
    "plank": ("Unterarmstütz", "Auf Unterarmen und Zehen, der Körper bildet eine Linie, Bauch fest."),
    "ausfallschritte": ("Ausfallschritte", "Großer Schritt nach vorn, hinteres Knie Richtung Boden, Beine abwechseln."),
    "bruecke": ("Brücke", "Rückenlage, Füße aufgestellt, Becken hochheben und kurz halten."),
    "bergsteiger": ("Bergsteiger", "In der Liegestützposition die Knie abwechselnd zügig zur Brust ziehen."),
    "crunches": ("Crunches", "Rückenlage, Knie angewinkelt, Schultern leicht anheben, Blick zur Decke."),
    "superman": ("Superman", "Bauchlage, Arme und Beine gleichzeitig leicht anheben und kurz halten."),
    "seitstuetz": ("Seitstütz", "Seitlich auf einen Unterarm stützen, Becken hoch. Zur Halbzeit die Seite wechseln."),
    "wandsitzen": ("Wandsitzen", "Rücken an die Wand, Knie im rechten Winkel, so halten."),
    # Geist
    "nacken": ("Nacken lockern", "Kopf langsam zu einer Schulter neigen, kurz halten, dann zur anderen."),
    "schulterkreisen": ("Schulterkreisen", "Schultern groß nach hinten kreisen, ruhig atmen."),
    "katze_kuh": ("Katze-Kuh", "Vierfüßlerstand. Im Wechsel den Rücken rund machen und sanft durchhängen lassen."),
    "hund": ("Herabschauender Hund", "Hände und Füße am Boden, Po nach oben, Fersen Richtung Boden."),
    "kind": ("Kindhaltung", "Auf die Fersen setzen, Oberkörper nach vorn ablegen, Arme lang."),
    "krieger": ("Krieger", "Großer Ausfallschritt, Arme nach oben, Blick nach vorn. Zur Halbzeit die Seite wechseln."),
    "vorbeuge": ("Vorbeuge", "Nach vorn beugen, Rücken lang, Knie leicht gebeugt, Kopf hängen lassen."),
    "huefte": ("Hüftöffner", "Tiefer Ausfallschritt, hinteres Knie ab, Becken sanft nach vorn. Zur Halbzeit wechseln."),
    "drehsitz": ("Drehsitz", "Im Sitzen ein Bein überschlagen, Oberkörper zur Seite drehen. Zur Halbzeit wechseln."),
    "kobra": ("Kobra", "Bauchlage, Hände neben der Brust, Oberkörper sanft aufrichten."),
    "schmetterling": ("Schmetterling", "Im Sitzen die Fußsohlen zusammen, Knie locker sinken lassen."),
    "baum": ("Baum", "Auf einem Bein stehen, anderer Fuß an Wade oder Oberschenkel. Zur Halbzeit wechseln."),
    "atmung": ("Ruhig atmen", "Bequem sitzen oder liegen. Vier Sekunden ein, sechs Sekunden aus."),
}

# id: (Titel, Art, Beschreibung, Pause zwischen den Übungen in Sekunden, [(Übung, Sekunden), ...])
PLANS = {
    "kurz": ("Kurz & knackig", "kraft", "Zehn Übungen, je 40 Sekunden. Bringt den Puls schnell hoch.", 20,
             [("hampelmann", 40), ("kniebeugen", 40), ("liegestuetze", 40), ("plank", 40), ("ausfallschritte", 40),
              ("bergsteiger", 40), ("kniebeugen", 40), ("plank", 40), ("hampelmann", 40), ("bruecke", 40)]),
    "ganzkoerper": ("Ganzkörper", "kraft", "Zwei Runden mit zehn Übungen für Beine, Arme, Bauch und Rücken.", 15,
                    [(e, 45) for e in ["hampelmann", "kniebeugen", "liegestuetze", "ausfallschritte", "bergsteiger",
                                       "plank", "bruecke", "wandsitzen", "superman", "seitstuetz"]] * 2),
    "bauch_ruecken": ("Bauch & Rücken", "kraft", "Drei Runden Rumpf: Crunches, Stütz, Superman, Brücke.", 15,
                      [(e, 45) for e in ["crunches", "plank", "superman", "seitstuetz", "bruecke"]] * 3),
    "morgen": ("Morgen-Dehnen", "geist", "Sanft wach werden: Nacken, Schultern, Rücken, Gleichgewicht.", 5,
               [("nacken", 60), ("schulterkreisen", 60), ("katze_kuh", 90), ("hund", 60), ("krieger", 90),
                ("vorbeuge", 60), ("baum", 60), ("atmung", 60)]),
    "flow": ("Yoga-Flow", "geist", "Ein ruhiger Ablauf vom Hund über den Krieger bis zur Kindhaltung.", 5,
             [("atmung", 60), ("katze_kuh", 90), ("hund", 90), ("kobra", 60), ("hund", 60), ("krieger", 120),
              ("huefte", 120), ("baum", 120), ("vorbeuge", 90), ("drehsitz", 120), ("schmetterling", 90),
              ("kind", 90), ("atmung", 90)]),
    "abend": ("Abend-Entspannung", "geist", "Runterkommen nach dem Tag: Hüfte, Rücken, langsames Atmen.", 5,
              [("schulterkreisen", 60), ("nacken", 60), ("katze_kuh", 90), ("kind", 120), ("huefte", 120),
               ("drehsitz", 120), ("schmetterling", 120), ("vorbeuge", 90), ("kind", 60), ("atmung", 120)]),
}

MIN_SHARE = 0.5  # so viel der Plan-Zeit muss seit dem Start vergangen sein


def total_seconds(plan_id: str) -> int:
    _, _, _, rest, steps = PLANS[plan_id]
    return sum(s for _, s in steps) + rest * (len(steps) - 1)


def plan_list() -> list[dict]:
    out = []
    for pid, (title, art, text, rest, steps) in PLANS.items():
        out.append({
            "id": pid, "title": title, "art": art, "text": text, "rest": rest,
            "minutes": round(total_seconds(pid) / 60),
            "steps": [{"key": k, "name": EXERCISES[k][0], "text": EXERCISES[k][1], "seconds": s} for k, s in steps],
        })
    return out


def credit_minutes(plan_id: str, elapsed: float) -> int | None:
    """Minuten, die gutgeschrieben werden – oder None, wenn zu wenig Zeit vergangen ist."""
    total = total_seconds(plan_id)
    if elapsed < total * MIN_SHARE:
        return None
    return max(1, round(min(elapsed, total) / 60))
