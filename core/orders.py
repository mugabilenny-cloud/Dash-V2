"""Order lifecycle rules (pure)."""
from __future__ import annotations

import secrets
import time
from datetime import datetime, timedelta

from . import data

TERMINAL = {"delivered", "rejected", "cancelled"}
ACCEPT_TIMEOUT_MIN = 10
MAX_ORDERS_PER_HOUR = 6
ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
LABELS = {"sent": "Order sent", "accepted": "Accepted", "preparing": "Being prepared",
          "out_for_delivery": "Out for delivery", "ready": "Ready for pickup",
          "delivered": "Delivered", "rejected": "Declined by vendor", "cancelled": "Cancelled"}


def new_code() -> str:
    return "D-" + "".join(secrets.choice(ALPHABET) for _ in range(5))


def label(status: str, pickup: bool = False) -> str:
    if status == "delivered" and pickup:
        return "Collected"
    return LABELS.get(status, status)


def flow(pickup: bool) -> list[str]:
    return ["sent", "accepted", "preparing", "ready" if pickup else "out_for_delivery", "delivered"]


def allowed(order: dict) -> list[str]:
    """All legal next statuses (vendor steps + decline + customer cancel)."""
    s = order["status"]
    if s in TERMINAL:
        return []
    f = flow(order["zone_id"] == "pickup")
    nxt = [f[f.index(s) + 1]]
    if s in ("sent", "accepted", "preparing"):
        nxt.append("rejected")
    if s == "sent":
        nxt.append("cancelled")
    return nxt


def vendor_allowed(order: dict) -> list[str]:
    return [s for s in allowed(order) if s != "cancelled"]


def is_overdue(order: dict, now_ts: float | None = None) -> bool:
    return order["status"] == "sent" and (now_ts or time.time()) - order["created_at"] > ACCEPT_TIMEOUT_MIN * 60


def validate_schedule(dt: datetime, now: datetime) -> str | None:
    if dt < now + timedelta(minutes=30):
        return "Pick a time at least 30 minutes from now."
    if dt > now + timedelta(days=7):
        return "Pick a time within the next 7 days."
    return None


def window_error(vendor: dict, dt: datetime, ov: dict | None, now: datetime) -> str | None:
    ov = ov or {}
    if ov.get("paused"):
        return f"{vendor['name']} is not taking orders right now."
    if ov.get("closed_today") and dt.date() == now.date():
        return f"{vendor['name']} is closed today. Schedule for another day."
    if not data.is_open_at(vendor, dt, ov, now):
        return f"{vendor['name']} will be closed then ({data.hours_label(vendor, ov)})."
    return None


def receipt(order: dict, vendor_name: str, tz) -> str:
    when = datetime.fromtimestamp(order["created_at"], tz).strftime("%d %b %Y %H:%M")
    rows = [f"DASH ORDER {order['code']}", f"{vendor_name} · {when}", ""]
    for l in order["lines"]:
        extra = f" [{l['note']}]" if l.get("note") else ""
        rows.append(f"{l['qty']} x {l['item_name']} ({l['option_label']}){extra}  {data.money(l['line_total'])}")
    rows.append("")
    rows.append(f"Subtotal: {data.money(order['subtotal'])}" + (" (minimum)" if order["is_minimum"] else ""))
    rows.append("Delivery: " + ("to be agreed" if order["fee"] is None else data.money(order["fee"])) +
                f" ({order['zone_label']})")
    if order["fee"] is not None:
        rows.append(f"TOTAL: {data.money(order['total'])}" + (" (minimum)" if order["is_minimum"] else ""))
    rows.append("Payment: " + ("Cash at pickup" if order["zone_id"] == "pickup" else "Cash on delivery"))
    if order.get("scheduled_for"):
        rows.append(f"Scheduled: {order['scheduled_for']}")
    return "\n".join(rows)
