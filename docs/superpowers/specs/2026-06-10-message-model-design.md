# Message Model & Delivery Mechanic — Design

**Date:** 2026-06-10 (revised 2026-06-11 after Codex review)
**Milestone:** Phase 1, milestone 2 (follows the backend skeleton)
**Scope decision:** full core mechanic in one milestone, built in five sub-steps — model, API, APScheduler delivery, loss chance, `FAST_FORWARD`.

## Goal

A sender posts a message between two cities. A virtual pigeon carries it at 80 km/h over the real great-circle distance. When the arrival time passes, a scheduled sweep decides whether the pigeon made it (distance-based loss chance). Recipients see only delivered messages; senders can track everything they sent.

## Decisions made during brainstorming

- **Scope:** full mechanic with scheduler (not send-and-view only).
- **Locations:** fixed built-in city catalog (~20 world cities with coordinates); unknown cities rejected.
- **Identity:** free-text sender/recipient handles; becomes FK to users when the auth milestone lands.
- **Loss model:** distance-based — `p = min(0.02 + 0.01 × (distance_km / 1000), 0.15)`, rolled once at resolution time.
- **Delivery resolution:** periodic sweep (one recurring APScheduler job, every 5 s) rather than one job per message — restart-safe by construction, trivially testable.
- **FAST_FORWARD:** in scope; `real duration = pigeon flight duration ÷ FAST_FORWARD`, applied at send time.

## FAST_FORWARD contract

- Affects **only newly created messages**: `arrival_at` is computed once at send time and never recomputed if `FAST_FORWARD` changes later. The sweep never reads `FAST_FORWARD`.
- Read from the environment per call (not at import). Unset → `1`. Invalid or `<= 0` → fail clearly at send time (500 with a clear log, not silent nonsense).

## Datetime convention

- Store **naive UTC** datetimes in SQLite: columns are `DateTime(timezone=False)`; values generated via `datetime.now(UTC).replace(tzinfo=None)`.
- Never compare aware and naive datetimes. API docs describe all datetime fields as UTC.

## Data model

Table `messages` — all columns `nullable=False` except `resolved_at`:

| Column | Type | Notes |
|---|---|---|
| `id` | int PK | |
| `sender` | str(50) | stripped, non-empty, max 50 chars |
| `recipient` | str(50) | stripped, non-empty, max 50 chars |
| `body` | str | 1–500 chars |
| `origin`, `destination` | str | city keys from catalog |
| `distance_km` | float | computed at send |
| `status` | constrained str enum | `in_flight` → `delivered` \| `lost` |
| `sent_at` | naive UTC datetime | |
| `arrival_at` | naive UTC datetime | real wall-clock arrival, FAST_FORWARD already applied |
| `resolved_at` | naive UTC datetime, nullable | stamped by the sweep |

Indexes: `(status, arrival_at)` for the sweep; `(recipient, status)` for the inbox.

Storing `arrival_at` pre-scaled keeps the sweep to a single comparison: `status == 'in_flight' AND arrival_at <= now`.

## Components

```
backend/app/
  main.py      create_app(start_scheduler: bool = True) + lifespan: create_all(), scheduler start/stop
  db.py        SQLite engine (./pigeon.db, gitignored), SessionLocal, Base, get_db
  models.py    Message
  schemas.py   MessageCreate (city/body/handle validation), MessageOut
  cities.py    CITIES = {name: (lat, lon)} (~20 cities), haversine_km(), distance_between()
  delivery.py  flight_duration(), loss_probability(), resolve_due_messages()
  routes.py    APIRouter for /messages endpoints
```

- Scheduler: APScheduler `BackgroundScheduler`, started/stopped in the FastAPI lifespan inside `create_app()` — **never at import time**. Interval 5 s, `max_instances=1`, `coalesce=True`. The job opens its own session and calls `resolve_due_messages()`.
- `create_app(start_scheduler=False)` skips scheduler startup — this is what API tests use, so test runs never spawn a background thread writing to the wrong DB.
- Single-process/dev-only assumption: multiple uvicorn workers would each run a scheduler. Acceptable for now; noted as a constraint, revisit if deployment ever matters.
- Tables created via `Base.metadata.create_all()` at startup. Alembic deferred until the schema changes (auth milestone).
- SQLite engine configured with a busy/write timeout and WAL mode to keep request/sweep contention brief.

## Delivery resolution

Signature: `resolve_due_messages(session, rng=random.random, now=None)`

- `rng` is `Callable[[], float]` returning `[0.0, 1.0)`. A message is **lost when `rng() < loss_probability(distance_km)`**.
- `now` defaults to current naive UTC; injectable for tests.
- **Idempotent conditional update** (safe under overlapping sweeps): select due ids, roll the outcome per id, then
  `UPDATE messages SET status=..., resolved_at=... WHERE id=... AND status='in_flight'` — only count rows where `rowcount == 1`.
- Short transactions: each row's resolution commits independently, so SQLite write locks stay brief and one failure doesn't poison the batch.

## API

| Endpoint | Behavior |
|---|---|
| `POST /messages` | `{sender, recipient, body, origin, destination}` → 201, `MessageOut` |
| `GET /messages/{id}` | any status → 200; unknown id → 404 |
| `GET /messages?recipient=X` | inbox: **delivered only** — no peeking at pigeons mid-flight |
| `GET /messages?sender=X` | tracking view: all of X's sent messages, every status |

If both params are given, they combine with AND; the presence of `recipient` keeps inbox semantics (delivered only).

List endpoints return newest first: `ORDER BY sent_at DESC, id DESC`.

`MessageOut` fields, explicitly: `id, sender, recipient, body, origin, destination, distance_km, status, sent_at, arrival_at, resolved_at`.

## Error handling

- Unknown city → 422 (Pydantic validator; error lists valid cities)
- `origin == destination` → 422 (no zero-length flights)
- Empty body or > 500 chars → 422; empty/oversized handles → 422
- `GET /messages` with neither query param → 422 (no unscoped listing)
- Invalid `FAST_FORWARD` (non-numeric or ≤ 0) → clear failure at send time

## Implementation sub-steps

Built and tested in this order, each one green before the next:

1. **Pure functions:** city catalog, `haversine()`, `flight_time()`, `loss_probability()` — unit tests only, no DB.
2. **Persistence:** SQLAlchemy model, engine/session setup, table creation.
3. **API:** POST and GET endpoints with TestClient tests — scheduler not started.
4. **Resolver:** `resolve_due_messages()` with direct unit tests (stubbed `rng`/`now`).
5. **Wiring:** APScheduler lifespan integration + manual FAST_FORWARD check.

## Testing

- **Unit:** haversine vs a known city pair (±1 %); flight-time scaling with monkeypatched `FAST_FORWARD`; loss-probability base/scaling/cap **and the exact boundary** (`rng() == p` → delivered, since lost requires `<`).
- **Resolver:** rows with past `arrival_at` + stubbed `rng`/`now` → deterministic delivered/lost assertions; future rows untouched; already-resolved rows untouched (idempotency).
- **API:** `TestClient` against `create_app(start_scheduler=False)` with `get_db` overridden to a temp SQLite DB per test. Module-level client from milestone 1 graduates to a fixture.
- **Scheduler wiring:** one dedicated test using `create_app(start_scheduler=True)` with a temp DB, asserting the scheduler starts and stops with the lifespan.

Manual check: `FAST_FORWARD=5000 uvicorn app.main:app --reload`; NYC → SF is roughly 50–52 pigeon-hours ≈ 36–38 real seconds; watch the tracking view flip.

## Out of scope

Auth/users table, named pigeons and stats (Phase 2), notifications/WebSockets (Phase 3), map view, Alembic migrations, pagination, multi-worker deployment.
