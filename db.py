"""SQLite-Speicher: Konten, Sitzungen, Einladungscodes, Partner (als JSON) und Tagebuch."""

from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
import time
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id       INTEGER PRIMARY KEY,
    name     TEXT NOT NULL UNIQUE COLLATE NOCASE,
    pw_hash  TEXT NOT NULL,
    is_admin INTEGER NOT NULL DEFAULT 0,
    settings TEXT NOT NULL DEFAULT '{}',
    created  REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id    INTEGER NOT NULL,
    expires    REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS invites (
    code       TEXT PRIMARY KEY,
    created_by INTEGER,
    used_by    INTEGER,
    created    REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS pets (
    id      INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    status  TEXT NOT NULL DEFAULT 'active',  -- active | hall (Ruhmeshalle)
    data    TEXT NOT NULL,
    created REAL NOT NULL,
    ended   REAL
);
CREATE INDEX IF NOT EXISTS pets_user ON pets(user_id, status);
CREATE TABLE IF NOT EXISTS diary (
    id      INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    pet_id  INTEGER,
    kind    TEXT NOT NULL,
    text    TEXT NOT NULL,
    data    TEXT NOT NULL DEFAULT '{}',
    at      REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS diary_user ON diary(user_id, at);
CREATE TABLE IF NOT EXISTS fasts (
    id      INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    start   REAL NOT NULL,
    end     REAL NOT NULL,
    goal    INTEGER NOT NULL,
    done    INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS fasts_user ON fasts(user_id, end);
CREATE TABLE IF NOT EXISTS cheers (
    from_id INTEGER NOT NULL,
    to_id   INTEGER NOT NULL,
    day     TEXT NOT NULL,
    PRIMARY KEY (from_id, to_id, day)
);
CREATE TABLE IF NOT EXISTS jogress (
    id      INTEGER PRIMARY KEY,
    from_id INTEGER NOT NULL,
    to_id   INTEGER NOT NULL,
    status  TEXT NOT NULL DEFAULT 'open',  -- open | done | declined | cancelled
    created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS synced (
    user_id  INTEGER NOT NULL,
    event_id TEXT NOT NULL,
    at       REAL NOT NULL,
    PRIMARY KEY (user_id, event_id)
);
CREATE TABLE IF NOT EXISTS steps (
    user_id INTEGER NOT NULL,
    day     TEXT NOT NULL,              -- Kalendertag, z. B. 2026-10-31
    steps   INTEGER NOT NULL,           -- höchster gemeldeter Stand des Tages
    at      REAL NOT NULL,              -- letzte Meldung
    PRIMARY KEY (user_id, day)
);
CREATE TABLE IF NOT EXISTS step_keys (
    key_hash TEXT PRIMARY KEY,          -- Schlüssel fürs iPhone (Kurzbefehl), nur als Hash gespeichert
    user_id  INTEGER NOT NULL UNIQUE,
    created  REAL NOT NULL,
    used     REAL
);
CREATE TABLE IF NOT EXISTS progress (
    user_id INTEGER PRIMARY KEY,
    data    TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS push_subs (
    endpoint TEXT PRIMARY KEY,          -- Adresse beim Push-Dienst (Apple/Google/Mozilla), je Gerät + Browser
    user_id  INTEGER NOT NULL,
    p256dh   TEXT NOT NULL,
    auth     TEXT NOT NULL,
    created  REAL NOT NULL,
    used     REAL                       -- letzte zugestellte Mitteilung
);
CREATE TABLE IF NOT EXISTS push_memo (
    user_id INTEGER PRIMARY KEY,
    data    TEXT NOT NULL               -- was schon gemeldet wurde (push.due)
);
"""


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class Store:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    # --- Konten ---------------------------------------------------------------------
    def user_count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]

    def add_user(self, name: str, pw_hash: str, is_admin: bool = False) -> int:
        with self.conn:
            cur = self.conn.execute("INSERT INTO users (name, pw_hash, is_admin, created) VALUES (?, ?, ?, ?)",
                                    (name, pw_hash, int(is_admin), time.time()))
        return cur.lastrowid

    def user_by_name(self, name: str) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM users WHERE name = ?", (name,)).fetchone()

    def user(self, user_id: int) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()

    def settings(self, user_id: int) -> dict:
        row = self.user(user_id)
        return json.loads(row["settings"]) if row else {}

    def save_settings(self, user_id: int, settings: dict) -> None:
        with self.conn:
            self.conn.execute("UPDATE users SET settings = ? WHERE id = ?", (json.dumps(settings), user_id))

    def users(self) -> list[dict]:
        return [dict(r) for r in self.conn.execute("SELECT id, name, settings FROM users ORDER BY name COLLATE NOCASE")]

    def set_password(self, user_id: int, pw_hash: str) -> None:
        with self.conn:
            self.conn.execute("UPDATE users SET pw_hash = ? WHERE id = ?", (pw_hash, user_id))

    # --- Sitzungen (nur der Hash des Tokens wird gespeichert) -------------------------
    def add_session(self, token: str, user_id: int, seconds: int) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM sessions WHERE expires < ?", (time.time(),))
            self.conn.execute("INSERT INTO sessions VALUES (?, ?, ?)", (_hash(token), user_id, time.time() + seconds))

    def session_user(self, token: str | None, seconds: int) -> int | None:
        if not token:
            return None
        with self.conn:
            row = self.conn.execute("SELECT user_id FROM sessions WHERE token_hash = ? AND expires > ?",
                                    (_hash(token), time.time())).fetchone()
            if row:
                self.conn.execute("UPDATE sessions SET expires = ? WHERE token_hash = ?",
                                  (time.time() + seconds, _hash(token)))
        return row["user_id"] if row else None

    def end_session(self, token: str | None) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM sessions WHERE token_hash = ?", (_hash(token or ""),))

    # --- Einladungscodes ----------------------------------------------------------------
    def new_invite(self, created_by: int) -> str:
        code = "-".join(secrets.token_hex(2).upper() for _ in range(3))
        with self.conn:
            self.conn.execute("INSERT INTO invites (code, created_by, created) VALUES (?, ?, ?)",
                              (code, created_by, time.time()))
        return code

    def invites(self) -> list[dict]:
        rows = self.conn.execute(
            "SELECT i.code, i.created, u.name AS used_by FROM invites i LEFT JOIN users u ON u.id = i.used_by "
            "ORDER BY i.created DESC").fetchall()
        return [dict(r) for r in rows]

    def use_invite(self, code: str, user_id: int) -> bool:
        with self.conn:
            cur = self.conn.execute("UPDATE invites SET used_by = ? WHERE code = ? AND used_by IS NULL",
                                    (user_id, code.strip().upper()))
        return cur.rowcount > 0

    def invite_open(self, code: str) -> bool:
        return self.conn.execute("SELECT 1 FROM invites WHERE code = ? AND used_by IS NULL",
                                 (code.strip().upper(),)).fetchone() is not None

    # --- Partner ----------------------------------------------------------------------
    def active_pet(self, user_id: int) -> tuple[int, dict] | None:
        row = self.conn.execute("SELECT id, data FROM pets WHERE user_id = ? AND status = 'active' ORDER BY id DESC",
                                (user_id,)).fetchone()
        return (row["id"], json.loads(row["data"])) if row else None

    def add_pet(self, user_id: int, pet: dict, status: str = "active") -> int:
        with self.conn:
            cur = self.conn.execute("INSERT INTO pets (user_id, status, data, created) VALUES (?, ?, ?, ?)",
                                    (user_id, status, json.dumps(pet), time.time()))
        return cur.lastrowid

    def save_pet(self, pet_id: int, pet: dict) -> None:
        with self.conn:
            self.conn.execute("UPDATE pets SET data = ? WHERE id = ?", (json.dumps(pet), pet_id))

    def team(self, user_id: int) -> list[tuple[int, str, dict]]:
        """Aktiver und pausierte Partner (id, status, daten), älteste zuerst."""
        rows = self.conn.execute("SELECT id, status, data FROM pets WHERE user_id = ? AND status IN ('active', 'paused') "
                                 "ORDER BY id", (user_id,)).fetchall()
        return [(r["id"], r["status"], json.loads(r["data"])) for r in rows]

    def set_pet_status(self, pet_id: int, status: str) -> None:
        with self.conn:
            self.conn.execute("UPDATE pets SET status = ? WHERE id = ?", (status, pet_id))

    def retire_pet(self, pet_id: int) -> None:
        with self.conn:
            self.conn.execute("UPDATE pets SET status = 'hall', ended = ? WHERE id = ?", (time.time(), pet_id))

    def hall(self, user_id: int) -> list[dict]:
        rows = self.conn.execute("SELECT id, data, created, ended FROM pets WHERE user_id = ? AND status = 'hall' "
                                 "ORDER BY ended DESC", (user_id,)).fetchall()
        return [{"id": r["id"], "pet": json.loads(r["data"]), "created": r["created"], "ended": r["ended"]} for r in rows]

    # --- Fortschritt (Serien, Erfolge) -----------------------------------------------------
    def progress(self, user_id: int) -> dict | None:
        row = self.conn.execute("SELECT data FROM progress WHERE user_id = ?", (user_id,)).fetchone()
        return json.loads(row["data"]) if row else None

    def save_progress(self, user_id: int, data: dict) -> None:
        with self.conn:
            self.conn.execute("INSERT INTO progress (user_id, data) VALUES (?, ?) "
                              "ON CONFLICT(user_id) DO UPDATE SET data = excluded.data", (user_id, json.dumps(data)))

    # --- Freunde: Anfeuern (einmal pro Tag und Freund) und Jogress-Anfragen -----------------
    def add_cheer(self, from_id: int, to_id: int, day: str) -> bool:
        with self.conn:
            cur = self.conn.execute("INSERT OR IGNORE INTO cheers (from_id, to_id, day) VALUES (?, ?, ?)", (from_id, to_id, day))
        return cur.rowcount > 0

    def cheered(self, from_id: int, day: str) -> set[int]:
        return {r[0] for r in self.conn.execute("SELECT to_id FROM cheers WHERE from_id = ? AND day = ?", (from_id, day))}

    def add_jogress(self, from_id: int, to_id: int) -> int:
        with self.conn:
            self.conn.execute("UPDATE jogress SET status = 'cancelled' WHERE status = 'open' AND from_id = ?", (from_id,))
            cur = self.conn.execute("INSERT INTO jogress (from_id, to_id, created) VALUES (?, ?, ?)", (from_id, to_id, time.time()))
        return cur.lastrowid

    def jogress_open(self, user_id: int) -> list[dict]:
        rows = self.conn.execute(
            "SELECT j.id, j.from_id, j.to_id, j.created, a.name AS from_name, b.name AS to_name FROM jogress j "
            "JOIN users a ON a.id = j.from_id JOIN users b ON b.id = j.to_id "
            "WHERE j.status = 'open' AND (j.from_id = ? OR j.to_id = ?) ORDER BY j.created DESC", (user_id, user_id)).fetchall()
        return [dict(r) for r in rows]

    def jogress_get(self, jid: int) -> dict | None:
        row = self.conn.execute("SELECT * FROM jogress WHERE id = ?", (jid,)).fetchone()
        return dict(row) if row else None

    def jogress_set(self, jid: int, status: str) -> None:
        with self.conn:
            self.conn.execute("UPDATE jogress SET status = ? WHERE id = ?", (status, jid))

    # --- Offline-Sync: jede Eintragung des Geräts zählt nur einmal ------------------------------
    def mark_synced(self, user_id: int, event_id: str) -> bool:
        """True, wenn die Eintragung neu ist (und jetzt als erledigt gilt)."""
        with self.conn:
            cur = self.conn.execute("INSERT OR IGNORE INTO synced (user_id, event_id, at) VALUES (?, ?, ?)",
                                    (user_id, event_id, time.time()))
        return cur.rowcount > 0

    # --- Fasten-Verlauf -------------------------------------------------------------------
    def add_fast(self, user_id: int, start: float, end: float, goal: int, done: bool) -> None:
        with self.conn:
            self.conn.execute("INSERT INTO fasts (user_id, start, end, goal, done) VALUES (?, ?, ?, ?, ?)",
                              (user_id, start, end, goal, int(done)))

    def fasts(self, user_id: int, since: float) -> list[dict]:
        rows = self.conn.execute("SELECT start, end, goal, done FROM fasts WHERE user_id = ? AND end >= ? ORDER BY end",
                                 (user_id, since)).fetchall()
        return [{"start": r["start"], "end": r["end"], "goal": r["goal"], "done": bool(r["done"])} for r in rows]

    # --- Schritte vom Handy -------------------------------------------------------------------
    def new_step_key(self, user_id: int) -> str:
        """Neuer Schlüssel; ein alter hört damit auf zu funktionieren."""
        key = "dp_" + secrets.token_urlsafe(24)
        with self.conn:
            self.conn.execute("DELETE FROM step_keys WHERE user_id = ?", (user_id,))
            self.conn.execute("INSERT INTO step_keys (key_hash, user_id, created) VALUES (?, ?, ?)",
                              (_hash(key), user_id, time.time()))
        return key

    def drop_step_key(self, user_id: int) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM step_keys WHERE user_id = ?", (user_id,))

    def step_key_user(self, key: str) -> int | None:
        row = self.conn.execute("SELECT user_id FROM step_keys WHERE key_hash = ?", (_hash(key),)).fetchone()
        if not row:
            return None
        with self.conn:
            self.conn.execute("UPDATE step_keys SET used = ? WHERE key_hash = ?", (time.time(), _hash(key)))
        return row["user_id"]

    def step_key_info(self, user_id: int) -> dict | None:
        row = self.conn.execute("SELECT created, used FROM step_keys WHERE user_id = ?", (user_id,)).fetchone()
        return {"created": row["created"], "used": row["used"]} if row else None

    def steps_of(self, user_id: int, day: str) -> int:
        row = self.conn.execute("SELECT steps FROM steps WHERE user_id = ? AND day = ?", (user_id, day)).fetchone()
        return row["steps"] if row else 0

    def set_steps(self, user_id: int, day: str, steps: int, at: float) -> None:
        """Pro Tag zählt der höchste Stand (der Kurzbefehl meldet mehrmals am Tag den bisherigen Stand)."""
        with self.conn:
            self.conn.execute("INSERT INTO steps (user_id, day, steps, at) VALUES (?, ?, ?, ?) "
                              "ON CONFLICT (user_id, day) DO UPDATE SET steps = MAX(steps, excluded.steps), at = excluded.at",
                              (user_id, day, steps, at))

    def steps_since(self, user_id: int, day: str) -> list[dict]:
        rows = self.conn.execute("SELECT day, steps, at FROM steps WHERE user_id = ? AND day >= ? ORDER BY day",
                                 (user_id, day)).fetchall()
        return [dict(r) for r in rows]

    # --- Benachrichtigungen (Web-Push) --------------------------------------------------------
    def add_push(self, user_id: int, endpoint: str, p256dh: str, auth: str) -> None:
        """Ein Gerät abonniert; meldet sich dasselbe Gerät mit einem anderen Konto an, gehört es danach diesem."""
        with self.conn:
            self.conn.execute("INSERT INTO push_subs (endpoint, user_id, p256dh, auth, created) VALUES (?, ?, ?, ?, ?) "
                              "ON CONFLICT (endpoint) DO UPDATE SET user_id = excluded.user_id, p256dh = excluded.p256dh, "
                              "auth = excluded.auth", (endpoint, user_id, p256dh, auth, time.time()))

    def drop_push(self, endpoint: str, user_id: int | None = None) -> None:
        with self.conn:
            if user_id is None:
                self.conn.execute("DELETE FROM push_subs WHERE endpoint = ?", (endpoint,))
            else:
                self.conn.execute("DELETE FROM push_subs WHERE endpoint = ? AND user_id = ?", (endpoint, user_id))

    def push_subs(self, user_id: int) -> list[dict]:
        rows = self.conn.execute("SELECT endpoint, p256dh, auth, created, used FROM push_subs WHERE user_id = ?",
                                 (user_id,)).fetchall()
        return [dict(r) for r in rows]

    def push_used(self, endpoint: str) -> None:
        with self.conn:
            self.conn.execute("UPDATE push_subs SET used = ? WHERE endpoint = ?", (time.time(), endpoint))

    def push_users(self) -> list[int]:
        return [r[0] for r in self.conn.execute("SELECT DISTINCT user_id FROM push_subs").fetchall()]

    def push_memo(self, user_id: int) -> dict:
        row = self.conn.execute("SELECT data FROM push_memo WHERE user_id = ?", (user_id,)).fetchone()
        return json.loads(row["data"]) if row else {}

    def save_push_memo(self, user_id: int, data: dict) -> None:
        with self.conn:
            self.conn.execute("INSERT INTO push_memo (user_id, data) VALUES (?, ?) "
                              "ON CONFLICT (user_id) DO UPDATE SET data = excluded.data", (user_id, json.dumps(data)))

    # --- Tagebuch -----------------------------------------------------------------------
    def log(self, user_id: int, pet_id: int | None, entries: list[dict], at: float) -> None:
        with self.conn:
            for e in entries:
                data = {k: v for k, v in e.items() if k not in ("kind", "text")}
                self.conn.execute("INSERT INTO diary (user_id, pet_id, kind, text, data, at) VALUES (?, ?, ?, ?, ?, ?)",
                                  (user_id, pet_id, e["kind"], e["text"], json.dumps(data), at))

    def diary_all(self, user_id: int) -> list[dict]:
        """Alle Einträge, älteste zuerst (zum Nachrechnen des Fortschritts für alte Konten)."""
        rows = self.conn.execute("SELECT kind, text, data FROM diary WHERE user_id = ? ORDER BY at, id",
                                 (user_id,)).fetchall()
        return [{**json.loads(r["data"]), "kind": r["kind"], "text": r["text"]} for r in rows]

    def diary(self, user_id: int, limit: int = 40) -> list[dict]:
        rows = self.conn.execute("SELECT kind, text, data, at FROM diary WHERE user_id = ? ORDER BY at DESC, id DESC "
                                 "LIMIT ?", (user_id, limit)).fetchall()
        return [{"kind": r["kind"], "text": r["text"], "data": json.loads(r["data"]), "at": r["at"]} for r in rows]
