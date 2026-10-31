"""Tests für Fasten: rückwirkender Start, Verlaufsdaten, Fasten-Serie. Start: python -m unittest discover -s tests"""

import sys
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import game as G  # noqa: E402
import progress as P  # noqa: E402

TZ = ZoneInfo("Europe/Berlin")
H = G.HOUR


def at(y, mo, d, h=12, mi=0) -> float:
    return datetime(y, mo, d, h, mi, tzinfo=TZ).timestamp()


class FastingTest(unittest.TestCase):
    def setUp(self):
        self.t0 = at(2026, 11, 2, 9)
        self.pet = G.new_pet(self.t0, line="agumon")
        G.tick(self.pet, self.t0 + 600)

    def test_backdated_start_is_clamped(self):
        now = at(2026, 11, 2, 22)
        G.start_fast(self.pet, now, start=now - 30 * H)
        self.assertEqual(self.pet["fasting"]["start"], now - 12 * H)

    def test_stop_reports_history_data(self):
        start = at(2026, 11, 2, 20)
        G.start_fast(self.pet, start)
        logs = G.stop_fast(self.pet, start + 16.5 * H)
        e = logs[0]
        self.assertEqual(e["kind"], "fast_done")
        self.assertEqual((e["day"], e["goal"], e["hours"]), ("2026-11-03", 16, 16.5))

    def test_fast_streak_counts_days_and_breaks(self):
        p = P.new_progress()
        days = ["2026-11-01", "2026-11-02", "2026-11-02", "2026-11-03", "2026-11-05"]
        fresh = P.apply(p, [{"kind": "fast_done", "text": "", "day": d, "hours": 16} for d in days], 1.0)
        self.assertIn("fasten_serie_3", [f["key"] for f in fresh])
        self.assertEqual((p["fast_streak"], p["best_fast_streak"], p["fasts"]), (1, 3, 5))

    def test_streak_view_expires_after_missed_day(self):
        p = P.new_progress()
        P.apply(p, [{"kind": "fast_done", "text": "", "day": "2026-11-02", "hours": 16}], 1.0)
        self.assertEqual(P.view(p, 0, 8, "2026-11-03")["fast_streak"], 1)
        self.assertEqual(P.view(p, 0, 8, "2026-11-04")["fast_streak"], 0)

    def test_long_broken_fast_counts_for_longest(self):
        p = P.new_progress()
        fresh = P.apply(p, [{"kind": "fast_break", "text": "", "hours": 21.0}], 1.0)
        self.assertIn("fasten_20", [f["key"] for f in fresh])
        self.assertEqual(p["fasts"], 0)


if __name__ == "__main__":
    unittest.main()
