# Dash

Mobile-first food & drink ordering app for **Hayat Drops** (juice) and **JI Foods** (chips & pilau) in Ishaka, Uganda.
Cash on delivery. WhatsApp is the always-on fallback if anything fails.

**Customer pages:** Home · Search · Vendor menu (+ item dialog) · Cart · Checkout · Confirmation · Tracking · Orders/Reorder · Events · Account · Help
**Vendor dashboard:** live orders, menu & stock, hours/fees/pause, reports + CSV, change history with undo.

## Run locally
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # set vendor passwords
streamlit run app.py
pytest -q
```

## Deploy (GitHub → Streamlit Community Cloud)
1. Push this folder to GitHub (`main`).
2. share.streamlit.io → New app → repo, branch `main`, file `app.py`.
3. App settings → **Secrets**: paste the contents of `secrets.toml.example` with real passwords.
4. On a phone: browser menu → **Add to Home screen**.

**Important:** Streamlit Cloud's disk is ephemeral. Orders/overrides (SQLite in `data/dash.db`) reset when the app restarts.
Fine for a pilot; for production swap `core/store.py` for a hosted DB (Supabase/Postgres) with the same methods.

## Update the menu
Static menu: `data/vendors.json`. Day-to-day changes (price, sold out, hours, fees, pause) are made by vendors in the dashboard.

See `PROGRESS.md` for architecture, decisions, assumptions and roadmap.
