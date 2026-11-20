from pathlib import Path

import pytest

pytest.importorskip("streamlit.testing.v1")
from streamlit.testing.v1 import AppTest  # noqa: E402

APP = str(Path(__file__).resolve().parent.parent / "app.py")


def fresh():
    return AppTest.from_file(APP, default_timeout=30).run()


def goto(at, page):
    at.session_state["page"] = page
    at.session_state["nav"] = {"checkout": "cart", "confirm": "orders", "track": "orders"}.get(page, page)
    return at.run()


@pytest.mark.parametrize("page", ["home", "search", "menu", "cart", "checkout", "confirm", "track", "orders",
                                  "events", "account", "help", "vendor"])
def test_every_page_renders(page):
    at = goto(fresh(), page)
    assert not at.exception, at.exception
    assert not at.error or page in ("track",)


def test_quick_add_checkout_and_vendor_flow():
    at = fresh()
    at.session_state["order_vendor"] = "ji"
    goto(at, "menu")
    at.button(key="m_ji_chips_plain").click().run()
    assert at.session_state["cart"][0]["item_id"] == "chips_plain"
    goto(at, "checkout")
    at.text_input(key="w_name").set_value("Amina").run()
    at.text_input(key="w_phone").set_value("0700123456").run()
    at.text_area(key="w_address").set_value("Near the market").run()
    at.session_state["sm_ji"] = "ASAP"
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from core import data
    open_now = data.open_status(data.get_vendor("ji"), datetime.now(ZoneInfo("Africa/Kampala")))[0]
    at.button(key="place_ji").click().run()
    assert not at.exception, at.exception
    if open_now:
        assert at.session_state["page"] == "confirm"
        code = at.session_state["track_code"]
        goto(at, "track")
        assert not at.exception
        # vendor logs in and sees it
        at2 = fresh()
        goto(at2, "vendor")
        at2.session_state["vd_vendor"] = "hayat"
        at2.run()
        at2.text_input(key="vpw").set_value("testpw").run()
        at2.button[0].click().run()
        assert not at2.exception
    else:
        assert at.session_state["page"] == "checkout"  # blocked: JI closed → must schedule


def test_vendor_login_rejects_wrong_password():
    at = fresh()
    goto(at, "vendor")
    at.text_input(key="vpw").set_value("nope").run()
    at.button[0].click().run()
    assert "vendor_auth" not in at.session_state or not at.session_state["vendor_auth"]


def _login_vendor(vid="hayat"):
    at = fresh()
    goto(at, "vendor")
    at.session_state["vd_vendor"] = vid
    at.run()
    at.text_input(key="vpw").set_value("testpw").run()
    next(b for b in at.button if b.label == "Sign in").click().run()
    return at


def test_end_to_end_order_to_delivery_and_pause():
    from core import data
    from ui.state import get_store  # noqa: F401  (same cached store as the app)

    # customer places a Hayat order (Hayat has no fixed hours -> always open)
    at = fresh()
    at.session_state["order_vendor"] = "hayat"
    goto(at, "menu")
    at.button(key="m_hayat_daily").click().run()      # opens the item dialog (AppTest can't drive dialogs further)
    assert not at.exception, at.exception
    at.session_state["cart"] = [{"vendor_id": "hayat", "item_id": "daily", "option_id": "1l", "qty": 2, "note": ""}]
    goto(at, "checkout")
    at.text_input(key="w_name").set_value("Amina").run()
    at.text_input(key="w_phone").set_value("0700123456").run()
    at.text_area(key="w_address").set_value("Near the market").run()
    at.button(key="place_hayat").click().run()
    assert at.session_state["page"] == "confirm", [e.value for e in at.error]
    code = at.session_state["track_code"]

    # vendor sees and processes it
    v = _login_vendor()
    assert not v.exception, v.exception
    assert any(code in m.value for m in v.markdown)
    for step in ("accepted", "preparing"):
        v.button(key=f"st_{code}_{step}").click().run()
    v.text_input(key=f"rn_{code}").set_value("Joel").run()
    v.text_input(key=f"rp_{code}").set_value("0700111222").run()
    v.button(key=f"st_{code}_out_for_delivery").click().run()
    v.button(key=f"st_{code}_delivered").click().run()
    assert not v.exception

    # customer tracking shows delivered
    goto(at, "track")
    assert any("Delivered" in m.value for m in at.markdown)

    # vendor pauses orders -> new order is blocked, storefront says so
    goto(v, "vendor")
    v.toggle(key="pz_hayat").set_value(True).run()
    at2 = fresh()
    at2.session_state["order_vendor"] = "hayat"
    goto(at2, "menu")
    assert any("paused" in e.value.lower() for e in at2.error)
