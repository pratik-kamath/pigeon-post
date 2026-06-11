from app import security


class TestPasswordHashing:
    def test_hash_verify_round_trip(self):
        h = security.hash_password("correct horse battery staple")
        assert h != "correct horse battery staple"
        assert h.startswith("$argon2")
        assert security.verify_password("correct horse battery staple", h)

    def test_wrong_password_fails(self):
        h = security.hash_password("right")
        assert not security.verify_password("wrong", h)

    def test_fresh_hash_needs_no_rehash(self):
        h = security.hash_password("pw")
        assert not security.password_needs_rehash(h)

    def test_malformed_stored_hash_is_invalid_not_error(self):
        # A corrupt DB value must read as "wrong password", never a 500.
        assert not security.verify_password("pw", "not-an-argon2-hash")
