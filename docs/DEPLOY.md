# Deploy and operate

Recommended production shape for SIH:

- **Frontend** → Cloudflare Pages (static React build)
- **Backend** → Fly.io (Docker, one machine, persistent SQLite volume)

You already have Pages. This doc gets the API public and wired to Pages, then explains how to ship changes later.

---

## 1. Deploy the API (Fly.io)

Prerequisites: [Fly CLI](https://fly.io/docs/hands-on/install-flyctl/), Docker (Fly builds remotely if you don’t).

```bash
# From the repo root
fly auth login
fly launch --copy-config --no-deploy
# If the app name in fly.toml is taken, edit `app = "..."` then continue.

fly volumes create sahakarsetu_data --region sin --size 1

fly secrets set \
  SAHAKARSETU_CORS_ORIGINS=https://YOUR-PROJECT.pages.dev \
  SAHAKARSETU_COOKIE_SECURE=1 \
  SAHAKARSETU_COOKIE_SAMESITE=none \
  SAHAKARSETU_COUNCIL_CODE=SABHA-2026

fly deploy
```

Note the URL, e.g. `https://sahakarsetu-api.fly.dev`. Check `https://…/` returns `{"status":"ok",…}` and `/docs` opens.

Optional seed (once):

```bash
fly ssh console -C "python scripts/seed_demo.py"
```

---

## 2. Point Cloudflare Pages at the API

In Pages → **Settings → Environment variables** (Production **and** Preview if you use previews):

| Name | Value |
|------|--------|
| `VITE_API_BASE_URL` | `https://sahakarsetu-api.fly.dev` (no trailing slash) |

`VITE_BASE_PATH` should stay `/` for Pages root hosting.

**Trigger a new Pages deploy** (push to the connected branch or “Retry deployment”). Vite bakes `VITE_*` in at **build** time — changing the env without rebuilding does nothing.

Also add the same Pages URL to Fly CORS if you haven’t:

```bash
fly secrets set SAHAKARSETU_CORS_ORIGINS=https://YOUR-PROJECT.pages.dev
```

---

## 3. Smoke test after go-live

1. Open the Pages URL → landing loads.
2. Sign up / sign in on Ghar (or use demo phones after seed).
3. Create a booking; open Sabha; see it on Demands / Overview.
4. Confirm Network tab calls go to the Fly host, not `pages.dev/auth/...`.

If login “works” then `/auth/me` is anonymous: cookies blocked — Bearer token in `localStorage` should still work with the updated `api.ts`. Hard-refresh once after deploy.

---

## 4. How to change code **after** deployment

### Backend only (API routes, allocation, DB)

```bash
# edit app/...
pytest -q
fly deploy
```

No Pages rebuild needed unless the API response shape changed in a breaking way.

### Frontend only (UI, copy, routes)

```bash
# edit frontend/...
cd frontend && npm run typecheck
git push   # or whatever triggers Cloudflare Pages
```

If you changed which API host to use, update `VITE_API_BASE_URL` in Pages and redeploy.

### Both (e.g. new endpoint + new UI)

1. Implement + test locally (Vite proxy ↔ uvicorn).
2. `fly deploy` first (API must exist before the UI calls it).
3. Push frontend so Pages rebuilds.

### Database / data

- Schema: add a migration in `app/database.py` `migrate()`, deploy API — it runs on startup.
- Never replace the volume casually; backups: `fly ssh console` + copy `/data/sahakarsetu.db`.
- Reseeding wipes nothing automatically — `seed_demo.py` refuses a second seed on the same file.

### Secrets / CORS / council code

```bash
fly secrets set KEY=value
# machines restart with new secrets
```

### Rollback

```bash
fly releases
fly deploy --image registry.fly.io/APP:deployment-XXXX
```

Or revert the git commit and `fly deploy` / Pages redeploy.

---

## 5. Local Docker (optional)

```bash
docker compose up --build
# API on http://127.0.0.1:8000
```

Set `SAHAKARSETU_CORS_ORIGINS` in the environment for a separate UI origin.

---

## 6. Alternative: VPS with a public IP

1. Create a droplet (1 GB+), install Docker.
2. Copy the repo; `docker compose up -d`.
3. Put Nginx + Let’s Encrypt in front (`api.yourdomain.com` → `:8000`).
4. Same secrets as Fly; set Pages `VITE_API_BASE_URL` to that HTTPS domain.

Raw HTTP IPs fight with Secure cookies — use HTTPS.

---

## 7. Limits to remember

| Topic | Reality |
|-------|---------|
| Workers | Keep `--workers 1` (SSE bus + SQLite) |
| Scale | Fine for hackathon / one cooperative; multi-region needs Postgres + Redis |
| Announcements | Sabha page is a placeholder — no API yet |
| Payments | Ledger only; cash/UPI outside the app |
