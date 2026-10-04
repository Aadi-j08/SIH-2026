# SahakarSetu API — one uvicorn worker (SSE and the DB handle are in-process).
FROM python:3.13-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl \
  && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY scripts ./scripts
# schema.sql is the single source of truth for the Postgres schema and is read
# from BASE_DIR at startup (app/database.py:_init_db_postgres). It is a
# repository-root file, so copying app/ alone left it out of the image and the
# service aborted on boot with FileNotFoundError: schema.sql ... not found at
# /app/schema.sql the moment DATABASE_URL was set.
COPY schema.sql .

ENV SAHAKARSETU_DB=/data/sahakarsetu.db
ENV PYTHONUNBUFFERED=1

RUN mkdir -p /data

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
  CMD curl -fsS "http://127.0.0.1:${PORT:-8000}/" || exit 1

# Single worker: the live events bus and the database handle are process-local.
#
# Render injects PORT (usually 10000) and routes to it, so the old hardcoded
# --port 8000 left the app listening somewhere the router never reached. The
# default keeps `docker run -p 8000:8000` working locally.
#
# The seeders are OFF unless SAHAKARSETU_SEED_DEMO=1. They create a council
# account with a known password (seed_demo_data.py, phone 9876543212) that can
# approve workers, verify documents and read every row in the tenant -- so a demo
# that enables itself leaves a publicly documented administrator login on the
# internet. Opt in deliberately, for as long as you need the walkthrough.
#
# Seeding also requires SAHAKARSETU_DEMO_PASSWORD (12+ characters), so an
# instance that is reachable by anyone else can never come up with the local-only
# demo1234. Data lives in Postgres whenever DATABASE_URL is set. Without it the
# service falls back to SQLite on the container filesystem, where anything you
# create during the walkthrough is gone on the next deploy: attach a disk at
# /data if you need it to persist.
#
# Both seeders are idempotent: seed_demo.py builds ~90 days of bookings and
# refuses to run when its data is already there, seed_demo_data.py is additive.
# About 15s on a first boot, then skipped. Their output is kept on purpose: a
# seed failure is the first sign of a database problem, and the `2>/dev/null` in
# render.yaml hides exactly that.
CMD ["sh", "-c", "if [ \"$SAHAKARSETU_SEED_DEMO\" = \"1\" ]; then if [ -z \"$SAHAKARSETU_DEMO_PASSWORD\" ]; then echo 'Refusing to seed: set SAHAKARSETU_DEMO_PASSWORD to 12+ characters.' >&2; exit 1; fi; python scripts/seed_demo.py; python scripts/seed_demo_data.py; else echo 'Demo seed skipped (set SAHAKARSETU_SEED_DEMO=1 to enable).'; fi; exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
