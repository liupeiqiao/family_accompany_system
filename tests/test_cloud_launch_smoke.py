from __future__ import annotations


def test_launch_smoke_user_can_persist_core_cloud_data_with_jwt(monkeypatch):
    from fastapi.testclient import TestClient

    from api.main import app
    from productization.chat_service import ChatResult
    from productization.cloud_repository import InMemoryCloudRepository

    repo = InMemoryCloudRepository()
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("JWT_SECRET", "launch-smoke-secret")
    monkeypatch.setenv("VOICE_PROVIDER", "mock")
    monkeypatch.setattr("productization.auth._auth_service", None)
    monkeypatch.setattr("api.handlers.get_cloud_repository", lambda: repo)
    monkeypatch.setattr(
        "api.handlers.generate_chat_reply",
        lambda text, **kwargs: ChatResult(text="妈，我在呢。", debug={"context_source": "cloud"}),
    )

    client = TestClient(app)

    send_code = client.post("/api/auth/send-code", json={"phone": "13800138008"})
    assert send_code.status_code == 200
    login = client.post("/api/auth/verify", json={"phone": "13800138008", "code": "000000"})
    assert login.status_code == 200
    token = login.json()["access_token"]
    headers = {"X-User-Token": token}

    family = client.post("/api/family", json={"name": "上线验收家庭"}, headers=headers)
    assert family.status_code == 200
    family_id = family.json()["family"]["id"]

    elder = client.put(
        "/api/elders/current",
        json={"family_id": family_id, "full_name": "妈妈"},
        headers=headers,
    )
    assert elder.status_code == 200

    persona = client.post(
        "/api/personas",
        json={"family_id": family_id, "role_label": "女儿 小雨", "relation": "女儿", "appellation": "妈"},
        headers=headers,
    )
    assert persona.status_code == 200
    persona_id = persona.json()["id"]

    memory = client.post(
        "/api/memories",
        json={"family_id": family_id, "content": "去年中秋一起赏月。", "memory_type": "家庭记忆"},
        headers=headers,
    )
    assert memory.status_code == 200

    voice = client.post(
        "/api/voices/clone",
        json={
            "family_id": family_id,
            "display_name": "小雨音色",
            "sample_ids": [],
            "consent_confirmed": True,
            "sample_source": "prepaid",
            "speaker_id": "S_launch_smoke_xiaoyu",
            "voice_type": "prepaid",
        },
        headers=headers,
    )
    assert voice.status_code == 200
    voice_id = voice.json()["id"]

    preview = client.post(
        "/api/voices/preview",
        json={"family_id": family_id, "voice_profile_id": voice_id},
        headers=headers,
    )
    assert preview.status_code == 200
    assert preview.json()["audio_url"]

    bound_voice = client.put(
        f"/api/voices/profiles/{voice_id}",
        json={"family_id": family_id, "persona_id": persona_id},
        headers=headers,
    )
    assert bound_voice.status_code == 200
    assert bound_voice.json()["persona_id"] == persona_id

    chat = client.post(
        "/api/elder/voice-chat",
        data={
            "family_id": family_id,
            "persona_id": persona_id,
            "voice_profile_id": voice_id,
            "client_session_id": "22222222-2222-2222-2222-222222222222",
        },
        files={"audio_file": ("speech.webm", b"fake-audio", "audio/webm")},
        headers=headers,
    )
    assert chat.status_code == 200
    assert chat.json()["audio_url"]

    records = {
        "elder": client.get(f"/api/elders/current?family_id={family_id}", headers=headers),
        "personas": client.get(f"/api/personas?family_id={family_id}", headers=headers),
        "memories": client.get(f"/api/memories?family_id={family_id}", headers=headers),
        "voices": client.get(f"/api/voices/profiles?family_id={family_id}", headers=headers),
        "history": client.get(f"/api/chat/history?family_id={family_id}", headers=headers),
    }
    assert all(response.status_code == 200 for response in records.values())
    assert records["elder"].json()["full_name"] == "妈妈"
    assert records["personas"].json()[0]["id"] == persona_id
    assert records["memories"].json()[0]["id"] == memory.json()["id"]
    assert records["voices"].json()[0]["id"] == voice_id
    history = records["history"].json()
    assert history[-1]["voice_profile_id"] == voice_id


def test_launch_pages_do_not_call_legacy_local_record_mutations():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    for page in ["records", "elder", "history", "voices", "family"]:
        source = (root / "web" / "src" / "app" / page / "page.tsx").read_text(encoding="utf-8")
        assert "importParsedData(" not in source, page
        assert "deleteMemory(" not in source, page
        assert "deleteFamilyProfile(" not in source, page
        assert "deletePersona(" not in source, page
        assert "deleteElder(" not in source, page
        assert 'family_id: "local"' not in source, page
        assert 'family_id={"local"}' not in source, page
