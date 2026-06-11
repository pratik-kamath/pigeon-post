REGISTER = {"username": "alice", "email": "alice@example.com", "password": "hunter2hunter2"}


def register(client, **overrides):
    return client.post("/auth/register", json={**REGISTER, **overrides})


class TestRegister:
    def test_register_returns_token_pair(self, client):
        resp = register(client)
        assert resp.status_code == 201
        body = resp.json()
        assert set(body) == {"access_token", "refresh_token", "token_type"}
        assert body["token_type"] == "bearer"
        assert resp.headers["Cache-Control"] == "no-store"

    def test_duplicate_username_409_case_insensitive(self, client):
        register(client)
        resp = register(client, username="ALICE", email="other@example.com")
        assert resp.status_code == 409

    def test_duplicate_email_409_case_insensitive(self, client):
        register(client)
        resp = register(client, username="bob", email="ALICE@example.com")
        assert resp.status_code == 409

    def test_invalid_username_422(self, client):
        assert register(client, username="no spaces!").status_code == 422
        assert register(client, username="ab").status_code == 422

    def test_short_password_422(self, client):
        assert register(client, password="short").status_code == 422
