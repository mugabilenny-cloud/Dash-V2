"""Vendor dashboard: live orders, menu & stock, settings, reports. Password protected."""
from __future__ import annotations

import csv
import io
import time
from collections import Counter
from datetime import datetime, time as dtime

import streamlit as st

from core import auth, data
from core import orders as ol
from core import whatsapp
from ui import state as ss
from ui.state import S, sx

STEP_LABEL = {"accepted": "✅ Accept", "preparing": "🍳 Start preparing", "out_for_delivery": "🛵 Out for delivery",
              "ready": "🛍️ Ready for pickup", "delivered": "✔️ Mark delivered", "rejected": "✖ Decline"}


# ---- login ---------------------------------------------------------------------
def _login(vid: str) -> None:
    cfg = ss.vendor_passwords()
    if S.get("login_fail", 0) >= auth.MAX_ATTEMPTS:
        ss.flash("error", "Too many attempts. Reload the page to try again later.")
        return
    if auth.check(vid, S.get("vpw", ""), cfg):
        S.setdefault("vendor_auth", [])
        S.vendor_auth = list(set(S.vendor_auth + [vid]))
    else:
        S.login_fail = S.get("login_fail", 0) + 1
        ss.log("login_fail", vid)
        ss.flash("error", "Wrong password.")


def _logout(vid: str) -> None:
    S.vendor_auth = [v for v in S.get("vendor_auth", []) if v != vid]


# ---- order actions ---------------------------------------------------------------
def _step(code: str, status: str) -> None:
    rn, rp = S.get(f"rn_{code}", ""), S.get(f"rp_{code}", "")
    if status == "out_for_delivery" and not (rn.strip() and rp.strip()):
        ss.flash("error", "Enter the rider's name and phone first.")
        return
    sx(ss.get_store().set_status, code, status, rn.strip(), rp.strip())


def _order_card(o: dict, v: dict) -> None:
    pickup = o["zone_id"] == "pickup"
    with st.container(border=True):
        when = datetime.fromtimestamp(o["created_at"], ss.TZ).strftime("%H:%M")
        st.markdown(f"**{o['code']}** · {when} · {ol.label(o['status'], pickup)}"
                    + (f" · 📅 {o['scheduled_for']}" if o["scheduled_for"] else ""))
        for l in o["lines"]:
            st.write(f"{l['qty']} × {l['item_name']} ({l['option_label']})" + (f" · **{l['note']}**" if l.get("note") else ""))
        st.write(f"💵 {data.money(o['total'])}" + (" (min.)" if o["is_minimum"] else "") +
                 (" · fee to agree" if o["fee"] is None else "") + (" · pickup" if pickup else f" · {o['zone_label']}"))
        st.write(f"👤 {o['name']} · [{o['phone']}](tel:{o['phone']})" + ("" if pickup else f"  \n📍 {o['address']}"))
        if o["notes"]:
            st.caption("Notes: " + o["notes"])
        if o["status"] == "preparing" and not pickup:
            st.text_input("Rider name", key=f"rn_{o['code']}")
            st.text_input("Rider phone", key=f"rp_{o['code']}")
        for s in ol.vendor_allowed(o):
            st.button(STEP_LABEL[s], key=f"st_{o['code']}_{s}", on_click=_step, args=(o["code"], s),
                      type="primary" if s != "rejected" else "secondary")
        if o["phone"]:
            st.link_button("Message customer on WhatsApp",
                           whatsapp.link(whatsapp.to_intl(o["phone"]), whatsapp.status_message(o, v["name"])))


@st.fragment(run_every="15s")
def _live_orders(vid: str) -> None:
    v = data.get_vendor(vid)
    orders = sx(ss.get_store().orders_for_vendor, vid, time.time() - 3 * 86400, default=[])
    new = [o for o in orders if o["status"] == "sent"]
    active = [o for o in orders if o["status"] in ("accepted", "preparing", "out_for_delivery", "ready")]
    done = [o for o in orders if o["status"] in ol.TERMINAL][:10]
    st.markdown(f"### 🔔 New ({len(new)})")
    for o in reversed(new):
        _order_card(o, v)
    if not new:
        st.caption("No new orders.")
    st.markdown(f"### In progress ({len(active)})")
    for o in reversed(active):
        _order_card(o, v)
    with st.expander(f"Recently finished ({len(done)})"):
        for o in done:
            st.write(f"{o['code']} · {ol.label(o['status'], o['zone_id'] == 'pickup')} · {data.money(o['total'])}"
                     + (f" · {'⭐' * o['rating']}" if o["rating"] else ""))


# ---- menu & stock ----------------------------------------------------------------
def _menu_tab(vid: str) -> None:
    v, ov = data.get_vendor(vid), S.ovs.get(vid, {})
    with st.form(f"menu_{vid}"):
        for cat in v["categories"]:
            st.subheader(cat["name"])
            for it in cat["items"]:
                st.markdown(f"**{it['name']}**")
                st.toggle("Available", value=data.is_available(it, ov), key=f"va_{vid}_{it['id']}")
                for op in it["options"]:
                    st.number_input(f"{op['label']} (UGX)", 100, 1_000_000, data.effective_price(it, op, ov),
                                    step=100, key=f"vp_{vid}_{it['id']}_{op['id']}")
        saved = st.form_submit_button("Save changes", type="primary")
    if saved:
        store, prices, unavailable = ss.get_store(), {}, []
        for cat in v["categories"]:
            for it in cat["items"]:
                if not S[f"va_{vid}_{it['id']}"]:
                    unavailable.append(it["id"])
                for op in it["options"]:
                    p = int(S[f"vp_{vid}_{it['id']}_{op['id']}"])
                    if p != op["price"]:
                        prices[f"{it['id']}|{op['id']}"] = p
        sx(store.set_override, vid, "price", prices or None)
        sx(store.set_override, vid, "unavailable", unavailable or None)
        ss.refresh_ovs()
        st.success("Saved. Customers see the new prices and stock now.")


# ---- settings --------------------------------------------------------------------
def _flag(vid: str, key: str, wkey: str) -> None:
    sx(ss.get_store().set_override, vid, key, True if S[wkey] else None)
    ss.refresh_ovs()


def _undo(vid: str) -> None:
    r = sx(ss.get_store().undo_last, vid)
    ss.refresh_ovs()
    ss.flash("success" if r else "error", f"Undid change to “{r['key']}”." if r else "Nothing to undo.")


def _settings_tab(vid: str) -> None:
    v, ov = data.get_vendor(vid), S.ovs.get(vid, {})
    st.toggle("⏸️ Pause all orders", value=bool(ov.get("paused")), key=f"pz_{vid}", on_change=_flag,
              args=(vid, "paused", f"pz_{vid}"))
    st.toggle("Closed today", value=bool(ov.get("closed_today")), key=f"ct_{vid}", on_change=_flag,
              args=(vid, "closed_today", f"ct_{vid}"))
    st.caption("“Closed today” resets only when you switch it off.")
    base = data.hours_for(v, ov)
    with st.form(f"set_{vid}"):
        if base:
            o = dtime(*map(int, base["open"].split(":")))
            c = dtime(*map(int, base["close"].split(":")))
            t_open = st.time_input("Opens", value=o, step=900)
            t_close = st.time_input("Closes", value=c, step=900)
        fees = {}
        for z in v["delivery_zones"]:
            if z["id"] == "pickup":
                continue
            cur = data.zone_fee(z, ov)
            agree = st.checkbox(f"{z['label']}: agree fee on WhatsApp", value=cur is None, key=f"za_{vid}_{z['id']}")
            fee = st.number_input(f"{z['label']} — fee (UGX)", 0, 50_000, int(cur or 0), step=500, key=f"zf_{vid}_{z['id']}")
            fees[z["id"]] = None if agree else int(fee)
        if st.form_submit_button("Save settings", type="primary"):
            store = ss.get_store()
            if base:
                if t_close <= t_open:
                    st.error("Closing time must be after opening time.")
                    return
                new = {"open": t_open.strftime("%H:%M"), "close": t_close.strftime("%H:%M")}
                sx(store.set_override, vid, "hours", None if new == v.get("hours") else new)
            changed = {k: val for k, val in fees.items() if val != next(z["fee"] for z in v["delivery_zones"] if z["id"] == k)}
            sx(store.set_override, vid, "zone_fee", changed or None)
            ss.refresh_ovs()
            st.success("Saved.")
    st.subheader("Change history")
    for a in sx(ss.get_store().audit_list, vid, 8, default=[]):
        ts = datetime.fromtimestamp(a["ts"], ss.TZ).strftime("%d %b %H:%M")
        st.caption(f"{ts} · {a['key']}" + (" (undone)" if a["undone"] else ""))
    st.button("↩️ Undo last change", key=f"undo_{vid}", on_click=_undo, args=(vid,))


# ---- reports ---------------------------------------------------------------------
def _reports_tab(vid: str) -> None:
    store = ss.get_store()
    days = {"Today": 0, "Last 7 days": 7, "Last 30 days": 30}[
        st.radio("Period", ["Today", "Last 7 days", "Last 30 days"], horizontal=True, key=f"rp_{vid}")]
    start = ss.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp() - days * 86400
    rows = sx(store.orders_for_vendor, vid, start, default=[])
    delivered = [o for o in rows if o["status"] == "delivered"]
    c1, c2 = st.columns(2)
    c1.metric("Orders", len(rows))
    c2.metric("Delivered", len(delivered))
    st.metric("Revenue (delivered)", data.money(sum(o["total"] for o in delivered)))
    s = sx(store.vendor_stats, vid, default=None) or {}
    st.caption(f"All-time: completion {s['completion']:.0%}" if s.get("completion") is not None else "All-time: no completed orders yet")
    if s.get("avg_accept_min") is not None:
        st.caption(f"Average acceptance time: {s['avg_accept_min']:.1f} min")
    if s.get("rating_avg"):
        st.caption(f"Average rating: {s['rating_avg']:.1f} ⭐ ({s['rating_n']} ratings)")
    top = Counter()
    for o in rows:
        for l in o["lines"]:
            top[l["item_name"]] += l["qty"]
    if top:
        st.markdown("**Top items**")
        st.table([{"Item": k, "Qty": n} for k, n in top.most_common(5)])
    issues = sx(store.events, "issue", vid, time.time() - 7 * 86400, default=[])
    st.markdown(f"**Customer issues (last 7 days): {len(issues)}**")
    for e in issues[:10]:
        p = e["payload"]
        st.caption(f"{p.get('tag')} · {p.get('code') or '—'} · {p.get('details', '')[:120]}")
    timeouts = sx(store.events, "timeout", vid, time.time() - 7 * 86400, default=[])
    st.caption(f"Orders not accepted within {ol.ACCEPT_TIMEOUT_MIN} min (7 days): {len(timeouts)}")
    misses = Counter(e["payload"].get("query", "") for e in sx(store.events, "search_miss", None, start, default=[]))
    if misses:
        st.caption("Searches with no results: " + ", ".join(f"{q} ({n})" for q, n in misses.most_common(5)))
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["code", "created", "status", "customer", "phone", "zone", "items", "subtotal", "fee", "total", "rating"])
    for o in rows:
        w.writerow([o["code"], datetime.fromtimestamp(o["created_at"], ss.TZ).isoformat(timespec="minutes"),
                    o["status"], o["name"], o["phone"], o["zone_label"],
                    "; ".join(f"{l['qty']}x {l['item_name']}" for l in o["lines"]), o["subtotal"],
                    "" if o["fee"] is None else o["fee"], o["total"], o["rating"] or ""])
    st.download_button("Export orders (CSV)", buf.getvalue(), file_name=f"{vid}-orders.csv", mime="text/csv")


def render() -> None:
    cfg = ss.vendor_passwords()
    vid = st.radio("Vendor", [v["id"] for v in data.vendors()], horizontal=True, key="vd_vendor",
                   format_func=lambda i: data.get_vendor(i)["name"], label_visibility="collapsed")
    if not auth.configured(vid, cfg):
        st.info("This dashboard is locked: no password is configured yet. Add it in Streamlit secrets "
                f"(`[vendor_passwords]` → `{vid} = \"your-password\"`) or the env var `DASH_PW_{vid.upper()}`.")
        return
    if vid not in S.get("vendor_auth", []):
        st.text_input("Vendor password", type="password", key="vpw")
        st.button("Sign in", type="primary", on_click=_login, args=(vid,))
        return
    st.markdown(f"### 🏪 {data.get_vendor(vid)['name']} dashboard")
    t1, t2, t3, t4 = st.tabs(["Orders", "Menu & stock", "Settings", "Reports"])
    with t1:
        _live_orders(vid)
    with t2:
        _menu_tab(vid)
    with t3:
        _settings_tab(vid)
    with t4:
        _reports_tab(vid)
    st.button("Sign out", key=f"so_{vid}", on_click=_logout, args=(vid,))
