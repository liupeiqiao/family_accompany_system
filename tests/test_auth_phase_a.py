from __future__ import annotations

from pathlib import Path

import pytest


def test_auth_module_uses_python310_compatible_utc_timezone():
    source = Path("productization/auth.py").read_text(encoding="utf-8")

    assert "from datetime import UTC" not in source
    assert "timezone.utc" in source


def test_auth_service_test_code_issues_and_verifies_jwt(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("COMPANION_ENV", "development")
    monkeypatch.setenv("TEST_LOGIN_ENABLED", "true")
    monkeypatch.setenv("TEST_LOGIN_CODE", "123456")

    from productization.auth import AuthError, InMemoryAuthStore, create_auth_service, decode_access_token

    service = create_auth_service(store=InMemoryAuthStore())

    send_result = service.send_code(phone="13800138000")
    assert send_result == {"ok": True, "expires_in_seconds": 300, "test_mode": True}

    with pytest.raises(AuthError):
        service.verify_code(phone="13800138000", code="000000")

    verify_result = service.verify_code(phone="13800138000", code="123456")
    assert verify_result["token_type"] == "bearer"
    assert verify_result["user"]["phone"] == "13800138000"

    payload = decode_access_token(verify_result["access_token"])
    assert payload["user_id"] == verify_result["user"]["id"]


def test_auth_service_uses_postgres_store_when_database_url_configured(monkeypatch):
    from productization import auth

    monkeypatch.setenv("DATABASE_URL", "postgresql://example/auth")
    monkeypatch.setattr(auth.PostgresAuthStore, "init_schema", lambda self: None)

    service = auth.create_auth_service()

    assert service.store.__class__.__name__ == "PostgresAuthStore"
    assert service.store.database_url == "postgresql://example/auth"


def test_postgres_auth_store_initializes_schema_when_selected(monkeypatch):
    from productization import auth

    calls = []

    class FakePostgresAuthStore:
        def __init__(self, database_url):
            self.database_url = database_url

        def init_schema(self):
            calls.append(self.database_url)

    monkeypatch.setenv("DATABASE_URL", "postgresql://example/auth")
    monkeypatch.setattr(auth, "PostgresAuthStore", FakePostgresAuthStore)

    auth.create_auth_service()

    assert calls == ["postgresql://example/auth"]


def test_fastapi_auth_routes_and_token_dependency(monkeypatch):
    from fastapi.testclient import TestClient

    from api.main import app
    from productization.cloud_repository import InMemoryCloudRepository

    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("COMPANION_ENV", "development")
    monkeypatch.setenv("TEST_LOGIN_ENABLED", "true")
    monkeypatch.setenv("TEST_LOGIN_CODE", "123456")
    monkeypatch.setattr("productization.auth._auth_service", None)
    repo = InMemoryCloudRepository()
    monkeypatch.setattr("api.handlers.get_cloud_repository", lambda: repo)

    client = TestClient(app)

    send_response = client.post("/api/auth/send-code", json={"phone": "13800138001"})
    assert send_response.status_code == 200
    assert send_response.json()["test_mode"] is True

    verify_response = client.post(
        "/api/auth/verify",
        json={"phone": "13800138001", "code": "123456"},
    )
    assert verify_response.status_code == 200
    token = verify_response.json()["access_token"]

    missing_token = client.get("/api/family/current")
    assert missing_token.status_code == 401

    create_response = client.post(
        "/api/family",
        json={"name": "云端家庭"},
        headers={"X-User-Token": token},
    )
    assert create_response.status_code == 200
    assert create_response.json()["family"]["name"] == "云端家庭"

    current_response = client.get(
        "/api/family/current",
        headers={"X-User-Token": token},
    )
    assert current_response.status_code == 200
    assert current_response.json()["family"]["id"] == create_response.json()["family"]["id"]


def test_staging_test_login_requires_whitelist_and_configured_code(monkeypatch):
    from productization.auth import AuthError, InMemoryAuthStore, create_auth_service

    monkeypatch.setenv("COMPANION_ENV", "staging")
    monkeypatch.setenv("TEST_LOGIN_ENABLED", "true")
    monkeypatch.setenv("TEST_LOGIN_CODE", "123456")
    monkeypatch.setenv("TEST_LOGIN_WHITELIST", "13800138002,13900139002")

    service = create_auth_service(store=InMemoryAuthStore())

    assert service.send_code(phone="13800138002")["test_mode"] is True
    assert service.verify_code(phone="13800138002", code="123456")["user"]["phone"] == "13800138002"

    with pytest.raises(AuthError, match="当前账号暂时无法登录"):
        service.send_code(phone="13800138003")

    with pytest.raises(AuthError):
        service.verify_code(phone="13800138002", code="000000")


def test_test_login_can_be_disabled_even_for_whitelisted_accounts(monkeypatch):
    from productization.auth import AuthError, InMemoryAuthStore, create_auth_service

    monkeypatch.setenv("COMPANION_ENV", "staging")
    monkeypatch.setenv("TEST_LOGIN_ENABLED", "false")
    monkeypatch.setenv("TEST_LOGIN_CODE", "123456")
    monkeypatch.setenv("TEST_LOGIN_WHITELIST", "13800138002")
    monkeypatch.setenv("SMS_ENABLED", "false")

    store = InMemoryAuthStore()
    store.save_code(phone="13800138002", code="123456", expires_at=9999999999)
    service = create_auth_service(store=store)

    with pytest.raises(AuthError, match="验证码服务暂不可用"):
        service.send_code(phone="13800138002")
    with pytest.raises(AuthError, match="验证码服务暂不可用"):
        service.verify_code(phone="13800138002", code="123456")


def test_production_rejects_fixed_test_login_without_sms_provider(monkeypatch):
    from productization.auth import AuthError, InMemoryAuthStore, create_auth_service

    monkeypatch.setenv("COMPANION_ENV", "production")
    monkeypatch.setenv("TEST_LOGIN_ENABLED", "true")
    monkeypatch.setenv("TEST_LOGIN_CODE", "123456")
    monkeypatch.setenv("TEST_LOGIN_WHITELIST", "13800138002")
    monkeypatch.setenv("SMS_ENABLED", "false")
    monkeypatch.setenv("SMS_PROVIDER", "none")

    service = create_auth_service(store=InMemoryAuthStore())

    with pytest.raises(AuthError, match="验证码服务暂不可用"):
        service.send_code(phone="13800138002")


def test_auth_service_rate_limits_send_and_verify_attempts(monkeypatch):
    from productization.auth import AuthError, InMemoryAuthStore, create_auth_service

    monkeypatch.setenv("COMPANION_ENV", "development")
    monkeypatch.setenv("TEST_LOGIN_ENABLED", "true")
    monkeypatch.setenv("TEST_LOGIN_CODE", "123456")
    monkeypatch.setenv("AUTH_SEND_CODE_LIMIT", "2")
    monkeypatch.setenv("AUTH_VERIFY_CODE_LIMIT", "2")

    service = create_auth_service(store=InMemoryAuthStore())

    service.send_code(phone="13800138004")
    service.send_code(phone="13800138004")
    with pytest.raises(AuthError, match="操作过于频繁"):
        service.send_code(phone="13800138004")

    service.send_code(phone="13800138005")
    with pytest.raises(AuthError):
        service.verify_code(phone="13800138005", code="111111")
    with pytest.raises(AuthError):
        service.verify_code(phone="13800138005", code="222222")
    with pytest.raises(AuthError, match="操作过于频繁"):
        service.verify_code(phone="13800138005", code="123456")
