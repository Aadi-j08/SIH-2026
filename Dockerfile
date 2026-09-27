# SahakarSetu API — one uvicorn worker (SSE + SQLite are in-process).
FROM python:3.13-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl \
  && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY scripts ./scripts

ENV SAHAKARSETU_DB=/data/sahakarsetu.db
ENV PYTHONUNBUFFERED=1

RUN mkdir -p /data

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
  CMD curl -fsS "http://127.0.0.1:${PORT:-8000}/" || exit 1

# Single worker: live events bus and SQLite writes are process-local.
#
# Render injects PORT (usually 10000) and routes to it, so the old hardcoded
# --port 8000 left the app listening somewhere the router never reached. The
# default keeps `docker run -p 8000:8000` working locally.
#
# Both seeders run before the server and are idempotent: seed_demo.py builds
# ~90 days of bookings and refuses to run when its data is already there, and
# seed_demo_data.py is additive. Together they leave the council verification
# queue populated with applicants whose Aadhaar is on file, which is the flow
# the demo shows. About 15s on a first boot, then skipped. Their output is kept
# on purpose: a seed failure is the first sign of a database problem, and the
# `2>/dev/null` in render.yaml hides exactly that.
CMD ["sh", "-c", "python scripts/seed_demo.py; python scripts/seed_demo_data.py; exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
