from sqlalchemy import text


def test_foreign_keys_enforced(db_session):
    # SQLite defaults this OFF; the app must turn it ON for FK integrity.
    enabled = db_session.execute(text("PRAGMA foreign_keys")).scalar()
    assert enabled == 1
