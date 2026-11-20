"""Session state, persistence, navigation and callbacks shared by all views."""
from __future__ import annotations

import json
import os
import re
import secrets
import string
import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import streamlit as st

from core import cart as cartlib
from core import data
from core import orders as ol
from core.store import Store

S = st.session_state
TZ = ZoneInfo("Africa/Kampala")
NAV = ["home", "search", "menu", "cart", "orders", "events", "account", "help", "vendor"]
NAV_FOR = {"checkout": "cart", "confirm": "orders", "track": "orders"}
NAV_LABEL = {"home": "🏠 Home", "search": "🔎 Search", "menu": "🍽️ Menu", "cart": "🛒 Cart",
             "orders": "📦 Orders", "events": "🎉 Events", "account": "👤 Account",
             "help": "ℹ️ Help", "vendor": "🏪 Vendor"}
PROFILE_DEFAULTS = {"name": "", "phone": "", "area": "", "address": "", "addresses": []}


def now() -> datetime:
    return datetime.now(TZ)


@st.cache_resource
def get_store() -> Store:
    path = os.environ.get("DASH_DB") or str(Path(__file__).resolve().parent.parent / "data" / "dash.db")
    try:
        return Store(path)
    except Exception:  # read-only filesystem etc.
        return Store(Path(tempfile.gettempdir()) / "dash.db")


def sx(fn, *args, default=None, **kw):
    """Run a store call; on failure degrade (WhatsApp keeps working) and flag the outage."""
    try:
        return fn(*args, **kw)
    except Exception:
        S["store_ok"] = False
        return default


def log(kind, vendor_id=None, actor=None, **payload):
    sx(get_store().log_event, kind, vendor_id, actor, payload)


# ---- boot / persistence --------------------------------------------------------
def boot() -> None:
    S["store_ok"] = True
    if "booted" not in S:
        S.booted = True
        cid = st.query_params.get("c", "")
        if not re.fullmatch(r"[a-z0-9]{12,32}", cid or ""):
            cid = "".join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(20))
            st.query_params["c"] = cid
        S.cid = cid
        blob = sx(get_store().load_profile, cid, default=None) or {}
        S.cart = blob.get("cart", [])
        S.profile = {**PROFILE_DEFAULTS, **blob.get("profile", {})}
        S.my_orders = blob.get("my_orders", [])
        S.zones = {}
        S.verified = []
        S.page = "home"
        S.nav = "home"
        S.order_vendor = data.vendors()[0]["id"]
        v, t = st.query_params.get("v"), st.query_params.get("track")
        if v in [x["id"] for x in data.vendors()]:
            S.order_vendor, S.page, S.nav = v, "menu", "menu"
        elif t:
            S.track_code, S.page, S.nav = t.upper(), "track", "orders"
    S.ovs = {v["id"]: sx(get_store().get_overrides, v["id"], default={}) or {} for v in data.vendors()}


def refresh_ovs() -> None:
    S.ovs = {v["id"]: sx(get_store().get_overrides, v["id"], default={}) or {} for v in data.vendors()}


def persist() -> None:
    blob = json.dumps({"cart": S.cart, "profile": S.profile, "my_orders": S.my_orders[-30:]}, sort_keys=True)
    if blob != S.get("_last_blob") and S.get("cid"):
        if sx(get_store().save_profile, S.cid, json.loads(blob), default=False) is not False:
            S["_last_blob"] = blob


# ---- navigation ----------------------------------------------------------------
def goto(page: str) -> None:
    """Call ONLY from callbacks (widget state can't change after render)."""
    S.page = page
    S.nav = NAV_FOR.get(page, page)


def nav_changed() -> None:
    S.page = S.nav


def flash(kind: str, msg: str) -> None:
    S["_flash"] = (kind, msg)


# ---- cart helpers --------------------------------------------------------------
def add_item(vendor_id, item_id, option_id, qty=1, note="") -> None:
    cartlib.add_line(S.cart, vendor_id, item_id, option_id, qty, note)
    st.toast(f"Added {qty} × {data.get_item(data.get_vendor(vendor_id), item_id)['name']}", icon="✅")


def quick_add(vendor_id, item_id) -> None:
    it = data.get_item(data.get_vendor(vendor_id), item_id)
    add_item(vendor_id, item_id, it["options"][0]["id"], 1, "")


def cart_summary() -> tuple[int, int]:
    lines = cartlib.resolve(S.cart, S.ovs)
    return cartlib.count(S.cart), sum(l["line_total"] for l in lines)


def reorder_cb(code: str) -> None:
    order = sx(get_store().get_order, code)
    if not order:
        flash("error", "Couldn't load that order.")
        return
    S["_reorder_notes"] = cartlib.reorder(S.cart, order, S.ovs)
    goto("cart")


def vendor_passwords() -> dict:
    cfg = {}
    try:
        cfg.update(dict(st.secrets.get("vendor_passwords", {})))
    except Exception:
        pass
    for v in data.vendors():
        env = os.environ.get("DASH_PW_" + v["id"].upper())
        if env:
            cfg[v["id"]] = env
    return cfg


def app_url() -> str:
    try:
        return str(st.secrets.get("app_url", "")).rstrip("/")
    except Exception:
        return ""


def track_url(code: str) -> str:
    u = app_url()
    return f"{u}/?track={code}" if u else ""


def can_view_order(order: dict) -> bool:
    return order["code"] in S.my_orders or order["code"] in S.verified
