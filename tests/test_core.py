from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from core import auth, data
from core import cart as cl
from core import orders as ol
from core import search, whatsapp

TZ = ZoneInfo("Africa/Kampala")


def test_catalog_integrity():
    ids = [v["id"] for v in data.vendors()]
    assert len(ids) == len(set(ids))
    for v in data.vendors():
        assert v["whatsapp"].startswith("256")
        zids = [z["id"] for z in v["delivery_zones"]]
        assert len(zids) == len(set(zids)) and v["default_zone"] in zids
        for cat in v["categories"]:
            for it in cat["items"]:
                oids = [o["id"] for o in it["options"]]
                assert oids and len(oids) == len(set(oids))
                assert all(isinstance(o["price"], int) and o["price"] > 0 for o in it["options"])


def test_prices_match_flyers():
    h = data.get_vendor("hayat")
    assert {o["id"]: o["price"] for o in data.get_item(h, "daily")["options"]} == {
        "300ml": 1000, "1l": 3500, "5l": 18000, "10l": 35000, "20l": 65000}
    j = data.get_vendor("ji")
    p = lambda i: data.get_item(j, i)["options"][0]["price"]  # noqa: E731
    assert (p("chips_plain"), p("chips_meat"), p("pilau_plain"), p("pilau_meat")) == (3000, 6000, 2000, 5000)


def test_cart_merge_remove_cap():
    c = []
    cl.add_line(c, "ji", "chips_plain", "std", 1)
    cl.add_line(c, "ji", "chips_plain", "std", 2)
    assert len(c) == 1 and c[0]["qty"] == 3
    cl.add_line(c, "ji", "chips_meat", "std", 1, "Liver")
    cl.add_line(c, "ji", "chips_meat", "std", 1, "Beef")
    assert len(c) == 3
    cl.set_qty(c, 0, 0)
    assert cl.count(c) == 2
    cl.add_line(c, "ji", "pilau_plain", "std", 999)
    assert c[-1]["qty"] == cl.MAX_QTY


def test_totals_fees_and_overrides():
    c = []
    cl.add_line(c, "ji", "pilau_meat", "std", 2, "Beef")
    ji = data.get_vendor("ji")
    lines = cl.group_by_vendor(c)["ji"]
    assert cl.totals(lines, ji, "near")["total"] == 10000
    assert cl.totals(lines, ji, "rest")["total"] == 11000
    ovs = {"ji": {"price": {"pilau_meat|std": 5500}, "zone_fee": {"rest": 2000}, "unavailable": ["pilau_meat"]}}
    lines = cl.group_by_vendor(c, ovs)["ji"]
    assert lines[0]["unit_price"] == 5500 and lines[0]["available"] is False
    assert cl.totals(lines, ji, "rest", ovs["ji"])["total"] == 13000
    h = data.get_vendor("hayat")
    c2 = []
    cl.add_line(c2, "hayat", "daily", "1l", 2)
    t = cl.totals(cl.group_by_vendor(c2)["hayat"], h, "town")
    assert t["fee_pending"] and t["subtotal"] == 7000


def test_missing_item_flagged():
    lines = cl.resolve([{"vendor_id": "ji", "item_id": "gone", "option_id": "x", "qty": 1, "note": ""}])
    assert lines[0]["missing"] and not lines[0]["available"]


def test_reorder_notes():
    order = {"vendor_id": "ji", "lines": [
        {"item_id": "chips_plain", "option_id": "std", "item_name": "Chips plain", "qty": 2, "note": "", "unit_price": 2500},
        {"item_id": "pilau_plain", "option_id": "std", "item_name": "Pilau plain", "qty": 1, "note": "", "unit_price": 2000}]}
    c = []
    notes = cl.reorder(c, order, {"ji": {"unavailable": ["pilau_plain"]}})
    assert cl.count(c) == 2 and any("sold out" in n for n in notes) and any("now UGX 3,000" in n for n in notes)


def test_hours_pause_and_windows():
    ji, hy = data.get_vendor("ji"), data.get_vendor("hayat")
    now = datetime(2026, 11, 18, 19, 0, tzinfo=TZ)
    assert data.open_status(ji, now)[0] is True
    assert data.open_status(ji, now.replace(hour=12))[0] is False
    assert data.open_status(hy, now)[0] is None
    assert data.open_status(ji, now, {"paused": True})[0] is False
    assert data.open_status(ji, now, {"hours": {"open": "20:00", "close": "22:00"}})[0] is False
    assert ol.window_error(ji, now, {}, now) is None
    assert "closed" in ol.window_error(ji, now.replace(hour=10), {}, now)
    assert "not taking" in ol.window_error(ji, now, {"paused": True}, now)
    assert "closed today" in ol.window_error(ji, now, {"closed_today": True}, now)
    assert ol.window_error(ji, now + timedelta(days=1), {"closed_today": True}, now) is None
    assert data.todays_special(hy, datetime(2026, 11, 18)) == "Golden Elixir"


def test_schedule_validation():
    now = datetime(2026, 11, 18, 12, 0, tzinfo=TZ)
    assert ol.validate_schedule(now + timedelta(minutes=10), now)
    assert ol.validate_schedule(now + timedelta(hours=2), now) is None
    assert ol.validate_schedule(now + timedelta(days=9), now)


def test_transitions():
    o = {"status": "sent", "zone_id": "near"}
    assert ol.allowed(o) == ["accepted", "rejected", "cancelled"]
    assert ol.vendor_allowed(o) == ["accepted", "rejected"]
    assert ol.allowed({"status": "preparing", "zone_id": "near"}) == ["out_for_delivery", "rejected"]
    assert ol.allowed({"status": "preparing", "zone_id": "pickup"}) == ["ready", "rejected"]
    assert ol.allowed({"status": "delivered", "zone_id": "near"}) == []
    assert ol.is_overdue({"status": "sent", "created_at": 0}, 1000)
    assert not ol.is_overdue({"status": "accepted", "created_at": 0}, 1000)
    assert ol.new_code().startswith("D-") and len(ol.new_code()) == 7


def test_whatsapp():
    assert whatsapp.norm_phone("+256 700 962 284") == whatsapp.norm_phone("0700962284") == "700962284"
    assert whatsapp.to_intl("0700962284") == "256700962284"
    assert whatsapp.to_intl("700962284") == "256700962284"
    assert not whatsapp.valid_phone("123")
    ji = data.get_vendor("ji")
    order = {"code": "D-AAAAA", "lines": [{"qty": 1, "item_name": "Chips with liver or beef", "option_label": "Portion",
                                          "note": "Liver", "line_total": 6000, "is_minimum": False}],
             "subtotal": 6000, "fee": 1000, "total": 7000, "is_minimum": False, "zone_id": "rest",
             "zone_label": "Rest of Ishaka", "scheduled_for": "", "name": "Amina", "phone": "0700000000",
             "address": "Near market", "notes": ""}
    msg = whatsapp.order_message(order, ji)
    assert "D-AAAAA" in msg and "UGX 7,000" in msg and "Cash on delivery" in msg and "Near market" in msg
    assert "\n" not in whatsapp.link(ji["whatsapp"], msg)


def test_search():
    now = datetime(2026, 11, 18, 12, 0, tzinfo=TZ)
    assert len(search.search("chps", {}, now)["items"]) == 2
    assert search.search("zzzzz", {}, now)["items"] == []
    r = search.search("", {}, now, open_only=True)  # JI closed at noon, Hayat has no hours
    assert {x["vendor"]["id"] for x in r["items"]} == {"hayat"}
    r = search.search("", {}, now, sort="price_low")["items"]
    assert [x["price"] for x in r] == sorted(x["price"] for x in r)
    assert search.search("hayat", {}, now)["vendors"][0]["id"] == "hayat"


def test_auth():
    cfg = {"hayat": "s3cret"}
    assert auth.check("hayat", "s3cret", cfg) and not auth.check("hayat", "x", cfg)
    assert not auth.check("ji", "", cfg) and not auth.configured("ji", cfg)
