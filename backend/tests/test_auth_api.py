import jwt

from app import security

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


def auth_headers(client, **overrides):
    body = register(client, **overrides).json()
    return {"Authorization": f"Bearer {body['access_token']}"}


class TestMe:
    def test_me_returns_current_user(self, client):
        headers = auth_headers(client)
        resp = client.get("/auth/me", headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["username"] == "alice"
        assert body["email"] == "alice@example.com"
        assert "password_hash" not in body

    def test_missing_header_401(self, client):
        resp = client.get("/auth/me")
        assert resp.status_code == 401
        assert resp.headers["WWW-Authenticate"] == "Bearer"

    def test_garbage_token_401(self, client):
        resp = client.get(
            "/auth/me", headers={"Authorization": "Bearer not.a.jwt"}
        )
        assert resp.status_code == 401

    def test_wrong_scheme_401(self, client):
        resp = client.get("/auth/me", headers={"Authorization": "Basic abc"})
        assert resp.status_code == 401

    def test_bearer_without_token_401(self, client):
        resp = client.get("/auth/me", headers={"Authorization": "Bearer "})
        assert resp.status_code == 401

    def test_lowercase_bearer_scheme_accepted(self, client):
        # RFC 7235: the auth scheme is case-insensitive.
        token = auth_headers(client)["Authorization"].removeprefix("Bearer ")
        resp = client.get(
            "/auth/me", headers={"Authorization": f"bearer {token}"}
        )
        assert resp.status_code == 200

    def test_signed_token_with_non_integer_sub_401(self, client):
        bad = jwt.encode(
            {"sub": "abc", "iat": 0, "exp": 9999999999, "iss": security.JWT_ISSUER},
            security.JWT_SECRET,
            algorithm="HS256",
        )
        resp = client.get("/auth/me", headers={"Authorization": f"Bearer {bad}"})
        assert resp.status_code == 401
