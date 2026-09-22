"""Entry point that loads .env then starts uvicorn."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

# Override CORS for the ngrok tunnel URL
_ngrok_url = "https://bb51-2401-4900-adc7-4841-b960-6e8f-9bc4-b655.ngrok-free.app"
os.environ["SAHAKARSETU_CORS_ORIGINS"] = (
    f"http://localhost:5173,https://sahakarsetu.pages.dev,{_ngrok_url}"
)
# Production mode to test docs restriction
os.environ["SAHAKARSETU_ENV"] = "production"

import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, workers=1)
