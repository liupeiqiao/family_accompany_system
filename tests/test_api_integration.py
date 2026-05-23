from __future__ import annotations

from pathlib import Path


def test_parse_handler_uses_existing_parser(monkeypatch):
    from api.handlers import handle_parse
    from api.schemas import ParseRequest

    def fake_parse_user_text(text: str, perspective: str, existing_families_text: str):
        assert text == "我儿子小明性格温和"
        assert perspective == "family"
        assert existing_families_text == ""
        return {
            "persona": {"role_label": "儿子小明"},
            "memories": [],
            "family_profiles": [],
            "elder_profile": {},
        }

    monkeypatch.setattr("api.handlers.parse_user_text", fake_parse_user_text)

    result = handle_parse(
        ParseRequest(
            family_id="local",
            text="我儿子小明性格温和",
            perspective="family",
        )
    )

    assert result.persona["role_label"] == "儿子小明"
    assert result.memories == []


def test_chat_service_generates_reply_from_sqlite_data(tmp_path, monkeypatch):
    from engine import db
    from productization.chat_service import generate_chat_reply

    monkeypatch.chdir(tmp_path)
    db.init_db()
    db.save_elder(
        {
            "full_name": "宋桂兰",
            "gender": "女",
            "personality": ["温和"],
            "preferences": ["听戏曲"],
            "habits": [],
            "health_notes": [],
            "speech_traits": [],
            "life_experiences": [],
            "important_memories": [],
            "notes": "",
        }
    )
    db.save_persona(
        {
            "role_label": "儿子小明",
            "relation": "子女",
            "appellation": "妈",
            "personality": ["细心"],
            "speech_style": ["说话慢一点"],
            "comfort_style": ["唠家常"],
        }
    )
    db.save_memory(
        {
            "id": "mem-1",
            "content": "去年中秋小明陪妈妈在院子里赏月。",
            "memory_type": "事件",
            "subject": "儿子小明",
            "family_members": ["小明(儿子)"],
            "emotion_tags": ["温馨"],
            "topic_tags": ["节日"],
            "intimacy_weight": 0.9,
        }
    )

    calls: list[tuple[str, str]] = []

    def fake_chat(system_prompt: str, user_prompt: str, temperature: float = 0.7):
        calls.append((system_prompt, user_prompt))
        if len(calls) == 1:
            return '{"intent":"日常闲聊","emotion":"平静","confidence":0.9,"keywords":[],"talk_to":"儿子小明","mentioned":["小明"]}'
        assert "去年中秋小明陪妈妈在院子里赏月" in system_prompt
        assert "老人画像" in system_prompt
        return "妈，我在呢。去年中秋咱们赏月那会儿，您笑得可开心。"

    result = generate_chat_reply("小明，你还记得中秋吗？", chat_fn=fake_chat)

    assert result.text.startswith("妈，我在呢")
    assert result.debug["intent"] == "日常闲聊"
    assert result.debug["talk_to"] == "儿子小明"
    assert result.debug["top_memories"][0]["content"].startswith("去年中秋")


def test_chat_handler_returns_text_and_debug(monkeypatch):
    from api.handlers import handle_chat
    from api.schemas import ChatRequest
    from productization.chat_service import ChatResult

    def fake_generate_chat_reply(text: str):
        assert text == "妈想你了"
        return ChatResult(text="妈，我也惦记您。", debug={"intent": "思念家人"})

    monkeypatch.setattr("api.handlers.generate_chat_reply", fake_generate_chat_reply)

    result = handle_chat(
        ChatRequest(
            family_id="local",
            elder_id="elder-1",
            persona_id="persona-1",
            text="妈想你了",
        )
    )

    assert result.text == "妈，我也惦记您。"
    assert result.debug == {"intent": "思念家人"}


def test_import_handler_saves_profile_and_memory_data(tmp_path, monkeypatch):
    from api.handlers import handle_import
    from api.schemas import ImportRequest
    from engine import db

    monkeypatch.chdir(tmp_path)

    result = handle_import(
        ImportRequest(
            family_id="local",
            persona={
                "role_label": "儿子小明",
                "relation": "子女",
                "appellation": "妈",
                "personality": ["细心"],
                "speech_style": ["慢慢说"],
                "comfort_style": ["唠家常"],
            },
            elder_profile={
                "full_name": "宋桂兰",
                "gender": "女",
                "personality": ["温和"],
                "preferences": ["听戏曲"],
                "habits": ["早起"],
                "health_notes": ["血压偏高"],
                "speech_traits": ["喜欢讲老家故事"],
                "life_experiences": ["年轻时在纺织厂工作"],
                "important_memories": ["去年中秋全家团圆"],
                "notes": "怕冷",
            },
            family_profiles=[
                {
                    "name": "小明",
                    "relation": "儿子",
                    "personality": ["稳重"],
                    "preferences": ["做饭"],
                    "habits": ["周末来看望"],
                    "relations": ["宋桂兰的儿子"],
                    "notes": "住得近",
                }
            ],
            memories=[
                {
                    "content": "去年中秋小明陪妈妈在院子里赏月。",
                    "memory_type": "事件",
                    "subject": "小明",
                    "family_members": ["小明(儿子)"],
                    "emotion_tags": ["温馨"],
                    "topic_tags": ["节日"],
                    "intimacy_weight": 0.9,
                }
            ],
        )
    )

    assert result.ok is True
    assert result.imported.persona == 1
    assert result.imported.elder_profile == 1
    assert result.imported.family_profiles == 1
    assert result.imported.memories == 1
    assert db.load_persona()["role_label"] == "儿子小明"
    assert db.load_elder()["full_name"] == "宋桂兰"
    assert db.load_all_family_profiles()[0]["name"] == "小明"
    assert db.load_all_memories()[0]["content"] == "去年中秋小明陪妈妈在院子里赏月。"


def test_import_handler_allows_empty_payload(tmp_path, monkeypatch):
    from api.handlers import handle_import
    from api.schemas import ImportRequest

    monkeypatch.chdir(tmp_path)

    result = handle_import(ImportRequest(family_id="local"))

    assert result.ok is True
    assert result.imported.persona == 0
    assert result.imported.elder_profile == 0
    assert result.imported.family_profiles == 0
    assert result.imported.memories == 0


def test_fastapi_entrypoint_declares_parse_and_chat_routes():
    source = Path("api/main.py").read_text(encoding="utf-8")

    assert '@app.post("/api/parse"' in source
    assert '@app.post("/api/chat"' in source
    assert '@app.post("/api/import"' in source


def test_fastapi_root_redirects_to_docs():
    from fastapi.testclient import TestClient

    from api.main import app

    client = TestClient(app)
    response = client.get("/", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/docs"
