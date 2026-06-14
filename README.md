# Pigeon Post

A fun, learning-oriented messaging app where messages are carried by virtual pigeons. Each message takes real-world pigeon-flight time to arrive (NYC → SF takes about 52 hours at 80 km/h), and there's a small chance the pigeon never makes it.

This is a personal learning project — not production software. The codebase is being built in phases, one small milestone at a time.

## Tech stack

**Backend:** Python 3.12 · FastAPI · SQLAlchemy · SQLite · APScheduler

**Frontend:** React · Vite · TypeScript

## Roadmap

- **Phase 1 — Core mechanic (complete).** Auth, send messages, scheduled arrival with chance of being lost, inbox, live pixel-map dashboard.
- **Phase 2 — Gamification.** Named pigeons with stats, leveling, feeding, training mini-games.
- **Phase 3 — Polish.** Notifications, real-time updates via WebSockets, richer delivery reports.

## Getting started

### Prerequisites

- [pyenv](https://github.com/pyenv/pyenv) (or any way to get Python 3.12)
- Node.js 20+ (for the frontend)

### Backend setup

```bash
cd backend

# pyenv will auto-pick Python 3.12.12 here (see backend/.python-version)
python -m venv .venv
source .venv/bin/activate

# requirements-dev.txt pulls in requirements.txt plus test tools (pytest, httpx2)
pip install -r requirements-dev.txt
```

### Running the backend

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload
```

The API will be available at <http://localhost:8000>. Interactive docs at <http://localhost:8000/docs>.

To test the delivery mechanic without waiting for realistic pigeon flight
time, set the fast-forward env var (it only affects newly sent messages):

```bash
FAST_FORWARD=5000 uvicorn app.main:app --reload  # NYC → SF lands in ~37s
```

### API at a glance

- `POST /auth/register` — `{username, email, password}` → access + refresh token pair
- `POST /auth/login` — `{email, password}` → token pair
- `POST /auth/google` — `{id_token}` (a Google ID token) → token pair; creates a new account or links to an existing one by verified email. Needs `GOOGLE_CLIENT_ID` set.
- `POST /auth/refresh` — `{refresh_token}` → rotated token pair (old one is revoked)
- `POST /auth/logout` — `{refresh_token}` revoked
- `GET /auth/me` — current user (send `Authorization: Bearer <access_token>`)
- `GET /cities` — the city catalog `[{name, lat, lon}]` (public; used by the map and send form)
- `POST /messages` — send a pigeon (auth required): `{recipient, body, origin, destination}`. `recipient` is a registered **username**; unknown → 404. Sender is taken from your access token. City names come from the built-in catalog (see `app/cities.py`).
- `GET /messages/inbox` — your inbox: delivered messages addressed to you (auth required)
- `GET /messages/sent` — everything you've sent, any status (auth required)
- `GET /messages/{id}` — track one message; visible only to its sender and recipient (auth required)

Set `JWT_SECRET` in real deployments; a dev default is baked in. Access tokens
last 15 minutes — use `/auth/refresh` to stay logged in. Set `GOOGLE_CLIENT_ID`
(your Google OAuth client ID) to enable `POST /auth/google`. Set `CORS_ORIGINS`
(comma-separated, e.g. `http://localhost:5173`) to allow the frontend origin.

Frontend env vars (in `frontend/.env`): `VITE_API_BASE_URL` (defaults to `http://localhost:8000`) and `VITE_GOOGLE_CLIENT_ID` (same OAuth client ID, enables the Google sign-in button).

### Running tests

```bash
cd backend
source .venv/bin/activate
pytest
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env   # set VITE_API_BASE_URL (default http://localhost:8000)
                       # and VITE_GOOGLE_CLIENT_ID (optional, enables Google sign-in)
npm run dev            # Vite dev server, http://localhost:5173
```

The dev server expects the backend running with CORS allowing the frontend origin:

```bash
cd backend
CORS_ORIGINS=http://localhost:5173 FAST_FORWARD=5000 uvicorn app.main:app --reload
```

Frontend tests: `npm test` (Vitest) · lint: `npm run lint` · build: `npm run build` · e2e smoke: `npm run test:e2e` (Playwright — first run once: `npx playwright install chromium`).

The dashboard is a Pokémon-style pixel world map: log in (password or Google), send a pigeon, and watch it fly between cities in real time.

## Project layout

```
pigeon-post/
├── backend/                  Python FastAPI service
│   ├── app/                  Application code
│   ├── tests/                Pytest tests
│   ├── requirements.txt      Runtime dependencies
│   ├── requirements-dev.txt  Dev/test dependencies (includes runtime)
│   └── .python-version       pyenv-pinned Python version
├── frontend/                 React + Vite + TypeScript pixel-RPG dashboard
└── README.md
```

## License

MIT — see [LICENSE](LICENSE).
