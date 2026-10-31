"""Schritte vom iPhone (Kurzbefehl / Health Auto Export) gegen den echten Server. Start: python -m unittest discover -s tests"""

import os
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

_tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
os.environ["DB_PATH"] = str(Path(_tmp.name) / "test.db")
_count = 0
os.environ["DEV"] = "1"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aiohttp.test_utils import AioHTTPTestCase  # noqa: E402

import app as A  # noqa: E402
import game  # noqa: E402
import progress as P  # noqa: E402


async def _noop():
    return None


class CountTest(unittest.TestCase):
    def test_numbers_and_text(self):
        self.assertEqual(A._count(5432), 5432)
        self.assertEqual(A._count(5432.7), 5432)
        self.assertEqual(A._count("5432"), 5432)
        self.assertEqual(A._count("5.432"), 5432)      # deutscher Tausenderpunkt
        self.assertEqual(A._count("5432,0"), 5432)
        self.assertEqual(A._count("5432.0"), 5432)
        self.assertEqual(A._count(10 ** 9), A.MAX_STEPS)
        for bad in (None, True, "viel", -5, float("nan"), [1]):
            self.assertIsNone(A._count(bad))

    def test_formats(self):
        today = "2026-10-31"
        self.assertEqual(A._step_reports({"heute": 100, "gestern": "9.000"}, today),
                         {"2026-10-31": 100, "2026-10-30": 9000})
        hae = {"data": {"metrics": [{"name": "step_count", "units": "count", "data": [
            {"date": "2026-10-31 00:00:00 +0100", "qty": 300}, {"date": "2026-10-31 01:00:00 +0100", "qty": 200},
            {"date": "2026-10-01 00:00:00 +0100", "qty": 999}]},       # zu alt: zählt nicht
            {"name": "heart_rate", "data": [{"date": "2026-10-31", "qty": 70}]}]}}
        self.assertEqual(A._step_reports(hae, today), {"2026-10-31": 500})

    def test_walk_and_streak(self):
        pet = game.new_pet(0)
        pet["form"] = "c001"
        logs = game.walk(pet, "2026-10-30", 0, 9000, 8000)
        self.assertEqual([e["kind"] for e in logs], ["steps", "steps_goal"])
        self.assertAlmostEqual(pet["stats"]["power"], 13.5)
        self.assertEqual(pet["period"]["sessions"], 1)
        self.assertEqual(game.walk(pet, "2026-10-30", 9000, 9500, 8000)[-1]["kind"], "steps")  # Ziel nur einmal
        pr = P.new_progress()
        P.apply(pr, logs, 0)
        P.apply(pr, game.walk(pet, "2026-10-31", 0, 8000, 8000), 0)
        self.assertEqual((pr["step_streak"], pr["steps_total"]), (2, 17000))
        self.assertIn("schritte_ziel", pr["unlocked"])


class StepsTest(AioHTTPTestCase):
    async def get_application(self):
        global _count
        _count += 1
        A.config.DB_PATH = Path(_tmp.name) / f"steps{_count}.db"
        app = A.make_app()
        app.on_cleanup.append(lambda a: a[A.store_key].conn.close() or _noop())
        return app

    async def asyncSetUp(self):
        await super().asyncSetUp()
        r = await self.client.post("/api/register", json={"name": "Geher", "password": "geheim12345"})
        self.assertEqual(r.status, 200)
        await self.client.post("/api/dev/skip", json={"hours": 1})   # Ei schlüpft
        self.key = (await (await self.client.post("/api/steps/key", json={})).json())["key"]

    async def state(self):
        return await (await self.client.get("/api/state")).json()

    async def test_shortcut_report_without_login(self):
        before = (await self.state())["pet"]["stats"]["power"]
        self.client.session.cookie_jar.clear()                       # der Kurzbefehl hat kein Anmelde-Cookie
        r = await self.client.post("/api/steps", json={"key": self.key, "heute": 4000})
        self.assertEqual(r.status, 200)
        self.assertEqual((await r.json())["heute"], 4000)
        r = await self.client.post("/api/steps", json={"key": self.key, "heute": 3000})   # älterer Stand: bleibt 4000
        self.assertEqual((await r.json())["heute"], 4000)
        r = await self.client.post("/api/steps", json={"key": "dp_falsch", "heute": 1})
        self.assertEqual(r.status, 401)
        await self.client.post("/api/login", json={"name": "Geher", "password": "geheim12345"})
        st = await self.state()
        self.assertEqual(st["steps"]["today"], 4000)
        self.assertIsNotNone(st["steps"]["key"]["used"])
        self.assertGreater(st["pet"]["stats"]["power"], before)

    async def test_goal_goes_to_diary_once(self):
        for n in (8500, 9000):
            await self.client.post("/api/steps", json={"key": self.key, "heute": n})
        st = await self.state()
        goals = [e for e in st["diary"] if e["kind"] == "steps_goal"]
        self.assertEqual(len(goals), 1)
        self.assertFalse(any(e["kind"] == "steps" for e in st["diary"]))   # die einzelnen Meldungen nicht
        self.assertIn("schritte_ziel", [a["key"] for a in st["progress"]["achievements"] if a["unlocked"]])

    async def test_bearer_header_and_new_key(self):
        r = await self.client.post("/api/steps", json={"heute": 100}, headers={"Authorization": f"Bearer {self.key}"})
        self.assertEqual(r.status, 200)
        await self.client.post("/api/steps/key", json={})              # neuer Schlüssel: der alte gilt nicht mehr
        r = await self.client.post("/api/steps", json={"key": self.key, "heute": 200})
        self.assertEqual(r.status, 401)

    async def test_yesterday(self):
        await self.client.post("/api/steps", json={"key": self.key, "heute": 10, "gestern": 9000})
        st = await self.state()
        today = date.fromisoformat(game.local_day(st["now"]))
        days = {d["day"]: d["steps"] for d in st["steps"]["days"]}
        self.assertEqual(days[(today - timedelta(days=1)).isoformat()], 9000)


if __name__ == "__main__":
    unittest.main()
