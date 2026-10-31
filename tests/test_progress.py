"""Tests für Serien und Erfolge. Start: python -m unittest discover -s tests"""

import sys
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import game as G  # noqa: E402
import progress as P  # noqa: E402

TZ = ZoneInfo("Europe/Berlin")


def at(y, mo, d, h=12, mi=0) -> float:
    return datetime(y, mo, d, h, mi, tzinfo=TZ).timestamp()


class ProgressTest(unittest.TestCase):
    def test_first_glass_unlocks_once(self):
        p = P.new_progress()
        fresh = P.apply(p, [{"kind": "water", "text": "", "glasses": 2}], 1.0)
        self.assertEqual([f["key"] for f in fresh], ["erstes_glas"])
        self.assertEqual(p["glasses"], 2)
        self.assertEqual(P.apply(p, [{"kind": "water", "text": "", "glasses": 1}], 2.0), [])

    def test_streak_breaks_and_best_stays(self):
        p = P.new_progress()
        days = [True, True, True, False, True]
        fresh = P.apply(p, [{"kind": "day", "text": "", "water_ok": ok} for ok in days], 1.0)
        self.assertIn("serie_3", [f["key"] for f in fresh])
        self.assertEqual((p["streak"], p["best_streak"]), (1, 3))

    def test_view_counts_today_when_goal_met(self):
        p = P.new_progress()
        P.apply(p, [{"kind": "day", "text": "", "water_ok": True}], 1.0)
        self.assertEqual(P.view(p, 3, 8)["streak"], 1)
        self.assertEqual(P.view(p, 8, 8)["streak"], 2)

    def test_stage_rank_from_evolution(self):
        p = P.new_progress()
        fresh = P.apply(p, [{"kind": "evolve", "text": "", "old": "c001", "new": "d001"}], 1.0)
        keys = [f["key"] for f in fresh]
        self.assertIn("digitation_1", keys)
        self.assertIn("champion", keys)
        self.assertNotIn("ultimate", keys)

    def test_game_emits_day_events(self):
        t0 = at(2026, 11, 2, 9)
        pet = G.new_pet(t0, line="agumon")
        G.tick(pet, t0 + 600)  # schlüpfen
        pet["stats"].update(hunger=100, thirst=100)
        logs = G.drink(pet, 8)
        logs += G.tick(pet, at(2026, 11, 3, 9))
        days = [e for e in logs if e["kind"] == "day"]
        self.assertEqual(len(days), 1)
        self.assertTrue(days[0]["water_ok"])
        p = P.new_progress()
        P.apply(p, logs, 1.0)
        self.assertEqual((p["glasses"], p["streak"]), (8, 1))

    def test_game_emits_week_event(self):
        t0 = at(2026, 11, 2, 9)
        pet = G.new_pet(t0, line="agumon")
        logs = G.tick(pet, t0 + 7 * G.DAY + 600)
        self.assertEqual(len([e for e in logs if e["kind"] == "week"]), 1)


if __name__ == "__main__":
    unittest.main()
