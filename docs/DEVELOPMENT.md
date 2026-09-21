# Development guide

How to change the code **before** production, safely.

## Daily loop

1. Run API: `uvicorn app.main:app --host 127.0.0.1 --port 8000`  
   (On Windows, avoid `--reload` if the new process fails to start — restart manually.)
2. Run UI: `cd frontend && npm run dev` → http://127.0.0.1:5173/
3. Change code → save → Vite hot-reloads; restart uvicorn after backend edits.
4. Before you push: `pytest -q` and `cd frontend && npm run typecheck`.

## Where to edit for common tasks

| Goal | Start here |
|------|------------|
| New API endpoint | `app/routers/*.py` + logic in `app/` or `app/services/` |
| Auth / roles | `app/auth.py`, `app/ownership.py` |
| Allocation scoring | `app/services/allocation.py` |
| Voice phrases | `app/services/voice.py` |
| Rate card / settlement | `app/rates.py`, `app/settlements.py` |
| Sabha dashboard numbers | `app/services/overview.py` |
| New React page | `frontend/src/pages/…` + route in `App.tsx` |
| Portal colours / copy | `components/PortalShell.tsx` (`PORTALS`) |
| API client types | `frontend/src/api.ts` |

## Database rules

- Schema lives in `app/database.py` (+ booking-flow extras in `booking_flow_db.py`).
- Prefer **additive migrations** in `migrate()` — never drop tables or wipe user data.
- Override DB file with `SAHAKARSETU_DB=/path/to/file.db`.
- Seed: `python scripts/seed_demo.py` (slow — PBKDF2; refuses to seed twice).

## Environment (local)

Copy `.env.example` ideas into your shell; you do not need a `.env` file for local same-origin Vite proxy.

| Variable | Local default | Meaning |
|----------|---------------|---------|
| `SAHAKARSETU_DB` | `./sahakarsetu.db` | SQLite path |
| `SAHAKARSETU_COUNCIL_CODE` | `SABHA-2026` | Sabha signup |
| `SAHAKARSETU_CORS_ORIGINS` | empty | Only needed if UI and API differ in origin |
| `VITE_API_BASE_URL` | empty | Empty in Vite = relative URLs via proxy |

## Checklist before calling it “production ready”

- [ ] `pytest -q` green
- [ ] `npm run typecheck` and `npm run build` green
- [ ] No merge conflict markers; app imports (`python -c "from app.main import app"`)
- [ ] Demo seed works on a fresh DB (optional)
- [ ] CORS origins list includes your real Pages URL
- [ ] Council code changed from default if this is a public demo
- [ ] Cookie flags set for cross-origin (`SECURE=1`, `SAMESITE=none`)
- [ ] Known stubs accepted: Sabha **Announcements** is UI-only for now

## Coding habits that keep the repo clean

- Match existing names and file layout; don’t invent a second API client.
- Keep booking-flow behaviour unless you intentionally change the lifecycle.
- Prefer small PRs: one feature or one fix.
- Don’t commit `.db`, `.env`, or `frontend/dist/`.
- Commit messages: what changed and why (no AI co-author trailers unless the team wants them).

## Design first

UI changes: check `docs/design/` mockups (Direction A “Warm civic”) before large layout rewrites. Preserve portal accents via `[data-portal]` CSS variables.
