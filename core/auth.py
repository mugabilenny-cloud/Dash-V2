"""Vendor dashboard authentication (shared-secret per vendor). Passwords live in Streamlit
secrets ([vendor_passwords] hayat = "...") or env vars DASH_PW_<VENDORID>, never in the repo."""
from __future__ import annotations

import hmac

MAX_ATTEMPTS = 5


def configured(vendor_id: str, config: dict) -> bool:
    return bool(config.get(vendor_id))


def check(vendor_id: str, attempt: str, config: dict) -> bool:
    secret = config.get(vendor_id)
    return bool(secret) and hmac.compare_digest(str(secret).encode(), (attempt or "").encode())
