"""Pure cart logic (no Streamlit imports) so it is unit-testable.

A cart is a list of dicts: {vendor_id, item_id, option_id, qty, note}.
Prices are NEVER stored in the cart; they are resolved from the live catalog (+ vendor
overrides) every time, so stale prices cannot occur.
"""
from __future__ import annotations

from . import data

MAX_QTY = 50


def add_line(cart: list[dict], vendor_id: str, item_id: str, option_id: str,
             qty: int = 1, note: str = "") -> None:
    note = note.strip()
    for line in cart:
        if (line["vendor_id"], line["item_id"], line["option_id"], line["note"]) == (
            vendor_id, item_id, option_id, note,
        ):
            line["qty"] = min(MAX_QTY, line["qty"] + qty)
            return
    cart.append({"vendor_id": vendor_id, "item_id": item_id, "option_id": option_id,
                 "qty": min(MAX_QTY, max(1, qty)), "note": note})


def set_qty(cart: list[dict], index: int, qty: int) -> None:
    if not 0 <= index < len(cart):
        return
    if qty <= 0:
        cart.pop(index)
    else:
        cart[index]["qty"] = min(MAX_QTY, qty)


def count(cart: list[dict]) -> int:
    return sum(line["qty"] for line in cart)


def resolve(cart: list[dict], ovs: dict | None = None) -> list[dict]:
    """Attach names, live prices and availability. Lines whose item vanished are flagged `missing`."""
    ovs = ovs or {}
    out = []
    for idx, line in enumerate(cart):
        try:
            v = data.get_vendor(line["vendor_id"])
            it = data.get_item(v, line["item_id"])
            op = data.get_option(it, line["option_id"])
        except KeyError:
            out.append({**line, "idx": idx, "item_name": "(no longer on the menu)", "option_label": "",
                        "unit_price": 0, "is_minimum": False, "line_total": 0,
                        "available": False, "missing": True})
            continue
        ov = ovs.get(v["id"], {})
        price = data.effective_price(it, op, ov)
        out.append({**line, "idx": idx, "item_name": it["name"], "option_label": op["label"],
                    "unit_price": price, "is_minimum": bool(op.get("from")),
                    "line_total": price * line["qty"],
                    "available": data.is_available(it, ov), "missing": False})
    return out


def group_by_vendor(cart: list[dict], ovs: dict | None = None) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = {}
    for line in resolve(cart, ovs):
        groups.setdefault(line["vendor_id"], []).append(line)
    return groups


def totals(lines: list[dict], vendor: dict, zone_id: str, ov: dict | None = None) -> dict:
    subtotal = sum(l["line_total"] for l in lines)
    fee = data.zone_fee(data.get_zone(vendor, zone_id), ov)  # None => to be agreed
    return {"subtotal": subtotal, "fee": fee, "total": subtotal + (fee or 0),
            "is_minimum": any(l["is_minimum"] for l in lines), "fee_pending": fee is None}


def reorder(cart: list[dict], order: dict, ovs: dict | None = None) -> list[str]:
    """Re-add a past order's lines at CURRENT prices. Returns human-readable notes."""
    ovs = ovs or {}
    notes = []
    for l in order["lines"]:
        try:
            v = data.get_vendor(order["vendor_id"])
            it = data.get_item(v, l["item_id"])
            op = data.get_option(it, l["option_id"])
        except KeyError:
            notes.append(f"{l['item_name']} is no longer on the menu.")
            continue
        ov = ovs.get(v["id"], {})
        if not data.is_available(it, ov):
            notes.append(f"{it['name']} is sold out right now.")
            continue
        add_line(cart, order["vendor_id"], l["item_id"], l["option_id"], l["qty"], l.get("note", ""))
        now_price = data.effective_price(it, op, ov)
        if now_price != l["unit_price"]:
            notes.append(f"{it['name']} ({op['label']}) is now {data.money(now_price)} "
                         f"(was {data.money(l['unit_price'])}).")
    return notes
