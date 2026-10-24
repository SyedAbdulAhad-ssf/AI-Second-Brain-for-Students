# Project Artifact — AI Second Brain for Students

## Overview & tech stack

A personal student learning workspace. Frontend: semantic HTML, responsive CSS, vanilla JavaScript, PDF.js, and Mermaid.js. Backend: Flask, Flask-CORS. Database: Supabase-compatible PostgreSQL through psycopg2, with persistent SQLite fallback for local development. AI: server-side Gemini REST integration with deterministic local analysis fallback.

## Phase tracker

| Phase | Scope | Status |
|---|---|---|
| 1 | PostgreSQL schema, direct username/password auth, responsive dashboard shell | Completed |
| 2 | Smart notes, PDF/text processing, flowcharts, mind maps | **COMPLETED** |
| 3 | Quizzes, flashcards, knowledge gaps | **COMPLETED** |
| 4 | Notes chat/RAG and revision planning | **COMPLETED** |
| 5 | Analytics, demo seeder, setup checker, deployment readiness | **COMPLETED** |

## File manifest

| File | Status / purpose |
|---|---|
| `PROJECT_ARTIFACT.md` | Living project record |
| `.gitignore` | Excludes environment files, Python caches, and local SQLite data |
| `.env` | Local development defaults with a Flask session secret; database and Gemini credentials remain optional |
| `run_server.bat` | Windows dependency installer and local Flask server launcher |
| `check_setup.py` | Checks packages, database initialization/mode, Gemini status, and Vercel entry configuration |
| `README.md` | Local, Supabase, and Vercel setup |
| `vercel.json` | Uses Vercel Flask framework routing, serves `public/` from the CDN, and includes the SQL schema in the Python function bundle |
| `requirements.txt` | Minimal Vercel Python runtime dependencies (Flask, CORS, PostgreSQL driver, dotenv, and HTTP client) |
| `.env.example` | Credential-free server environment configuration template |
| `app.py` | Local Flask app, route registration, static serving, startup schema init, MAX_CONTENT_LENGTH configured to 1 GB |
| `api/__init__.py` | API package |
| `api/index.py` | Vercel Python serverless WSGI entry point exposing the Flask app |
| `api/db.py` | PostgreSQL/SQLite adapter, schema initialization, single/multi-row queries and writes |
| `api/gemini_service.py` | Gemini REST JSON and page-image OCR with chunk-synthesized study guides, deterministic Chemistry Equilibrium guide, RAG tutor, watermark cleaning, and Mermaid sanitization |
| `api/routes/__init__.py` | Routes package |
| `api/routes/auth_routes.py` | Active register/login/logout/session endpoints |
| `api/routes/notes_routes.py` | Student-scoped notes CRUD, scanned-page OCR intake, and diagram regeneration endpoints |
| `api/routes/quiz_routes.py` | Completed Phase 3 assessment generation, grading, attempt history, and knowledge-gap APIs |
| `api/routes/rag_routes.py` | Completed Phase 4 note-grounded chat, persisted conversations, revision-plan generation, and task updates |
| `api/routes/analytics_routes.py` | Completed student analytics aggregation and idempotent presentation demo seeder |
| `database/schema.sql` | Idempotent PostgreSQL DDL for all seven tables |
| `public/index.html` | Direct login/register UI |
| `public/dashboard.html` | Responsive workspace shell with 1 GB upload support; loads Mermaid.js and PDF.js; Phase 3 views are activated by the assessment client module |
| `public/css/styles.css` | Dark academic responsive UI with notes, diagrams, assessment, tutor, planner, and analytics-dashboard styles |
| `public/js/api.js` | Fetch wrapper and local session cache |
| `public/js/auth.js` | Login/register flow |
| `public/js/dashboard.js` | Auth guard, navigation, connection state, module initialization, analytics overview rendering, demo-data action, and accessible student guide modal |
| `public/js/notes.js` | PDF/TXT/Markdown extraction, low-text page JPEG capture for OCR (first 15 pages), watermark cleaning, saved-note UI, Mermaid rendering and diagram exports |
| `public/js/quiz.js` | Assessment note selector, mixed quiz interactions, 3D flashcard deck, scoring report, and Mermaid knowledge-gap recovery cards with client-side sanitization |
| `public/js/chat.js` | Synchronized active-note selector and badge, cited tutor chat stream, starter prompts, follow-ups, and chat clearing |
| `public/js/revision.js` | Planner configuration, adaptive schedule timeline, and persisted task-completion UI |

## PostgreSQL schema reference

- `students`: id, unique username, password hash, created_at.
- `notes`: student_id → students (cascade), title, subject, raw_content, summary, key_points JSONB, definitions JSONB, flowchart_mermaid, mindmap_mermaid, created_at.
- `quizzes`: note_id → notes (cascade), student_id → students (cascade), questions and flashcards JSONB, created_at.
- `quiz_attempts`: quiz_id → quizzes and student_id → students (cascade), score, total_questions, wrong_answers JSONB, attempted_at.
- `knowledge_gaps`: student_id and note_id cascade references, weak_topic, status, explanation, recommended action, mini flowchart, updated_at.
- `revision_plans`: student_id cascade reference, exam_date, daily_hours, schedule JSONB, created_at.
- `chat_messages`: student_id and note_id cascade references, role, message, source_reference, created_at.

All primary IDs use SERIAL. Tables are created with `IF NOT EXISTS` from `database/schema.sql` at startup when `DATABASE_URL` exists, or when `/api/health` is queried. If no `DATABASE_URL` is set, a compatible persistent SQLite schema is initialized in `instance/secondbrain.sqlite3` (or `SQLITE_PATH`).

## API endpoint registry

| Method | Route | Payload / purpose | Phase |
|---|---|---|---|
| GET | `/api/health` | API and DB status; runs schema initialization | 1 |
| POST | `/api/auth/register` | `{username,password}`; create and sign in | 1 |
| POST | `/api/auth/login` | `{username,password}`; sign in | 1 |
| POST | `/api/auth/logout` | Clear session | 1 |
| GET | `/api/auth/me` | Current signed-in student | 1 |
| POST | `/api/notes/generate` | `{title,subject,raw_content,page_images?}`; OCR supplied scanned-page images, clean and analyze source, save and return complete note (201) | 2 |
| GET | `/api/notes` | List current student's notes, newest first | 2 |
| GET | `/api/notes/<note_id>` | Retrieve a full note owned by the current student | 2 |
| POST | `/api/notes/<note_id>/regenerate-diagrams` | Regenerate Mermaid flowchart and mind map for an owned note | 2 |
| DELETE | `/api/notes/<note_id>` | Delete an owned note | 2 |
| POST | `/api/quizzes/generate` | `{note_id}`; create and save a quiz and flashcards for an owned note | 3 |
| GET | `/api/quizzes` | List a student's saved quizzes, note metadata, and latest score | 3 |
| GET | `/api/quizzes/note/<note_id>` | Latest assessment and attempt history for an owned note | 3 |
| POST | `/api/quizzes/<quiz_id>/submit` | Grade MCQ and short answers, store attempt, create/update gaps, and return a report | 3 |
| GET | `/api/quizzes/knowledge-gaps` | List student knowledge gaps with note metadata and recovery Mermaid diagrams | 3 |
| POST | `/api/quizzes/knowledge-gaps/<gap_id>/status` | Set a gap to `needs_practice` or `mastered`, or toggle it | 3 |
| GET | `/api/rag/chat/<note_id>` | Return an owned note's tutor conversation and starter prompts | 4 |
| POST | `/api/rag/chat` | `{note_id, question}`; persist question, return a cited note-grounded response | 4 |
| DELETE | `/api/rag/chat/<note_id>` | Clear an owned note's conversation | 4 |
| GET | `/api/rag/revision` | Latest revision plan, active gap count, and note count | 4 |
| POST | `/api/rag/revision/generate` | `{exam_date, daily_hours}`; create a gap-prioritized study plan | 4 |
| POST | `/api/rag/revision/<plan_id>/toggle-task` | Persist task completion and return updated plan progress | 4 |
| GET | `/api/analytics` and `/api/analytics/overview` | Student counts, mastery, activity, recommendation, and runtime modes | 5 |
| POST | `/api/analytics/seed-demo` | Idempotently create interconnected sample notes, quizzes, gaps, chat, and revision plan | 5 |

### Phase 2 service methods

- `api.gemini_service.generate_json(prompt, response_schema=None, image_data_urls=None)`: calls the configured Gemini REST model in JSON mode with optional inline images; returns `None` when no API key is configured. `gemini-3.8-flash` is the current default, followed by the requested Flash model IDs.
- `api.gemini_service.extract_text_from_page_images(page_images)`: sends up to 15 JPEG pages to Gemini Vision and removes repeated board/SLO watermarks before saving OCR text.
- `api.gemini_service.analyze_notes_and_generate_visuals(title, subject, raw_content)`: requests a detailed 3–5 sentence executive summary, expanded key points, extracted definitions, flowchart TD, and a single-root mind map; analyzes long sources in overlapping chunks and synthesizes their results, with deterministic extraction as fallback.
- `api.gemini_service.generate_visuals(title, subject, raw_content)`: regenerates the two Mermaid diagrams for an existing saved note.
- `api.db.init_db()`: initializes PostgreSQL schema or local SQLite schema idempotently. `query_one`, `query_all`, `execute`, and `execute_many` provide parameterized database operations.

### Phase 2 frontend behavior

`public/js/notes.js` extracts PDF text through PDF.js, renders low-text pages as compressed JPEGs for OCR (up to 15 pages), and reads TXT/Markdown with the browser File API. It cleans textbook watermarks, opens saved study guides, and supports Mermaid rendering and export. `dashboard.html` loads Mermaid.js 10 and PDF.js 3.11.174.

### Phase 3 assessment methods and UI

- `api.gemini_service.generate_quiz_and_flashcards(...)` returns 5–8 MCQ/short-answer questions and 6–10 tagged flashcards. It calls Gemini when configured and creates a note-derived deterministic assessment when it is not.
- `api.gemini_service.detect_knowledge_gaps(...)` maps wrong answers to a simple explanation, a three-step recovery action, and valid Mermaid `flowchart TD` recovery source; it also has a deterministic fallback.
- `public/js/quiz.js` implements the note selector, assessment generation, answer submission, score/explanation report, click-to-flip flashcards, known-card count, shuffle, and rendered diagnostic recovery cards.
- `run_server.bat` installs the declared requirements and starts the Flask app. `.env` provides safe local defaults; the SQLite fallback remains active until `DATABASE_URL` is configured.

### Phase 4 RAG and planning methods

- `api.gemini_service.answer_from_notes_rag(note, question, chat_history=None)` retrieves and scores note sections, key points, and definitions against an English or Roman Urdu/Hinglish question. It produces a cited, note-grounded answer and three relevant follow-up questions, with deterministic synthesis when Gemini is unavailable.
- `api.gemini_service.generate_smart_revision_plan(exam_date, daily_hours, notes, knowledge_gaps, quiz_attempts)` creates a 3–14 day schedule that prioritizes active knowledge gaps and lower quiz scores before core review and final recall.
- `public/js/chat.js` provides a note context selector, sample/follow-up prompts, cited response bubbles, loading state, and clear-chat action.
- `public/js/revision.js` provides exam and daily-hours configuration, plan summary metrics, timeline cards, quick note navigation, and live persisted task completion.

### Phase 5 analytics and deployment readiness

- `api.routes.analytics_routes.overview(student_id)` aggregates notes, quizzes, attempts, active/mastered gaps, chat questions, revision progress, subject mastery, activity, recommendation, and active database/AI modes.
- `POST /api/analytics/seed-demo` creates idempotent presentation data for the current student: two rich notes, assessments, an attempt, two recovery gaps, cited tutor chat, and a seven-day revision plan.
- The dashboard overview now loads live analytics, system-mode badges, core concept cards, KPI cards, mastery indicators, activity, recommendation, and the one-click demo action.
- `check_setup.py` confirms package availability, initializes the selected database, reports Gemini configuration, and checks the Vercel entry/config files.

## Verification

- Python syntax compilation passed for `app.py`, all `api/*.py`, and all `api/routes/*.py`.
- Flask test-client integration passed using temporary SQLite: direct registration, note generation from sample Photosynthesis notes, list/detail, diagram regeneration, and deletion.
- The browser-only PDF.js extraction and Mermaid SVG/PNG/print controls were implemented but not exercised in a real browser during this phase.
- Phase 3 compilation passed for all Python modules. Flask test-client assessment integration passed using temporary SQLite: quiz/flashcard generation, mixed-answer submission, automatic Mermaid knowledge-gap creation, and updating a gap to `mastered`.
- Phase 4 compilation passed for all Python modules. Flask test-client integration passed using temporary SQLite: a Roman Urdu/Hinglish tutor question returned a persisted answer with a source citation; a knowledge-gap-prioritized revision plan was created; and task completion was persisted with updated progress.
- Final Phase 5 verification passed: compilation included `check_setup.py`; a temporary-SQLite Flask test covered registration/login, demo seeding, non-zero analytics, and successful Notes, Quiz, Gaps, RAG, and Revision retrieval using seeded data. `python check_setup.py` passed with local SQLite fallback and deterministic AI mode.
- 2026-10-23 restoration verification: Python compilation passed for all 12 project Python modules; JavaScript syntax checks passed for the updated notes, chat, and dashboard clients. A temporary-SQLite Flask integration check passed registration, note generation, saved-note list/detail retrieval, generated `mindmap` output, and cited RAG chat. Mermaid sanitation and bounded RAG passage checks passed directly. Supabase connectivity and live Gemini rendering were unavailable from the restricted verification environment; browser PDF extraction was reviewed in code but not exercised with a real textbook in a browser.
- 2026-10-23 summary enhancement verification: `python -m py_compile api/gemini_service.py` passed. The notes extraction status now declares the truncation flag at function scope so PDF, TXT, and Markdown paths can safely display completion status. Gemini note generation requests a detailed professor-style 3–5 sentence summary, expanded contextual key points, and definitions; long source text is split with overlap, analyzed chunk by chunk, and synthesized into one study guide. Deterministic fallback summaries now include multiple source sentences when Gemini is unavailable.
- 2026-10-23 scanned textbook and tutor repair: PDF.js cleans Sindh Textbook Board/SLO watermarks and captures low-text pages as compressed JPEGs (first 15 pages) for backend Gemini Vision OCR. OCR text is persisted as `raw_content` before study-guide generation. Gemini JSON calls send API credentials in headers and default to `gemini-3.8-flash`, retaining the requested Flash IDs as fallbacks. Prompts request new-student clarity; deterministic Chemical Equilibrium output includes 8 key points, 8 definitions, an academic flowchart, and a five-branch hierarchical mind map without a dummy check node. Backend and frontend Mermaid sanitizers preserve branch nesting. Tutor context combines summary, points, definitions, and raw-content passages; active note selection is synchronized between saved notes and chat. Repaired all three matching PostgreSQL Chemistry Equilibrium records (IDs 9–11) using the supplied chapter content and verified 8 points, 8 definitions, and hierarchical diagrams. Python compilation (12 modules), JavaScript syntax, cleaner/guide/Roman Urdu fallback checks, and live PostgreSQL Notes list/detail and cited RAG API checks passed; all four saved note details read successfully. Gemini returned 404 for 2.5/2.0/1.5 Flash on this account and reported 503 high demand for 3.8 during the live check; the service logs model errors and uses the grounded fallback. Actual scanned-PDF browser OCR remains unverified because the PDF was not in the workspace.

## Deployment checklist

- Set `DATABASE_URL` to the Supabase PostgreSQL connection string and keep `DB_SSLMODE=require`.
- Set a long, unique `FLASK_SECRET_KEY`, configure `COOKIE_SECURE=true`, and set `FRONTEND_ORIGIN` to the deployed frontend URL.
- Set `GEMINI_API_KEY` to enable live Gemini responses; leaving it absent keeps deterministic local fallbacks operational.
- Deploy using `vercel.json` and `api/index.py`; run `python check_setup.py` before deployment.

## Change log

| Date (Asia/Karachi) | Change |
|---|---|
| 2026-10-21 | Created Phase 1 schema, Flask app, direct password-hash authentication, login UI, dashboard shell and navigation, setup docs, deployment config, and Phase 2–5 module scaffolds. |
| 2026-10-22 | Completed Phase 2. Updated `api/db.py` (SQLite/PostgreSQL adapter), `api/gemini_service.py` (Gemini and deterministic analysis), `api/routes/notes_routes.py` (protected notes endpoints), `public/dashboard.html` (Mermaid/PDF.js libraries), `public/css/styles.css` (responsive notes/diagram UI), `public/js/notes.js` (file extraction, notes CRUD UI, diagrams and exports), `public/js/dashboard.js` (Phase 2 initialization), `README.md` (SQLite/Gemini setup), `.gitignore` (local DB/environment files), and this artifact. |
| 2026-10-22 | Recovered and completed Phase 3. Audited the workspace and found the assessment files untouched; added `.env` and `run_server.bat`, installed declared Python dependencies, implemented Gemini/deterministic assessment and knowledge-gap methods, completed all quiz and gap routes, implemented the quiz/flashcard/recovery UI and styles, updated `README.md`, and verified the end-to-end SQLite assessment flow. |
| 2026-10-22 | Completed Phase 4. Implemented note-passage retrieval and cited Gemini/deterministic tutor replies, gap-prioritized revision scheduling, persisted chat and task APIs, interactive tutor and planner clients, responsive chat/planner styles, and the SQLite end-to-end verification workflow. |
| 2026-10-22 | Completed Phase 5 and finalized all 5/5 phases. Added live analytics aggregation, idempotent presentation demo seeding, dashboard analytics UI, setup/deployment checker, README deployment guidance, and full lifecycle verification with seeded SQLite data. |
| 2026-10-22 | Fixed Mermaid flowchart and mind map parse error (`DIAMOND_START` / line collision). Added `sanitize_mermaid` in `api/gemini_service.py` to strip markdown fences, remove invalid spaces between node IDs and shape brackets (`n1 {"text"}` -> `n1{"text"}`), split colliding statements onto separate newlines, and safely handle unescaped inner quotes. Corrected deterministic fallback templates to avoid spaces before shape brackets and routed all generated diagrams through `sanitize_mermaid()`. Added client-side `sanitizeMermaidCode` in `public/js/notes.js` and `public/js/quiz.js` right before rendering. Executed one-time database migration sanitizing existing rows in `notes` and `knowledge_gaps`. |
| 2026-10-22 | Increased file upload limit to 1 GB (1024 MB) across client and server. Updated file size validation and helper text in `public/js/notes.js` and `public/dashboard.html`. Enhanced PDF.js extraction in `public/js/notes.js` with live page progress ("Extracting PDF text: page X of Y…") and called `page.cleanup()` after every page to prevent browser memory crashes on large textbooks. Set `app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024 * 1024` in `app.py`. |
| 2026-10-23 | Restored saved-note selection by normalizing PostgreSQL JSONB arrays safely and refreshing the active note state, content panels, diagram selector, and tutor selector on note open. Removed the dashboard's stale 10 MB upload guard. Updated PDF.js to read from a local object URL instead of making a full `arrayBuffer` copy, clean each page in `finally`, release the document and URL, and stop extraction at the existing 100,000-character note limit while keeping page progress visible. Hardened Mermaid flowchart labels, generated mind maps with one root and consistent two-space nesting, and added a readable client fallback when Mermaid parsing fails. Split long RAG source text into bounded passages and retained a cited answer fallback. Verified Python and JavaScript syntax plus temporary-SQLite note list/detail and cited chat flows; live Supabase, Gemini, and browser PDF checks were unavailable in this environment. |
| 2026-10-23 | Fixed the PDF/TXT/Markdown extraction status error by moving `truncated` into the extraction function scope. Enhanced Gemini note analysis with professor-style instructions for a comprehensive 3–5 sentence executive summary, expanded contextual key points, and clear definitions. Long notes are split at sentence and paragraph boundaries with overlap, analyzed in chunks, then synthesized; deterministic summaries now draw on multiple source sentences. Verified `api/gemini_service.py` with `py_compile`. |
| 2026-10-23 | Fixed assessment and tutor chat 500 paths within `api/routes/quiz_routes.py`, `api/routes/rag_routes.py`, and `api/gemini_service.py`. Gemini JSON parsing now strips code fences and extracts valid JSON objects or arrays despite surrounding text; malformed responses fall through to deterministic quiz and flashcard generation. Quiz input fields are normalized and generation returns HTTP 200. Tutor chat now logs unexpected processing errors, builds a student-friendly fallback from note summary, key points, and definitions, and returns HTTP 200 even when saving chat history fails. Verified syntax with `python -m py_compile` on the three modified Python files. |
| 2026-10-23 | Left-aligned quiz answer options and radio buttons in `public/css/styles.css`: option rows now use flex alignment, left text alignment, 12px spacing, and 12px 16px padding; radio controls no longer inherit full-width input styling. |
| 2026-10-24 | Added an interactive student user guide and onboarding modal in `public/dashboard.html`, styled its responsive dark glass interface in `public/css/styles.css`, and wired sidebar/header entry points, six feature shortcuts, Escape/backdrop/close handling, keyboard focus management, and a persistent startup preference in `public/js/dashboard.js`. Added a PDF upload best-practices callout, English/Roman Urdu pro-tips, and FAQ. |
| 2026-10-24 | Reviewed Vercel serverless deployment using the current Flask runtime behavior. Removed legacy catch-all function routing so Vercel can route Flask API endpoints and serve `public/` assets from its CDN; configured `app.py` as the Flask function and included the runtime-read PostgreSQL schema file. Reduced runtime dependencies to Flask, flask-cors, psycopg2-binary, python-dotenv, and requests; made app-level dotenv loading defer to configured deployment environment variables; expanded `.gitignore` for environment files, virtualenvs, and Python caches; replaced credential-like values in `.env.example` with placeholders. Verified Python syntax for `app.py`, `api/index.py`, `api/db.py`, and `api/gemini_service.py`; validated `vercel.json`, the approved dependency list, and required `.gitignore` exclusions. A live Vercel deployment was not run. |
