"""Typo-tolerant search over vendors and items (difflib, no dependencies)."""
from __future__ import annotations

import re
from datetime import datetime
from difflib import SequenceMatcher

from . import data


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", text.lower())


def _score(query: str, fields: list[tuple[str, float]]) -> float:
    q = query.lower().strip()
    qw = _words(q)
    best = 0.0
    for text, weight in fields:
        tl = text.lower()
        if q and q in tl:
            best = max(best, 3 * weight)
            continue
        for w in _words(text):
            for t in qw:
                if t in w or w in t and len(w) > 3:
                    best = max(best, 2 * weight)
                else:
                    r = SequenceMatcher(None, t, w).ratio()
                    if r >= 0.75:
                        best = max(best, (1 + r) * weight)
    return best


def search(query: str, ovs: dict, now: datetime, open_only: bool = False,
           free_delivery: bool = False, sort: str = "relevance") -> dict:
    items, vend = [], []
    for v in data.vendors():
        ov = ovs.get(v["id"], {})
        state, _ = data.open_status(v, now, ov)
        if open_only and state is False:
            continue
        if free_delivery and not any(data.zone_fee(z, ov) == 0 and z["id"] != "pickup"
                                     for z in v["delivery_zones"]):
            continue
        if query.strip():
            vs = _score(query, [(v["name"], 1.5), (v["tagline"], 0.5)])
            if vs:
                vend.append((vs, v))
        for cat in v["categories"]:
            for it in cat["items"]:
                if query.strip():
                    s = _score(query, [(it["name"], 1.5), (cat["name"], 1.0),
                                       (it["description"], 0.5), (v["name"], 0.6)])
                    if not s:
                        continue
                else:
                    s = 1.0
                items.append({"score": s, "vendor": v, "item": it, "price": data.min_price(it, ov)})
    if sort == "price_low":
        items.sort(key=lambda r: r["price"])
    elif sort == "price_high":
        items.sort(key=lambda r: -r["price"])
    else:
        items.sort(key=lambda r: -r["score"])
    return {"vendors": [v for _, v in sorted(vend, key=lambda x: -x[0])], "items": items}
