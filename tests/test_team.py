"""Tests fürs Team: Pausieren friert die Zeit ein, Wasser und Fasten wandern zum aktiven Partner.
Start: python -m unittest discover -s tests"""

import sys
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import game as G  # noqa: E402

TZ = ZoneInfo("Europe/Berlin")
H, D = G.HOUR, G.DAY


def at(y, mo, d, h=12) -> float:
    return datetime(y, mo, d, h, tzinfo=TZ).timestamp()


class TeamTest(unittest.TestCase):
    def setUp(self):
        self.t0 = at(2026, 11, 2, 9)
        self.a = G.new_pet(self.t0, line="agumon")
        G.tick(self.a, self.t0 + 600)  # geschlüpft

    def test_paused_partner_does_not_age_or_starve(self):
        G.tick(self.a, self.t0 + 2 * H)
        stats, stage_left = dict(self.a["stats"]), self.a["stage_since"]
        G.pause(self.a, self.t0 + 2 * H)
        later = self.t0 + 10 * D
        G.resume(self.a, later)
        logs = G.tick(self.a, later + 60)
        self.assertEqual(self.a["form"], "a001")  # keine Digitation in der Pause
        self.assertEqual(self.a["mistakes"], 0)
        self.assertAlmostEqual(self.a["stats"]["hunger"], stats["hunger"], delta=0.5)
        self.assertAlmostEqual(self.a["stage_since"] - stage_left, later - (self.t0 + 2 * H), delta=1)
        self.assertFalse([e for e in logs if e["kind"] in ("evolve", "mistake")])

    def test_water_and_fast_move_to_new_partner(self):
        now = self.t0 + 3 * H
        G.tick(self.a, now)
        G.drink(self.a, 5)
        G.start_fast(self.a, now)
        carry = G.pause(self.a, now)
        b = G.new_pet(now, line="gabumon")
        b.update(carry)
        self.assertEqual(b["water_today"], 5)
        self.assertEqual(b["fasting"]["start"], now)
        self.assertIsNone(self.a["fasting"])
        self.assertIsNone(self.a["today"])

    def test_resume_takes_over_today_without_day_event(self):
        now = self.t0 + 3 * H
        G.tick(self.a, now)
        G.pause(self.a, now)
        b = G.new_pet(now, line="gabumon")
        G.tick(b, now + 600)
        G.drink(b, 3)
        G.tick(b, now + 2 * D)  # wie in der App: vor dem Pausieren auf jetzt nachrechnen
        carry = G.pause(b, now + 2 * D)  # zwei Tage später zurück zu Agumon
        b_today = carry["today"]
        G.resume(self.a, now + 2 * D, carry)
        logs = G.tick(self.a, now + 2 * D + 600)
        self.assertEqual(self.a["today"], b_today)
        self.assertFalse([e for e in logs if e["kind"] == "day"])


if __name__ == "__main__":
    unittest.main()
