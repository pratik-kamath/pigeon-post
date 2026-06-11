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


class TestLogin:
    def test_login_returns_token_pair(self, client):
        register(client)
        resp = client.post(
            "/auth/login",
            json={"email": "alice@example.com", "password": REGISTER["password"]},
        )
        assert resp.status_code == 200
        assert set(resp.json()) == {"access_token", "refresh_token", "token_type"}
        assert resp.headers["Cache-Control"] == "no-store"

    def test_wrong_password_and_unknown_email_are_identical_401s(self, client):
        register(client)
        wrong_pw = client.post(
            "/auth/login",
            json={"email": "alice@example.com", "password": "wrong-password"},
        )
        unknown = client.post(
            "/auth/login",
            json={"email": "nobody@example.com", "password": "whatever123"},
        )
        assert wrong_pw.status_code == unknown.status_code == 401
        assert wrong_pw.json() == unknown.json()
        assert wrong_pw.headers["WWW-Authenticate"] == "Bearer"
        assert unknown.headers["WWW-Authenticate"] == "Bearer"

    def test_login_email_case_insensitive(self, client):
        register(client)
        resp = client.post(
            "/auth/login",
            json={"email": "ALICE@example.com", "password": REGISTER["password"]},
        )
        assert resp.status_code == 200
