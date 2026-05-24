from __future__ import annotations


def test_family_context_service_converts_cloud_records_to_engine_context():
    from productization.cloud_repository import InMemoryCloudRepository
    from productization.family_context_service import build_family_chat_context

    repo = InMemoryCloudRepository()
    family = repo.create_family(name="宋家", user_id="owner")
    repo.upsert_elder_current(
        family_id=family["id"],
        user_id="owner",
        payload={"full_name": "宋桂兰", "gender": "女", "preferences": ["听秦腔"]},
    )
    repo.create_family_profile(
        family_id=family["id"],
        user_id="owner",
        payload={"name": "小明", "gender": "男", "relation": "子女", "preferences": ["做饭"]},
    )
    repo.create_memory(
        family_id=family["id"],
        user_id="owner",
        payload={
            "content": "去年中秋小明陪妈妈在院子里赏月。",
            "memory_type": "节日",
            "subject": "小明",
            "topic_tags": ["中秋"],
            "intimacy_weight": 0.9,
        },
    )
    repo.create_persona(
        family_id=family["id"],
        user_id="owner",
        payload={
            "role_label": "儿子小明",
            "relation": "子女",
            "appellation": "妈",
            "speech_style": ["慢慢说"],
        },
    )

    context = build_family_chat_context(repo=repo, family_id=family["id"], user_id="owner")

    assert context.elder.full_name == "宋桂兰"
    assert context.elder.preferences == ["听秦腔"]
    assert context.families["小明"].relation == "儿子"
    assert context.memories[0].content == "去年中秋小明陪妈妈在院子里赏月。"
    assert context.personas["儿子小明"].appellation == "妈"


def test_chat_endpoint_uses_cloud_family_context(monkeypatch):
    from fastapi.testclient import TestClient

    from api.main import app
    from productization.cloud_repository import InMemoryCloudRepository

    repo = InMemoryCloudRepository()
    family = repo.create_family(name="宋家", user_id="owner")
    repo.upsert_elder_current(
        family_id=family["id"],
        user_id="owner",
        payload={"full_name": "宋桂兰", "gender": "女", "preferences": ["听秦腔"]},
    )
    repo.create_family_profile(
        family_id=family["id"],
        user_id="owner",
        payload={"name": "小明", "gender": "男", "relation": "儿子", "preferences": ["做饭"]},
    )
    repo.create_memory(
        family_id=family["id"],
        user_id="owner",
        payload={
            "content": "去年中秋小明陪妈妈在院子里赏月，妈妈说桂花香。",
            "memory_type": "节日",
            "subject": "小明",
            "family_members": ["小明"],
            "emotion_tags": ["温馨"],
            "topic_tags": ["中秋"],
            "intimacy_weight": 0.9,
        },
    )
    repo.create_persona(
        family_id=family["id"],
        user_id="owner",
        payload={
            "role_label": "儿子小明",
            "relation": "儿子",
            "appellation": "妈",
            "personality": ["细心"],
            "speech_style": ["说话慢一点"],
            "comfort_style": ["唠家常"],
        },
    )
    monkeypatch.setattr("api.handlers.get_cloud_repository", lambda: repo)

    captured_prompts: list[str] = []

    def fake_chat(system_prompt: str, user_prompt: str, temperature: float = 0.7):
        captured_prompts.append(system_prompt)
        if len(captured_prompts) == 1:
            return '{"intent":"怀念","emotion":"思念","confidence":0.95,"keywords":["中秋"],"talk_to":"儿子小明","mentioned":["小明"]}'
        return "妈，我也记得去年中秋咱们在院子里赏月。"

    monkeypatch.setattr("productization.chat_service.llm_client.chat", fake_chat)

    client = TestClient(app)
    response = client.post(
        "/api/chat",
        json={
            "family_id": family["id"],
            "text": "小明，你还记得去年中秋吗？",
        },
        headers={"X-User-Id": "owner"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["text"].startswith("妈，我也记得")
    assert body["debug"]["context_source"] == "cloud"
    assert body["debug"]["top_memories"][0]["content"].startswith("去年中秋")
    assert "宋桂兰" in captured_prompts[1]
    assert "听秦腔" in captured_prompts[1]
    assert "去年中秋小明陪妈妈在院子里赏月" in captured_prompts[1]


def test_cloud_chat_permission_failure_returns_text_fallback(monkeypatch):
    from fastapi.testclient import TestClient

    from api.main import app
    from productization.cloud_repository import InMemoryCloudRepository

    repo = InMemoryCloudRepository()
    family = repo.create_family(name="宋家", user_id="owner")
    monkeypatch.setattr("api.handlers.get_cloud_repository", lambda: repo)

    client = TestClient(app)
    response = client.post(
        "/api/chat",
        json={"family_id": family["id"], "text": "有人在吗？"},
        headers={"X-User-Id": "outsider"},
    )

    assert response.status_code == 200
    assert response.json()["text"] == "我这边暂时没读到家里的资料，您先慢慢说，我在听。"
    assert response.json()["debug"]["context_source"] == "cloud"
    assert "cloud_context_error" in response.json()["debug"]
