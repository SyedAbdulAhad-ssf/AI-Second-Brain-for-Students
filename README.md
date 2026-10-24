# AI Second Brain for Students

A Flask and PostgreSQL learning workspace. Phase 1 provides direct student accounts; Phase 2 adds smart notes, browser-side PDF/TXT/Markdown text extraction, Mermaid diagrams, exports, and persistent local SQLite support when PostgreSQL is not configured.

## Local setup

1. Install Python 3.10+.
2. Create a virtual environment and install dependencies: `python -m venv .venv` then activate it and run `pip install -r requirements.txt`.
3. Copy `.env.example` to `.env` and set a long random `FLASK_SECRET_KEY`. Without `DATABASE_URL`, the app automatically creates a persistent SQLite database in `instance/secondbrain.sqlite3`. To use PostgreSQL or Supabase instead, set `DATABASE_URL`; Supabase URLs generally require SSL and `DB_SSLMODE=require` is the default.
4. Optionally set `GEMINI_API_KEY` to enable Gemini 2.5 Flash analysis. Without it (or if the Gemini request fails), deterministic local analysis keeps the notes workflow usable.
5. Start with `python app.py` and open [http://localhost:5000](http://localhost:5000). The schema is initialized automatically on startup. `/api/health` reports API/database status.

Passwords are stored as Werkzeug password hashes. Usernames are direct accounts with no email or OTP flow. Do not use the development secret in production.

## Vercel

Import the repository into Vercel, configure `DATABASE_URL`, `FLASK_SECRET_KEY`, and optional `GEMINI_API_KEY` environment variables, then deploy. Vercel detects the Flask app in `app.py`, routes its `/api/*` endpoints to the Python function, and serves files in `public/` from the CDN (including `/` from `public/index.html`). `vercel.json` includes `database/schema.sql` in the function because the app reads it at runtime. A remote PostgreSQL service must accept connections from the deployment environment.

## Phase status

- Phase 1: schema, direct auth, app shell, protected dashboard navigation.
- Phase 2: smart notes, PDF/TXT/Markdown extraction, generated summaries and concepts, Mermaid diagrams, saved-note management, and diagram export.
- Phase 3: generated mixed-format quizzes, 3D review flashcards, scored attempts, and personalized knowledge-gap recovery plans.
- Phase 4: note-grounded AI tutor chat with source citations, plus a gap-prioritized revision planner with persisted task completion.
- Phase 5: analytics and demo seeder scaffolds remain pending.

## Starting locally

Run `run_server.bat` on Windows, or run `python -m pip install -r requirements.txt` followed by `python app.py`. The default `.env` enables local SQLite; add `DATABASE_URL` and `GEMINI_API_KEY` when ready to use Supabase PostgreSQL and live Gemini output.

Run `python check_setup.py` before deployment to confirm required packages, database initialization, Gemini mode, and Vercel configuration. For Vercel, set `DATABASE_URL`, `FLASK_SECRET_KEY`, `GEMINI_API_KEY` when using live AI, `COOKIE_SECURE=true`, and `FRONTEND_ORIGIN` to the deployed site URL.
