"""Tests der Spiel-Logik. Start: python -m unittest discover -s tests"""

import sys
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import game as G  # noqa: E402
import lines as L  # noqa: E402

TZ = ZoneInfo("Europe/Berlin")
H, D = G.HOUR, G.DAY


def at(y, mo, d, h=12, mi=0) -> float:
    return datetime(y, mo, d, h, mi, tzinfo=TZ).timestamp()


def fed(pet):
    pet["stats"].update(hunger=100, thirst=100)


def to_stage(pet, form, now):
    pet["form"], pet["stage_since"], pet["last_tick"] = form, now, now
    pet["period"] = G._period()


class NutritionTest(unittest.TestCase):
    def test_daily_reset_and_partner_switch(self):
        now = at(2026, 11, 2, 12)
        pet = G.new_pet(now)
        G.tick(pet, now + 1)
        G.drink(pet, ml=700)
        pet["calories_today"] = 650
        other = G.new_pet(now)
        G.resume(other, now + 1, G.pause(pet, now + 1))
        self.assertEqual(other["calories_today"], 650)
        self.assertAlmostEqual(other["water_today"], 2.8)
        G.tick(other, now + G.DAY)
        self.assertEqual(other["calories_today"], 0)
        self.assertEqual(other["water_today"], 0)


class GameTest(unittest.TestCase):
    def setUp(self):
        self.t0 = at(2026, 11, 2, 9)  # Montag 9 Uhr
        self.pet = G.new_pet(self.t0, line="agumon")

    def run_days(self, days, feed=True, train=None):
        """Tage vergehen lassen; jeden Tag füttern/tränken und optional trainieren."""
        t = self.pet["last_tick"]
        logs = []
        for _ in range(days * 4):
            t += 6 * H
            logs += G.tick(self.pet, t)
            if feed:
                fed(self.pet)
                G.drink(self.pet, 2)
            if train and _ % 4 == 0:
                logs += G.train(self.pet, train, 30)
        return logs

    def test_egg_hatches_into_line_start(self):
        logs = G.tick(self.pet, self.t0 + 10 * 60)
        self.assertEqual(self.pet["form"], "a001")
        self.assertEqual(logs[-1]["kind"], "hatch")

    def test_no_decay_while_asleep(self):
        to_stage(self.pet, "c001", at(2026, 11, 2, 23, 30))
        before = dict(self.pet["stats"])
        G.tick(self.pet, at(2026, 11, 3, 6, 30))
        self.assertAlmostEqual(self.pet["stats"]["hunger"], before["hunger"], places=3)

    def test_empty_thirst_makes_care_mistake(self):
        to_stage(self.pet, "c001", self.t0)
        self.pet["stats"]["thirst"] = 0
        logs = G.tick(self.pet, self.t0 + 3 * H)
        self.assertEqual(self.pet["mistakes"], 1)
        self.assertTrue(any(lg["kind"] == "mistake" for lg in logs))

    def test_fasting_hunger_is_no_mistake(self):
        to_stage(self.pet, "c001", self.t0)
        fed(self.pet)
        G.start_fast(self.pet, self.t0)
        self.pet["stats"]["hunger"] = 0
        G.tick(self.pet, self.t0 + 3 * H)
        self.pet["stats"]["thirst"] = 100
        self.assertEqual(self.pet["mistakes"], 0)

    def test_lazy_rookie_becomes_numemon(self):
        to_stage(self.pet, "c001", self.t0)
        self.run_days(8)
        self.assertEqual(self.pet["form"], "d059")
        self.assertEqual(self.pet["faul_origin"], "numemon")

    def test_kraft_rookie_becomes_greymon(self):
        to_stage(self.pet, "c001", self.t0)
        self.run_days(8, train="kraft")
        self.assertEqual(self.pet["form"], "d001")

    def test_geist_rookie_becomes_blue_greymon(self):
        to_stage(self.pet, "c001", self.t0)
        self.run_days(8, train="geist")
        self.assertEqual(self.pet["form"], "d053")

    def test_exveemon_waits_for_jogress_then_falls_back(self):
        self.pet = G.new_pet(self.t0, line="veemon")
        to_stage(self.pet, "d009", self.t0)
        self.run_days(15, train="kraft")
        self.assertEqual(self.pet["form"], "d009")
        self.assertTrue(self.pet["wait_since"])
        self.run_days(15, train="kraft")
        self.assertEqual(self.pet["form"], "e017")  # ohne Partner: AeroVeedramon

    def test_gallantmon_perfect_week_changes_form(self):
        self.pet = G.new_pet(self.t0, line="guilmon")
        to_stage(self.pet, "f014", self.t0)
        self.pet["week"] = G._week(self.t0)
        t = self.t0
        for day in range(8):
            for _ in range(4):
                t += 6 * H
                G.tick(self.pet, t)
                fed(self.pet)
                G.drink(self.pet, 3)
            if day < 3:
                G.train(self.pet, "kraft", 30)
            if day < 2:
                G.train(self.pet, "geist", 20)
        self.assertEqual(self.pet["form"], "g013")

    def test_fast_done_gives_discipline(self):
        to_stage(self.pet, "c001", self.t0)
        disc = self.pet["stats"]["disc"]
        G.start_fast(self.pet, self.t0)
        logs = G.stop_fast(self.pet, self.t0 + 17 * H)
        self.assertEqual(logs[0]["kind"], "fast_done")
        self.assertGreater(self.pet["stats"]["disc"], disc)

    def test_every_line_reaches_a_mega(self):
        """Jede Linie kommt mit Kraft- und mit Geist-Training bis zu einer Endstufe ohne Fehler."""
        for line in L.LINES:
            for kind in ("kraft", "geist"):
                self.pet = G.new_pet(self.t0, line=line)
                G.tick(self.pet, self.t0 + 600)
                self.run_days(70, train=kind)
                self.assertEqual(L.stage_of(self.pet["form"]), "mega", f"{line}/{kind}: {self.pet['form']}")

    def test_all_forms_have_names(self):
        for line in L.LINES.values():
            for src, rules in line["evo"].items():
                self.assertIn(src, L.NAMES)
                for _, dst in rules:
                    self.assertIn(dst, L.NAMES)


if __name__ == "__main__":
    unittest.main()
