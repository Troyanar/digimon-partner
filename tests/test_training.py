"""Tests für Trainingspläne und Gutschrift. Start: python -m unittest discover -s tests"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import progress as P  # noqa: E402
import training as T  # noqa: E402


class TrainingTest(unittest.TestCase):
    def test_plans_use_known_exercises(self):
        for plan in T.plan_list():
            self.assertIn(plan["art"], ("kraft", "geist"))
            self.assertTrue(plan["steps"])
            for step in plan["steps"]:
                self.assertIn(step["key"], T.EXERCISES)

    def test_too_fast_gives_nothing(self):
        total = T.total_seconds("kurz")
        self.assertIsNone(T.credit_minutes("kurz", total * 0.3))

    def test_credit_is_capped_at_plan_length(self):
        total = T.total_seconds("kurz")
        self.assertEqual(T.credit_minutes("kurz", total * 3), round(total / 60))
        self.assertEqual(T.credit_minutes("kurz", total * 0.6), round(total * 0.6 / 60))

    def test_progress_counts_training(self):
        p = P.new_progress()
        fresh = P.apply(p, [{"kind": "train", "text": "", "art": "geist", "minutes": 10}], 1.0)
        self.assertIn("erstes_training", [f["key"] for f in fresh])
        self.assertEqual((p["trainings"], p["geist"], p["kraft"], p["train_minutes"]), (1, 1, 0, 10))

    def test_old_progress_gets_new_fields(self):
        old = P.new_progress()
        for key in ("trainings", "kraft", "geist", "train_minutes"):
            del old[key]
        P.apply(old, [{"kind": "train", "text": "", "art": "kraft", "minutes": 20}], 1.0)
        self.assertEqual(old["kraft"], 1)


if __name__ == "__main__":
    unittest.main()
