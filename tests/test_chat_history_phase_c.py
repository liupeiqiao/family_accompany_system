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


def test_chat_turns_endpoint_includes_readable_names(monkeypatch):
    from fastapi.testclient import TestClient

    from api.main import app
    from productization.cloud_repository import InMemoryCloudRepository

    repo = InMemoryCloudRepository()
    family = repo.create_family(name="Song family", user_id="owner")
    elder = repo.upsert_elder_current(
        family_id=family["id"],
        user_id="owner",
        payload={"full_name": "宋桂兰"},
    )
    persona = repo.create_persona(
        family_id=family["id"],
        user_id="owner",
        payload={"role_label": "女儿 小雨", "relation": "女儿"},
    )
    voice = repo.create_voice_profile(
        family_id=family["id"],
        user_id="owner",
        payload={
            "display_name": "小雨音色",
            "provider": "mock",
            "provider_voice_id": "voice-xiaoyu",
            "status": "ready",
            "consent_confirmed": True,
            "sample_source": "preset",
            "voice_type": "preset",
        },
    )
    repo.record_voice_chat_exchange(
        family_id=family["id"],
        user_id="owner",
        elder_id=elder["id"],
        persona_id=persona["id"],
        voice_profile_id=voice["id"],
        user_text="小雨，我今天去医院了",
        assistant_text="妈，我听着呢。",
        audio_url="generated-audio/family/session/reply.mp3",
        asr_provider="doubao",
        tts_provider="doubao",
        session_id="22222222-2222-2222-2222-222222222222",
    )
    monkeypatch.setattr("api.handlers.get_cloud_repository", lambda: repo)

    client = TestClient(app)
    response = client.get(
        f"/api/chat/turns?family_id={family['id']}",
        headers={"X-User-Id": "owner"},
    )

    assert response.status_code == 200
    turn = response.json()[0]
    assert turn["persona_display_name"] == "女儿 小雨"
    assert turn["elder_display_name"] == "宋桂兰"
    assert turn["voice_display_name"] == "小雨音色"


def test_memory_candidate_endpoint_returns_reviewable_candidate_without_saving(monkeypatch):
    from fastapi.testclient import TestClient

    from api.main import app
    from productization.cloud_repository import InMemoryCloudRepository

    repo = InMemoryCloudRepository()
    family = repo.create_family(name="Song family", user_id="owner")

    def fake_parse_user_text(text: str, perspective: str, existing_families_text: str):
        return {
            "persona": {},
            "elder_profile": {},
            "family_profiles": [],
            "memories": [
                {
                    "content": "老人今天去医院复查，医生说血压还可以。",
                    "memory_type": "健康",
                    "subject": "老人",
                    "family_members": ["女儿 小雨"],
                    "emotion_tags": ["安心"],
                    "topic_tags": ["医院", "血压"],
                }
            ],
        }

    monkeypatch.setattr("api.handlers.get_cloud_repository", lambda: repo)
    monkeypatch.setattr("api.handlers.parse_user_text", fake_parse_user_text)

    client = TestClient(app)
    response = client.post(
        "/api/chat/memory-candidate",
        json={
            "family_id": family["id"],
            "user_text": "小雨，我今天去医院了，医生说血压还可以。",
            "assistant_text": "妈，那挺好，晚上早点休息。",
            "persona_display_name": "女儿 小雨",
            "elder_display_name": "宋桂兰",
        },
        headers={"X-User-Id": "owner"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["candidate"]["content"] == "老人今天去医院复查，医生说血压还可以。"
    assert body["candidate"]["memory_type"] == "健康"
    assert body["candidate"]["family_members"] == ["女儿 小雨"]
    assert body["source"] == "parser"
    assert repo.list_memories(family_id=family["id"], user_id="owner") == []
