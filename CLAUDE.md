# Pigeon Post

Fun-and-learn messaging app where messages travel at real pigeon flight speed. Personal learning project, built in small phased milestones (roadmap in README). Phase 1 in progress — only the backend skeleton exists so far.

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

- Future rule: never start APScheduler at import time; wire it into the app lifespan inside `create_app()`.
- README's `FAST_FORWARD` env var is a planned feature, not built yet.
