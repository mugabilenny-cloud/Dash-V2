"""SQLite persistence: orders, vendor overrides (+ audit/undo), event log, customer profiles.

NOTE: on Streamlit Community Cloud the filesystem is ephemeral — data resets when the app
restarts. Swap this class for a Supabase/Postgres backend with the same methods for durability.
The app is designed to keep working (via WhatsApp) if every method here raises.
"""
from __future__ import annotations

import json
import sqlite3
import time
from contextlib import closing
from pathlib import Path

from . import orders as ol

SCHEMA = """
CREATE TABLE IF NOT EXISTS orders(
  code TEXT PRIMARY KEY, created_at REAL, vendor_id TEXT, name TEXT, phone TEXT, phone_norm TEXT,
  address TEXT, zone_id TEXT, zone_label TEXT, payment TEXT, scheduled_for TEXT, notes TEXT,
  lines TEXT, subtotal INT, fee INT, total INT, is_minimum INT, status TEXT, history TEXT,
  rider_name TEXT, rider_phone TEXT, rating INT, review TEXT);
CREATE INDEX IF NOT EXISTS ix_orders_vendor ON orders(vendor_id, created_at);
CREATE INDEX IF NOT EXISTS ix_orders_phone ON orders(phone_norm);
CREATE TABLE IF NOT EXISTS overrides(vendor_id TEXT, key TEXT, value TEXT, PRIMARY KEY(vendor_id,key));
CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, vendor_id TEXT,
  key TEXT, old TEXT, new TEXT, undone INT DEFAULT 0);
CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, kind TEXT,
  vendor_id TEXT, actor TEXT, payload TEXT);
CREATE INDEX IF NOT EXISTS ix_events ON events(kind, ts);
CREATE TABLE IF NOT EXISTS profiles(cart_id TEXT PRIMARY KEY, data TEXT, updated REAL);
"""
COLS = ["code", "created_at", "vendor_id", "name", "phone", "phone_norm", "address", "zone_id",
        "zone_label", "payment", "scheduled_for", "notes", "lines", "subtotal", "fee", "total",
        "is_minimum", "status", "history", "rider_name", "rider_phone", "rating", "review"]
JSON_COLS = ("lines", "history")


class Store:
    def __init__(self, path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with closing(self._conn()) as c:
            c.executescript(SCHEMA)

    def _conn(self):
        c = sqlite3.connect(self.path, timeout=10)
        c.row_factory = sqlite3.Row
        return c

    def _exec(self, sql, args=()):
        with closing(self._conn()) as c, c:
            return c.execute(sql, args).lastrowid

    def _all(self, sql, args=()):
        with closing(self._conn()) as c:
            return [dict(r) for r in c.execute(sql, args).fetchall()]

    @staticmethod
    def _order(row: dict | None):
        if not row:
            return None
        for k in JSON_COLS:
            row[k] = json.loads(row[k])
        row["is_minimum"] = bool(row["is_minimum"])
        return row

    # ---- orders
    def create_order(self, o: dict) -> dict:
        o = {**o, "status": "sent", "rider_name": "", "rider_phone": "", "rating": None, "review": "",
             "history": [{"s": "sent", "t": o["created_at"]}]}
        vals = [json.dumps(o[c]) if c in JSON_COLS else o[c] for c in COLS]
        self._exec(f"INSERT INTO orders({','.join(COLS)}) VALUES({','.join('?' * len(COLS))})", vals)
        return o

    def get_order(self, code: str):
        rows = self._all("SELECT * FROM orders WHERE code=?", (code,))
        return self._order(rows[0]) if rows else None

    def get_orders(self, codes: list[str]) -> list[dict]:
        if not codes:
            return []
        q = ",".join("?" * len(codes))
        return [self._order(r) for r in self._all(
            f"SELECT * FROM orders WHERE code IN ({q}) ORDER BY created_at DESC", tuple(codes))]

    def orders_for_phone(self, phone_norm: str) -> list[dict]:
        if not phone_norm:
            return []
        return [self._order(r) for r in self._all(
            "SELECT * FROM orders WHERE phone_norm=? ORDER BY created_at DESC LIMIT 50", (phone_norm,))]

    def orders_for_vendor(self, vendor_id: str, since: float = 0, statuses=None) -> list[dict]:
        rows = [self._order(r) for r in self._all(
            "SELECT * FROM orders WHERE vendor_id=? AND created_at>=? ORDER BY created_at DESC",
            (vendor_id, since))]
        return [r for r in rows if not statuses or r["status"] in statuses]

    def set_status(self, code: str, status: str, rider_name: str = "", rider_phone: str = "",
                   now: float | None = None) -> dict:
        o = self.get_order(code)
        if not o:
            raise KeyError(code)
        if status not in ol.allowed(o):
            raise ValueError(f"{o['status']} -> {status} not allowed")
        hist = o["history"] + [{"s": status, "t": now or time.time()}]
        self._exec("UPDATE orders SET status=?, history=?, rider_name=COALESCE(NULLIF(?,''),rider_name), "
                   "rider_phone=COALESCE(NULLIF(?,''),rider_phone) WHERE code=?",
                   (status, json.dumps(hist), rider_name, rider_phone, code))
        return self.get_order(code)

    def rate_order(self, code: str, rating: int, review: str = "") -> bool:
        o = self.get_order(code)
        if not o or o["status"] != "delivered" or o["rating"] is not None or not 1 <= rating <= 5:
            return False
        self._exec("UPDATE orders SET rating=?, review=? WHERE code=?", (rating, review[:300], code))
        return True

    def count_recent_orders(self, phone_norm: str, window_s: int = 3600) -> int:
        r = self._all("SELECT COUNT(*) n FROM orders WHERE phone_norm=? AND created_at>=?",
                      (phone_norm, time.time() - window_s))
        return r[0]["n"]

    def anonymize_orders(self, phone_norm: str) -> None:
        if phone_norm:
            self._exec("UPDATE orders SET name='(deleted)', phone='', phone_norm='', address='' "
                       "WHERE phone_norm=?", (phone_norm,))

    def vendor_stats(self, vendor_id: str) -> dict:
        rows = self._all("SELECT status, history, rating FROM orders WHERE vendor_id=?", (vendor_id,))
        delivered = sum(r["status"] == "delivered" for r in rows)
        rejected = sum(r["status"] == "rejected" for r in rows)
        waits, ratings = [], []
        for r in rows:
            h = {x["s"]: x["t"] for x in json.loads(r["history"])}
            if "accepted" in h and "sent" in h:
                waits.append((h["accepted"] - h["sent"]) / 60)
            if r["rating"]:
                ratings.append(r["rating"])
        den = delivered + rejected
        return {"total": len(rows), "delivered": delivered, "rejected": rejected,
                "completion": delivered / den if den else None,
                "avg_accept_min": sum(waits) / len(waits) if waits else None,
                "rating_avg": sum(ratings) / len(ratings) if ratings else None,
                "rating_n": len(ratings)}

    # ---- overrides + audit
    def get_overrides(self, vendor_id: str) -> dict:
        return {r["key"]: json.loads(r["value"])
                for r in self._all("SELECT key,value FROM overrides WHERE vendor_id=?", (vendor_id,))}

    def set_override(self, vendor_id: str, key: str, value) -> None:
        old = self.get_overrides(vendor_id).get(key)
        if old == value:
            return
        self._write_override(vendor_id, key, value)
        self._exec("INSERT INTO audit(ts,vendor_id,key,old,new) VALUES(?,?,?,?,?)",
                   (time.time(), vendor_id, key, json.dumps(old), json.dumps(value)))

    def _write_override(self, vendor_id, key, value):
        if value is None:
            self._exec("DELETE FROM overrides WHERE vendor_id=? AND key=?", (vendor_id, key))
        else:
            self._exec("INSERT OR REPLACE INTO overrides(vendor_id,key,value) VALUES(?,?,?)",
                       (vendor_id, key, json.dumps(value)))

    def audit_list(self, vendor_id: str, limit: int = 15) -> list[dict]:
        return self._all("SELECT * FROM audit WHERE vendor_id=? ORDER BY id DESC LIMIT ?", (vendor_id, limit))

    def undo_last(self, vendor_id: str):
        rows = self._all("SELECT * FROM audit WHERE vendor_id=? AND undone=0 ORDER BY id DESC LIMIT 1",
                         (vendor_id,))
        if not rows:
            return None
        r = rows[0]
        self._write_override(vendor_id, r["key"], json.loads(r["old"]))
        self._exec("UPDATE audit SET undone=1 WHERE id=?", (r["id"],))
        return r

    # ---- events
    def log_event(self, kind: str, vendor_id: str | None = None, actor: str | None = None,
                  payload: dict | None = None) -> None:
        self._exec("INSERT INTO events(ts,kind,vendor_id,actor,payload) VALUES(?,?,?,?,?)",
                   (time.time(), kind, vendor_id, actor, json.dumps(payload or {})))

    def events(self, kind: str, vendor_id: str | None = None, since: float = 0) -> list[dict]:
        rows = self._all("SELECT * FROM events WHERE kind=? AND ts>=? ORDER BY id DESC", (kind, since))
        rows = [r for r in rows if vendor_id is None or r["vendor_id"] == vendor_id]
        for r in rows:
            r["payload"] = json.loads(r["payload"])
        return rows

    def count_events(self, kind: str, actor: str, window_s: int = 3600) -> int:
        r = self._all("SELECT COUNT(*) n FROM events WHERE kind=? AND actor=? AND ts>=?",
                      (kind, actor, time.time() - window_s))
        return r[0]["n"]

    # ---- profiles (cart + saved details keyed by private cart id)
    def save_profile(self, cart_id: str, blob: dict) -> None:
        self._exec("INSERT OR REPLACE INTO profiles(cart_id,data,updated) VALUES(?,?,?)",
                   (cart_id, json.dumps(blob), time.time()))

    def load_profile(self, cart_id: str):
        r = self._all("SELECT data FROM profiles WHERE cart_id=?", (cart_id,))
        return json.loads(r[0]["data"]) if r else None

    def delete_profile(self, cart_id: str) -> None:
        self._exec("DELETE FROM profiles WHERE cart_id=?", (cart_id,))
