import pytest
from datetime import timedelta
from jose import jwt
from src.auth import (
    get_password_hash,
    verify_password,
    create_access_token,
    SECRET_KEY,
    ALGORITHM,
    _DEFAULT_SECRET,
    _resolve_secret_key,
)


def test_password_hashing():
    raw_pass = "SecurePass123!"
    hashed = get_password_hash(raw_pass)
    assert hashed != raw_pass
    assert verify_password(raw_pass, hashed) is True
    assert verify_password("WrongPass", hashed) is False


def test_jwt_token_generation_and_decoding():
    data = {"sub": "testuser"}
    token = create_access_token(data, expires_delta=timedelta(minutes=15))
    assert isinstance(token, str)

    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    assert payload.get("sub") == "testuser"
    assert "exp" in payload


def test_production_requires_unique_secret_key(monkeypatch):
    monkeypatch.setenv("RAILWAY_ENVIRONMENT_NAME", "production")
    monkeypatch.delenv("SECRET_KEY", raising=False)
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        _resolve_secret_key()
    monkeypatch.setenv("SECRET_KEY", _DEFAULT_SECRET)
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        _resolve_secret_key()
    monkeypatch.setenv("SECRET_KEY", "a" * 64)
    assert _resolve_secret_key() == "a" * 64


def test_development_secret_fallback_is_preserved(monkeypatch):
    monkeypatch.delenv("RAILWAY_ENVIRONMENT_NAME", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("SECRET_KEY", raising=False)
    assert _resolve_secret_key() == _DEFAULT_SECRET
