"""Catalog access. Menu content lives in data/vendors.json; vendor overrides (price, stock,
hours, fees, pause) are applied on top via the `ov` dict stored by core.store."""
from __future__ import annotations

import json
from datetime import datetime
from functools import lru_cache
from pathlib import Path

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "vendors.json"
DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


@lru_cache(maxsize=1)
def _load() -> dict:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def currency() -> str:
    return _load()["currency"]


def vendors() -> list[dict]:
    return _load()["vendors"]


def areas() -> list[str]:
    return _load().get("areas", [])


def banners() -> list[str]:
    return _load().get("banners", [])


def get_vendor(vendor_id: str) -> dict:
    for v in vendors():
        if v["id"] == vendor_id:
            return v
    raise KeyError(vendor_id)


def get_item(vendor: dict, item_id: str) -> dict:
    for cat in vendor["categories"]:
        for it in cat["items"]:
            if it["id"] == item_id:
                return it
    raise KeyError(item_id)


def get_option(item: dict, option_id: str) -> dict:
    for op in item["options"]:
        if op["id"] == option_id:
            return op
    raise KeyError(option_id)


def get_zone(vendor: dict, zone_id: str) -> dict:
    for z in vendor["delivery_zones"]:
        if z["id"] == zone_id:
            return z
    raise KeyError(zone_id)


# ---- overrides-aware helpers -------------------------------------------------
def effective_price(item: dict, option: dict, ov: dict | None) -> int:
    return int((ov or {}).get("price", {}).get(f"{item['id']}|{option['id']}", option["price"]))


def is_available(item: dict, ov: dict | None) -> bool:
    return item["id"] not in (ov or {}).get("unavailable", [])


def zone_fee(zone: dict, ov: dict | None):
    fees = (ov or {}).get("zone_fee", {})
    return fees[zone["id"]] if zone["id"] in fees else zone["fee"]


def min_price(item: dict, ov: dict | None) -> int:
    return min(effective_price(item, o, ov) for o in item["options"])


def default_zone(vendor: dict, area: str | None) -> str:
    if area and area in vendor.get("walkable_areas", []):
        return vendor.get("walkable_zone", vendor["delivery_zones"][0]["id"])
    return vendor.get("default_zone", vendor["delivery_zones"][0]["id"])


def todays_special(vendor: dict, now: datetime) -> str | None:
    return vendor.get("weekly_specials", {}).get(DAYS[now.weekday()])


# ---- hours / status ----------------------------------------------------------
def fmt_time(hhmm: str) -> str:
    h, m = map(int, hhmm.split(":"))
    return f"{(h % 12) or 12}:{m:02d} {'am' if h < 12 else 'pm'}"


def hours_for(vendor: dict, ov: dict | None) -> dict | None:
    return (ov or {}).get("hours") or vendor.get("hours")


def hours_label(vendor: dict, ov: dict | None) -> str:
    if (ov or {}).get("hours"):
        h = ov["hours"]
        return f"Open daily {fmt_time(h['open'])} – {fmt_time(h['close'])}"
    return vendor["hours_label"]


def is_open_at(vendor: dict, dt: datetime, ov: dict | None, now: datetime) -> bool:
    ov = ov or {}
    if ov.get("paused"):
        return False
    if ov.get("closed_today") and dt.date() == now.date():
        return False
    h = hours_for(vendor, ov)
    if not h:
        return True
    oh, om = map(int, h["open"].split(":"))
    ch, cm = map(int, h["close"].split(":"))
    t = dt.hour * 60 + dt.minute
    return oh * 60 + om <= t < ch * 60 + cm


def open_status(vendor: dict, now: datetime, ov: dict | None = None) -> tuple[bool | None, str]:
    """(is_open, label). is_open is None when the vendor has no fixed hours."""
    ov = ov or {}
    if ov.get("paused"):
        return False, "Paused · not taking orders right now"
    if ov.get("closed_today"):
        return False, "Closed today"
    if not hours_for(vendor, ov):
        return None, vendor["hours_label"]
    st = is_open_at(vendor, now, ov, now)
    return st, ("Open now" if st else "Closed now") + f" · {hours_label(vendor, ov)}"


def money(n: int | float) -> str:
    return f"{currency()} {int(n):,}"
