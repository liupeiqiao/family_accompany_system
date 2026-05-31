from __future__ import annotations


def test_chat_endpoint_persists_cloud_chat_exchange(monkeypatch):
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
        lambda text, **kwargs: ChatResult(text="I am here with you.", debug={"context_source": "cloud"}),
    )

    client = TestClient(app)
    response = client.post(
        "/api/chat",
        json={
            "family_id": family["id"],
            "elder_id": "",
            "persona_id": "",
            "text": "Are you there?",
        },
        headers={"X-User-Id": "owner"},
    )

    assert response.status_code == 200
    messages = repo.list_chat_messages(family_id=family["id"], user_id="owner")
    assert [(message["role"], message["text"]) for message in messages] == [
        ("user", "Are you there?"),
        ("assistant", "I am here with you."),
    ]
    assert messages[0]["session_id"] == messages[1]["session_id"]


def test_chat_history_endpoint_returns_family_scoped_messages(monkeypatch):
    from fastapi.testclient import TestClient

    from api.main import app
    from productization.cloud_repository import InMemoryCloudRepository

    repo = InMemoryCloudRepository()
    family = repo.create_family(name="Song family", user_id="owner")
    repo.record_chat_exchange(
        family_id=family["id"],
        user_id="owner",
        elder_id="",
        user_text="First question",
        assistant_text="First answer",
        audio_url="data:audio/mpeg;base64,ZmFrZQ==",
        tts_provider="doubao",
    )
    monkeypatch.setattr("api.handlers.get_cloud_repository", lambda: repo)

    client = TestClient(app)
    response = client.get(
        f"/api/chat/history?family_id={family['id']}",
        headers={"X-User-Id": "owner"},
    )

    assert response.status_code == 200
    body = response.json()
    assert [message["role"] for message in body] == ["user", "assistant"]
    assert body[1]["audio_storage_path"] == "data:audio/mpeg;base64,ZmFrZQ=="
    assert body[1]["tts_provider"] == "doubao"


def test_chat_turns_endpoint_returns_paired_turns_newest_first(monkeypatch):
    from fastapi.testclient import TestClient

    from api.main import app
    from productization.cloud_repository import InMemoryCloudRepository

    repo = InMemoryCloudRepository()
    family = repo.create_family(name="Song family", user_id="owner")
    repo.record_voice_chat_exchange(
        family_id=family["id"],
        user_id="owner",
        elder_id="elder-1",
        persona_id="persona-1",
        voice_profile_id="voice-1",
        user_text="First question",
        assistant_text="First answer",
        audio_url="generated-audio/family/session/first.mp3",
        asr_provider="doubao",
        tts_provider="doubao",
        session_id="11111111-1111-1111-1111-111111111111",
    )
    repo.record_voice_chat_exchange(
        family_id=family["id"],
        user_id="owner",
        elder_id="elder-1",
        persona_id="persona-2",
        voice_profile_id="voice-2",
        user_text="Second question",
        assistant_text="Second answer",
        audio_url="generated-audio/family/session/second.mp3",
        asr_provider="doubao",
        tts_provider="doubao",
        session_id="11111111-1111-1111-1111-111111111111",
    )
    monkeypatch.setattr("api.handlers.get_cloud_repository", lambda: repo)

    client = TestClient(app)
    response = client.get(
        f"/api/chat/turns?family_id={family['id']}",
        headers={"X-User-Id": "owner"},
    )

    assert response.status_code == 200
    body = response.json()
    assert [turn["user_text"] for turn in body] == ["Second question", "First question"]
    assert body[0]["assistant_text"] == "Second answer"
    assert body[0]["audio_url"] == "generated-audio/family/session/second.mp3"
    assert body[0]["persona_id"] == "persona-2"
    assert body[0]["voice_profile_id"] == "voice-2"
    assert body[0]["asr_provider"] == "doubao"
    assert body[0]["tts_provider"] == "doubao"
