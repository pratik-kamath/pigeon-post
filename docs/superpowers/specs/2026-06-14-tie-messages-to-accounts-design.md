# Tie messages to user accounts — design

- **Date:** 2026-06-14
- **Phase:** 1 (Core mechanic)
- **Status:** Approved, ready for implementation plan

## Context

The app has two halves that don't touch each other:

- **Accounts** — a `users` table plus full password auth (`/auth/register|login|refresh|logout|me`) and a working `get_current_user` bearer-token guard.
- **Messaging** — `POST /messages` and the listing/track endpoints, but `sender` and `recipient` are free-text strings on the `Message` row, unrelated to any account. Anyone can send as anyone, and `GET /messages?recipient=NAME` lets anyone read anyone's inbox by passing a name.

This milestone wires the two together: a message is sent *by* the authenticated user *to* a registered user, and the listing/track endpoints are scoped to the caller's identity.

The dev database is created with `Base.metadata.create_all` (no Alembic/migrations) and the SQLite file is throwaway, so schema changes — including dropping columns — are free.

## Goals

- `POST /messages` requires authentication; the sender is the token's user, never client-supplied.
- The recipient is addressed by **username** and must be a registered user.
- Inbox and sent listings are scoped to the authenticated user, not a query-param name.
- Track-by-id is visible only to the two parties of a message.
- Referential integrity between messages and users is real (enforced by the DB).

## Non-goals (out of scope for this milestone)

- Changing the city/flight mechanic — `origin`/`destination` stay sender-chosen per message.
- Tying cities to users (home cities) — a natural future milestone.
- Google OAuth and the frontend — later milestones.
- A username-change feature (so no need to snapshot usernames onto messages).

## Decisions

| Decision | Choice |
|---|---|
| Sender | Derived from the access token (`get_current_user`); no longer a request field |
| Recipient | A **username** that must belong to a registered user → else `404` |
| Inbox / sent | Two endpoints: `GET /messages/inbox` (delivered, to me) and `GET /messages/sent` (all I sent, any state) |
| Track by id | Sender **and** recipient may view in any state; non-parties → `404` |
| Cities | Unchanged — sender picks `origin`/`destination` per message |
| Data model | **Approach A** — `sender_id` / `recipient_id` FK columns; drop the free-text strings |

## Detailed design

### Data model (`app/models.py`)

Replace the free-text columns on `Message`:

```python
# removed:  sender: Mapped[str],  recipient: Mapped[str]
sender_id:    Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
recipient_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

sender_user:    Mapped["User"] = relationship(foreign_keys=[sender_id])
recipient_user: Mapped["User"] = relationship(foreign_keys=[recipient_id])

@property
def sender(self) -> str:
    return self.sender_user.username

@property
def recipient(self) -> str:
    return self.recipient_user.username
```

- The relationships are named `sender_user` / `recipient_user`; `foreign_keys=` is required because there are two FKs into the same table.
- The `sender` / `recipient` **properties** return the username, so `MessageOut`'s serialized shape is unchanged from today (no `*_id` leakage in the API, no client changes).
- **Indexes:** replace `ix_messages_recipient_status` with a composite on `(recipient_id, status)` for the inbox query; `sender_id`'s own index (via `index=True`) serves the sent list. The sweep's `(status, arrival_at)` index is untouched.
- **Self-send backstop:** add `CheckConstraint("sender_id <> recipient_id", name="ck_messages_distinct_parties")`.

### Database (`app/db.py`)

SQLite ignores foreign keys unless `PRAGMA foreign_keys=ON` is set **per connection**. Add it to the existing `connect` event listener (alongside the WAL pragma) so the FKs we added are actually enforced. Without this, Approach A's referential-integrity benefit is nominal only.

### Schemas (`app/schemas.py`)

- `MessageCreate`: **drop the `sender` field** (now derived from the token). `recipient` stays as a non-blank string (a username). `body`, `origin`, `destination`, the `known_city` validator, and the `no_zero_length_flights` check are unchanged. The `not_blank` validator now applies to `recipient` and `body` only.
- `MessageOut`: **unchanged** — `sender` / `recipient` continue to serialize as username strings via the model properties.

### Endpoints (`app/routes.py`)

All message endpoints gain `current_user: models.User = Depends(get_current_user)`, so an absent/invalid token yields the standard `401`.

- **`POST /messages`** (201)
  - `sender_id = current_user.id`.
  - Resolve `recipient` username case-insensitively (`func.lower(User.username) == payload.recipient.lower()`), matching the login lookup pattern.
  - Unknown recipient → **404** `"recipient not found"`.
  - Recipient resolves to the caller → **422** `"can't send a pigeon to yourself"` (the `CheckConstraint` is the DB backstop).
  - Otherwise build the `Message` with both FK ids; existing distance/arrival logic and the `FAST_FORWARD` misconfig → 500 path are unchanged.

- **`GET /messages/inbox`** — `WHERE recipient_id == me AND status == DELIVERED`, ordered `sent_at DESC, id DESC`.
- **`GET /messages/sent`** — `WHERE sender_id == me`, any status, ordered `sent_at DESC, id DESC`.
- **`GET /messages/{id}`** — load the row; `404` if missing or if `current_user.id not in (sender_id, recipient_id)` (so non-parties can't probe existence). Otherwise return it in any state.

The list queries use `joinedload(Message.sender_user, Message.recipient_user)` to avoid N+1 lookups when resolving usernames. The old `GET /messages?sender=&recipient=` query-param listing is **removed**.

> Judgment call: unknown recipient returns **404** rather than 422. It is a referential lookup miss on an authenticated endpoint, so account enumeration isn't the concern it was for the unauthenticated login/register endpoints; 404 gives the clearer client message. 422 would also be defensible.

### Testing (TDD — write the test first, watch it fail meaningfully)

- **`tests/test_models.py`**
  - `test_message_roundtrip`: seed two users, build the message with FK ids, assert `.sender` / `.recipient` resolve to the usernames.
  - Add: self-send violates the `CheckConstraint` → `IntegrityError`.
  - Add: a `sender_id`/`recipient_id` pointing at a non-existent user → `IntegrityError` (proves `PRAGMA foreign_keys=ON` is active under the test engine).
- **`tests/test_delivery.py`**
  - `make_message` seeds one sender/recipient user pair (once) and reuses their ids. The sweep behavior tests are otherwise unchanged (the sweep never reads sender/recipient).
- **`tests/test_messages_api.py`** — rewritten around a small auth helper (register a user, return a bearer header). Cases:
  - `POST /messages` without a token → 401.
  - Sender is taken from the token (client-supplied sender, if any, is ignored); response shows correct sender/recipient usernames; 201.
  - Recipient addressed by username; unknown recipient → 404.
  - Self-send → 422.
  - Unknown city / same origin+destination / blank body still → 422.
  - `GET /messages/{id}`: visible to sender (any state) and recipient (any state); non-party → 404; unknown id → 404; no token → 401.
  - `GET /messages/inbox`: only my delivered messages, newest first; an in-flight message to me is excluded; another user's delivered message to me is included.
  - `GET /messages/sent`: all my messages in any state, newest first; not other users' messages.

Test infrastructure note: a register/auth helper (in `conftest.py` or the test module) keeps the API tests readable now that every call needs a real user and token.

### Docs

- **README** "API at a glance": rewrite the `/messages` rows — `POST /messages` requires auth and takes `{recipient (username), body, origin, destination}`; add `GET /messages/inbox` and `GET /messages/sent`; note `GET /messages/{id}` requires auth and is limited to the two parties; remove the `?sender=`/`?recipient=` query-param lines.
- **CLAUDE.md**: move "messages tied to user accounts" out of *still to come*; note that all message endpoints now require auth, and add a gotcha that SQLite FK enforcement depends on the `PRAGMA foreign_keys=ON` connect listener.

## Risks / notes

- Dropping the string columns is safe because the dev DB is throwaway and the delivery sweep never reads sender/recipient.
- Enabling `PRAGMA foreign_keys=ON` means the delivery/model tests must seed real users before inserting messages — accounted for above.
- Lazy-loading the `sender_user`/`recipient_user` relationships during serialization works while the request's session is open; `joinedload` on the list endpoints both avoids N+1 and sidesteps any detached-instance edge case.
