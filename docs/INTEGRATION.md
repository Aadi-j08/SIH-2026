# Booking flow backend: integration notes

New files only. Nothing here replaces `allocation.py`, `voice.py`, `forecast.py`,
`database.py`, `repository.py` or `schemas.py`.

## 1. Copy the files into your project

```
app/booking_flow_db.py          connections, atomic transactions, schema additions
app/booking_flow_schemas.py     request/response models for the new endpoints
app/routers/__init__.py         empty (skip if you already have one)
app/routers/booking_flow.py     the five endpoints
app/services/allocation_bridge.py   rows -> ServiceRequest -> recommend_workers()
app/services/booking_flow.py    assign / detail / complete / rating / dashboard
app/services/ledger.py          mock 85/10/5 split, in paise
tests/test_booking_flow.py      tests for every new endpoint
```

## 2. Add two lines to app/main.py

```python
from app.routers.booking_flow import router as booking_flow_router
app.include_router(booking_flow_router)   # after app = FastAPI(...)
```

## 3. Check the "Adapt to your project" block at the top of the test file

It assumes `app.main.app`, `database.DB_PATH`, `database.init_db()`, and the
request bodies for your existing `POST /workers` and `POST /bookings`.
Edit those few lines if your names differ. Then run:

```
.venv/bin/python -m pytest -q
```

## What gets added to the database (automatically, on first request)

- New tables: `payment_ledger`, `booking_ratings`
- `assignments`: `score_breakdown`, `explanation` (and `allocation_score` only if no score column exists)
- `bookings`: `completed_at`
- `workers`: `base_rating`, `rating_count` (only if a rating column exists)

Existing rows and columns are never changed or dropped.

## Where the code adapts to your naming

- `allocation_bridge.SYNONYMS`: if a booking column is spelled differently
  from a `ServiceRequest` field (e.g. `service_type` vs `trade`), add it here.
- `booking_flow_db._PATH_ATTRIBUTES` / `_CONNECTION_FACTORIES`: how the SQLite
  file is found in `app/database.py`.
- If the bridge can't match your data, the endpoint returns a 500 whose message
  names the missing field; no data is written.

## Behaviour

| Endpoint | Allowed from | Result | Errors |
|---|---|---|---|
| POST /bookings/{id}/assign | pending | assigned, jobs_this_week +1 | 404, 409 (not pending / no eligible worker) |
| GET /bookings/{id} | any | booking + assignment + ledger + rating | 404 |
| POST /bookings/{id}/complete `{"amount": 500}` | assigned | completed, 3 ledger rows | 404, 409, 422 |
| POST /bookings/{id}/rating `{"rating": 1-5}` | completed, once | worker average updated | 404, 409, 422 |
| GET /admin/dashboard | any | counts, money, ratings, fairness, engagement days | none |

Assign, complete and rating each run in one `BEGIN IMMEDIATE` transaction:
all writes succeed together or none happen. Change the split in
`app/services/ledger.py` (`SPLIT_PERCENT`).
