from __future__ import annotations

import pytest


def test_auth_service_test_code_issues_and_verifies_jwt(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-secret")

    from productization.auth import AuthError, InMemoryAuthStore, create_auth_service, decode_access_token

    service = create_auth_service(store=InMemoryAuthStore())

    send_result = service.send_code(phone="13800138000")
    assert send_result == {"ok": True, "expires_in_seconds": 300, "test_mode": True}

    with pytest.raises(AuthError):
        service.verify_code(phone="13800138000", code="123456")

    verify_result = service.verify_code(phone="13800138000", code="000000")
    assert verify_result["token_type"] == "bearer"
    assert verify_result["user"]["phone"] == "13800138000"

    payload = decode_access_token(verify_result["access_token"])
    assert payload["user_id"] == verify_result["user"]["id"]


def test_fastapi_auth_routes_and_token_dependency(monkeypatch):
    from fastapi.testclient import TestClient

    from api.main import app
    from productization.cloud_repository import InMemoryCloudRepository

    monkeypatch.setenv("JWT_SECRET", "test-secret")
    repo = InMemoryCloudRepository()
    monkeypatch.setattr("api.handlers.get_cloud_repository", lambda: repo)

    client = TestClient(app)

    send_response = client.post("/api/auth/send-code", json={"phone": "13800138001"})
    assert send_response.status_code == 200
    assert send_response.json()["test_mode"] is True

    verify_response = client.post(
        "/api/auth/verify",
        json={"phone": "13800138001", "code": "000000"},
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
