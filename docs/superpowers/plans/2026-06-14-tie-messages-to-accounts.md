# Tie Messages to User Accounts — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every pigeon message belong to real accounts — sent by the authenticated user, addressed to a registered user by username — and scope all message reads to the caller.

**Architecture:** Replace `Message.sender`/`Message.recipient` free-text columns with `sender_id`/`recipient_id` foreign keys into `users`, exposing usernames through read-only properties so the API response shape is unchanged. All `/messages` endpoints gain the `get_current_user` bearer guard. Listing splits into `GET /messages/inbox` and `GET /messages/sent`; track-by-id is restricted to the two parties. SQLite foreign-key enforcement is turned on so the FKs are real.

**Tech Stack:** Python 3.12 · FastAPI · SQLAlchemy 2.0 · SQLite · pytest · PyJWT (existing auth).

**Spec:** `docs/superpowers/specs/2026-06-14-tie-messages-to-accounts-design.md`

---

## File Structure

| File | Change | Responsibility |
|---|---|---|
| `backend/app/db.py` | Modify | Add an `Engine`-level `PRAGMA foreign_keys=ON` connect listener so FKs are enforced on **every** SQLite connection (prod engine *and* the per-test engines). |
| `backend/app/models.py` | Modify | `Message` gets `sender_id`/`recipient_id` FKs, `sender_user`/`recipient_user` relationships, `sender`/`recipient` username properties, updated indexes, and a self-send `CheckConstraint`. |
| `backend/app/schemas.py` | Modify | `MessageCreate` drops `sender`. `MessageOut` unchanged. |
| `backend/app/routes.py` | Rewrite | All endpoints auth-guarded; send-by-username; `/inbox`, `/sent`, party-restricted `/{id}`. |
| `backend/tests/test_db.py` | Create | Verify FK enforcement is on. |
| `backend/tests/test_models.py` | Modify | Roundtrip via FK ids; self-send and dangling-FK integrity tests. |
| `backend/tests/test_delivery.py` | Modify | `make_message` seeds a sender/recipient user pair. |
| `backend/tests/test_messages_api.py` | Rewrite | Auth-driven API tests for send/inbox/sent/track. |
| `README.md` (repo root) | Modify | Update the `/messages` API section. |
| `CLAUDE.md` (repo root) | Modify | Update Phase 1 status + add a gotcha. |

> **Why model+routes+all-tests move together (Task 2):** changing `sender`/`recipient` from columns to properties breaks both the write path (`Message(sender=...)`) and the read queries (`where(Message.recipient == ...)`) at once. There is no green intermediate state that migrates the model without also migrating every endpoint, so Task 2 is one atomic, fully-green commit. Task 1 (pragma) and Task 3 (docs) are independent.

---

## Task 1: Enforce SQLite foreign keys

**Files:**
- Modify: `backend/app/db.py`
- Test: `backend/tests/test_db.py` (create)

> SQLite ignores foreign keys unless `PRAGMA foreign_keys=ON` is set per connection. The spec said "add it to the existing connect listener"; we instead register an **`Engine`-class-level** listener (the canonical SQLAlchemy recipe) so the per-test engines in `conftest.py` — which are built separately and never see the prod engine's listener — also enforce FKs. The WAL pragma stays on the prod engine only.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_db.py`:

```python
from sqlalchemy import text


def test_foreign_keys_enforced(db_session):
    # SQLite defaults this OFF; the app must turn it ON for FK integrity.
    enabled = db_session.execute(text("PRAGMA foreign_keys")).scalar()
    assert enabled == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_db.py -v`
Expected: FAIL — `assert 0 == 1` (pragma defaults off on the test engine).

- [ ] **Step 3: Add the Engine-level listener**

In `backend/app/db.py`, add the imports and a new listener. Add `sqlite3` and `Engine`:

```python
import sqlite3

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
```

Then, below the existing `_enable_wal` listener, add:

```python
@event.listens_for(Engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
    # Engine-level so every engine (prod and the per-test engines) enforces FKs.
    # Guard for SQLite only — this listener fires for ANY engine in the process.
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_db.py -v`
Expected: PASS.

- [ ] **Step 5: Run the full suite (nothing else should break)**

Run: `cd backend && pytest -q`
Expected: PASS — all existing tests still green (existing `refresh_tokens.user_id` FKs are always satisfied in tests).

- [ ] **Step 6: Commit**

```bash
cd backend && git add app/db.py tests/test_db.py
git commit -m "feat: enforce SQLite foreign keys via Engine-level pragma"
```

---

## Task 2: Migrate messages to user foreign keys (model + schemas + routes + tests)

**Files:**
- Modify: `backend/app/models.py`
- Modify: `backend/app/schemas.py`
- Rewrite: `backend/app/routes.py`
- Modify: `backend/tests/test_models.py`
- Modify: `backend/tests/test_delivery.py`
- Rewrite: `backend/tests/test_messages_api.py`

This task is done test-first: write/adjust all failing tests, watch them fail, then implement model → schemas → routes until the whole suite is green, then one commit.

### Step 1: Rewrite the API test suite (failing)

- [ ] Replace the entire contents of `backend/tests/test_messages_api.py` with:

```python
from datetime import datetime

from app.models import DELIVERED, IN_FLIGHT, LOST, Message


def register(client, username, password="password123"):
    """Register a user and return their access token."""
    resp = client.post(
        "/auth/register",
        json={"username": username, "email": f"{username}@example.com", "password": password},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["access_token"]


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def send(client, token, *, recipient="alex", **overrides):
    payload = {
        "recipient": recipient,
        "body": "wish you were here",
        "origin": "new york",
        "destination": "san francisco",
    }
    payload.update(overrides)
    return client.post("/messages", json=payload, headers=auth(token))


def send_ok(client, token, **overrides):
    """Send and assert it was created, returning the new message id.

    Asserting 201 up front means a broken send path fails on the status code
    (clear) instead of a later KeyError on ["id"] (noise).
    """
    resp = send(client, token, **overrides)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def set_status(db_session, message_id, status):
    db_session.get(Message, message_id).status = status
    db_session.commit()


# --- POST /messages ---------------------------------------------------------

def test_send_requires_auth(client):
    register(client, "alex")
    resp = client.post(
        "/messages",
        json={"recipient": "alex", "body": "hi", "origin": "new york",
              "destination": "san francisco"},
    )
    assert resp.status_code == 401


def test_send_returns_full_message_with_usernames(client):
    register(client, "alex")
    token = register(client, "pratik")
    resp = send(client, token)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["sender"] == "pratik"
    assert data["recipient"] == "alex"
    assert data["status"] == "in_flight"
    assert data["resolved_at"] is None
    assert data["distance_km"] > 4000
    assert set(data) == {
        "id", "sender", "recipient", "body", "origin", "destination",
        "distance_km", "status", "sent_at", "arrival_at", "resolved_at",
    }
    assert datetime.fromisoformat(data["arrival_at"]) > datetime.fromisoformat(data["sent_at"])


def test_sender_comes_from_token_not_body(client):
    register(client, "alex")
    token = register(client, "pratik")
    # A stray "sender" field in the body is ignored; identity is the token's.
    resp = send(client, token, sender="somebodyelse")
    assert resp.status_code == 201
    assert resp.json()["sender"] == "pratik"


def test_send_to_unknown_recipient_404(client):
    token = register(client, "pratik")
    resp = send(client, token, recipient="ghost")
    assert resp.status_code == 404


def test_recipient_lookup_is_case_insensitive(client):
    register(client, "alex")
    token = register(client, "pratik")
    resp = send(client, token, recipient="ALEX")
    assert resp.status_code == 201
    assert resp.json()["recipient"] == "alex"


def test_cannot_send_to_self(client):
    token = register(client, "pratik")
    resp = send(client, token, recipient="pratik")
    assert resp.status_code == 422


def test_unknown_city_rejected(client):
    register(client, "alex")
    token = register(client, "pratik")
    assert send(client, token, origin="atlantis").status_code == 422


def test_same_origin_and_destination_rejected(client):
    register(client, "alex")
    token = register(client, "pratik")
    assert send(client, token, destination="new york").status_code == 422


def test_blank_body_rejected(client):
    register(client, "alex")
    token = register(client, "pratik")
    assert send(client, token, body="   ").status_code == 422


# --- GET /messages/{id} -----------------------------------------------------

def test_sender_can_track_in_any_state(client, db_session):
    register(client, "alex")
    token = register(client, "pratik")
    message_id = send_ok(client, token)
    set_status(db_session, message_id, LOST)
    resp = client.get(f"/messages/{message_id}", headers=auth(token))
    assert resp.status_code == 200
    assert resp.json()["status"] == "lost"


def test_recipient_can_track_in_any_state(client, db_session):
    alex = register(client, "alex")
    token = register(client, "pratik")
    message_id = send_ok(client, token)  # still in flight
    resp = client.get(f"/messages/{message_id}", headers=auth(alex))
    assert resp.status_code == 200
    assert resp.json()["status"] == "in_flight"


def test_non_party_gets_404(client):
    register(client, "alex")
    token = register(client, "pratik")
    zoe = register(client, "zoe")
    message_id = send_ok(client, token)
    assert client.get(f"/messages/{message_id}", headers=auth(zoe)).status_code == 404


def test_track_unknown_message_404(client):
    token = register(client, "pratik")
    assert client.get("/messages/9999", headers=auth(token)).status_code == 404


def test_track_requires_auth(client):
    register(client, "alex")
    token = register(client, "pratik")
    message_id = send_ok(client, token)
    assert client.get(f"/messages/{message_id}").status_code == 401


def test_old_query_param_listing_is_gone(client):
    # The leaky GET /messages?recipient=NAME endpoint was removed; only POST
    # lives at that path, so GET must not return anyone's mail.
    token = register(client, "pratik")
    resp = client.get("/messages", params={"recipient": "pratik"}, headers=auth(token))
    assert resp.status_code == 405


# --- GET /messages/inbox ----------------------------------------------------

def test_inbox_shows_only_my_delivered_newest_first(client, db_session):
    alex = register(client, "alex")
    token = register(client, "pratik")
    in_flight = send_ok(client, token)                      # stays in flight
    first = send_ok(client, token, body="one")
    second = send_ok(client, token, body="two")
    set_status(db_session, first, DELIVERED)
    set_status(db_session, second, DELIVERED)

    inbox = client.get("/messages/inbox", headers=auth(alex)).json()
    assert [m["id"] for m in inbox] == [second, first]
    assert in_flight not in [m["id"] for m in inbox]


def test_inbox_is_scoped_to_me(client, db_session):
    alex = register(client, "alex")
    token = register(client, "pratik")
    zoe = register(client, "zoe")
    mine = send_ok(client, token, recipient="zoe")
    set_status(db_session, mine, DELIVERED)
    # zoe sees the delivered message; alex (no delivered mail) sees nothing.
    assert client.get("/messages/inbox", headers=auth(zoe)).json()[0]["id"] == mine
    assert client.get("/messages/inbox", headers=auth(alex)).json() == []


def test_inbox_requires_auth(client):
    assert client.get("/messages/inbox").status_code == 401


# --- GET /messages/sent -----------------------------------------------------

def test_sent_shows_all_my_statuses_newest_first(client, db_session):
    register(client, "alex")
    token = register(client, "pratik")
    first = send_ok(client, token)
    second = send_ok(client, token, body="second")
    set_status(db_session, first, LOST)  # still shows in sent
    sent = client.get("/messages/sent", headers=auth(token)).json()
    assert [m["id"] for m in sent] == [second, first]
    statuses = {m["id"]: m["status"] for m in sent}
    assert statuses[first] == "lost"


def test_sent_is_scoped_to_me(client):
    register(client, "alex")
    token = register(client, "pratik")
    zoe = register(client, "zoe")
    send_ok(client, token)
    assert client.get("/messages/sent", headers=auth(zoe)).json() == []


def test_sent_requires_auth(client):
    assert client.get("/messages/sent").status_code == 401
```

- [ ] **Step 2: Run the API tests to confirm they fail meaningfully**

Run: `cd backend && pytest tests/test_messages_api.py -q`
Expected: FAIL — `recipient`-only payload rejected / `sender` no longer settable / `/messages/inbox` 404s. (Failures, not collection errors.)

### Step 2: Update the model-layer tests (failing)

- [ ] In `backend/tests/test_models.py`, replace the `test_message_roundtrip` function and add two integrity tests. Replace lines 10-29 (the existing `test_message_roundtrip`) with:

```python
def test_message_roundtrip(db_session):
    sender = User(username="pratik", email="pratik@example.com",
                  password_hash="x", created_at=utcnow())
    recipient = User(username="alex", email="alex@example.com",
                     password_hash="x", created_at=utcnow())
    db_session.add_all([sender, recipient])
    db_session.commit()

    sent = utcnow()
    message = Message(
        sender_id=sender.id,
        recipient_id=recipient.id,
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
    assert loaded.sender == "pratik"      # property resolves to username
    assert loaded.recipient == "alex"
    assert loaded.arrival_at - loaded.sent_at == timedelta(hours=51)


def test_cannot_send_to_self(db_session):
    user = _user()
    db_session.add(user)
    db_session.commit()
    db_session.add(Message(
        sender_id=user.id, recipient_id=user.id, body="hi",
        origin="new york", destination="san francisco", distance_km=1.0,
        status=IN_FLIGHT, sent_at=utcnow(), arrival_at=utcnow(),
    ))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_message_requires_real_users(db_session):
    db_session.add(Message(
        sender_id=9999, recipient_id=9998, body="hi",
        origin="new york", destination="san francisco", distance_km=1.0,
        status=IN_FLIGHT, sent_at=utcnow(), arrival_at=utcnow(),
    ))
    with pytest.raises(IntegrityError):
        db_session.commit()
```

> `_user`, `utcnow`, `IN_FLIGHT`, `Message`, `User`, `timedelta`, `pytest`, and `IntegrityError` are all already imported/defined in this file.

- [ ] **Step 3: Run model tests to confirm they fail**

Run: `cd backend && pytest tests/test_models.py -q`
Expected: FAIL — `Message` has no `sender_id` keyword yet (`TypeError`).

### Step 3: Update the delivery test helper (failing)

- [ ] In `backend/tests/test_delivery.py`, update the import line (line 13) to include `User`:

```python
from app.models import DELIVERED, IN_FLIGHT, LOST, Message, User
```

- [ ] Replace the `make_message` helper (lines 56-70) with a version that seeds a reusable user pair:

```python
def _ensure_users(db_session):
    sender = db_session.query(User).filter_by(username="sender").one_or_none()
    if sender is None:
        sender = User(username="sender", email="sender@example.com",
                      password_hash="x", created_at=NOW)
        recipient = User(username="recipient", email="recipient@example.com",
                         password_hash="x", created_at=NOW)
        db_session.add_all([sender, recipient])
        db_session.commit()
        return sender.id, recipient.id
    recipient = db_session.query(User).filter_by(username="recipient").one()
    return sender.id, recipient.id


def make_message(db_session, *, arrival_at, status=IN_FLIGHT, distance_km=4130.0):
    sender_id, recipient_id = _ensure_users(db_session)
    message = Message(
        sender_id=sender_id,
        recipient_id=recipient_id,
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
```

### Step 4: Implement the model change

- [ ] In `backend/app/models.py`, add `relationship` to the ORM import:

```python
from sqlalchemy.orm import Mapped, mapped_column, relationship
```

- [ ] Replace the `Message` class body (the `sender`/`recipient` columns and `__table_args__`) so it reads:

```python
class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    recipient_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
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

    sender_user: Mapped["User"] = relationship(foreign_keys=[sender_id])
    recipient_user: Mapped["User"] = relationship(foreign_keys=[recipient_id])

    @property
    def sender(self) -> str:
        return self.sender_user.username

    @property
    def recipient(self) -> str:
        return self.recipient_user.username

    __table_args__ = (
        CheckConstraint(
            "status IN ('in_flight', 'delivered', 'lost')",
            name="ck_messages_status",
        ),
        CheckConstraint(
            "sender_id <> recipient_id", name="ck_messages_distinct_parties"
        ),
        Index("ix_messages_status_arrival_at", "status", "arrival_at"),
        Index("ix_messages_recipient_id_status", "recipient_id", "status"),
    )
```

- [ ] **Step 5: Run model + delivery tests**

Run: `cd backend && pytest tests/test_models.py tests/test_delivery.py -q`
Expected: PASS.

> The **full** suite is intentionally still red here — `tests/test_messages_api.py` fails because `schemas.py`/`routes.py` aren't updated yet (the route still builds `Message(sender=...)` and the old read queries reference the removed columns). Run only the two files above at this checkpoint; the single green commit for this task comes after Step 7.

### Step 5: Implement the schema change

- [ ] In `backend/app/schemas.py`, update `MessageCreate` (lines 11-40): remove the `sender` field and drop `sender` from the `not_blank` validator decorator. Result:

```python
class MessageCreate(BaseModel):
    recipient: str = Field(max_length=50)
    body: str = Field(min_length=1, max_length=500)
    origin: str
    destination: str

    @field_validator("recipient", "body")
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
```

`MessageOut` is unchanged.

### Step 6: Rewrite the routes

- [ ] Replace the entire contents of `backend/app/routes.py` with:

```python
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app import models
from app.auth_routes import get_current_user
from app.cities import distance_between
from app.db import get_db
from app.delivery import flight_duration, utcnow
from app.schemas import MessageCreate, MessageOut

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/messages", tags=["messages"])


@router.post("", response_model=MessageOut, status_code=201)
def send_message(
    payload: MessageCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    recipient = db.execute(
        select(models.User).where(
            func.lower(models.User.username) == payload.recipient.lower()
        )
    ).scalar_one_or_none()
    if recipient is None:
        raise HTTPException(status_code=404, detail="recipient not found")
    if recipient.id == current_user.id:
        raise HTTPException(
            status_code=422, detail="can't send a pigeon to yourself"
        )

    distance_km = distance_between(payload.origin, payload.destination)
    sent_at = utcnow()
    try:
        arrival_at = sent_at + flight_duration(distance_km)
    except ValueError as exc:
        # Misconfigured FAST_FORWARD — fail clearly at send time, per spec.
        logger.error("rejecting send: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    message = models.Message(
        sender_id=current_user.id,
        recipient_id=recipient.id,
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


# Static paths MUST be declared before "/{message_id}" so they aren't captured
# by the dynamic route.
@router.get("/inbox", response_model=list[MessageOut])
def inbox(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Inbox semantics: only delivered messages addressed to me.
    query = (
        select(models.Message)
        .options(
            joinedload(models.Message.sender_user),
            joinedload(models.Message.recipient_user),
        )
        .where(
            models.Message.recipient_id == current_user.id,
            models.Message.status == models.DELIVERED,
        )
        .order_by(models.Message.sent_at.desc(), models.Message.id.desc())
    )
    return db.execute(query).scalars().all()


@router.get("/sent", response_model=list[MessageOut])
def sent(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    query = (
        select(models.Message)
        .options(
            joinedload(models.Message.sender_user),
            joinedload(models.Message.recipient_user),
        )
        .where(models.Message.sender_id == current_user.id)
        .order_by(models.Message.sent_at.desc(), models.Message.id.desc())
    )
    return db.execute(query).scalars().all()


@router.get("/{message_id}", response_model=MessageOut)
def get_message(
    message_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    message = db.get(
        models.Message,
        message_id,
        # Eager-load both parties so MessageOut resolves usernames without a
        # lazy load, consistent with the inbox/sent endpoints.
        options=[
            joinedload(models.Message.sender_user),
            joinedload(models.Message.recipient_user),
        ],
    )
    if message is None or current_user.id not in (
        message.sender_id,
        message.recipient_id,
    ):
        # 404 (not 403) so non-parties can't probe which ids exist.
        raise HTTPException(status_code=404, detail="message not found")
    return message
```

- [ ] **Step 7: Run the whole suite**

Run: `cd backend && pytest -q`
Expected: PASS — every test green.

- [ ] **Step 8: Reset the dev DB, then sanity-check the live app**

The existing `backend/pigeon.db` was created with the old `sender`/`recipient` columns, and `create_all` never ALTERs an existing table — so the running app would error on `sender_id`. It's a gitignored dev throwaway, so delete it (and its WAL/SHM sidecars) first:

```bash
cd backend && rm -f pigeon.db pigeon.db-wal pigeon.db-shm
```

Then run `FAST_FORWARD=5000 uvicorn app.main:app --reload` and, in another shell (or via `/docs`), register two users, send between them, and hit `/messages/inbox` and `/messages/sent`. Confirm `POST /messages` 401s without a token and 404s for an unknown recipient. Stop the server when done.

- [ ] **Step 9: Commit**

```bash
cd backend && git add app/models.py app/schemas.py app/routes.py \
  tests/test_models.py tests/test_delivery.py tests/test_messages_api.py
git commit -m "feat: tie messages to user accounts (FK sender/recipient, auth-scoped reads)"
```

---

## Task 3: Update documentation

**Files:**
- Modify: `README.md` (repo root)
- Modify: `CLAUDE.md` (repo root)

> All paths in this task are at the **repo root**, not under `backend/`. Run the commit from the repo root.

- [ ] **Step 1: Update the README API section**

In `README.md` (repo root), replace the four `/messages` bullet lines in "API at a glance" with:

```markdown
- `POST /messages` — send a pigeon (auth required): `{recipient, body, origin, destination}`. `recipient` is a registered **username**; unknown → 404. Sender is taken from your access token. City names come from the built-in catalog (see `app/cities.py`).
- `GET /messages/inbox` — your inbox: delivered messages addressed to you (auth required)
- `GET /messages/sent` — everything you've sent, any status (auth required)
- `GET /messages/{id}` — track one message; visible only to its sender and recipient (auth required)
```

- [ ] **Step 2: Update CLAUDE.md**

In `CLAUDE.md`, in the intro paragraph, change the "Still to come" sentence from:

```
Still to come: messages tied to user accounts, Google OAuth, and the frontend.
```

to:

```
Messages are now tied to user accounts (sent by the authenticated user, addressed to a registered username). Still to come: Google OAuth and the frontend.
```

- [ ] **Step 3: Add a gotcha**

In `CLAUDE.md` under "## Gotchas", add two bullets:

```markdown
- All `/messages` endpoints require a bearer access token. The sender is always the token's user (any `sender` in the body is ignored); the recipient is looked up by username (case-insensitive) and must exist.
- SQLite enforces foreign keys only because of the `Engine`-level `PRAGMA foreign_keys=ON` listener in `db.py`; without it the `Message` → `User` FKs would be silently unenforced.
```

- [ ] **Step 4: Commit** (from the repo root)

```bash
git add README.md CLAUDE.md
git commit -m "docs: update API and CLAUDE.md for account-tied messages"
```

---

## Final verification

- [ ] Run the full suite once more: `cd backend && pytest -q` → all green.
- [ ] `git log --oneline` shows three feature commits (pragma, messages, docs) on `feat/messages-tied-to-accounts`.
- [ ] Hand off via `superpowers:finishing-a-development-branch` to decide merge/PR.
