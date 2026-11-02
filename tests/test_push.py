"""Benachrichtigungen: wann das Digimon sich meldet (push.due) und die Push-API. Start: python -m unittest discover -s tests"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

_tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
os.environ["DB_PATH"] = str(Path(_tmp.name) / "test.db")
os.environ["DEV"] = "1"
os.environ["PUSH_EVERY"] = "0"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aiohttp.test_utils import AioHTTPTestCase  # noqa: E402

import app as A  # noqa: E402
import push as P  # noqa: E402

H = 3600.0
APPLE = "https://web.push.apple.com/QGsomething-long-enough"
KEYS = {"p256dh": "B" + "x" * 86, "auth": "a" * 22}


def view(**kw):
    v = {"name": "Agumon", "form": "c001", "asleep": False, "fasting": None, "water_today": 2, "water_goal": 8,
         "stats": {"hunger": 80.0, "thirst": 80.0, "mood": 80.0}}
    stats = kw.pop("stats", {})
    v.update(kw)
    v["stats"] = {**v["stats"], **stats}
    return v


class DueTest(unittest.TestCase):
    def test_thirst_repeats_only_after_a_while_and_resets_when_fixed(self):
        out, memo = P.due(view(stats={"thirst": 30}), {}, 1000, [], 1)
        self.assertEqual([m["tag"] for m in out], ["thirst"])
        out, memo = P.due(view(stats={"thirst": 25}), memo, 1000 + H, [], 1)
        self.assertEqual(out, [])                                   # nicht gleich nochmal
        out, memo = P.due(view(stats={"thirst": 10}), memo, 1000 + 3 * H, [], 1)
        self.assertEqual([m["tag"] for m in out], ["thirst"])       # nach 3 Std. schon
        _, memo = P.due(view(), memo, 1000 + 4 * H, [], 1)           # getrunken
        out, _ = P.due(view(stats={"thirst": 30}), memo, 1000 + 4.5 * H, [], 1)
        self.assertEqual([m["tag"] for m in out], ["thirst"])       # neuer Durst: sofort

    def test_quiet_while_asleep_and_evolution_comes_in_the_morning(self):
        _, memo = P.due(view(), {}, 0, [], 1)
        out, memo = P.due(view(form="d001", name="Greymon", asleep=True, stats={"thirst": 0}), memo, H, [], 1)
        self.assertEqual(out, [])
        out, _ = P.due(view(form="d001", name="Greymon"), memo, 8 * H, [], 1)
        self.assertEqual([m["title"] for m in out], ["Digitation!"])
        self.assertIn("Greymon", out[0]["body"])

    def test_switching_partner_is_no_evolution(self):
        _, memo = P.due(view(), {}, 0, [], 1)
        out, _ = P.due(view(form="c002", name="Gabumon"), memo, H, [], 2)
        self.assertEqual(out, [])

    def test_hatching(self):
        _, memo = P.due(view(form="egg", name="Digi-Ei"), {}, 0, [], 1)
        out, _ = P.due(view(form="a001", name="Botamon"), memo, H, [], 1)
        self.assertEqual(out[0]["title"], "Dein Ei ist geschlüpft!")

    def test_fasting_hunger_is_no_alarm_but_goal_is_announced_once(self):
        fast = {"start": 100.0, "goal": 16, "hours": 16.2}
        out, memo = P.due(view(fasting=fast, stats={"hunger": 5}), {}, 1000, [], 1)
        self.assertEqual([m["tag"] for m in out], ["fast"])
        out, _ = P.due(view(fasting={**fast, "hours": 17}), memo, 1000 + H, [], 1)
        self.assertEqual(out, [])

    def test_jogress_request_once(self):
        out, memo = P.due(view(), {}, 0, [(7, "Mia")], 1)
        self.assertEqual(out[0]["title"], "Mia möchte Jogress!")
        out, _ = P.due(view(), memo, H, [(7, "Mia")], 1)
        self.assertEqual(out, [])

    def test_only_known_push_services(self):
        self.assertTrue(P.allowed_endpoint(APPLE))
        self.assertTrue(P.allowed_endpoint("https://fcm.googleapis.com/fcm/send/abc"))
        self.assertFalse(P.allowed_endpoint("https://evil.example/push.apple.com"))
        self.assertFalse(P.allowed_endpoint("http://web.push.apple.com/x"))
        self.assertFalse(P.allowed_endpoint("https://127.0.0.1/x"))


class PushApiTest(AioHTTPTestCase):
    async def get_application(self):
        A.config.DB_PATH = Path(_tmp.name) / f"push{id(self)}.db"
        A.config.PUSH_EVERY = 0
        return A.make_app()

    async def asyncSetUp(self):
        await super().asyncSetUp()
        r = await self.client.post("/api/register", json={"name": "Push Tester", "password": "geheim12345"})
        self.assertEqual(r.status, 200)
        self.sent = []

        async def fake_send(session, vapid, contact, sub, message):
            self.sent.append((sub["endpoint"], message))
            return sub["endpoint"] != APPLE + "-weg"

        self._orig, P.send = P.send, fake_send

    async def asyncTearDown(self):
        P.send = self._orig
        await super().asyncTearDown()

    async def test_manifest_without_login(self):
        r = await self.client.get("/manifest.webmanifest")
        self.assertEqual(r.status, 200)
        self.assertEqual(r.content_type, "application/manifest+json")
        self.assertEqual((await r.json())["display"], "standalone")

    async def test_subscribe_test_and_unsubscribe(self):
        info = await (await self.client.get("/api/push")).json()
        self.assertEqual(len(info["key"]), 87)                       # 65 Byte, base64url ohne "="
        r = await self.client.post("/api/push", json={"endpoint": APPLE, "keys": KEYS})
        self.assertEqual((await r.json())["devices"], 1)
        r = await self.client.post("/api/push/test", json={})
        self.assertEqual(r.status, 200)
        self.assertEqual(self.sent[0][0], APPLE)
        self.assertEqual(self.sent[0][1]["url"], "/")
        r = await self.client.delete("/api/push", json={"endpoint": APPLE})
        self.assertEqual((await r.json())["devices"], 0)

    async def test_gone_subscription_is_removed(self):
        await self.client.post("/api/push", json={"endpoint": APPLE + "-weg", "keys": KEYS})
        r = await self.client.post("/api/push/test", json={})
        self.assertEqual(r.status, 502)
        self.assertEqual((await (await self.client.get("/api/push")).json())["devices"], 0)

    async def test_rejects_foreign_endpoints_and_bad_keys(self):
        r = await self.client.post("/api/push", json={"endpoint": "https://example.com/x", "keys": KEYS})
        self.assertEqual(r.status, 400)
        r = await self.client.post("/api/push", json={"endpoint": APPLE, "keys": {"p256dh": "<script>", "auth": "x"}})
        self.assertEqual(r.status, 400)

    async def test_push_check_reports_thirst_after_time_passes(self):
        await self.client.post("/api/dev/skip", json={"hours": 1})   # Ei schlüpft
        await self.client.post("/api/push", json={"endpoint": APPLE, "keys": KEYS})
        s = self.app[A.store_key]
        uid = s.push_users()[0]
        self.assertEqual(A._push_check(s, uid), [])
        await self.client.post("/api/dev/skip", json={"hours": 6})   # wach, Werte sinken (Schlaf zählt nicht)
        tags = {m["tag"] for m in A._push_check(s, uid)}
        st = await (await self.client.get("/api/state")).json()
        thirsty = not st["pet"]["asleep"] and st["pet"]["stats"]["thirst"] < P.LOW
        self.assertEqual("thirst" in tags, thirsty)


if __name__ == "__main__":
    unittest.main()
