from __future__ import annotations

import streamlit as st

from core import data, whatsapp
from core.search import search
from ui import components as C
from ui import state as ss
from ui.state import S


def _view_menu(vid: str) -> None:
    S.order_vendor = vid
    ss.goto("menu")


def render() -> None:
    q = st.text_input("Search dishes, drinks or vendors", key="search_q", placeholder="e.g. chips, mango, pilau")
    c1, c2 = st.columns(2)
    open_only = c1.toggle("Open now", key="f_open")
    free = c2.toggle("Free delivery", key="f_free")
    sort = st.selectbox("Sort by", ["relevance", "price_low", "price_high"], key="f_sort",
                        format_func={"relevance": "Best match", "price_low": "Price: low to high",
                                     "price_high": "Price: high to low"}.get)
    res = search(q, S.ovs, ss.now(), open_only, free, sort)
    for v in res["vendors"]:
        with st.container(border=True):
            st.markdown(f"**{v['emoji']} {v['name']}** — {v['tagline']}")
            st.button("Open menu", key=f"sv_{v['id']}", on_click=_view_menu, args=(v["id"],))
    for r in res["items"]:
        C.item_card(r["vendor"], r["item"], "s")
    if q.strip() and not res["items"] and not res["vendors"]:
        st.warning(f"Nothing matched “{q}”.")
        if S.get("_miss") != q.lower():
            S["_miss"] = q.lower()
            ss.log("search_miss", actor=whatsapp.norm_phone(S.profile.get("phone", "")), query=q.strip()[:80])
        st.markdown("**Can't find it? Ask a vendor — they may be able to make it.**")
        vid = st.selectbox("Ask", [v["id"] for v in data.vendors()], key="miss_v",
                           format_func=lambda i: data.get_vendor(i)["name"])
        v = data.get_vendor(vid)
        st.link_button(f"Ask {v['name']} on WhatsApp",
                       whatsapp.link(v["whatsapp"], whatsapp.custom_request_message(v["name"], q, S.profile.get("name", ""))))
