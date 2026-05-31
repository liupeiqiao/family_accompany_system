from __future__ import annotations


def test_store_generated_audio_returns_original_when_storage_disabled(monkeypatch):
    from productization.audio_storage import store_generated_audio_if_configured

    monkeypatch.delenv("AUDIO_STORAGE_PROVIDER", raising=False)

    original = "data:audio/mpeg;base64,ZmFrZQ=="

    assert (
        store_generated_audio_if_configured(family_id="family-1", source_audio_url=original)
        == original
    )


def test_tos_audio_storage_uploads_data_url_and_returns_public_url():
    from productization.audio_storage import TOSAudioStorage, TOSAudioStorageConfig

    uploaded = {}

    class FakeClient:
        def put_object(self, bucket, key, content, content_type):
            uploaded["bucket"] = bucket
            uploaded["key"] = key
            uploaded["content"] = content
            uploaded["content_type"] = content_type

    storage = TOSAudioStorage(
        TOSAudioStorageConfig(
            access_key_id="ak",
            secret_access_key="sk",
            endpoint="https://tos-cn.example.com",
            region="cn-beijing",
            bucket="companion-audio",
            public_base_url="https://cdn.example.com/audio",
            prefix="generated-audio",
        ),
        client=FakeClient(),
        object_id_factory=lambda: "message-1",
    )

    url = storage.store_data_url(
        family_id="family-1",
        source_audio_url="data:audio/mpeg;base64,ZmFrZQ==",
    )

    assert url == "https://cdn.example.com/audio/generated-audio/family-1/message-1.mp3"
    assert uploaded == {
        "bucket": "companion-audio",
        "key": "generated-audio/family-1/message-1.mp3",
        "content": b"fake",
        "content_type": "audio/mpeg",
    }


def test_chat_endpoint_persists_uploaded_tts_audio_url(monkeypatch):
    from fastapi.testclient import TestClient

    from api.main import app
    from productization.chat_service import ChatResult
    from productization.cloud_repository import InMemoryCloudRepository
    from productization.voice import TextToSpeechResult

    repo = InMemoryCloudRepository()
    family = repo.create_family(name="Song family", user_id="owner")
    profile = repo.create_voice_profile(
        family_id=family["id"],
        user_id="owner",
        payload={
            "display_name": "Owner voice",
            "provider": "doubao",
            "provider_voice_id": "voice_owner",
            "status": "ready",
            "consent_confirmed": True,
            "sample_source": "upload",
            "sample_ids": [],
        },
    )
    repo.upsert_elder_current(family_id=family["id"], user_id="owner", payload={"full_name": "Grandma"})
    monkeypatch.setattr("api.handlers.get_cloud_repository", lambda: repo)
    monkeypatch.setattr(
        "api.handlers.generate_chat_reply",
        lambda text, **kwargs: ChatResult(text="Mom, I am here.", debug={"context_source": "cloud"}),
    )

    class FakeProvider:
        provider_name = "doubao"

        def synthesize(self, request):
            return TextToSpeechResult(provider="doubao", audio_path="data:audio/mpeg;base64,ZmFrZQ==")

    monkeypatch.setattr("api.handlers.get_voice_provider", lambda: FakeProvider())
    monkeypatch.setattr(
        "api.handlers.store_generated_audio_if_configured",
        lambda *, family_id, source_audio_url: f"https://cdn.example.com/generated-audio/{family_id}/reply.mp3",
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
    assert body["audio_url"] == f"https://cdn.example.com/generated-audio/{family['id']}/reply.mp3"
    messages = repo.list_chat_messages(family_id=family["id"], user_id="owner")
    assert messages[-1]["audio_storage_path"] == body["audio_url"]
