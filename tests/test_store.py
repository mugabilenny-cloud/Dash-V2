import time

import pytest

from core.store import Store


def make_order(code="D-AAAAA", vendor="ji", zone="near", phone="700000001"):
    return {"code": code, "created_at": time.time(), "vendor_id": vendor, "name": "Amina", "phone": "0" + phone,
            "phone_norm": phone, "address": "Market", "zone_id": zone, "zone_label": "Near", "payment": "cod",
            "scheduled_for": "", "notes": "", "lines": [{"item_name": "Chips", "qty": 1, "line_total": 3000}],
            "subtotal": 3000, "fee": 0, "total": 3000, "is_minimum": True}


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path / "t.db")


def test_order_lifecycle(store):
    store.create_order(make_order())
    assert store.get_order("D-AAAAA")["status"] == "sent"
    store.set_status("D-AAAAA", "accepted")
    store.set_status("D-AAAAA", "preparing")
    o = store.set_status("D-AAAAA", "out_for_delivery", "Joel", "0700111222")
    assert o["rider_name"] == "Joel" and [h["s"] for h in o["history"]][-1] == "out_for_delivery"
    with pytest.raises(ValueError):
        store.set_status("D-AAAAA", "sent")
    store.set_status("D-AAAAA", "delivered")
    with pytest.raises(ValueError):
        store.set_status("D-AAAAA", "cancelled")


def test_cancel_only_before_accept(store):
    store.create_order(make_order("D-BBBBB"))
    store.set_status("D-BBBBB", "cancelled")
    store.create_order(make_order("D-CCCCC"))
    store.set_status("D-CCCCC", "accepted")
    with pytest.raises(ValueError):
        store.set_status("D-CCCCC", "cancelled")


def test_rating_and_stats(store):
    for i in range(3):
        store.create_order(make_order(f"D-R000{i}"))
        for s in ("accepted", "preparing", "out_for_delivery", "delivered"):
            store.set_status(f"D-R000{i}", s)
    assert store.rate_order("D-R0000", 5, "great") and not store.rate_order("D-R0000", 1)
    store.create_order(make_order("D-NOPE1"))
    assert not store.rate_order("D-NOPE1", 5)
    store.set_status("D-NOPE1", "rejected")
    s = store.vendor_stats("ji")
    assert s["delivered"] == 3 and s["rejected"] == 1 and s["completion"] == 0.75
    assert s["rating_avg"] == 5 and s["avg_accept_min"] is not None


def test_overrides_audit_undo(store):
    store.set_override("ji", "paused", True)
    store.set_override("ji", "price", {"chips_plain|std": 3500})
    assert store.get_overrides("ji") == {"paused": True, "price": {"chips_plain|std": 3500}}
    store.set_override("ji", "paused", True)  # no-op, no audit row
    assert len(store.audit_list("ji")) == 2
    assert store.undo_last("ji")["key"] == "price"
    assert store.get_overrides("ji") == {"paused": True}
    store.undo_last("ji")
    assert store.get_overrides("ji") == {}
    assert store.undo_last("ji") is None


def test_phone_lookup_rate_anonymize(store):
    store.create_order(make_order("D-P0001"))
    store.create_order(make_order("D-P0002"))
    assert len(store.orders_for_phone("700000001")) == 2
    assert store.count_recent_orders("700000001") == 2
    store.anonymize_orders("700000001")
    assert store.orders_for_phone("700000001") == [] and store.get_order("D-P0001")["name"] == "(deleted)"


def test_events_profiles(store):
    store.log_event("issue", "ji", "7000", {"tag": "Late"})
    store.log_event("search_miss", None, "7000", {"query": "burger"})
    assert len(store.events("issue", "ji")) == 1 and store.events("issue", "hayat") == []
    assert store.count_events("issue", "7000") == 1
    store.save_profile("abc", {"cart": [1]})
    assert store.load_profile("abc") == {"cart": [1]}
    store.delete_profile("abc")
    assert store.load_profile("abc") is None
