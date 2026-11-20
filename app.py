"""Dash — mobile-first food & drink ordering for Ishaka (Hayat Drops + JI Foods).

Run:  streamlit run app.py        Orders: cash on delivery, WhatsApp is the always-on fallback.
"""
from __future__ import annotations

import streamlit as st

from core import theme
from ui import account_view, cart_view, events_view, help_view, home, menu_view
from ui import orders_view, search_view, vendor_view
from ui import state as ss
from ui.state import NAV, NAV_LABEL, S

st.set_page_config(page_title="Dash", page_icon="🍹", layout="centered", initial_sidebar_state="collapsed")
st.markdown(theme.CSS, unsafe_allow_html=True)
ss.boot()

PAGES = {
    "home": home.render, "search": search_view.render, "menu": menu_view.render,
    "cart": cart_view.render_cart, "checkout": cart_view.render_checkout,
    "confirm": orders_view.render_confirm, "track": orders_view.render_track,
    "orders": orders_view.render_orders, "events": events_view.render,
    "account": account_view.render, "help": help_view.render, "vendor": vendor_view.render,
}

n, _ = ss.cart_summary()
st.radio("Navigate", NAV, key="nav", horizontal=True, label_visibility="collapsed", on_change=ss.nav_changed,
         format_func=lambda p: NAV_LABEL[p] + (f" ({n})" if p == "cart" and n else ""))

if "_flash" in S:
    kind, msg = S.pop("_flash")
    getattr(st, kind if kind in ("error", "success", "warning", "info") else "info")(msg)
if not S.get("store_ok", True):
    st.warning("Order tracking is temporarily offline. You can still order — it goes out via WhatsApp.")

try:
    PAGES.get(S.page, home.render)()
except Exception as exc:  # degrade, never block: keep WhatsApp reachable
    st.error("Something went wrong on this page. You can still reach the vendors on WhatsApp below.")
    ss.log("error", None, None, page=str(S.get("page")), error=repr(exc)[:200])

ss.persist()
st.markdown("<div class='fallback'>Always works: WhatsApp Hayat Drops <b>0700 962 284</b> · JI Foods <b>0704 747 008</b></div>",
            unsafe_allow_html=True)
