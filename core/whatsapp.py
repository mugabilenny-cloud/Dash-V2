"""WhatsApp deep links (wa.me) and message builders. WhatsApp is Dash's always-on fallback rail."""
from __future__ import annotations

import re
from urllib.parse import quote

from . import data


def digits(raw: str) -> str:
    return re.sub(r"\D", "", raw or "")


def valid_phone(raw: str) -> bool:
    return 9 <= len(digits(raw)) <= 13


def norm_phone(raw: str) -> str:
    """Last 9 digits — identifies a Ugandan number regardless of 0 / +256 prefix."""
    d = digits(raw)
    return d[-9:] if len(d) >= 9 else d


def to_intl(raw: str) -> str:
    d = digits(raw)
    if d.startswith("256") and len(d) >= 12:
        return d
    if d.startswith("0"):
        return "256" + d[1:]
    return "256" + d if len(d) == 9 else d


def link(number: str, text: str = "") -> str:
    return f"https://wa.me/{number}" + (f"?text={quote(text)}" if text else "")


def order_message(order: dict, vendor: dict, track_url: str = "") -> str:
    rows = [f"*New order {order['code']} — {vendor['name']}*", ""]
    for l in order["lines"]:
        extra = f" [{l['note']}]" if l.get("note") else ""
        rows.append(f"• {l['qty']} × {l['item_name']} — {l['option_label']}{extra} = "
                    f"{data.money(l['line_total'])}{' (from)' if l['is_minimum'] else ''}")
    rows.append("")
    rows.append(f"Subtotal: {data.money(order['subtotal'])}" + (" (minimum)" if order["is_minimum"] else ""))
    rows.append(f"Delivery: {order['zone_label']} — " +
                ("fee to be agreed" if order["fee"] is None else data.money(order["fee"])))
    if order["fee"] is not None:
        rows.append(f"*Total: {data.money(order['total'])}*" + (" (minimum)" if order["is_minimum"] else ""))
    rows.append("Payment: " + ("Cash at pickup" if order["zone_id"] == "pickup" else "Cash on delivery"))
    rows.append(f"When: {order['scheduled_for'] or 'ASAP'}")
    rows += ["", f"Name: {order['name']}", f"Phone: {order['phone']}"]
    if order["zone_id"] != "pickup":
        rows.append(f"Deliver to: {order['address']}")
    if order.get("notes", "").strip():
        rows.append(f"Notes: {order['notes'].strip()}")
    if track_url:
        rows.append(f"Track: {track_url}")
    return "\n".join(rows)


STATUS_TEXT = {
    "accepted": "your order {code} has been accepted ✅",
    "preparing": "your order {code} is being prepared 🍳",
    "out_for_delivery": "your order {code} is on its way 🛵",
    "ready": "your order {code} is ready for pickup 🛍️",
    "delivered": "thank you! Order {code} is complete 🙏",
    "rejected": "sorry, we can't fulfil order {code} right now",
}


def status_message(order: dict, vendor_name: str) -> str:
    base = STATUS_TEXT.get(order["status"], "update on your order {code}").format(code=order["code"])
    extra = ""
    if order["status"] == "out_for_delivery" and order.get("rider_name"):
        extra = f" Rider: {order['rider_name']} {order.get('rider_phone', '')}."
    return f"Hello {order['name']}, {vendor_name} here — {base}.{extra}"


def custom_request_message(vendor_name: str, text: str, name: str = "") -> str:
    return f"Hello {vendor_name}, I'm looking for: {text}. Can you help? {('— ' + name) if name else ''}".strip()


def event_message(vendor: dict, name: str, phone: str, event_type: str, date_str: str,
                  litres: int, venue: str, flavours: str, budget: str) -> str:
    rows = [f"*Event enquiry — {vendor['name']}*", "", f"Event: {event_type}", f"Date: {date_str}",
            f"Venue: {venue}", f"Approx. quantity: {litres} litres", f"Budget: {budget}"]
    if flavours.strip():
        rows.append(f"Flavours: {flavours.strip()}")
    rows += ["", f"Name: {name}", f"Phone: {phone}", "", "Please send a quote. Thank you!"]
    return "\n".join(rows)
