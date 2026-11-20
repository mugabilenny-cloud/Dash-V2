from __future__ import annotations

import streamlit as st

from core import data, theme
from ui import components as C
from ui import state as ss
from ui.state import S, sx


def _view_menu(vid: str) -> None:
    S.order_vendor = vid
    ss.goto("menu")


def _browse() -> None:
    v = S.get("w_cat")
    if v == "Events":
        ss.goto("events")
    elif v:
        S.search_q = v
        ss.goto("search")
    S.w_cat = None


def render() -> None:
    P, n = S.profile, ss.now()
    st.markdown(theme.hero("Dash", "Fresh juice & hot food, delivered in Ishaka.", "#1B7F3B"), unsafe_allow_html=True)
    areas = data.areas()
    P["area"] = st.selectbox("📍 Deliver to", areas, index=areas.index(P["area"]) if P.get("area") in areas else 0,
                             key="w_area")
    for b in data.banners():
        st.info(b)
    st.pills("Browse", ["Juice", "Chips", "Pilau", "Events"], key="w_cat", on_change=_browse)

    past = [o for o in sx(ss.get_store().get_orders, S.my_orders[-8:], default=[]) if o["status"] == "delivered"][:3]
    if past:
        st.markdown("**Order again**")
        for o in past:
            st.button(f"↻ {data.get_vendor(o['vendor_id'])['name']} · {o['code']} · {data.money(o['total'])}",
                      key=f"ra_{o['code']}", on_click=ss.reorder_cb, args=(o["code"],))

    for v in data.vendors():
        ov = S.ovs.get(v["id"], {})
        with st.container(border=True):
            st.markdown(f"### {v['emoji']} {v['name']}")
            st.caption(v["tagline"])
            C.status_pill(v)
            rel = C.reliability(v["id"])
            if rel:
                st.caption(rel)
            sp = data.todays_special(v, n)
            if sp:
                st.markdown(f"**Today's special:** {sp}")
            st.write(v["note"])
            st.caption(f"📍 {v['location']}")
            st.button(f"View {v['name']} menu", key=f"vm_{v['id']}", type="primary",
                      on_click=_view_menu, args=(v["id"],))
