# Message Model & Delivery Mechanic Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Messages sent between cities travel at real pigeon speed (80 km/h over great-circle distance) and are marked delivered or lost by a periodic scheduler sweep, with a distance-based loss chance.

**Architecture:** Single `messages` table in SQLite. `POST /messages` computes distance and a `FAST_FORWARD`-scaled arrival time at send. An APScheduler interval job (every 5 s, started in the FastAPI lifespan, never at import time) calls a plain function `resolve_due_messages()` that conditionally updates overdue in-flight rows — idempotent, testable without the scheduler. Spec: `docs/superpowers/specs/2026-06-10-message-model-design.md`.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0 (Mapped/mapped_column style), SQLite (WAL), APScheduler 3.x `BackgroundScheduler`, pytest + TestClient (httpx2).

**Working directory:** all commands run from `backend/` with the venv: use `.venv/bin/pytest`. Run git commands from the repo root.

**File map (final state):**

| File | Responsibility |
|---|---|
| `backend/app/cities.py` | City catalog `{name: (lat, lon)}`, haversine distance |
| `backend/app/delivery.py` | `utcnow()`, `fast_forward_factor()`, `flight_duration()`, `loss_probability()`, `resolve_due_messages()` |
| `backend/app/db.py` | Engine (SQLite WAL, busy timeout), `SessionLocal`, `Base`, `get_db` |
| `backend/app/models.py` | `Message` model + status constants + indexes |
| `backend/app/schemas.py` | `MessageCreate` (validation), `MessageOut` |
| `backend/app/routes.py` | `/messages` APIRouter |
| `backend/app/main.py` | `create_app(start_scheduler=True)`, lifespan: create tables + scheduler |
| `backend/tests/conftest.py` | `test_engine`, `db_session`, `client` fixtures |
| `backend/tests/test_cities.py` | catalog + haversine tests |
| `backend/tests/test_delivery.py` | flight time, FAST_FORWARD, loss probability, resolver tests |
| `backend/tests/test_messages_api.py` | endpoint tests |
| `backend/tests/test_scheduler.py` | lifespan wiring test |
| `backend/tests/test_health.py` | existing — graduates to the `client` fixture |

---

### Task 1: City catalog + haversine distance

**Files:**
- Create: `backend/app/cities.py`
- Test: `backend/tests/test_cities.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_cities.py`:

```python
import pytest

from app.cities import CITIES, distance_between


def test_catalog_has_cities_with_coordinates():
    assert len(CITIES) >= 15
    for name, (lat, lon) in CITIES.items():
        assert name == name.strip().lower()
        assert -90 <= lat <= 90
        assert -180 <= lon <= 180


def test_london_paris_distance_within_one_percent():
    # Known great-circle distance ~343.8 km
    assert distance_between("london", "paris") == pytest.approx(343.8, rel=0.01)


def test_distance_is_symmetric():
    assert distance_between("new york", "san francisco") == pytest.approx(
        distance_between("san francisco", "new york")
    )


def test_nyc_sf_is_about_4130_km():
    assert distance_between("new york", "san francisco") == pytest.approx(4130, rel=0.01)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_cities.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.cities'`

- [ ] **Step 3: Write the implementation**

Create `backend/app/cities.py`:

```python
import math

EARTH_RADIUS_KM = 6371.0

CITIES: dict[str, tuple[float, float]] = {
    "amsterdam": (52.3676, 4.9041),
    "berlin": (52.5200, 13.4050),
    "cairo": (30.0444, 31.2357),
    "cape town": (-33.9249, 18.4241),
    "chicago": (41.8781, -87.6298),
    "dubai": (25.2048, 55.2708),
    "hong kong": (22.3193, 114.1694),
    "istanbul": (41.0082, 28.9784),
    "london": (51.5074, -0.1278),
    "los angeles": (34.0522, -118.2437),
    "melbourne": (-37.8136, 144.9631),
    "mexico city": (19.4326, -99.1332),
    "mumbai": (19.0760, 72.8777),
    "new york": (40.7128, -74.0060),
    "paris": (48.8566, 2.3522),
    "rio de janeiro": (-22.9068, -43.1729),
    "san francisco": (37.7749, -122.4194),
    "singapore": (1.3521, 103.8198),
    "sydney": (-33.8688, 151.2093),
    "tokyo": (35.6762, 139.6503),
}


def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(h))


def distance_between(origin: str, destination: str) -> float:
    """Great-circle distance in km between two catalog cities."""
    return haversine_km(CITIES[origin], CITIES[destination])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_cities.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/cities.py backend/tests/test_cities.py
git commit -m "feat: city catalog and haversine distance"
```

---

### Task 2: Flight time, FAST_FORWARD, loss probability

**Files:**
- Create: `backend/app/delivery.py`
- Test: `backend/tests/test_delivery.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_delivery.py`:

```python
from datetime import timedelta

import pytest

from app.delivery import (
    BASE_LOSS_PROBABILITY,
    MAX_LOSS_PROBABILITY,
    fast_forward_factor,
    flight_duration,
    loss_probability,
)


def test_flight_duration_at_pigeon_speed(monkeypatch):
    monkeypatch.delenv("FAST_FORWARD", raising=False)
    # 80 km at 80 km/h = 1 hour
    assert flight_duration(80.0) == timedelta(hours=1)


def test_fast_forward_scales_duration(monkeypatch):
    monkeypatch.setenv("FAST_FORWARD", "120")
    # 80 km -> 1 pigeon-hour -> 30 real seconds at 120x
    assert flight_duration(80.0) == timedelta(seconds=30)


def test_fast_forward_unset_means_real_time(monkeypatch):
    monkeypatch.delenv("FAST_FORWARD", raising=False)
    assert fast_forward_factor() == 1.0


@pytest.mark.parametrize("bad", ["banana", "0", "-5"])
def test_invalid_fast_forward_fails_clearly(monkeypatch, bad):
    monkeypatch.setenv("FAST_FORWARD", bad)
    with pytest.raises(ValueError, match="FAST_FORWARD"):
        fast_forward_factor()


def test_loss_probability_base():
    assert loss_probability(0.0) == pytest.approx(BASE_LOSS_PROBABILITY)


def test_loss_probability_scales_with_distance():
    # 2% base + 1% per 1000 km
    assert loss_probability(5000.0) == pytest.approx(0.07)


def test_loss_probability_is_capped():
    assert loss_probability(50_000.0) == pytest.approx(MAX_LOSS_PROBABILITY)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_delivery.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.delivery'`

- [ ] **Step 3: Write the implementation**

Create `backend/app/delivery.py`:

```python
import os
from datetime import UTC, datetime, timedelta

PIGEON_SPEED_KMH = 80.0
BASE_LOSS_PROBABILITY = 0.02
LOSS_PER_1000_KM = 0.01
MAX_LOSS_PROBABILITY = 0.15


def utcnow() -> datetime:
    """Naive UTC now — the one datetime convention for the whole app."""
    return datetime.now(UTC).replace(tzinfo=None)


def fast_forward_factor() -> float:
    """Time-scale factor from the FAST_FORWARD env var. Unset means 1 (real time)."""
    raw = os.environ.get("FAST_FORWARD")
    if raw is None:
        return 1.0
    try:
        factor = float(raw)
    except ValueError:
        raise ValueError(f"FAST_FORWARD must be a number, got {raw!r}") from None
    if factor <= 0:
        raise ValueError(f"FAST_FORWARD must be > 0, got {factor}")
    return factor


def flight_duration(distance_km: float) -> timedelta:
    """Real-time duration of a pigeon flight, FAST_FORWARD applied."""
    pigeon_hours = distance_km / PIGEON_SPEED_KMH
    return timedelta(hours=pigeon_hours / fast_forward_factor())


def loss_probability(distance_km: float) -> float:
    """Chance the pigeon never arrives: 2% base + 1% per 1000 km, capped at 15%."""
    return min(
        BASE_LOSS_PROBABILITY + LOSS_PER_1000_KM * (distance_km / 1000.0),
        MAX_LOSS_PROBABILITY,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_delivery.py -v`
Expected: 9 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/delivery.py backend/tests/test_delivery.py
git commit -m "feat: flight time, FAST_FORWARD scaling, loss probability"
```

---

### Task 3: Database setup + Message model

**Files:**
- Create: `backend/app/db.py`
- Create: `backend/app/models.py`
- Create: `backend/tests/conftest.py`
- Test: `backend/tests/test_models.py`

- [ ] **Step 1: Write the shared test fixtures**

Create `backend/tests/conftest.py`:

```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models  # noqa: F401  — registers tables on Base.metadata
from app.db import Base


@pytest.fixture()
def test_engine(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def db_session(test_engine):
    TestingSession = sessionmaker(
        bind=test_engine, autoflush=False, expire_on_commit=False
    )
    session = TestingSession()
    yield session
    session.close()
```

- [ ] **Step 2: Write the failing model test**

Create `backend/tests/test_models.py`:

```python
from datetime import timedelta

from app.delivery import utcnow
from app.models import IN_FLIGHT, Message


def test_message_roundtrip(db_session):
    sent = utcnow()
    message = Message(
        sender="pratik",
        recipient="alex",
        body="wish you were here",
        origin="new york",
        destination="san francisco",
        distance_km=4130.0,
        status=IN_FLIGHT,
        sent_at=sent,
        arrival_at=sent + timedelta(hours=51),
    )
    db_session.add(message)
    db_session.commit()

    loaded = db_session.get(Message, message.id)
    assert loaded.status == IN_FLIGHT
    assert loaded.resolved_at is None
    assert loaded.arrival_at - loaded.sent_at == timedelta(hours=51)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.db'` (via conftest import)

- [ ] **Step 4: Write db.py**

Create `backend/app/db.py`:

```python
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = "sqlite:///./pigeon.db"

# check_same_thread=False: the scheduler thread and request threads share the pool.
# timeout: SQLite busy timeout so brief write locks don't error out.
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": 5},
)


@event.listens_for(engine, "connect")
def _enable_wal(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 5: Write models.py**

Create `backend/app/models.py`:

```python
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Float, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

IN_FLIGHT = "in_flight"
DELIVERED = "delivered"
LOST = "lost"


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    sender: Mapped[str] = mapped_column(String(50), index=True)
    recipient: Mapped[str] = mapped_column(String(50))
    body: Mapped[str] = mapped_column(String(500))
    origin: Mapped[str] = mapped_column(String(50))
    destination: Mapped[str] = mapped_column(String(50))
    distance_km: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(20), default=IN_FLIGHT)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=False))
    arrival_at: Mapped[datetime] = mapped_column(DateTime(timezone=False))
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('in_flight', 'delivered', 'lost')",
            name="ck_messages_status",
        ),
        Index("ix_messages_status_arrival_at", "status", "arrival_at"),
        Index("ix_messages_recipient_status", "recipient", "status"),
    )
```

(`Mapped[str]` without `Optional` makes columns `nullable=False` by default in SQLAlchemy 2.0 — only `resolved_at` is nullable, per spec.)

- [ ] **Step 6: Run tests to verify everything passes**

Run: `.venv/bin/pytest -v`
Expected: all pass (cities, delivery, models, health)

- [ ] **Step 7: Commit**

```bash
git add backend/app/db.py backend/app/models.py backend/tests/conftest.py backend/tests/test_models.py
git commit -m "feat: SQLite setup and Message model"
```

---

### Task 4: Schemas, endpoints, app wiring

**Files:**
- Create: `backend/app/schemas.py`
- Create: `backend/app/routes.py`
- Modify: `backend/app/main.py` (replace entirely — adds lifespan + router, keeps `/health`)
- Modify: `backend/tests/conftest.py` (add `client` fixture)
- Modify: `backend/tests/test_health.py` (graduate to fixture)
- Test: `backend/tests/test_messages_api.py`

- [ ] **Step 1: Add the client fixture**

Append to `backend/tests/conftest.py`:

```python
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker as _sessionmaker

from app.db import get_db
from app.main import create_app


@pytest.fixture()
def client(test_engine):
    TestingSession = _sessionmaker(
        bind=test_engine, autoflush=False, expire_on_commit=False
    )

    app = create_app(start_scheduler=False, create_tables=False)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)
```

(`create_tables=False` and `start_scheduler=False` keep the lifespan inert even if someone later wraps the client in a `with` block — nothing ever touches the real `pigeon.db`. Tables come from the `test_engine` fixture.)

- [ ] **Step 2: Write the failing API tests**

Create `backend/tests/test_messages_api.py`:

```python
from datetime import datetime

from app.models import DELIVERED, Message


def send(client, **overrides):
    payload = {
        "sender": "pratik",
        "recipient": "alex",
        "body": "wish you were here",
        "origin": "new york",
        "destination": "san francisco",
    }
    payload.update(overrides)
    return client.post("/messages", json=payload)


def test_send_message_returns_full_message(client):
    response = send(client)
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "in_flight"
    assert data["resolved_at"] is None
    assert data["distance_km"] > 4000
    assert set(data) == {
        "id", "sender", "recipient", "body", "origin", "destination",
        "distance_km", "status", "sent_at", "arrival_at", "resolved_at",
    }
    sent_at = datetime.fromisoformat(data["sent_at"])
    arrival_at = datetime.fromisoformat(data["arrival_at"])
    assert arrival_at > sent_at


def test_unknown_city_rejected(client):
    response = send(client, origin="atlantis")
    assert response.status_code == 422
    assert "valid cities" in response.text


def test_same_origin_and_destination_rejected(client):
    response = send(client, destination="new york")
    assert response.status_code == 422


def test_blank_sender_rejected(client):
    response = send(client, sender="   ")
    assert response.status_code == 422


def test_blank_body_rejected(client):
    response = send(client, body="   ")
    assert response.status_code == 422


def test_get_message_by_id(client):
    message_id = send(client).json()["id"]
    response = client.get(f"/messages/{message_id}")
    assert response.status_code == 200
    assert response.json()["id"] == message_id


def test_get_unknown_message_404(client):
    assert client.get("/messages/9999").status_code == 404


def test_list_requires_a_filter(client):
    assert client.get("/messages").status_code == 422


def test_inbox_shows_only_delivered(client, db_session):
    send(client)  # stays in flight
    delivered_id = send(client, body="made it!").json()["id"]
    message = db_session.get(Message, delivered_id)
    message.status = DELIVERED
    db_session.commit()

    inbox = client.get("/messages", params={"recipient": "alex"}).json()
    assert [m["id"] for m in inbox] == [delivered_id]


def test_sender_tracking_shows_all_statuses_newest_first(client):
    first = send(client).json()["id"]
    second = send(client, body="second pigeon").json()["id"]
    tracking = client.get("/messages", params={"sender": "pratik"}).json()
    assert [m["id"] for m in tracking] == [second, first]


def test_combined_sender_and_recipient_filters(client, db_session):
    mine = send(client).json()["id"]                 # pratik -> alex, delivered below
    other = send(client, sender="zoe").json()["id"]  # zoe -> alex, delivered below
    send(client, body="still flying")                # pratik -> alex, stays in flight
    for message_id in (mine, other):
        db_session.get(Message, message_id).status = DELIVERED
    db_session.commit()

    result = client.get(
        "/messages", params={"sender": "pratik", "recipient": "alex"}
    ).json()
    assert [m["id"] for m in result] == [mine]
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_messages_api.py -v`
Expected: ERROR on every test — the `client` fixture calls `create_app(start_scheduler=False)`, but `create_app()` takes no arguments yet: `TypeError: create_app() got an unexpected keyword argument 'start_scheduler'`

- [ ] **Step 4: Write schemas.py**

Create `backend/app/schemas.py`:

```python
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.cities import CITIES


class MessageCreate(BaseModel):
    sender: str = Field(max_length=50)
    recipient: str = Field(max_length=50)
    body: str = Field(min_length=1, max_length=500)
    origin: str
    destination: str

    @field_validator("sender", "recipient", "body")
    @classmethod
    def not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("origin", "destination")
    @classmethod
    def known_city(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in CITIES:
            raise ValueError(
                f"unknown city {value!r}; valid cities: {', '.join(sorted(CITIES))}"
            )
        return value

    @model_validator(mode="after")
    def no_zero_length_flights(self) -> "MessageCreate":
        if self.origin == self.destination:
            raise ValueError("origin and destination must differ")
        return self


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sender: str
    recipient: str
    body: str
    origin: str
    destination: str
    distance_km: float
    status: str
    sent_at: datetime
    arrival_at: datetime
    resolved_at: datetime | None
```

- [ ] **Step 5: Write routes.py**

Create `backend/app/routes.py`:

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.cities import distance_between
from app.db import get_db
from app.delivery import flight_duration, utcnow
from app.schemas import MessageCreate, MessageOut

router = APIRouter(prefix="/messages", tags=["messages"])


@router.post("", response_model=MessageOut, status_code=201)
def send_message(payload: MessageCreate, db: Session = Depends(get_db)):
    distance_km = distance_between(payload.origin, payload.destination)
    sent_at = utcnow()
    try:
        arrival_at = sent_at + flight_duration(distance_km)
    except ValueError as exc:
        # Misconfigured FAST_FORWARD — fail clearly at send time, per spec.
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    message = models.Message(
        sender=payload.sender,
        recipient=payload.recipient,
        body=payload.body,
        origin=payload.origin,
        destination=payload.destination,
        distance_km=distance_km,
        status=models.IN_FLIGHT,
        sent_at=sent_at,
        arrival_at=arrival_at,
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


@router.get("/{message_id}", response_model=MessageOut)
def get_message(message_id: int, db: Session = Depends(get_db)):
    message = db.get(models.Message, message_id)
    if message is None:
        raise HTTPException(status_code=404, detail="message not found")
    return message


@router.get("", response_model=list[MessageOut])
def list_messages(
    recipient: str | None = None,
    sender: str | None = None,
    db: Session = Depends(get_db),
):
    if recipient is None and sender is None:
        raise HTTPException(
            status_code=422, detail="provide recipient and/or sender"
        )
    query = select(models.Message)
    if recipient is not None:
        # Inbox semantics: only delivered messages — no peeking mid-flight.
        query = query.where(
            models.Message.recipient == recipient,
            models.Message.status == models.DELIVERED,
        )
    if sender is not None:
        query = query.where(models.Message.sender == sender)
    query = query.order_by(models.Message.sent_at.desc(), models.Message.id.desc())
    return db.execute(query).scalars().all()
```

- [ ] **Step 6: Rewrite main.py**

Replace `backend/app/main.py` entirely:

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import db, models  # noqa: F401  — models registers tables on Base.metadata
from app.routes import router


def create_app(start_scheduler: bool = True, create_tables: bool = True) -> FastAPI:
    # Both flags exist so tests can opt out: start_scheduler is wired up in the
    # scheduler task; create_tables=False keeps test runs away from pigeon.db.
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if create_tables:
            db.Base.metadata.create_all(bind=db.engine)
        yield

    app = FastAPI(title="Pigeon Post API", lifespan=lifespan)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(router)
    return app


app = create_app()
```

- [ ] **Step 7: Graduate test_health.py to the fixture**

Replace `backend/tests/test_health.py` entirely:

```python
def test_health_returns_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 8: Run the full suite**

Run: `.venv/bin/pytest -v`
Expected: all pass (≈23 tests)

- [ ] **Step 9: Commit**

```bash
git add backend/app/schemas.py backend/app/routes.py backend/app/main.py backend/tests/conftest.py backend/tests/test_health.py backend/tests/test_messages_api.py
git commit -m "feat: message endpoints with validation, inbox and tracking views"
```

---

### Task 5: Delivery resolver

**Files:**
- Modify: `backend/app/delivery.py` (add `resolve_due_messages`)
- Test: `backend/tests/test_delivery.py` (append resolver tests)

- [ ] **Step 1: Write the failing resolver tests**

Append to `backend/tests/test_delivery.py`:

```python
from datetime import datetime

from app.delivery import loss_probability as _p
from app.delivery import resolve_due_messages
from app.models import DELIVERED, IN_FLIGHT, LOST, Message

NOW = datetime(2026, 6, 11, 12, 0, 0)


def make_message(db_session, *, arrival_at, status=IN_FLIGHT, distance_km=4130.0):
    message = Message(
        sender="pratik",
        recipient="alex",
        body="hello",
        origin="new york",
        destination="san francisco",
        distance_km=distance_km,
        status=status,
        sent_at=datetime(2026, 6, 9, 12, 0, 0),
        arrival_at=arrival_at,
    )
    db_session.add(message)
    db_session.commit()
    return message


def test_overdue_message_is_delivered_when_roll_survives(db_session):
    message = make_message(db_session, arrival_at=datetime(2026, 6, 11, 11, 0, 0))
    count = resolve_due_messages(db_session, rng=lambda: 0.999, now=NOW)
    assert count == 1
    db_session.refresh(message)
    assert message.status == DELIVERED
    assert message.resolved_at == NOW


def test_overdue_message_is_lost_when_roll_fails(db_session):
    message = make_message(db_session, arrival_at=datetime(2026, 6, 11, 11, 0, 0))
    resolve_due_messages(db_session, rng=lambda: 0.0, now=NOW)
    db_session.refresh(message)
    assert message.status == LOST


def test_roll_exactly_at_probability_boundary_is_delivered(db_session):
    message = make_message(db_session, arrival_at=datetime(2026, 6, 11, 11, 0, 0))
    boundary = _p(message.distance_km)
    resolve_due_messages(db_session, rng=lambda: boundary, now=NOW)
    db_session.refresh(message)
    assert message.status == DELIVERED  # lost only when rng() < p


def test_future_message_left_alone(db_session):
    message = make_message(db_session, arrival_at=datetime(2026, 6, 12, 12, 0, 0))
    count = resolve_due_messages(db_session, rng=lambda: 0.0, now=NOW)
    assert count == 0
    db_session.refresh(message)
    assert message.status == IN_FLIGHT
    assert message.resolved_at is None


def test_already_resolved_message_untouched(db_session):
    message = make_message(
        db_session, arrival_at=datetime(2026, 6, 11, 11, 0, 0), status=DELIVERED
    )
    count = resolve_due_messages(db_session, rng=lambda: 0.0, now=NOW)
    assert count == 0
    db_session.refresh(message)
    assert message.status == DELIVERED
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_delivery.py -v`
Expected: FAIL — `ImportError: cannot import name 'resolve_due_messages'`

- [ ] **Step 3: Implement the resolver**

Append to `backend/app/delivery.py` (and add the imports at the top of the file):

```python
# add to the imports at the top:
import logging
import random
from collections.abc import Callable

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import DELIVERED, IN_FLIGHT, LOST, Message

logger = logging.getLogger(__name__)
```

```python
# append at the bottom:
def resolve_due_messages(
    session: Session,
    rng: Callable[[], float] = random.random,
    now: datetime | None = None,
) -> int:
    """Roll fate for overdue in-flight messages. Returns how many were resolved.

    Idempotent under overlapping sweeps: the UPDATE only applies while the row
    is still in_flight, and each row commits independently so SQLite write
    locks stay brief.
    """
    if now is None:
        now = utcnow()
    due = session.execute(
        select(Message.id, Message.distance_km).where(
            Message.status == IN_FLIGHT, Message.arrival_at <= now
        )
    ).all()
    resolved = 0
    for message_id, distance_km in due:
        try:
            status = LOST if rng() < loss_probability(distance_km) else DELIVERED
            result = session.execute(
                update(Message)
                .where(Message.id == message_id, Message.status == IN_FLIGHT)
                .values(status=status, resolved_at=now)
            )
            session.commit()
            resolved += result.rowcount or 0
        except Exception:
            # One bad row must not poison the rest of the batch.
            session.rollback()
            logger.exception("failed to resolve message %s", message_id)
    return resolved
```

- [ ] **Step 4: Run the full suite**

Run: `.venv/bin/pytest -v`
Expected: all pass (≈28 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/delivery.py backend/tests/test_delivery.py
git commit -m "feat: idempotent delivery resolver with injectable rng and clock"
```

---

### Task 6: Scheduler wiring

**Files:**
- Modify: `backend/app/main.py` (start/stop scheduler in lifespan)
- Test: `backend/tests/test_scheduler.py`

- [ ] **Step 1: Write the failing wiring test**

Create `backend/tests/test_scheduler.py`:

```python
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import db
from app.main import create_app


def test_lifespan_starts_and_stops_scheduler(tmp_path, monkeypatch):
    # Point the app at a temp DB so the lifespan's create_all and any sweep
    # that fires never touch the real pigeon.db.
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}",
        connect_args={"check_same_thread": False},
    )
    monkeypatch.setattr(db, "engine", engine)
    monkeypatch.setattr(
        db,
        "SessionLocal",
        sessionmaker(bind=engine, autoflush=False, expire_on_commit=False),
    )

    app = create_app(start_scheduler=True)
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        assert app.state.scheduler.running is True
    assert app.state.scheduler.running is False
    engine.dispose()


def test_scheduler_not_started_when_disabled(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}",
        connect_args={"check_same_thread": False},
    )
    monkeypatch.setattr(db, "engine", engine)

    app = create_app(start_scheduler=False)
    with TestClient(app):
        assert getattr(app.state, "scheduler", None) is None
    engine.dispose()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_scheduler.py -v`
Expected: FAIL — `AttributeError: 'State' object has no attribute 'scheduler'`

- [ ] **Step 3: Wire the scheduler into the lifespan**

Replace `backend/app/main.py` entirely:

```python
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI

from app import db, models  # noqa: F401  — models registers tables on Base.metadata
from app.delivery import resolve_due_messages
from app.routes import router

SWEEP_INTERVAL_SECONDS = 5


def _run_sweep() -> None:
    session = db.SessionLocal()
    try:
        resolve_due_messages(session)
    finally:
        session.close()


def create_app(start_scheduler: bool = True, create_tables: bool = True) -> FastAPI:
    # Single-process assumption: each worker would run its own scheduler, so
    # this app is dev-only until that's revisited. Scheduler starts in the
    # lifespan — never at import time.
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if create_tables:
            db.Base.metadata.create_all(bind=db.engine)
        scheduler = None
        if start_scheduler:
            scheduler = BackgroundScheduler()
            scheduler.add_job(
                _run_sweep,
                "interval",
                seconds=SWEEP_INTERVAL_SECONDS,
                max_instances=1,
                coalesce=True,
            )
            scheduler.start()
        app.state.scheduler = scheduler
        yield
        if scheduler is not None:
            scheduler.shutdown(wait=False)

    app = FastAPI(title="Pigeon Post API", lifespan=lifespan)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(router)
    return app


app = create_app()
```

Note for the wiring test: `_run_sweep` reads `db.SessionLocal` through the module, so the monkeypatch in the test reaches it.

- [ ] **Step 4: Run the full suite**

Run: `.venv/bin/pytest -v`
Expected: all pass (≈30 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/main.py backend/tests/test_scheduler.py
git commit -m "feat: APScheduler delivery sweep wired into app lifespan"
```

---

### Task 7: Housekeeping + manual verification

**Files:**
- Modify: `.gitignore` (WAL sidecar files)
- Modify: `README.md` (FAST_FORWARD section is now real; API summary)

- [ ] **Step 1: Cover SQLite WAL sidecar files**

In `.gitignore`, replace:

```
*.db
*.db-journal
```

with:

```
*.db
*.db-journal
*.db-wal
*.db-shm
```

- [ ] **Step 2: Update the README**

In `README.md`, replace the paragraph that begins "Later, once the delivery mechanic exists" with:

```markdown
To test the delivery mechanic without waiting for realistic pigeon flight
time, set the fast-forward env var (it only affects newly sent messages):

```bash
FAST_FORWARD=5000 uvicorn app.main:app --reload  # NYC → SF lands in ~37s
```
```

And add after the "Running the backend" section:

```markdown
### API at a glance

- `POST /messages` — send a pigeon: `{sender, recipient, body, origin, destination}` (city names from the built-in catalog, see `app/cities.py`)
- `GET /messages/{id}` — track one message
- `GET /messages?sender=NAME` — everything you've sent, any status
- `GET /messages?recipient=NAME` — your inbox (delivered messages only)
```

- [ ] **Step 3: Manual verification**

```bash
cd backend
FAST_FORWARD=5000 .venv/bin/uvicorn app.main:app --port 8000
```

In another shell:

```bash
curl -s -X POST localhost:8000/messages -H 'content-type: application/json' \
  -d '{"sender":"pratik","recipient":"alex","body":"hello","origin":"new york","destination":"san francisco"}'
# note the returned id and arrival_at (~37s away), then after ~45s
# (replace <id> with the returned id):
curl -s localhost:8000/messages/<id>
# status should be "delivered" (or, ~6% of the time, "lost")
curl -s 'localhost:8000/messages?recipient=alex'
# delivered → shows the message; lost → empty list
```

Stop the server. Confirm `git status` shows no `pigeon.db*` files.

- [ ] **Step 4: Run the full suite one last time**

Run: `.venv/bin/pytest -v`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add .gitignore README.md
git commit -m "docs: FAST_FORWARD usage and API summary; ignore WAL sidecars"
```
