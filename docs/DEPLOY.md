# Deploy and operate

Recommended production shape for SIH:

- **Frontend** → Cloudflare Pages (static React build)
- **Backend** → Render.com (Python web service via `render.yaml`)

You already have Pages. This doc gets the API public and wired to Pages, then explains how to ship changes later.

---

## 0. Feedback loop

A full feedback mechanism is built in:

- **Users** → open `https://YOUR-APP.pages.dev/` (or `/app/` on the API host) and click the blue **feedback** button (bottom-right) on any page. No login needed.
- **Council** → Sabha → **User Feedback** in the sidebar to read, filter, and triage every submission.
- Data lives in the `feedback` table (see `schema.sql`).

---

## 1. Deploy the API (Render.com)

The repo ships a ready `render.yaml`. One-time setup in the Render dashboard:

1. Go to [dashboard.render.com](https://dashboard.render.com) and sign in (or create a free account).
2. Click **New + → Web Service** (choose *Use a YAML file* if asked).
3. Connect your GitHub repo (`Aadi-j08/SIH-2026`; if you forked it, select the fork).
4. Render auto-detects `render.yaml`. Review and click **Create Web Service**.
5. After the service is created, open **Environment → Environment Variables** and add the secrets that are marked `sync: false`:

   | Key | Value |
   |-----|-------|
   | `GEMINI_API_KEY` | Your Google AI Studio key (from [aistudio.google.com](https://aistudio.google.com)) |
   | `SAHAKARSETU_CORS_ORIGINS` | `https://951dd6a2.sih-2026-hvs.pages.dev` (your exact Pages domain, **no trailing slash**) |
   | `DATABASE_URL` | Your Neon.tech PostgreSQL connection string (or omit for local SQLite) |

   | `SAHAKARSETU_COOKIE_SECURE` | `"1"` |
   | `SAHAKARSETU_COOKIE_SAMESITE` | `"none"` |
   | `SAHAKARSETU_ENV` | `"production"` |

   Also set `VITE_BASE_PATH=/app/` so assets resolve under `/app/`.

6. Render restarts and builds automatically. Note the URL, e.g. `https://sahakarsetu-api.onrender.com`.

Verify: `https://…/` returns `{"status":"ok",…}` and `/docs` opens.

### Seed demo data (once)

After deploy, open a **Shell** from the Render dashboard and run:

```bash
python scripts/seed_demo.py
```

---

## 2. Point Cloudflare Pages at the API

In Pages → **Settings → Environment variables** (Production **and** Preview):

| Name | Value |
|------|--------|
| `VITE_API_BASE_URL` | `https://sahakarsetu-api.onrender.com` (no trailing slash) |

`VITE_BASE_PATH` should stay `/` for Pages root hosting.

**Trigger a new Pages deploy** (push to the connected branch or “Retry deployment”). Vite bakes `VITE_*` in at **build** time — changing the env without rebuilding does nothing.

---

## 3. Smoke test after go-live

1. Open the Pages URL → landing loads.
2. Sign in as Sabha: phone `9000000300`, password `demo1234` (if seeded).
3. Create a booking on Ghar; open Sabha → Overview to see it.
4. Submit feedback via the bottom-right button.
5. In DevTools Network tab, confirm calls go to the Render host, not `pages.dev/auth/...`.

If login “works” then `/auth/me` is anonymous: cookies blocked — Bearer token in `localStorage` should still work with the updated `api.ts`. Hard-refresh once after deploy.

---

## 4. How to change code **after** deployment

### Backend only (API routes, allocation, DB)

```bash
# edit app/...
pytest -q
git push   # Render auto-redeploys from render.yaml
```

Render runs DB migrations on startup via `database.init_db()`.

### Frontend only (UI, copy, routes)

```bash
cd frontend && npm run typecheck
git push   # Cloudflare Pages auto-redeploys
```

If you changed which API host to use, update `VITE_API_BASE_URL` in Pages and redeploy.

### Both (e.g. new endpoint + new UI)

1. Implement + test locally (Vite proxy ↔ uvicorn).
2. Push API first (Render must be up before the UI calls it).
3. Push frontend so Pages rebuilds.

### Secrets / CORS / council code

Set in the Render dashboard under **Environment → Environment Variables**. Each change restarts the service.

### Rollback

In the Render dashboard, open the service → **Deploys** tab → find the previous deploy → click the ⋮ menu → **Rollback**.

---

## 5. Local Docker (optional)

```bash
docker compose up --build
# API on http://127.0.0.1:8000
# Frontend served at http://127.0.0.1:8000/app/
```

Set `SAHAKARSETU_CORS_ORIGINS` in the environment for a separate UI origin.

---

## 6. Alternative: VPS with a public IP

1. Create a droplet (1 GB+), install Docker.
2. Copy the repo; `docker compose up -d`.
3. Put Nginx + Let’s Encrypt in front (`api.yourdomain.com` → `:8000`).
4. Same secrets; set Pages `VITE_API_BASE_URL` to that HTTPS domain.

Raw HTTP IPs fight with Secure cookies — use HTTPS.

---

## 7. Temporary tunnel (for testing)

While the permanent Render deployment is being set up, the backend can be run locally and exposed via ngrok:

```bash
# Terminal 1 — start the API (loads .env automatically)
python3 scripts/run_server.py

# Terminal 2 — expose it
ngrok http 8000
# → https://<random>.ngrok-free.app
```

Then open `https://<random>.ngrok-free.app/app/` to use the full app (frontend + API, same origin, no CORS issues).

> ngrok free URLs are **temporary** — they change when the tunnel restarts. Use Render.com for the permanent deployment.

---

## 8. Limits to remember

| Topic | Reality |
|-------|---------|
| Workers | Keep `--workers 1` (SSE bus + SQLite) |
| Scale | Fine for hackathon / one cooperative; multi-region needs Postgres + Redis |
| Announcements | Sabha page is a placeholder — no API yet |
| Payments | Ledger only; cash/UPI outside the app |
