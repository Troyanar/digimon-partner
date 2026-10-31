"""Offline-Sync gegen den echten Server (eigene Test-Datenbank). Start: python -m unittest discover -s tests"""

import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

_tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
os.environ["DB_PATH"] = str(Path(_tmp.name) / "test.db")
_count = 0
os.environ["DEV"] = "1"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aiohttp.test_utils import AioHTTPTestCase  # noqa: E402

import app as A  # noqa: E402
import training as T  # noqa: E402


async def _noop():
    return None


class SyncTest(AioHTTPTestCase):
    async def get_application(self):
        # jeder Test mit eigener, leerer Datenbank (das erste Konto braucht keinen Einladungscode)
        global _count
        _count += 1
        A.config.DB_PATH = Path(_tmp.name) / f"test{_count}.db"
        app = A.make_app()
        app.on_cleanup.append(lambda a: a[A.store_key].conn.close() or _noop())
        return app

    async def asyncSetUp(self):
        await super().asyncSetUp()
        r = await self.client.post("/api/register", json={"name": "Sync Tester", "password": "geheim12345"})
        self.assertEqual(r.status, 200)
        await self.client.post("/api/dev/skip", json={"hours": 1})   # Ei schlüpft
        st = await (await self.client.get("/api/state")).json()
        self.assertNotEqual(st["pet"]["form"], "egg")
        self.now = st["now"]

    async def sync(self, events):
        r = await self.client.post("/api/sync", json={"events": events})
        self.assertEqual(r.status, 200)
        return await r.json()

    async def test_events_count_once_at_their_own_time(self):
        ev = [{"id": "wasser-0001", "kind": "water", "at": self.now + 5, "data": {"glasses": 2}},
              {"id": "essen-00001", "kind": "eat", "at": self.now + 2, "data": {}}]
        st = await self.sync(ev)
        self.assertEqual(sorted(st["synced"]), ["essen-00001", "wasser-0001"])
        self.assertEqual(st["pet"]["water_today"], 2)
        texts = [e["text"] for e in st["diary"] if e["kind"] != "achievement"][:2]
        self.assertEqual(texts, ["2 Gläser Wasser.", "Etwas gegessen."])   # neueste zuerst, Reihenfolge nach Uhrzeit
        again = await self.sync(ev)                                          # nochmal geschickt: zählt nicht doppelt
        self.assertEqual(again["pet"]["water_today"], 2)

    async def test_offline_fast_with_real_times(self):
        st = await self.sync([{"id": "fast-start-1", "kind": "fast_start", "at": self.now + 1, "data": {"minutes_ago": 0}}])
        self.assertIsNotNone(st["pet"]["fasting"])
        await self.client.post("/api/dev/skip", json={"hours": 17})
        st = await self.sync([{"id": "fast-stop-01", "kind": "fast_stop", "at": self.now + 16.5 * 3600, "data": {}}])
        self.assertIsNone(st["pet"]["fasting"])
        self.assertEqual(len(st["fasts"]), 1)
        self.assertTrue(st["fasts"][0]["done"])
        self.assertAlmostEqual(st["fasts"][0]["end"] - st["fasts"][0]["start"], 16.5 * 3600 - 1, delta=2)

    async def test_offline_training_needs_real_time(self):
        total = T.total_seconds("kurz")
        await self.client.post("/api/dev/skip", json={"hours": 1})
        st = await self.sync([{"id": "train-zuschnell", "kind": "train", "at": self.now + 3000, "data": {"plan": "kurz", "start": self.now + 2990}}])
        self.assertEqual(st["rejected"][0]["id"], "train-zuschnell")
        st = await self.sync([{"id": "train-richtig1", "kind": "train", "at": self.now + 3000,
                               "data": {"plan": "kurz", "start": self.now + 3000 - total}}])
        self.assertEqual(st["rejected"], [])
        self.assertEqual(st["pet"]["week"]["kraft"], 1)

    async def test_event_in_the_future_is_clamped(self):
        st = await self.sync([{"id": "zukunft-0001", "kind": "water", "at": time.time() + 10 * 86400, "data": {}}])
        self.assertLessEqual(st["diary"][0]["at"], st["now"] + 1)


if __name__ == "__main__":
    unittest.main()
