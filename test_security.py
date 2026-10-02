from app.core.security import hash_password, verify_password

def test_password_hashing():
    h=hash_password("secret-123")
    assert h.startswith("scrypt$")
    assert verify_password("secret-123",h)
    assert not verify_password("wrong",h)
