# Pigeon Post

A fun, learning-oriented messaging app where messages are carried by virtual pigeons. Each message takes real-world pigeon-flight time to arrive (NYC → SF takes about 49 hours at 80 km/h), and there's a small chance the pigeon never makes it.

This is a personal learning project — not production software. The codebase is being built in phases, one small milestone at a time.

## Tech stack

**Backend:** Python 3.12 · FastAPI · SQLAlchemy · SQLite · APScheduler

**Frontend (Phase 1):** React · Vite · TypeScript

## Roadmap

- **Phase 1 — Core mechanic (in progress).** Auth, send messages, scheduled arrival with chance of being lost, inbox, live progress dashboard.
- **Phase 2 — Gamification.** Named pigeons with stats, leveling, feeding, training mini-games.
- **Phase 3 — Polish.** Map view, notifications, real-time updates via WebSockets, richer delivery reports.

## Getting started

### Prerequisites

- [pyenv](https://github.com/pyenv/pyenv) (or any way to get Python 3.12)
- Node.js 20+ (for the frontend, when Phase 1 reaches the frontend milestones)

### Backend setup

```bash
cd backend

# pyenv will auto-pick Python 3.12.12 here (see backend/.python-version)
python -m venv .venv
source .venv/bin/activate

# requirements-dev.txt pulls in requirements.txt plus test tools (pytest, httpx)
pip install -r requirements-dev.txt
```

### Running the backend

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload
```

The API will be available at <http://localhost:8000>. Interactive docs at <http://localhost:8000/docs>.

To test the delivery mechanic without waiting for realistic pigeon flight time, set the fast-forward env var:

```bash
FAST_FORWARD=120 uvicorn app.main:app --reload  # 1 real hour = 30s of pigeon time
```

### Running tests

```bash
cd backend
source .venv/bin/activate
pytest
```

## Project layout

```
pigeon-post/
├── backend/                  Python FastAPI service
│   ├── app/                  Application code
│   ├── tests/                Pytest tests
│   ├── requirements.txt      Runtime dependencies
│   ├── requirements-dev.txt  Dev/test dependencies (includes runtime)
│   └── .python-version       pyenv-pinned Python version
├── frontend/                 React + Vite + TypeScript (Phase 1, later milestones)
└── README.md
```

## License

MIT — see [LICENSE](LICENSE).
