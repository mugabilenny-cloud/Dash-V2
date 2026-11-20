from __future__ import annotations

from datetime import datetime, time as dtime, timedelta

import streamlit as st

from core import cart as cartlib
from core import data
from core import orders as ol
from core import whatsapp
from ui import components as C
from ui import state as ss
from ui.state import S, sx


def _find(key: tuple):
    for i, l in enumerate(S.cart):
        if (l["vendor_id"], l["item_id"], l["option_id"], l["note"]) == key:
            return i
    return None


def _change_qty(key: tuple, wkey: str) -> None:
    i = _find(key)
    if i is None:
        return
    q = int(S[wkey])
    cartlib.set_qty(S.cart, i, q)
    if q <= 0:
        S.pop(wkey, None)


def _clear(vid: str) -> None:
    S.cart = [l for l in S.cart if l["vendor_id"] != vid]


def _remove_unavailable() -> None:
    ok = {(l["vendor_id"], l["item_id"], l["option_id"], l["note"]) for l in cartlib.resolve(S.cart, S.ovs)
          if l["available"]}
    S.cart = [l for l in S.cart if (l["vendor_id"], l["item_id"], l["option_id"], l["note"]) in ok]


def _zone(v: dict) -> str:
    ids = [z["id"] for z in v["delivery_zones"]]
    z = S.zones.get(v["id"])
    return z if z in ids else data.default_zone(v, S.profile.get("area"))


def _zone_picker(v: dict, key: str) -> str:
    ids = [z["id"] for z in v["delivery_zones"]]
    ov = S.ovs.get(v["id"], {})
    zid = st.selectbox("Delivery", ids, index=ids.index(_zone(v)), key=f"{key}_{v['id']}",
                       format_func=lambda i: data.get_zone(v, i)["label"] + (
                           "" if data.zone_fee(data.get_zone(v, i), ov) is None else
                           f" — {data.money(data.zone_fee(data.get_zone(v, i), ov))}"
                           if data.zone_fee(data.get_zone(v, i), ov) else " — free"))
    S.zones[v["id"]] = zid
    return zid


def render_cart() -> None:
    for note in S.pop("_reorder_notes", []) or []:
        st.warning(note)
    if not S.cart:
        st.info("Your cart is empty.")
        st.button("Browse the menu", on_click=ss.goto, args=("menu",))
        return
    blocked = False
    for vid, lines in cartlib.group_by_vendor(S.cart, S.ovs).items():
        v, ov = data.get_vendor(vid), S.ovs.get(vid, {})
        with st.container(border=True):
            st.markdown(f"### {v['emoji']} {v['name']}")
            C.status_pill(v)
            for l in lines:
                key = (l["vendor_id"], l["item_id"], l["option_id"], l["note"])
                wkey = "cq_" + "_".join(key).replace(" ", "")
                extra = f" · {l['note']}" if l["note"] else ""
                st.markdown(f"**{l['item_name']}** — {l['option_label']}{extra}  \n"
                            f"{'from ' if l['is_minimum'] else ''}{data.money(l['unit_price'])} each → "
                            f"**{data.money(l['line_total'])}**")
                if not l["available"]:
                    blocked = True
                    st.error("Not available right now — remove it to continue.")
                st.number_input("Qty (0 removes)", 0, cartlib.MAX_QTY, l["qty"], key=wkey,
                                on_change=_change_qty, args=(key, wkey))
            zid = _zone_picker(v, "zone")
            t = cartlib.totals(lines, v, zid, ov)
            st.write(f"Subtotal: **{data.money(t['subtotal'])}**" + (" (minimum)" if t["is_minimum"] else ""))
            st.write("Delivery: " + ("**agreed on WhatsApp**" if t["fee_pending"] else f"**{data.money(t['fee'])}**"))
            if not t["fee_pending"]:
                st.markdown(f"#### Total: {data.money(t['total'])}" + (" (min.)" if t["is_minimum"] else ""))
            st.caption("💵 Cash on delivery. " + v["delivery_note"])
            st.button("Clear this order", key=f"clr_{vid}", on_click=_clear, args=(vid,))
    if blocked:
        st.button("Remove unavailable items", on_click=_remove_unavailable)
    st.button("Continue to checkout", type="primary", disabled=blocked, on_click=ss.goto, args=("checkout",))


def _place(vid: str) -> None:
    v, ov, n, P = data.get_vendor(vid), S.ovs.get(vid, {}), ss.now(), S.profile
    lines = cartlib.group_by_vendor(S.cart, S.ovs).get(vid, [])
    zid = _zone(v)
    pickup = zid == "pickup"
    err = None
    if not lines:
        err = "That order is empty."
    elif any(not l["available"] for l in lines):
        err = "Some items are sold out. Remove them first."
    elif not P["name"].strip() or not whatsapp.valid_phone(P["phone"]):
        err = "Please enter your name and a valid phone number."
    elif not pickup and not P["address"].strip():
        err = "Please enter a delivery address."
    target, sched = n, ""
    if not err and S.get(f"sm_{vid}") == "Schedule":
        target = datetime.combine(S[f"sd_{vid}"], S[f"stime_{vid}"], tzinfo=ss.TZ)
        err = ol.validate_schedule(target, n)
        sched = target.strftime("%a %d %b, %I:%M %p")
    err = err or ol.window_error(v, target, ov, n)
    if not err and ss.sx(ss.get_store().count_recent_orders, whatsapp.norm_phone(P["phone"]), default=0) >= ol.MAX_ORDERS_PER_HOUR:
        err = "Too many orders from this number in the last hour. Please call the vendor."
    if err:
        ss.flash("error", err)
        return
    t = cartlib.totals(lines, v, zid, ov)
    order = {
        "code": ol.new_code(), "created_at": n.timestamp(), "vendor_id": vid, "name": P["name"].strip(),
        "phone": P["phone"].strip(), "phone_norm": whatsapp.norm_phone(P["phone"]),
        "address": "" if pickup else P["address"].strip(), "zone_id": zid,
        "zone_label": data.get_zone(v, zid)["label"], "payment": "cod", "scheduled_for": sched,
        "notes": S.get(f"notes_{vid}", "").strip(),
        "lines": [{k: l[k] for k in ("item_id", "option_id", "item_name", "option_label", "qty", "note",
                                     "unit_price", "line_total", "is_minimum")} for l in lines],
        "subtotal": t["subtotal"], "fee": t["fee"], "total": t["total"], "is_minimum": t["is_minimum"],
    }
    created = sx(ss.get_store().create_order, order, default=None)
    S["_last_order"] = created or {**order, "status": "sent", "history": [], "rider_name": "", "rider_phone": "",
                                   "rating": None, "review": ""}
    S["_last_tracked"] = created is not None
    S.cart = [l for l in S.cart if l["vendor_id"] != vid]
    if created:
        S.my_orders.append(order["code"])
    S.track_code = order["code"]
    ss.goto("confirm")


def render_checkout() -> None:
    if not S.cart:
        st.info("Nothing to check out.")
        st.button("Browse the menu", on_click=ss.goto, args=("menu",))
        return
    st.subheader("Your details")
    C.pfield("Name", "name")
    C.pfield("Phone (WhatsApp)", "phone", placeholder="07XX XXX XXX")
    saved = S.profile.get("addresses", [])
    if saved:
        def _use():
            pick = S.get("w_saved")
            if pick and pick != "—":
                a = next(x["address"] for x in saved if x["label"] == pick)
                S.profile["address"] = a
                S["w_address"] = a
        st.selectbox("Saved addresses", ["—"] + [x["label"] for x in saved], key="w_saved", on_change=_use)
    C.pfield("Delivery address / landmark", "address", area=True, height=80)
    st.button("← Back to cart", on_click=ss.goto, args=("cart",))
    for vid, lines in cartlib.group_by_vendor(S.cart, S.ovs).items():
        v, ov, n = data.get_vendor(vid), S.ovs.get(vid, {}), ss.now()
        with st.container(border=True):
            st.markdown(f"### {v['emoji']} {v['name']}")
            C.status_pill(v)
            zid = _zone_picker(v, "cz")
            pickup = zid == "pickup"
            t = cartlib.totals(lines, v, zid, ov)
            for l in lines:
                st.write(f"{l['qty']} × {l['item_name']} ({l['option_label']})"
                         + (f" · {l['note']}" if l["note"] else "") + f" — {data.money(l['line_total'])}")
            when = st.radio("When?", ["ASAP", "Schedule"], horizontal=True, key=f"sm_{vid}")
            if when == "Schedule":
                d = st.date_input("Date", min_value=n.date(), max_value=n.date() + timedelta(days=7), key=f"sd_{vid}")
                st.time_input("Time", value=dtime(18, 30), key=f"stime_{vid}", step=900)
            st.text_input("Notes for the vendor (optional)", key=f"notes_{vid}")
            st.write(f"Subtotal: **{data.money(t['subtotal'])}**" + (" (minimum)" if t["is_minimum"] else ""))
            st.write("Delivery: " + ("**agreed on WhatsApp**" if t["fee_pending"] else f"**{data.money(t['fee'])}**"))
            if not t["fee_pending"]:
                st.markdown(f"#### Total: {data.money(t['total'])}")
            st.success("💵 " + ("Cash at pickup" if pickup else "Cash on delivery") + " — pay when you receive your order.")
            problems = []
            if not S.profile["name"].strip():
                problems.append("name")
            if not whatsapp.valid_phone(S.profile["phone"]):
                problems.append("valid phone")
            if not pickup and not S.profile["address"].strip():
                problems.append("delivery address")
            if problems:
                st.caption("Add your " + ", ".join(problems) + " to continue.")
            st.button(f"Place order with {v['name']}", key=f"place_{vid}", type="primary",
                      disabled=bool(problems), on_click=_place, args=(vid,))
            with st.expander("Trouble placing the order? Send it on WhatsApp instead"):
                draft = {"code": "(pending)", "lines": lines, "subtotal": t["subtotal"], "fee": t["fee"],
                         "total": t["total"], "is_minimum": t["is_minimum"], "zone_id": zid,
                         "zone_label": data.get_zone(v, zid)["label"], "scheduled_for": "",
                         "name": S.profile["name"], "phone": S.profile["phone"],
                         "address": S.profile["address"], "notes": S.get(f"notes_{vid}", "")}
                st.link_button("Send order on WhatsApp only", whatsapp.link(v["whatsapp"], whatsapp.order_message(draft, v)),
                               disabled=bool(problems))
