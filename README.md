# SahakarSetu

A cooperative-run platform that matches household service requests with local
skilled workers **fairly**, lets workers declare availability **by voice**
(Hindi / English / Hinglish), and **forecasts demand** so the cooperative can
plan. FastAPI + SQLite backend, React PWA frontend. No login, no real
payments — a working prototype.

## Run it

```bash
# backend (Python 3.13, one-time setup)
py -3.13 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt

# frontend (Node 20+, one-time setup)
cd frontend && npm install && npm run build && cd ..

# start
.venv\Scripts\python -m uvicorn app.main:app --reload --reload-dir app
```

| Open | What |
|---|---|
| http://127.0.0.1:8000/app/ | the web app: landing page + three portals — **Ghar** (customer), **Kaam** (worker), **Sabha** (cooperative admin) |
| http://127.0.0.1:8000/docs | interactive API docs |

While working on the UI, run `npm run dev` inside `frontend/` and open
http://127.0.0.1:5173/app/ — it hot-reloads and proxies API calls to :8000.

The SQLite file is `sahakarsetu.db` in the project root (override with the
`SAHAKARSETU_DB` environment variable). It is created on first start.

## Tests

```bash
.venv\Scripts\python -m pytest -q        # backend: 78 tests
cd frontend && npm run typecheck          # frontend: TypeScript
```

## Layout

```
app/
  main.py                  FastAPI app: workers, bookings, voice, forecast, serves /app
  database.py              SQLite setup (workers, bookings, assignments)
  repository.py            DB access functions
  schemas.py               Pydantic contracts
  services/
    allocation.py          fair allocation engine (proximity · fairness · rating · availability)
    voice.py               voice availability parser (offline, rule-based)
    forecast.py            weekday-seasonal demand forecast
    booking_flow.py        assign → complete (85/10/5 ledger) → rating; admin dashboard
    allocation_bridge.py   SQLite rows → allocation engine
    ledger.py              mock payment split, in paise
  routers/booking_flow.py  the booking-lifecycle endpoints
  booking_flow_db.py       booking-flow tables, atomic transactions
frontend/                  Vite + React + TypeScript PWA: landing page + Ghar / Kaam / Sabha portals
tests/                     pytest suite
docs/
  INTEGRATION.md           notes on the booking-flow module
  design/                  screen mockups (Direction A "Warm civic"); design/portals/ = landing + portal identities
```

## How the pieces fit

1. A **customer** books a service (trade, place, time).
2. The **allocation engine** ranks eligible workers: 30% proximity, 35% fairness
   (fewest jobs this week), 20% rating, 15% declared availability — and explains
   its pick in plain language.
3. The **admin** (or an automated step) assigns the top pick; the worker sees the
   job and, when done, enters the bill.
4. Completion writes a **ledger**: 85% worker, 10% cooperative welfare fund,
   5% platform, exact to the paisa. The customer rates the job.
5. **Workers** keep availability current by speaking to the app; the
   **forecast** tells the cooperative how many workers to keep on call each day.
