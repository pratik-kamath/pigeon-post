# Message Model & Delivery Mechanic — Design

**Date:** 2026-06-10
**Milestone:** Phase 1, milestone 2 (follows the backend skeleton)
**Scope decision:** full core mechanic in one milestone — model, API, APScheduler delivery, loss chance, `FAST_FORWARD`.

## Goal

A sender posts a message between two cities. A virtual pigeon carries it at 80 km/h over the real great-circle distance. When the arrival time passes, a scheduled sweep decides whether the pigeon made it (distance-based loss chance). Recipients see only delivered messages; senders can track everything they sent.

## Decisions made during brainstorming

- **Scope:** full mechanic with scheduler (not send-and-view only).
- **Locations:** fixed built-in city catalog (~20 world cities with coordinates); unknown cities rejected.
- **Identity:** free-text sender/recipient handles; becomes FK to users when the auth milestone lands.
- **Loss model:** distance-based — `p = min(0.02 + 0.01 × (distance_km / 1000), 0.15)`, rolled once at resolution time.
- **Delivery resolution:** periodic sweep (one recurring APScheduler job, every 5 s) rather than one job per message — restart-safe by construction, trivially testable.
- **FAST_FORWARD:** in scope; `real duration = pigeon flight duration ÷ FAST_FORWARD` (default 1), applied at send time. Read from the environment per call, not at import.

## Data model

Table `messages`:

| Column | Type | Notes |
|---|---|---|
| `id` | int PK | |
| `sender` | str, indexed | free-text handle |
| `recipient` | str, indexed | free-text handle |
| `body` | str | 1–500 chars |
| `origin`, `destination` | str | city keys from catalog |
| `distance_km` | float | computed at send |
| `status` | str | `in_flight` → `delivered` \| `lost` |
| `sent_at` | datetime UTC | |
| `arrival_at` | datetime UTC | real wall-clock arrival, FAST_FORWARD already applied |
| `resolved_at` | datetime UTC, nullable | stamped by the sweep |

Storing `arrival_at` pre-scaled keeps the sweep to a single comparison: `status == 'in_flight' AND arrival_at <= now`.

## Components

```
backend/app/
  main.py      create_app() + lifespan: create_all(), scheduler start/stop
  db.py        SQLite engine (./pigeon.db, gitignored), SessionLocal, Base, get_db
  models.py    Message
  schemas.py   MessageCreate (city/body validation), MessageOut
  cities.py    CITIES = {name: (lat, lon)} (~20 cities), haversine()
  delivery.py  flight_time(), loss_probability(), resolve_due_messages(session, rng)
  routes.py    APIRouter for /messages endpoints
```

- Scheduler: APScheduler `BackgroundScheduler`, started/stopped in the FastAPI lifespan inside `create_app()` — **never at import time**. Interval 5 s. The job opens its own session and calls `resolve_due_messages()`.
- `resolve_due_messages(session, rng)` is a plain function taking an injectable random source — tests call it directly, no scheduler involved.
- Tables created via `Base.metadata.create_all()` at startup. Alembic deferred until the schema changes (auth milestone).

## API

| Endpoint | Behavior |
|---|---|
| `POST /messages` | `{sender, recipient, body, origin, destination}` → 201, full message (`distance_km`, `arrival_at`, `status: in_flight`) |
| `GET /messages/{id}` | any status → 200; unknown id → 404 |
| `GET /messages?recipient=X` | inbox: **delivered only** — no peeking at pigeons mid-flight |
| `GET /messages?sender=X` | tracking view: all of X's sent messages, every status |

If both params are given, they combine with AND; the presence of `recipient` keeps inbox semantics (delivered only).

## Error handling

- Unknown city → 422 (Pydantic validator; error lists valid cities)
- `origin == destination` → 422 (no zero-length flights)
- Empty body or > 500 chars → 422
- `GET /messages` with neither query param → 422 (no unscoped listing)
- Sweep resolves each due message independently; one failure doesn't poison the batch

## Testing

- **Unit:** haversine vs a known city pair (±1 %); flight-time scaling with monkeypatched `FAST_FORWARD`; loss-probability base/scaling/cap.
- **Sweep:** rows with past `arrival_at` + stubbed RNG → deterministic delivered/lost assertions; future rows untouched.
- **API:** `TestClient` with `get_db` overridden to a temp SQLite DB per test. Module-level client from milestone 1 graduates to a `create_app()`-based fixture.
- **Scheduler wiring:** one light test that lifespan starts/stops the scheduler.

Manual check: `FAST_FORWARD=5000 uvicorn app.main:app --reload`; NYC → SF ≈ 49 pigeon-hours ≈ 35 real seconds; watch the tracking view flip.

## Out of scope

Auth/users table, named pigeons and stats (Phase 2), notifications/WebSockets (Phase 3), map view, Alembic migrations, pagination.
