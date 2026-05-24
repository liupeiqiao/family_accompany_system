from __future__ import annotations


def test_tts_endpoint_synthesizes_with_ready_voice_profile(monkeypatch):
    from fastapi.testclient import TestClient

    from api.main import app
    from productization.cloud_repository import InMemoryCloudRepository

    repo = InMemoryCloudRepository()
    family = repo.create_family(name="Song family", user_id="owner")
    sample = repo.create_voice_sample_upload_intent(
        family_id=family["id"],
        user_id="owner",
        filename="hello.wav",
        sample_source="upload",
    )
    profile = repo.create_voice_profile(
        family_id=family["id"],
        user_id="owner",
        payload={
            "display_name": "Owner voice",
            "provider": "mock",
            "provider_voice_id": "mock_voice_owner",
            "status": "ready",
            "consent_confirmed": True,
            "sample_source": "upload",
            "sample_ids": [sample["id"]],
        },
    )
    monkeypatch.setattr("api.handlers.get_cloud_repository", lambda: repo)

    client = TestClient(app)
    response = client.post(
        "/api/tts",
        json={"family_id": family["id"], "voice_profile_id": profile["id"], "text": "Mom, I am here."},
        headers={"X-User-Id": "owner"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "mock"
    assert body["audio_url"].startswith(f"generated-audio/{family['id']}/")


def test_chat_endpoint_adds_audio_when_voice_profile_is_requested(monkeypatch):
    from fastapi.testclient import TestClient

    from api.main import app
    from productization.chat_service import ChatResult
    from productization.cloud_repository import InMemoryCloudRepository

    repo = InMemoryCloudRepository()
    family = repo.create_family(name="Song family", user_id="owner")
    sample = repo.create_voice_sample_upload_intent(
        family_id=family["id"],
        user_id="owner",
        filename="hello.wav",
        sample_source="upload",
    )
    profile = repo.create_voice_profile(
        family_id=family["id"],
        user_id="owner",
        payload={
            "display_name": "Owner voice",
            "provider": "mock",
            "provider_voice_id": "mock_voice_owner",
            "status": "ready",
            "consent_confirmed": True,
            "sample_source": "upload",
            "sample_ids": [sample["id"]],
        },
    )
    repo.upsert_elder_current(family_id=family["id"], user_id="owner", payload={"full_name": "Grandma"})
    monkeypatch.setattr("api.handlers.get_cloud_repository", lambda: repo)
    monkeypatch.setattr(
        "api.handlers.generate_chat_reply",
        lambda text, **kwargs: ChatResult(text="Mom, I am here.", debug={"context_source": "cloud"}),
    )

    client = TestClient(app)
    response = client.post(
        "/api/chat",
        json={
            "family_id": family["id"],
            "elder_id": "",
            "persona_id": "",
            "text": "Are you there?",
            "voice_profile_id": profile["id"],
        },
        headers={"X-User-Id": "owner"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["text"] == "Mom, I am here."
    assert body["audio_url"].startswith(f"generated-audio/{family['id']}/")
    assert body["debug"]["tts_provider"] == "mock"


def test_chat_endpoint_keeps_text_when_tts_fails(monkeypatch):
    from fastapi.testclient import TestClient

    from api.main import app
    from productization.chat_service import ChatResult
    from productization.cloud_repository import InMemoryCloudRepository

    repo = InMemoryCloudRepository()
    family = repo.create_family(name="Song family", user_id="owner")
    repo.upsert_elder_current(family_id=family["id"], user_id="owner", payload={"full_name": "Grandma"})
    monkeypatch.setattr("api.handlers.get_cloud_repository", lambda: repo)
    monkeypatch.setattr(
        "api.handlers.generate_chat_reply",
        lambda text, **kwargs: ChatResult(text="Text still works.", debug={"context_source": "cloud"}),
    )

    client = TestClient(app)
    response = client.post(
        "/api/chat",
        json={
            "family_id": family["id"],
            "elder_id": "",
            "persona_id": "",
            "text": "Are you there?",
            "voice_profile_id": "missing-profile",
        },
        headers={"X-User-Id": "owner"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["text"] == "Text still works."
    assert body["audio_url"] is None
    assert "tts_error" in body["debug"]
