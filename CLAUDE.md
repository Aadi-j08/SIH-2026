# SahakarSetu — project context

Cooperative-run platform for household services in India (SIH 2026 prototype).
FastAPI + SQLite backend, React PWA frontend, local phone+password accounts
(one per portal), no payments / external APIs by design. Owner: Aadi Jain
(GitHub `Aadi-j08`); teammate Aman is to be added as a collaborator.
Windows 10 machine, project at `G:\SIH 2026\SIH-2026`.

## Status (as of 15 Sep 2026)

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

- Sabha dashboard v2 (12 Sep): `app/routers/sabha.py` — `GET /admin/overview`
  (one call: health metrics, needs-attention, demand vs workforce per trade,
  engine matching suggestions, worker network + workload %, performance,
  disputes, forecast insight; `app/services/overview.py`), `GET/PUT
  /cooperative` (`app/cooperative.py`: profile + weekly job limit + fund
  allocation policy), `/disputes` (`app/disputes.py`: raise by
  customer/worker on own booking, council lists/resolves), `POST
  /allocation/auto?trade=` (assign all pending with the engine), `GET
  /admin/customers`. New tables `cooperative`, `disputes`. Frontend:
  `components/SabhaShell.tsx` (sidebar + header + shared overview context),
  `pages/sabha/{Overview,Demands,Workers,Customers,Payments,Fund,Disputes,
  Reports,Announcements,Profile,Settings}.tsx`; `pages/Admin.tsx` became
  `pages/sabha/Demands.tsx` (exports ForecastChart/MoneySplit/WorkersList).
  Fund pie palette validated (#435ab8 #25984d #e0a028 #8a8fd9).
- Demo data: `scripts/seed_demo.py [--db demo.db]` — 52 workers, 76
  households, 14 council, ~430 bookings over 90 days through the real engine
  and ledger, 21 disputes. All passwords `demo1234`; council 9000000300,
  customer 9000000100, worker 9000000200. Takes ~90 s (PBKDF2). Refuses to
  seed twice.

In progress / next:
1. Landing hero: the user moved the "Why Asha got this job" card on the auth
   canvas (https://claude.ai/code/artifact/30c35ae7-877d-4670-9ede-63ad402ea700)
   but the drag landed oddly (a 250×161 box); waiting on what they intended.
2. Photos `neighbourhood.jpg`, `money.jpg`, `demand-forecast.jpg` are no
   longer used on the landing (the feature cards became audience sections).
3. Announcements page is a placeholder (no table yet). Ideas not built:
   forgot-password, one PWA manifest per portal, mobile app.
4. A second session is working on Kaam v2 in the same tree (app/kaam.py,
   routers/kaam.py, pages/WorkerJobs.tsx, WorkerWeek.tsx, JobCard.tsx,
   PendingWorkers.tsx, api.kaam). Until it lands, `npm run build` fails on
   tsc; `npx vite build` bundles without type-checking.

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

## Kaam v2 (12 Sep): the worker's own portal

Mockups in `docs/design/kaam-v2/` (canvas sources; the seeded html is
git-ignored). Built as designed:
- `app/kaam.py` + `app/routers/kaam.py`: `GET /workers/me/summary` and
  `/workers/me/jobs` (the home-page numbers and history — the old page called
  the council-only dashboard and always showed ₹0), `PUT/PATCH/DELETE
  /workers/{id}/availability[/{index}]` (structured edits of what the voice
  parser wrote), `POST /bookings/{id}/accept` and `/decline {reason,
  mark_busy_today}` (a decline removes the assignment, records it in
  `declines`, and re-runs `assign_booking` excluding whoever passed; stays
  pending if nobody else fits), `GET /workers/pending` + `POST
  /workers/{id}/approve` (council).
- Workers have `status` pending|active (migration 3). Kaam sign-ups start
  **pending** and the engine skips them until the council approves (Sabha →
  Workers page, "Waiting for approval" panel). Council-created workers are
  active at once. Test fixture `make_client("worker")` auto-approves; pass
  `approved=False` to test the queue. `assign_booking` gained
  `exclude_worker_ids` and the active-only filter — the only edit to the
  booking-flow files.
- Voice parser: weekday ranges ("somvar se shukravar", "monday to friday"),
  common misspellings (tommorrow…), and `assumptions` (no day named → "every
  day" and confidence capped at 0.5; only a start time). The UI shows them and
  turns Save into "Save anyway".
- Frontend: `pages/Worker.tsx` (home v2: job needing a reply → 7-day strip
  with morning/noon/evening bars → compact mic → stats → recent jobs; pending
  state with timeline), `pages/WorkerWeek.tsx` (`/kaam/week`: tap a slot →
  mark free / busy / remove), `pages/WorkerJobs.tsx` (`/kaam/jobs`: 85/10/5
  split, ratings, history), `components/JobCard.tsx` (accept / decline reason
  sheet / call / directions / job done), `components/VoiceAvailability.tsx`
  (extracted, `compact` mode; adds by default, checkbox to replace),
  `components/PendingWorkers.tsx` (Sabha approval panel), `lib/week.ts`
  (windows + jobs → 7×3 slot grid).
- `scripts/seed_demo.py` approves all but the three newest workers.

## Pricing, agreed settlement and live updates (15 Sep)

No money moves through the platform; a household pays its worker directly
(cash/UPI) and the system records only what the two agreed.
- `app/rates.py`: **community rate card** — per trade a visit charge, hourly
  rate, minimum hours and a fair band (±25%), fixed by the general body.
  Table `standard_rates` (seeded with defaults on first read; unknown trades
  get a placeholder row). `GET /rates`, `GET /rates/quote?trade=&hours=&
  materials=` (any signed-in user), `PUT /rates/{trade}` (council).
  `typical_hours` = median of the last agreed jobs of that trade.
- `app/settlements.py` + `app/routers/pricing.py`: **agreed price**. Table
  `settlements` (one per booking). Worker `POST /bookings/{id}/settlement`
  {hours_worked, materials_rupees, work_note, amount_rupees?} — the card
  prices it; a proposal outside the band is 422. Customer `POST
  …/settlement/respond` {action: agree|counter|dispute, amount_rupees?, note?,
  paid_via?}; worker responds agree|dispute to a counter. **Agree calls the
  unchanged `booking_flow.complete_booking`** → 85/10/5 ledger. Dispute opens
  a `payment` dispute (status `disputed`); council `POST …/settlement/resolve`
  {amount_rupees, resolution} fixes the amount, completes the job and closes
  the dispute. `GET /bookings/{id}/settlement` (parties), `GET
  /settlements?status=open|…` (council). The old `POST /bookings/{id}/complete`
  still exists for tests/seed; the Kaam UI no longer uses it. Kaam
  `WorkerJob.settlement` carries a brief; `Dispute` gained `settlement_*`.
- `app/events.py`: **live updates**. `PublishChanges` middleware publishes an
  event (topic, action, booking/worker/dispute id, no data) for every 2xx
  POST/PUT/PATCH/DELETE it recognises; `GET /events/stream` is SSE (async
  generator, 1 s tick, keep-alive every 20 s), `GET /events?after=seq` polls.
  In-process ring buffer — one uvicorn worker. Frontend `lib/live.ts`
  `useLive(onEvents, {filter})` (EventSource, falls back to polling); the
  Sabha shell (header shows Live/Polling), Kaam home and the Ghar booking
  page reload on events and slow their timers while connected.
- Overview: attention kind `settle` (prices unanswered > 24 h → Payments),
  "Auto-allocate all (n)" button on AI matching; the loop strip says "Agreed
  price" instead of "Payment".
- Frontend: `components/Settlement.tsx` (RateHint, ProposePrice sheet,
  SettlementCard for customer/worker), JobCard "Job done · propose the
  price" replaces the typed bill, Customer booking page shows the rate card
  before booking, a **Call worker** button, and the agreement card;
  `pages/sabha/Payments.tsx` = rate card editor + prices being agreed +
  split; Disputes page: "Fix the price & close" for `disputed` settlements.
- Seed: completed jobs are priced from the rate card with an agreed
  settlement row each; three assigned jobs carry a proposed / countered /
  disputed price (the disputed one is one of the 3 open disputes).
  `tests/test_pricing.py` (10 tests). Known pre-existing failure:
  `test_kaam.py::test_decline_with_nobody_else_leaves_the_booking_pending`
  hard-codes a 12 Sep booking and "busy for the rest of today".

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
`/`, `/stats`, `/voice/parse`, `/app/*`, `/auth/*`. `/rates*` and `/events*` need any session.

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
