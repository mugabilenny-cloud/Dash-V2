from __future__ import annotations

import time
from datetime import datetime

import streamlit as st

from core import data
from core import orders as ol
from core import whatsapp
from ui import state as ss
from ui.state import S, sx


def _track(code: str) -> None:
    S.track_code = code
    ss.goto("track")


def _report(code: str) -> None:
    S.report_code = code
    ss.goto("help")


def _cancel(code: str) -> None:
    sx(ss.get_store().set_status, code, "cancelled")


# ---- confirmation --------------------------------------------------------------
def render_confirm() -> None:
    o = S.get("_last_order")
    if not o:
        st.info("No recent order.")
        st.button("Go to my orders", on_click=ss.goto, args=("orders",))
        return
    v = data.get_vendor(o["vendor_id"])
    st.success(f"Order placed! Your code is **{o['code']}**")
    if not S.get("_last_tracked"):
        st.error("Order tracking is temporarily offline. **Send your order to the vendor on WhatsApp now** — "
                 "that is how they will receive it.")
    else:
        st.caption("The vendor sees your order in their dashboard. For a faster response, also notify them on WhatsApp.")
    st.link_button(f"📲 Notify {v['name']} on WhatsApp",
                   whatsapp.link(v["whatsapp"], whatsapp.order_message(o, v, ss.track_url(o["code"]))), type="primary")
    if S.get("_last_tracked"):
        st.button("Track my order", on_click=_track, args=(o["code"],))
    st.markdown("**Receipt** (tap the copy icon to save or share)")
    st.code(ol.receipt(o, v["name"], ss.TZ), language=None)
    if S.cart:
        st.info("You still have items from another vendor in your cart.")
        st.button("Go to cart", on_click=ss.goto, args=("cart",))
    else:
        st.button("Keep shopping", on_click=ss.goto, args=("menu",))


# ---- tracking ------------------------------------------------------------------
def _timeline(o: dict) -> None:
    pickup = o["zone_id"] == "pickup"
    if o["status"] in ("rejected", "cancelled"):
        st.error("❌ " + ol.label(o["status"], pickup))
        return
    f = ol.flow(pickup)
    cur = f.index(o["status"])
    for i, s in enumerate(f):
        cls, icon = ("done", "✅") if i < cur else (("now", "🟢") if i == cur else ("todo", "⚪"))
        st.markdown(f"<div class='step {cls}'>{icon} {ol.label(s, pickup)}</div>", unsafe_allow_html=True)


@st.fragment(run_every="15s")
def _live(code: str) -> None:
    o = sx(ss.get_store().get_order, code)
    if not o:
        st.error("Order not found, or tracking is offline.")
        return
    v = data.get_vendor(o["vendor_id"])
    st.markdown(f"### {o['code']} · {v['name']}")
    st.caption(f"{data.money(o['total'])}" + (" (minimum)" if o["is_minimum"] else "") +
               (f" · scheduled {o['scheduled_for']}" if o["scheduled_for"] else ""))
    _timeline(o)
    if o["status"] == "out_for_delivery" and o["rider_name"]:
        st.info(f"🛵 Rider: **{o['rider_name']}**  [📞 {o['rider_phone']}](tel:{o['rider_phone']})")
    if ol.is_overdue(o):
        st.warning(f"{v['name']} hasn't accepted yet. Nudge them on WhatsApp, or cancel and try another vendor.")
        st.link_button("Nudge on WhatsApp", whatsapp.link(v["whatsapp"], f"Hello, please check order {o['code']}."))
        if not S.get(f"_to_{code}"):
            S[f"_to_{code}"] = True
            ss.log("timeout", o["vendor_id"], o["phone_norm"], code=code)
    if "cancelled" in ol.allowed(o):
        st.button("Cancel order", key=f"cx_{code}", on_click=_cancel, args=(code,))
    if o["status"] == "delivered":
        if o["rating"]:
            st.success("You rated this order " + "⭐" * o["rating"])
        else:
            st.markdown("**How was it?**")
            r = st.radio("Rating", [5, 4, 3, 2, 1], horizontal=True, key=f"rt_{code}",
                         format_func=lambda n: "⭐" * n, label_visibility="collapsed")
            rev = st.text_input("Comment (optional)", key=f"rv_{code}")
            if st.button("Submit rating", key=f"rs_{code}"):
                sx(ss.get_store().rate_order, code, int(r), rev)
                st.rerun(scope="fragment")
    with st.expander("Receipt"):
        st.code(ol.receipt(o, v["name"], ss.TZ), language=None)


def render_track() -> None:
    code = S.get("track_code")
    if not code:
        st.info("Choose an order to track.")
        st.button("My orders", on_click=ss.goto, args=("orders",))
        return
    o = sx(ss.get_store().get_order, code)
    if not o:
        st.error("We couldn't find that order (or tracking is offline).")
    elif not ss.can_view_order(o):
        st.info("For privacy, enter the phone number used for this order.")
        ph = st.text_input("Phone number", key="trk_phone")
        if st.button("Show my order"):
            if whatsapp.norm_phone(ph) == o["phone_norm"]:
                S.verified.append(code)
                st.rerun()
            else:
                st.error("That number doesn't match this order.")
    else:
        _live(code)
        c = st.columns(1)[0]
        c.button("Report a problem", key="trk_rep", on_click=_report, args=(code,))
        if o["status"] == "delivered":
            c.button("Reorder", key="trk_re", on_click=ss.reorder_cb, args=(code,))
    st.button("← My orders", key="trk_back", on_click=ss.goto, args=("orders",))


# ---- history -------------------------------------------------------------------
def _find_orders(phone: str, code: str) -> None:
    store = ss.get_store()
    o = sx(store.get_order, code.strip().upper())
    if o and o["phone_norm"] and o["phone_norm"] == whatsapp.norm_phone(phone):
        found = sx(store.orders_for_phone, o["phone_norm"], default=[])
        for f in found:
            if f["code"] not in S.my_orders:
                S.my_orders.append(f["code"])
        ss.flash("success", f"Found {len(found)} order(s).")
    else:
        ss.flash("error", "That phone number and order code don't match.")


def render_orders() -> None:
    orders = sx(ss.get_store().get_orders, S.my_orders, default=[])
    if not orders:
        st.info("No orders on this device yet.")
    for o in orders:
        v = data.get_vendor(o["vendor_id"])
        with st.container(border=True):
            when = datetime.fromtimestamp(o["created_at"], ss.TZ).strftime("%d %b, %H:%M")
            st.markdown(f"**{o['code']}** · {v['emoji']} {v['name']}  \n"
                        f"{ol.label(o['status'], o['zone_id'] == 'pickup')} · {data.money(o['total'])} · {when}")
            st.button("Track / receipt", key=f"tr_{o['code']}", on_click=_track, args=(o["code"],))
            st.button("Reorder", key=f"ro_{o['code']}", on_click=ss.reorder_cb, args=(o["code"],))
    with st.expander("Find my orders on this device"):
        st.caption("Enter your phone number and any one order code you have.")
        ph = st.text_input("Phone", key="fo_phone")
        cd = st.text_input("Order code (e.g. D-7K3PQ)", key="fo_code")
        st.button("Find my orders", on_click=_find_orders, args=(ph, cd))
