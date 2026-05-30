from __future__ import annotations

import pytest


def test_cloud_repository_creates_voice_sample_paths_and_profiles():
    from productization.cloud_repository import InMemoryCloudRepository

    repo = InMemoryCloudRepository()
    family = repo.create_family(name="Song family", user_id="owner")

    sample = repo.create_voice_sample_upload_intent(
        family_id=family["id"],
        user_id="owner",
        filename="greeting.wav",
        sample_source="upload",
    )

    assert sample["storage_path"].startswith(f"voice-samples/{family['id']}/owner/")
    assert sample["storage_path"].endswith(".wav")
    assert sample["status"] == "pending_upload"
    assert repo.list_voice_samples(family_id=family["id"], user_id="owner")[0]["id"] == sample["id"]

    profile = repo.create_voice_profile(
        family_id=family["id"],
        user_id="owner",
        payload={
            "display_name": "My voice",
            "provider": "mock",
            "provider_voice_id": "mock_voice_123",
            "status": "ready",
            "consent_confirmed": True,
            "sample_source": "upload",
            "sample_ids": [sample["id"]],
        },
    )

    assert profile["created_by"] == "owner"
    assert profile["status"] == "ready"
    assert repo.list_voice_profiles(family_id=family["id"], user_id="owner")[0]["id"] == profile["id"]
    assert repo.list_voice_samples(family_id=family["id"], user_id="owner")[0]["voice_profile_id"] == profile["id"]


def test_cloud_repository_blocks_viewer_voice_writes():
    from productization.cloud_repository import FamilyPermissionError, InMemoryCloudRepository

    repo = InMemoryCloudRepository()
    family = repo.create_family(name="Song family", user_id="owner")
    repo.add_member(family_id=family["id"], user_id="viewer", role="viewer")

    with pytest.raises(FamilyPermissionError):
        repo.create_voice_sample_upload_intent(
            family_id=family["id"],
            user_id="viewer",
            filename="sample.wav",
            sample_source="upload",
        )


def test_fastapi_voice_upload_intent_and_clone_flow(monkeypatch):
    from fastapi.testclient import TestClient

    from api.main import app
    from productization.cloud_repository import InMemoryCloudRepository

    repo = InMemoryCloudRepository()
    family = repo.create_family(name="Song family", user_id="owner")
    repo.add_member(family_id=family["id"], user_id="viewer", role="viewer")
    monkeypatch.setenv("VOICE_PROVIDER", "mock")
    monkeypatch.setattr("api.handlers.get_cloud_repository", lambda: repo)

    client = TestClient(app)

    sample_response = client.post(
        "/api/voices/upload-intent",
        json={"family_id": family["id"], "filename": "hello.m4a", "sample_source": "recording"},
        headers={"X-User-Id": "owner"},
    )
    assert sample_response.status_code == 200
    sample = sample_response.json()
    assert sample["bucket"] == "voice-samples"
    assert sample["storage_path"].startswith(f"voice-samples/{family['id']}/owner/")

    missing_consent = client.post(
        "/api/voices/clone",
        json={
            "family_id": family["id"],
            "display_name": "Owner voice",
            "sample_ids": [sample["id"]],
            "consent_confirmed": False,
        },
        headers={"X-User-Id": "owner"},
    )
    assert missing_consent.status_code == 400

    clone_response = client.post(
        "/api/voices/clone",
        json={
            "family_id": family["id"],
            "display_name": "Owner voice",
            "sample_ids": [sample["id"]],
            "consent_confirmed": True,
        },
        headers={"X-User-Id": "owner"},
    )
    assert clone_response.status_code == 200
    profile = clone_response.json()
    assert profile["provider"] == "mock"
    assert profile["status"] == "ready"
    assert profile["consent_confirmed"] is True

    profiles = client.get(
        f"/api/voices/profiles?family_id={family['id']}",
        headers={"X-User-Id": "owner"},
    )
    assert profiles.status_code == 200
    assert profiles.json()[0]["id"] == profile["id"]

    viewer_upload = client.post(
        "/api/voices/upload-intent",
        json={"family_id": family["id"], "filename": "viewer.wav", "sample_source": "upload"},
        headers={"X-User-Id": "viewer"},
    )
    assert viewer_upload.status_code == 403


def test_fastapi_voice_clone_accepts_inline_audio_payload(monkeypatch):
    from fastapi.testclient import TestClient

    from api.main import app
    from productization.cloud_repository import InMemoryCloudRepository
    from productization.voice import VoiceCloneResult

    repo = InMemoryCloudRepository()
    family = repo.create_family(name="Song family", user_id="owner")
    monkeypatch.setattr("api.handlers.get_cloud_repository", lambda: repo)

    captured = {}

    class FakeVoiceProvider:
        provider_name = "doubao"

        def create_clone(self, request):
            captured["request"] = request
            return VoiceCloneResult(
                provider="doubao",
                provider_voice_id=request.custom_speaker_id,
                audit={"status": "2"},
            )

        def synthesize(self, request):  # pragma: no cover - not used in this test
            raise NotImplementedError

    monkeypatch.setattr("api.handlers.get_voice_provider", lambda: FakeVoiceProvider())

    client = TestClient(app)
    response = client.post(
        "/api/voices/clone",
        json={
            "family_id": family["id"],
            "display_name": "Owner real voice",
            "sample_ids": [],
            "consent_confirmed": True,
            "sample_source": "upload",
            "audio_data_base64": "ZmFrZS13YXY=",
            "audio_format": "wav",
            "speaker_id": "custom_speaker_id",
            "custom_speaker_id": "custom_family_voice_001",
            "prompt_text": "这是一段本人授权声音样本。",
            "language": 0,
            "demo_text": "妈，我在呢。",
            "enable_audio_denoise": False,
        },
        headers={"X-User-Id": "owner"},
    )

    assert response.status_code == 200
    profile = response.json()
    assert profile["provider"] == "doubao"
    assert profile["provider_voice_id"] == "custom_family_voice_001"
    assert profile["status"] == "ready"
    assert captured["request"].audio_data_base64 == "ZmFrZS13YXY="
    assert captured["request"].audio_format == "wav"
    assert captured["request"].speaker_id == "custom_speaker_id"
    assert captured["request"].custom_speaker_id == "custom_family_voice_001"
    assert captured["request"].text == "这是一段本人授权声音样本。"
    assert captured["request"].demo_text == "妈，我在呢。"
    assert captured["request"].enable_audio_denoise is False


def test_fastapi_voice_status_and_local_hide(monkeypatch):
    from fastapi.testclient import TestClient

    from api.main import app
    from productization.cloud_repository import InMemoryCloudRepository
    from productization.voice import TextToSpeechResult, VoiceCloneResult

    repo = InMemoryCloudRepository()
    family = repo.create_family(name="Song family", user_id="owner")
    profile = repo.create_voice_profile(
        family_id=family["id"],
        user_id="owner",
        payload={
            "display_name": "Custom voice",
            "provider": "doubao",
            "provider_voice_id": "custom_family_voice_001",
            "status": "ready",
            "consent_confirmed": True,
            "sample_source": "upload",
            "sample_ids": [],
        },
    )
    monkeypatch.setattr("api.handlers.get_cloud_repository", lambda: repo)

    captured = {}

    class FakeVoiceProvider:
        provider_name = "doubao"

        def create_clone(self, request):  # pragma: no cover - not used
            return VoiceCloneResult(provider="doubao", provider_voice_id="unused", audit={})

        def synthesize(self, request):  # pragma: no cover - not used
            return TextToSpeechResult(provider="doubao", audio_path="data:audio/mpeg;base64,ZmFrZQ==")

        def get_voice_status(self, provider_voice_id):
            captured["status_voice_id"] = provider_voice_id
            return {
                "speaker_id": provider_voice_id,
                "status": 4,
                "available_training_times": 12,
                "speaker_status": [{"model_type": 4, "demo_audio": "https://example.test/demo.wav"}],
            }

        def upgrade_voice(self, provider_voice_id):  # pragma: no cover - not used
            raise NotImplementedError

    monkeypatch.setattr("api.handlers.get_voice_provider", lambda: FakeVoiceProvider())
    client = TestClient(app)

    status_response = client.post(
        "/api/voices/status",
        json={"family_id": family["id"], "voice_profile_id": profile["id"]},
        headers={"X-User-Id": "owner"},
    )

    assert status_response.status_code == 200
    assert captured["status_voice_id"] == "custom_family_voice_001"
    status = status_response.json()
    assert status["profile_id"] == profile["id"]
    assert status["provider_voice_id"] == "custom_family_voice_001"
    assert status["voice_status"]["status"] == 4

    hide_response = client.delete(
        f"/api/voices/profiles/{profile['id']}?family_id={family['id']}",
        headers={"X-User-Id": "owner"},
    )

    assert hide_response.status_code == 200
    profiles = client.get(
        f"/api/voices/profiles?family_id={family['id']}",
        headers={"X-User-Id": "owner"},
    )
    assert profiles.status_code == 200
    assert profiles.json() == []


def test_derive_voice_type_correctly_classifies_requests():
    from api.handlers import _derive_voice_type
    from api.schemas import VoiceCloneCreateRequest

    preset = VoiceCloneCreateRequest(
        family_id="f1",
        sample_source="preset",
        audio_data_base64="",
        speaker_id="",
        custom_speaker_id="",
    )
    assert _derive_voice_type(preset, "preset") == "preset"

    prepaid = VoiceCloneCreateRequest(
        family_id="f1",
        sample_source="upload",
        audio_data_base64="ZmFrZQ==",
        speaker_id="S_test_001",
        custom_speaker_id="",
    )
    assert _derive_voice_type(prepaid, "upload") == "prepaid"

    postpaid = VoiceCloneCreateRequest(
        family_id="f1",
        sample_source="upload",
        audio_data_base64="ZmFrZQ==",
        speaker_id="custom_speaker_id",
        custom_speaker_id="my_custom_voice_001",
    )
    assert _derive_voice_type(postpaid, "upload") == "postpaid"
