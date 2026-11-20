from __future__ import annotations

import streamlit as st

from core import data
from ui import components as C
from ui import state as ss
from ui.state import S


def render() -> None:
    vid = st.radio("Vendor", [v["id"] for v in data.vendors()], horizontal=True, key="order_vendor",
                   format_func=lambda i: f"{data.get_vendor(i)['emoji']} {data.get_vendor(i)['name']}",
                   label_visibility="collapsed")
    v = data.get_vendor(vid)
    ov = S.ovs.get(vid, {})
    st.markdown(f"### {v['name']}")
    st.caption(v["tagline"])
    C.status_pill(v)
    rel = C.reliability(vid)
    st.caption(" · ".join(x for x in [rel, f"📍 {v['location']}", "📞 " + " / ".join(v["phones"])] if x))
    if ov.get("paused"):
        st.error("This vendor has paused orders for now. Please check back soon.")
    elif data.open_status(v, ss.now(), ov)[0] is False:
        st.warning("Closed right now. You can still schedule an order for later at checkout.")
    st.caption(v["delivery_note"])
    for cat in v["categories"]:
        st.subheader(cat["name"])
        for it in cat["items"]:
            C.item_card(v, it, "m")
    n, total = ss.cart_summary()
    if n:
        st.button(f"🛒 View cart · {n} items · {data.money(total)}", key="menu_cart", type="primary",
                  on_click=ss.goto, args=("cart",))
    st.link_button(f"Chat with {v['name']} on WhatsApp", f"https://wa.me/{v['whatsapp']}")
