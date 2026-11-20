"""Reusable UI pieces: status pills, item cards, item dialog."""
from __future__ import annotations

import streamlit as st

from core import data, theme
from ui import state as ss
from ui.state import S, sx


def status_pill(vendor: dict) -> None:
    is_open, label = data.open_status(vendor, ss.now(), S.ovs.get(vendor["id"], {}))
    st.markdown(theme.pill(label, is_open), unsafe_allow_html=True)


def reliability(vendor_id: str) -> str:
    s = sx(ss.get_store().vendor_stats, vendor_id, default=None)
    if not s:
        return ""
    bits = []
    if s["rating_n"] >= 3:
        bits.append(f"⭐ {s['rating_avg']:.1f} ({s['rating_n']})")
    if s["delivered"] + s["rejected"] >= 5 and s["completion"] is not None:
        bits.append(f"{s['completion']:.0%} completed")
    if s["avg_accept_min"] is not None and s["total"] >= 5:
        bits.append(f"accepts in ~{max(1, round(s['avg_accept_min']))} min")
    return " · ".join(bits)


def item_desc(vendor: dict, item: dict) -> str:
    if item.get("dynamic") == "daily_special":
        return f"Today: **{data.todays_special(vendor, ss.now()) or 'Chef’s choice'}**"
    return item["description"]


def price_label(item: dict, ov: dict) -> str:
    p = data.min_price(item, ov)
    from_ = len(item["options"]) > 1 or any(o.get("from") for o in item["options"])
    return ("from " if from_ else "") + data.money(p)


def is_simple(item: dict) -> bool:
    return len(item["options"]) == 1 and not item.get("requires_note") and not item.get("requires_choice")


def item_card(vendor: dict, item: dict, prefix: str) -> None:
    ov = S.ovs.get(vendor["id"], {})
    avail = data.is_available(item, ov)
    paused = bool(ov.get("paused"))
    with st.container(border=True):
        st.markdown(f"**{item['name']}**  ·  <span class='price'>{price_label(item, ov)}</span>",
                    unsafe_allow_html=True)
        st.caption(item_desc(vendor, item) + (f"  ·  {vendor['name']}" if prefix == "s" else ""))
        key = f"{prefix}_{vendor['id']}_{item['id']}"
        if not avail:
            st.button("Sold out for now", key=key, disabled=True)
        elif paused:
            st.button("Orders paused", key=key, disabled=True)
        elif is_simple(item):
            st.button("Add +", key=key, type="primary", on_click=ss.quick_add, args=(vendor["id"], item["id"]))
        elif st.button("Customise & add", key=key, type="primary"):
            item_dialog(vendor["id"], item["id"])


@st.dialog("Customise your item")
def item_dialog(vendor_id: str, item_id: str) -> None:
    v = data.get_vendor(vendor_id)
    it = data.get_item(v, item_id)
    ov = S.ovs.get(vendor_id, {})
    k = f"{vendor_id}_{item_id}"
    st.markdown(f"**{it['name']}** · {v['name']}")
    st.caption(item_desc(v, it))
    ops = it["options"]
    oid = st.selectbox("Size", [o["id"] for o in ops], key=f"dlg_opt_{k}",
                       format_func=lambda i: next(f"{o['label']} — {data.money(data.effective_price(it, o, ov))}"
                                                  for o in ops if o["id"] == i)) if len(ops) > 1 else ops[0]["id"]
    note = ""
    if it.get("requires_choice"):
        note = st.radio("Choice", it["requires_choice"], horizontal=True, key=f"dlg_ch_{k}")
    if it.get("requires_note"):
        note = st.text_input(it.get("note_label", "Details"), key=f"dlg_note_{k}", placeholder="e.g. passion + mango")
    qty = st.number_input("Quantity", 1, 50, 1, key=f"dlg_qty_{k}")
    op = data.get_option(it, oid)
    st.markdown(f"**Total: {data.money(data.effective_price(it, op, ov) * qty)}**")
    if st.button("Add to cart", type="primary", key=f"dlg_add_{k}"):
        if it.get("requires_note") and not note.strip():
            st.warning(f"Please tell us: {it.get('note_label', 'details')}")
            return
        ss.add_item(vendor_id, item_id, oid, int(qty), note)
        st.rerun()


def pfield(label: str, key: str, area: bool = False, **kw) -> str:
    """Text input mirrored into the persistent profile (widget state is dropped between pages)."""
    fn = st.text_area if area else st.text_input
    val = fn(label, value=S.profile.get(key, ""), key=f"w_{key}", **kw)
    S.profile[key] = val
    return val
