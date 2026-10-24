"""Quick local readiness check for AI Second Brain for Students."""
import importlib.util
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(dotenv_path=ROOT / ".env", override=True)
for package in ("flask", "flask_cors", "psycopg2", "dotenv", "requests", "google.generativeai"):
    print(f"{'OK' if importlib.util.find_spec(package) else 'MISSING'}  {package}")

os.environ.setdefault("FLASK_SECRET_KEY", "setup-check-only")
from api.db import init_db, using_postgres  # noqa: E402

try:
    init_db()
    print(f"OK  database mode: {'PostgreSQL' if using_postgres() else 'local SQLite fallback'}")
except Exception as exc:
    if os.getenv("DATABASE_URL"):
        print(f"ERROR  PostgreSQL connection/initialization failed: {type(exc).__name__}: {exc}")
    else:
        print(f"ERROR  local SQLite initialization failed: {type(exc).__name__}: {exc}")

key = os.getenv("GEMINI_API_KEY", "")
print("OK  Gemini API key configured" if key and not key.startswith("replace-") else "INFO  Gemini not configured; deterministic fallback is active")
print("OK  Vercel entry point present" if (ROOT / "api" / "index.py").is_file() and (ROOT / "vercel.json").is_file() else "MISSING  Vercel configuration")
