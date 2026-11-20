from __future__ import annotations

import streamlit as st

from core import data, theme, whatsapp
from ui import components as C
from ui import state as ss
from ui.state import S


def render() -> None:
    hv = data.get_vendor("hayat")
    st.markdown(theme.hero("Events & bulk orders", "Weddings, Nikkah, Eid, corporate & private parties.",
                           hv["accent"]), unsafe_allow_html=True)
    st.write("We serve at: " + ", ".join(hv["serves"]) + ".")
    C.pfield("Your name", "name")
    C.pfield("Phone (WhatsApp)", "phone")
    etype = st.selectbox("Event type", ["Introduction ceremony", "Wedding", "Nikkah", "Eid celebration",
                                        "Corporate event", "Private party", "Juice-making training", "Other"])
    edate = st.date_input("Event date", min_value=ss.now().date())
    venue = st.text_input("Venue / location", key="e_venue")
    litres = st.number_input("Approx. litres needed", 1, 1000, 20, step=5)
    budget = st.selectbox("Budget range (UGX)", ["Not sure yet", "Under 100,000", "100,000 – 300,000",
                                                 "300,000 – 1,000,000", "Over 1,000,000"])
    flav = st.text_input("Flavours / fruits wanted (optional)", key="e_flav")
    ok = S.profile["name"].strip() and whatsapp.valid_phone(S.profile["phone"]) and venue.strip()
    if not ok:
        st.caption("Add your name, a valid phone and the venue to continue.")
    msg = whatsapp.event_message(hv, S.profile["name"], S.profile["phone"], etype, edate.strftime("%d %b %Y"),
                                 int(litres), venue, flav, budget)

    def _log():
        ss.log("event_enquiry", "hayat", whatsapp.norm_phone(S.profile["phone"]), type=etype,
               date=edate.isoformat(), venue=venue, litres=int(litres), budget=budget)

    st.link_button("Request a quote on WhatsApp", whatsapp.link(hv["whatsapp"], msg), type="primary", disabled=not ok)
    st.button("Save my enquiry (so Hayat Drops can follow up)", disabled=not ok, on_click=_log)
