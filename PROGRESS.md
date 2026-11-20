# PROGRESS — Dash (handoff for another model)

_Updated 2026-11-19. Status: **v0.2 — all 13 pages implemented, 33 tests passing, not yet deployed.** Mobile Money intentionally excluded (cash on delivery only)._
Spec document: `Dash-Specification.docx` (13 pages, principles, lifecycle).

## 1. Goal
Mobile-first Streamlit app (GitHub → Streamlit Cloud) for Ishaka customers to order from Hayat Drops and JI Foods, modelled on DoorDash/Uber Eats/Glovo and **antifragile**: WhatsApp fallback, static catalog, degrade-never-block, stress → data, vendor-owned data, light pages, no lock-in.

## 2. Source facts (flyers; ground truth in data/vendors.json)
**Hayat Drops** — "It's life added to the glass". Specials: Mon Tropical Temptation, Tue Paradise Punch, Wed Golden Elixir, Thu Velvet Sunrise, Fri Nature's Sunrise, Sat Mango Tango, Sun Pineapple Paradise. UGX: 300 ml 1,000 · 1 L 3,500 · 5 L 18,000 · 10 L 35,000 · 20 L 65,000; also 2 L, 3 L, other quantities (no price). Any fruit blended on request. Events: introductions, Eid, Nikkah, weddings, corporate, private parties, training. Every day, mobile, door-to-door. WhatsApp 0700 962 284 | 0762 249 091.
**JI Foods** — Chips plain 3,000+ · Pilau plain 2,000+ · Chips w/ liver or beef 6,000 · Pilau w/ liver or beef 5,000. Abuja stage. 0704747008. Open daily from 6:30 pm. Free delivery in "evening-safe and walkable distances"; "1,000 Jaj" for rest of Ishaka.

## 3. Architecture
```
app.py                 entry: nav (radio), flash/outage banners, page dispatch inside try/except (degrade, never block)
core/  (no Streamlit)  data.py (catalog+override-aware helpers, hours/status) · cart.py · orders.py (lifecycle rules,
                       receipt) · store.py (SQLite) · whatsapp.py (links/messages/phone norm) · search.py (difflib)
                       · auth.py (vendor passwords) · theme.py (CSS)
ui/                    state.py (session, boot/persist, goto, callbacks) · components.py (item card, dialog, pfield)
                       home · search_view · menu_view · cart_view (cart+checkout+place order) · orders_view
                       (confirm/track/history) · events_view · account_view · help_view · vendor_view
data/vendors.json      menu, zones, hours, phones, areas, banners (single source of truth)
tests/                 test_core, test_store, test_app_smoke (AppTest, incl. order→vendor→delivered e2e)
```
**Pages ↔ files:** 1 Home=home · 2 Search=search_view · 3 Storefront=menu_view · 4 Item dialog=components.item_dialog · 5 Cart/6 Checkout=cart_view · 7 Confirm/8 Track/9 History=orders_view · 10 Account=account_view · 11 Events=events_view · 12 Vendor=vendor_view · 13 Help=help_view.

## 4. Key design decisions
- **State:** `S.page` + horizontal radio `nav` (set `S.page`/`S.nav` only via `ss.goto` inside callbacks). Streamlit drops widget state for unrendered widgets → persistent data lives in `S.profile`/`S.cart` dicts (`pfield` mirrors inputs).
- **Persistence:** private cart id in URL `?c=…` → `profiles` table holds cart, profile, my_orders (survives refresh). Deep links: `?v=hayat` (storefront), `?track=D-XXXXX` (tracking, phone-verified).
- **Prices never stored in cart**; resolved from catalog + vendor overrides each render. Orders snapshot lines/prices.
- **Overrides** (per vendor, JSON): `price {"item|opt": int}`, `unavailable [ids]`, `paused`, `closed_today`, `hours {open,close}`, `zone_fee {zone: int|null}`. Every change → `audit` row; Undo last restores `old`.
- **Order lifecycle:** sent → accepted → preparing → out_for_delivery|ready → delivered; terminal rejected/cancelled; customer cancel only at `sent` (rules in `core/orders.allowed`, enforced in `Store.set_status`).
- **Antifragile mechanics:** store failures caught by `sx()` → banner + WhatsApp-only order path; 10-min acceptance timeout → nudge + `timeout` event; failed searches → `search_miss` events + ask-vendor WhatsApp; issues → `issue` events in vendor reports; per-phone rate limits (6 orders/h, 5 reports/h); vendor login lockout after 5 tries/session.
- **Scheduling:** ASAP or 30 min–7 days ahead; validated against hours/pause/closed-today at the target time. Closed vendors accept scheduled orders only.
- **Payment:** cash on delivery / cash at pickup only (stated in UI, receipts, WhatsApp messages).
- **Privacy:** delete-my-data anonymises past orders; export JSON; vendor passwords only in secrets/env.

## 5. Done
All 13 pages; vendor dashboard (live orders w/ 15 s auto-refresh, rider details, WhatsApp-to-customer, menu/stock/price edits, pause, closed today, hours, fees, reports, CSV, audit+undo); order log; tracking; ratings/reliability badges; reorder with price-change warnings; search; events enquiries; tests; CI.

## 6. Known limitations / honest caveats
1. **Ephemeral storage on Streamlit Cloud** → orders reset on restart. Next job: hosted DB backend for `core/store.py`.
2. No push notifications: vendors must keep dashboard open (auto-refresh) and/or receive the WhatsApp message customers send.
3. Dialog (item customise) can't be driven by Streamlit AppTest; covered by manual test only.
4. Cart-id URL is a bearer link; anyone holding it sees that profile. Order tracking additionally needs phone match.
5. Not implemented: "use my current location", Luganda/Runyankore translations (need native review), vendor-created items/photos, event deposits/calendar, Mobile Money.

## 7. Assumptions to confirm with owner
"1,000 Jaj" = UGX 1,000 · JI closing 23:00 placeholder · Hayat delivery fee "agreed on WhatsApp" · 2 L/3 L Hayat sizes unpriced (omitted) · area list (Abuja stage, Ishaka town, KIU Western Campus area, Other) · policy/FAQ wording is draft · app name Dash.

## 8. Roadmap
1. Deploy; set secrets; pilot with both vendors. 2. Durable DB (Supabase). 3. Vendor alert (WhatsApp Business API/SMS) for new orders. 4. Photos + vendor-managed items. 5. Mobile Money (later, as an extra payment option). 6. Translations. 7. Weekly vendor report email/WhatsApp.

## 9. Conventions
Edit menu data in JSON; add tests with features; keep `core/` free of Streamlit; callbacks for navigation; run `pytest -q` before commit; avoid `use_container_width` (CSS makes buttons full width); `st.link_button` can't be in forms.
