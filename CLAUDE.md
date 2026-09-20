# Agent / maintainer notes for SahakarSetu (SIH 2026).
# Public docs for humans: README.md, docs/ARCHITECTURE.md, docs/DEVELOPMENT.md, docs/DEPLOY.md

Owner: Aadi Jain (GitHub Aadi-j08). FastAPI + SQLite + React PWA. Local phone+password
accounts per portal; no payments / external APIs.

## Run

```
uvicorn app.main:app --host 127.0.0.1 --port 8000
cd frontend && npm run dev
```

Council code default `SABHA-2026`. Tests: `pytest -q`. Frontend: `npm run typecheck`.

## Known incomplete

- Sabha Announcements page: UI placeholder, no table/API yet.
- Unused landing photos may remain under `frontend/public/img/` (see its README).
- Horizontal scale (multi-worker): needs Postgres + Redis for `events.py` bus.

## Deploy

See docs/DEPLOY.md. Pages + Fly; `VITE_API_BASE_URL`; CORS + cookie flags.

## Conventions

- Additive DB migrations only; don’t rebuild tables.
- Booking-flow core stays stable unless asked.
- User commits themselves; no force push; no AI co-author trailers on commits.
