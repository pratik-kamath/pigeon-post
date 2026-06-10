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
