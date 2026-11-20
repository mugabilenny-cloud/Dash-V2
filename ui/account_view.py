from __future__ import annotations

import json
import secrets
import string

import streamlit as st

from core import data, whatsapp
from ui import components as C
from ui import state as ss
from ui.state import S, sx


def _add_addr() -> None:
    label, addr = S.get("na_label", "").strip(), S.get("na_addr", "").strip()
    if label and addr:
        S.profile["addresses"] = [a for a in S.profile["addresses"] if a["label"] != label] + [
            {"label": label, "address": addr}]
        S.na_label = S.na_addr = ""


def _del_addr(label: str) -> None:
    S.profile["addresses"] = [a for a in S.profile["addresses"] if a["label"] != label]


def _delete_all() -> None:
    store = ss.get_store()
    sx(store.anonymize_orders, whatsapp.norm_phone(S.profile.get("phone", "")))
    sx(store.delete_profile, S.cid)
    for k in list(S.keys()):
        if k not in ("page", "nav"):
            del S[k]
    st.query_params.clear()
    S["_deleted"] = True


def render() -> None:
    if S.pop("_deleted", False):
        st.success("Your data was deleted and your past orders were anonymised.")
    C.pfield("Name", "name")
    C.pfield("Phone (WhatsApp)", "phone")
    areas = data.areas()
    S.profile["area"] = st.selectbox("Preferred area", areas, key="w_area2",
                                     index=areas.index(S.profile["area"]) if S.profile.get("area") in areas else 0)
    st.subheader("Saved addresses")
    for a in S.profile["addresses"]:
        st.markdown(f"**{a['label']}** — {a['address']}")
        st.button("Remove", key=f"da_{a['label']}", on_click=_del_addr, args=(a["label"],))
    st.text_input("Label (Home, Hostel, Work)", key="na_label")
    st.text_input("Address / landmark", key="na_addr")
    st.button("Save address", on_click=_add_addr)
    st.subheader("Your data")
    orders = sx(ss.get_store().orders_for_phone, whatsapp.norm_phone(S.profile.get("phone", "")), default=[])
    export = {"profile": S.profile, "orders": orders}
    st.download_button("Export my data (JSON)", json.dumps(export, indent=2, default=str),
                       file_name="dash-my-data.json", mime="application/json")
    with st.expander("Delete my data"):
        st.caption("Removes your saved profile and cart, and anonymises your name, phone and address on past "
                   "orders. Vendors keep the sales record without your details.")
        if st.checkbox("I understand this can't be undone", key="del_ok"):
            st.button("Delete everything", type="primary", on_click=_delete_all)
