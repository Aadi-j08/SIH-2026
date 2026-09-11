# SahakarSetu — project context

Cooperative-run platform for household services in India (SIH 2026 prototype).
FastAPI + SQLite backend, React PWA frontend, local phone+password accounts
(one per portal), no payments / external APIs by design. Owner: Aadi Jain
(GitHub `Aadi-j08`); teammate Aman is to be added as a collaborator.
Windows 10 machine, project at `G:\SIH 2026\SIH-2026`.

## Status (as of 11 Sep 2026, evening)

Done and working locally:
- Backend: workers, bookings, fair allocation engine, voice availability parser
  (Hindi/English/Hinglish, rule-based), demand forecast, booking flow
  (assign → complete with 85/10/5 ledger → rating), admin dashboard.
- Accounts (added 11 Sep, modelled on how labourlinksoftware.co.za keeps its
  products apart): `app/auth.py` + `app/routers/auth.py` — `users` and
  `sessions` tables, PBKDF2 passwords, httpOnly cookie `sahakarsetu_session`.
  An account belongs to exactly one portal (unique on portal+phone); a Kaam
  sign-up also creates the worker record; Sabha sign-up needs the council code
  (`SAHAKARSETU_COUNCIL_CODE`, default `SABHA-2026`). Endpoints
  `/auth/signup`, `/auth/login`, `/auth/me`, `/auth/logout`.
  `require_portal("sabha")` exists as a dependency but the data endpoints are
  still open — API-level enforcement is a next step. 87 tests.
- Frontend routes (`App.tsx`): `/` landing → `/login` chooser → per portal
  `/ghar`, `/ghar/login`, `/ghar/signup`, `/ghar/home[/:bookingId]` (same
  shape for `/kaam` and `/sabha`). Old `/customer`, `/worker`, `/admin`
  redirect. `RequireAuth` sends a missing or wrong-portal session to that
  portal's sign-in; inside a portal the only exit is Sign out (no cross-portal
  links, by design). `lib/auth.tsx` holds the session; `PORTALS` in
  `PortalShell.tsx` holds every portal's paths/colours/copy.
- Landing: hero → three-portal strip → "Why a cooperative" band → one audience
  section per portal → how a job flows → live numbers → footer with Portals.
  Photos in `frontend/public/img/` (see its README for where each appears).
- Design mockups in `docs/design/` (Direction A "Warm civic"),
  `docs/design/portals/` (portal identities) and `docs/design/auth/` (login
  gateway + separated portals — the built pages follow these). The `.dc.html`
  files + `canvas.json` are the sources; the seeded `sahakarsetu-*.html`
  canvases are generated and git-ignored.

In progress / next:
1. Landing hero: the user moved the "Why Asha got this job" card on the auth
   canvas (https://claude.ai/code/artifact/30c35ae7-877d-4670-9ede-63ad402ea700)
   but the drag landed oddly (a 250×161 box); waiting on what they intended.
2. Photos `neighbourhood.jpg`, `money.jpg`, `demand-forecast.jpg` are no
   longer used on the landing (the feature cards became audience sections).
3. Ideas discussed, not built: protect data endpoints with `require_portal`,
   forgot-password, one PWA manifest per portal, seed data script, mobile app.

## Run

```
.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```
Then http://127.0.0.1:8000/app/ (web app) and /docs (API). Sabha sign-up
needs the council code `SABHA-2026` unless `SAHAKARSETU_COUNCIL_CODE` is set.
Frontend dev: `cd frontend && npm run dev` → http://127.0.0.1:5173/app/
(proxies API incl. `/auth`). Rebuild the production bundle with `npm run
build` (served by FastAPI from `frontend/dist`). Tests:
`.venv\Scripts\python -m pytest -q`.

Python is 3.13 (3.12 not installed). Node 24. `.venv` and `node_modules` are
already set up on this machine.

## Roles and ownership (backend-enforced)

Accounts are per portal and map to an access role: `ghar` → **customer**,
`kaam` → **worker**, `sabha` → **council** (`User.access_role`; `User.role`
is a council member's *title*). Session = httpOnly cookie, or
`Authorization: Bearer <session_token>` (returned by /auth/signup and
/auth/login) for Swagger/curl/tests. Dependencies in `app/auth.py`:
`require_customer`, `require_worker`, `require_council`, `require_user`.
Council may do everything; customers see/rate only their own bookings
(`bookings.customer_user_id`), workers see/complete only bookings assigned to
them and edit only their own availability (`app/ownership.py`). Public:
`/`, `/stats`, `/voice/parse`, `/app/*`, `/auth/*`.

Other backend rules: trades are canonicalised at the pydantic boundary
(`app/trades.py`, e.g. "pipe repair" → "plumbing"); `app/database.py` has
CHECK constraints for fresh DBs plus versioned additive migrations
(`schema_migrations`, triggers) for existing ones — never rebuilds tables or
drops rows; `GET /forecast/staffing?trade=` compares workers needed with
workers not declared busy (`app/services/staffing.py`); unexpected errors
return a generic 500 and are logged (logger `sahakarsetu`).

## Architecture in one breath

`app/main.py` (routes + serves `/app`) → `app/repository.py` (sqlite) →
`app/schemas.py` (pydantic). `app/auth.py` (accounts, sessions) +
`app/routers/auth.py`. AI modules in `app/services/`: `allocation.py`
(`recommend_workers`, weights proximity .30 / fairness .35 / rating .20 /
availability .15), `voice.py` (`parse_availability`), `forecast.py`
(`forecast_demand`). The booking flow (`app/services/booking_flow.py`,
`allocation_bridge.py`, `ledger.py`, `app/routers/booking_flow.py`,
`app/booking_flow_db.py`, `app/booking_flow_schemas.py`) came from a zip and
is integrated unchanged — keep it that way unless the user asks.

Frontend: `frontend/src/api.ts` (typed client incl. `api.auth`),
`pages/{Landing,Login,PortalLanding,SignIn,SignUp,Customer,Worker,Admin}.tsx`,
`components/PortalShell.tsx` (PORTALS: names, colours, paths; top bar /
sidebar / UserMenu), `components/AuthForm.tsx` (auth shell + fields),
`components/Photo.tsx`, `lib/auth.tsx` (AuthProvider, RequireAuth),
`styles.css` (design tokens; portal accent via `[data-portal]` CSS variables
— `--accent`, `--accent-d`, `--accent-t`).

## Design system (from the mockups)

Paper `#FCFAF6`, ink `#261D17`, line `#E2DDD5`; terracotta `#C65D26`
(Ghar/actions), green `#25984D` (Kaam/positive), indigo `#5E78D9` (Sabha).
Fonts: Bricolage Grotesque (display), Manrope (body), Noto Sans Devanagari
(Hindi). 44–56px tap targets. No emoji as icons — inline SVG.

## How the user likes to work

- Mockups first (design canvas), then code. Report at milestones, then keep going.
- The user commits and pushes themselves from the IDE; give them commands.
  **No force pushes.** Commit messages must NOT carry a Claude co-author
  trailer (they want only their own names as GitHub contributors).
- Keep everything local until they say push.

## Windows gotchas hit in this repo

- `uvicorn --reload` detects changes but the new process never starts —
  run without `--reload` and restart manually after backend edits.
- Windows PowerShell 5: no `&&`; give commands on separate lines.
- The Bash tool chokes on heredocs containing quotes — write scripts to a
  file and run them instead.
- Console is cp1252: set `PYTHONIOENCODING=utf-8` when printing Devanagari.
- Headless Edge (`msedge.exe --headless=new --screenshot`) works for
  screenshots; drive it over CDP (`--remote-debugging-port`) for signed-in
  pages. Its window won't go narrower than ~500px without device emulation.
