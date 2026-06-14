# Pigeon Post

Fun-and-learn messaging app where messages travel at real pigeon flight speed. Personal learning project, built in small phased milestones (roadmap in README). Phase 1 in progress — the messaging core exists (message model, send/track/inbox endpoints, APScheduler delivery sweep) and password auth with a JWT access/refresh pair (`/auth/*`). Messages are tied to user accounts, and Google sign-in is implemented (`POST /auth/google`, verify-ID-token flow). Still to come: the frontend.

## Commands

Run all backend commands from `backend/` (pyenv reads `.python-version` there, not from the repo root):

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt   # includes runtime deps
pytest                                # tests
uvicorn app.main:app --reload         # dev server :8000, docs at /docs
```

## Architecture

- `backend/app/main.py` — `create_app()` factory; the module-level `app = create_app()` must stay exported for uvicorn.
- `backend/tests/` — pytest; config in `backend/pytest.ini`.
- Frontend (React/Vite/TS) doesn't exist yet (later milestone).

## Workflow

- Use the superpowers plugin skills: `brainstorming` before any new feature or behavior change, `test-driven-development` while implementing (write the test first, watch it fail meaningfully), `systematic-debugging` for any bug.
- This is a learning project: build one small milestone at a time and explain each piece — no end-to-end code dumps, no scope creep.
- Plans get an external Codex critique before approval: write the plan down and provide a ready-to-paste critique prompt.

## Gotchas

- Never start APScheduler at import time — it's wired into the app lifespan inside `create_app()` (tests pass `start_scheduler=False`).
- `FAST_FORWARD` only affects newly sent messages: `arrival_at` is fixed at send time and the sweep never reads the env var.
- The app is single-process/dev-only: multiple uvicorn workers would each run their own delivery scheduler.
- Refresh tokens rotate on every use; replaying an old one revokes all of a user's tokens (reuse detection). Tests that refresh twice must use the newest token.
- All `/messages` endpoints require a bearer access token. The sender is always the token's user (any `sender` in the body is ignored); the recipient is looked up by username (case-insensitive) and must exist.
- SQLite enforces foreign keys only because of the `Engine`-level `PRAGMA foreign_keys=ON` listener in `db.py`; without it the `Message` → `User` FKs would be silently unenforced.
- No migrations in dev: the schema is created by `Base.metadata.create_all`, which never ALTERs an existing table. After a schema-changing milestone, delete the gitignored `backend/pigeon.db*` so the dev DB is recreated cleanly.
- `POST /auth/google` verifies a Google ID token (no redirect flow) and needs `GOOGLE_CLIENT_ID` set, else it returns 500. Verification is isolated in `app/google_auth.py` behind `verify_google_id_token` — tests monkeypatch that seam (and patch `app.auth_routes.verify_google_id_token` for route tests). A Google login auto-links to an existing account by verified email; password-side emails aren't verified, a documented trust tradeoff.
