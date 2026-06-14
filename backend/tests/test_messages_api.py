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
