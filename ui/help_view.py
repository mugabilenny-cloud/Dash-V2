from __future__ import annotations

import streamlit as st

from core import data, whatsapp
from ui import state as ss
from ui.state import S, sx

FAQ = [
    ("How do I pay?", "Cash on delivery (or cash at pickup). There is no online payment in Dash yet."),
    ("Can I cancel?", "Yes, from the order's tracking page until the vendor accepts it. After that, call the vendor."),
    ("What if an item is wrong or late?", "Use “Report a problem” below. Your report goes to the vendor and is reviewed."),
    ("Why is my total marked “minimum”?", "Some items are priced “and above”. The vendor confirms the final amount."),
    ("What happens to my details?", "Your name, phone and address are used only to fulfil orders. You can export or delete them in Account."),
]


def _report(tag: str, details: str) -> None:
    code = (S.get("rp_code") or "").strip().upper()
    phone = whatsapp.norm_phone(S.profile.get("phone", ""))
    if ss.sx(ss.get_store().count_events, "issue", phone or "anon", default=0) >= 5:
        ss.flash("error", "Too many reports in the last hour. Please call the vendor.")
        return
    vid = None
    if code:
        o = sx(ss.get_store().get_order, code)
        vid = o["vendor_id"] if o else None
    ss.log("issue", vid, phone or "anon", tag=tag, code=code, details=details[:500])
    ss.flash("success", "Thanks — your report was sent to the vendor team.")
    S.report_code = ""


def render() -> None:
    st.subheader("Vendors")
    for v in data.vendors():
        ov = S.ovs.get(v["id"], {})
        with st.container(border=True):
            st.markdown(f"**{v['emoji']} {v['name']}**")
            st.write(f"📍 {v['location']}  \n🕒 {data.hours_label(v, ov)}  \n📞 " + " · ".join(v["phones"]))
            st.caption(v["delivery_note"])
            st.link_button("Chat on WhatsApp", f"https://wa.me/{v['whatsapp']}")
    st.subheader("FAQ")
    for q, a in FAQ:
        with st.expander(q):
            st.write(a)
    st.subheader("Report a problem")
    if S.get("report_code"):
        S["rp_code"] = S.pop("report_code")
    st.text_input("Order code (optional)", key="rp_code")
    tag = st.selectbox("What went wrong?", ["Late", "Wrong item", "Quality", "Rude service", "Other"], key="rp_tag")
    details = st.text_area("Details", key="rp_details", height=80)
    st.button("Send report", on_click=_report, args=(tag, details), disabled=not details.strip())
    with st.expander("Policies (draft)"):
        st.write("**Cancellation:** free until the vendor accepts. **Refunds:** no online payments are taken, so "
                 "issues are resolved directly with the vendor. **Delivery:** fees and zones are set by each vendor. "
                 "**About Dash:** a local ordering app for Ishaka vendors.")
