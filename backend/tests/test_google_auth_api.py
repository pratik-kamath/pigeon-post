from app import auth_routes
from app.google_auth import GoogleIdentity, GoogleNotConfigured, GoogleVerifyUnavailable, InvalidGoogleToken
from app.models import User


def patch_identity(monkeypatch, *, sub="sub-123", email="alex@example.com",
                   email_verified=True, name="Alex Example"):
    identity = GoogleIdentity(sub=sub, email=email,
                              email_verified=email_verified, name=name)
    # raising=False: in the red phase auth_routes hasn't imported the seam yet
    # (that happens in Step 4), so the attribute doesn't exist. raising=False
    # lets the patch create it, so the red run fails on the missing route (404),
    # not an AttributeError at setup.
    monkeypatch.setattr(
        auth_routes, "verify_google_id_token", lambda token: identity, raising=False
    )
    return identity


def patch_raises(monkeypatch, exc):
    def boom(token):
        raise exc
    monkeypatch.setattr(auth_routes, "verify_google_id_token", boom, raising=False)


def google_login(client, id_token="tok"):
    return client.post("/auth/google", json={"id_token": id_token})


def test_new_user_created_and_logged_in(client, monkeypatch, db_session):
    patch_identity(monkeypatch, sub="sub-new", email="newbie@example.com", name="New Bie")
    resp = google_login(client)
    assert resp.status_code == 200, resp.text
    tokens = resp.json()
    assert tokens["access_token"] and tokens["refresh_token"]
    me = client.get("/auth/me",
                    headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert me.status_code == 200
    assert me.json()["email"] == "newbie@example.com"
    assert me.json()["username"]  # auto-generated, non-empty
    created = db_session.query(User).filter(User.email == "newbie@example.com").one()
    assert created.password_hash is None     # Google-only account, no password
    assert created.google_sub == "sub-new"


def test_returning_user_no_duplicate(client, monkeypatch, db_session):
    patch_identity(monkeypatch, sub="sub-xyz", email="rep@example.com")
    assert google_login(client).status_code == 200
    assert google_login(client).status_code == 200
    assert db_session.query(User).filter(User.google_sub == "sub-xyz").count() == 1


def test_links_to_existing_password_account(client, monkeypatch, db_session):
    reg = client.post("/auth/register", json={
        "username": "alex", "email": "alex@example.com", "password": "password123",
    })
    assert reg.status_code == 201
    patch_identity(monkeypatch, sub="sub-link", email="alex@example.com")
    assert google_login(client).status_code == 200
    user = db_session.query(User).filter(User.email == "alex@example.com").one()
    assert user.google_sub == "sub-link"
    assert db_session.query(User).count() == 1
    # the original password still works after linking
    pw = client.post("/auth/login",
                     json={"email": "alex@example.com", "password": "password123"})
    assert pw.status_code == 200


def test_unverified_email_rejected(client, monkeypatch, db_session):
    patch_identity(monkeypatch, email="x@example.com", email_verified=False)
    assert google_login(client).status_code == 401
    assert db_session.query(User).count() == 0


def test_different_google_sub_same_email_conflict(client, monkeypatch, db_session):
    patch_identity(monkeypatch, sub="sub-A", email="dup@example.com")
    assert google_login(client).status_code == 200
    patch_identity(monkeypatch, sub="sub-B", email="dup@example.com")
    assert google_login(client).status_code == 401
    user = db_session.query(User).filter(User.email == "dup@example.com").one()
    assert user.google_sub == "sub-A"  # unchanged, not overwritten


def test_invalid_token_401(client, monkeypatch):
    patch_raises(monkeypatch, InvalidGoogleToken("bad"))
    assert google_login(client).status_code == 401


def test_unavailable_503(client, monkeypatch):
    patch_raises(monkeypatch, GoogleVerifyUnavailable("network"))
    assert google_login(client).status_code == 503


def test_missing_config_500(client, monkeypatch):
    patch_raises(monkeypatch, GoogleNotConfigured("missing"))
    assert google_login(client).status_code == 500


def test_blank_id_token_422(client):
    assert client.post("/auth/google", json={"id_token": ""}).status_code == 422


def test_missing_id_token_key_422(client):
    assert client.post("/auth/google", json={}).status_code == 422


def test_username_collision_distinct_handles(client, monkeypatch, db_session):
    patch_identity(monkeypatch, sub="sub-1", email="sam@example.com")
    assert google_login(client).status_code == 200
    patch_identity(monkeypatch, sub="sub-2", email="sam@other.com")
    assert google_login(client).status_code == 200
    names = {u.username for u in db_session.query(User).all()}
    assert "sam" in names and "sam1" in names
