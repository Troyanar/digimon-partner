"""Tests für Jogress und Freunde-Fortschritt. Start: python -m unittest discover -s tests"""

import sys
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import game as G  # noqa: E402
import lines as L  # noqa: E402
import progress as P  # noqa: E402

TZ = ZoneInfo("Europe/Berlin")
H = G.HOUR


def champion_waiting(line, form, now):
    """Partner, der als Champion fertig ist und auf seinen Jogress-Partner wartet."""
    pet = G.new_pet(now - 400 * H, line=line)
    pet.update(form=form, stage_since=now - 400 * H, last_tick=now - 400 * H)
    pet["period"].update(sessions=10, kraft_min=300)
    pet["stats"].update(hunger=100, thirst=100)
    G._maybe_evolve(pet, now)
    return pet


class JogressTest(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 20, 12, tzinfo=TZ).timestamp()

    def test_waiting_forms_can_jogress(self):
        ex = champion_waiting("veemon", "d009", self.now)
        self.assertTrue(G.can_jogress(ex))
        self.assertEqual(ex["form"], "d009")

    def test_preview_shows_paildramon(self):
        ex = champion_waiting("veemon", "d009", self.now)
        self.assertEqual(G.next_form(ex, preview=True), L.JOGRESS_TARGET)
        self.assertNotEqual(G.next_form(ex), L.JOGRESS_TARGET)  # ohne Partner: Ausweichweg

    def test_jogress_evolves_and_counts(self):
        ex = champion_waiting("veemon", "d009", self.now)
        logs = G.jogress(ex, self.now, "Marios Stingmon")
        self.assertEqual(ex["form"], "e009")
        self.assertFalse(G.can_jogress(ex))
        self.assertIn("Marios Stingmon", logs[0]["text"])
        p = P.new_progress()
        keys = [f["key"] for f in P.apply(p, logs, 1.0)]
        self.assertIn("jogress", keys)
        self.assertEqual(p["evolutions"], 1)

    def test_paildramon_continues_to_imperialdramon(self):
        st = champion_waiting("wormmon", "d011", self.now)
        G.jogress(st, self.now, "x")
        self.assertEqual(G.next_form(st, preview=True), "f057")

    def test_cheers_count(self):
        p = P.new_progress()
        keys = [f["key"] for f in P.apply(p, [{"kind": "cheer_sent", "text": ""}], 1.0)]
        self.assertIn("anfeuern_1", keys)


if __name__ == "__main__":
    unittest.main()
