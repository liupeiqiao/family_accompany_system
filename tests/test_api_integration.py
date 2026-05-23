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
                    "gender": "男",
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
    assert db.load_all_family_profiles()[0]["gender"] == "男"
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


def test_family_profile_gender_persists_through_sqlite(tmp_path, monkeypatch):
    from engine import db

    monkeypatch.chdir(tmp_path)
    db.init_db()

    db.save_family_profile(
        {
            "name": "小红",
            "gender": "女",
            "relation": "女儿",
            "personality": ["细心"],
            "preferences": ["唱歌"],
            "habits": ["周三打电话"],
            "relations": [],
            "notes": "住在兰州",
        }
    )

    profile = db.load_all_family_profiles()[0]

    assert profile["name"] == "小红"
    assert profile["gender"] == "女"
    assert profile["relation"] == "女儿"


def test_family_profile_relation_is_normalized_by_gender_on_import(tmp_path, monkeypatch):
    from api.handlers import handle_import
    from api.schemas import ImportRequest
    from engine import db

    monkeypatch.chdir(tmp_path)

    result = handle_import(
        ImportRequest(
            family_id="local",
            family_profiles=[
                {"name": "小明", "gender": "男", "relation": "子女"},
                {"name": "小红", "gender": "女", "relation": "子女"},
                {"name": "小刚", "gender": "", "relation": "子女"},
            ],
        )
    )

    profiles = {profile["name"]: profile for profile in db.load_all_family_profiles()}

    assert result.imported.family_profiles == 3
    assert profiles["小明"]["relation"] == "儿子"
    assert profiles["小红"]["relation"] == "女儿"
    assert profiles["小刚"]["relation"] == "子女"


def test_fastapi_import_endpoint_saves_payload(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from api.main import app
    from engine import db

    monkeypatch.chdir(tmp_path)
    client = TestClient(app)

    response = client.post(
        "/api/import",
        json={
            "family_id": "local",
            "persona": {
                "role_label": "儿子小明",
                "relation": "子女",
                "appellation": "妈",
            },
            "elder_profile": {"full_name": "宋桂兰", "gender": "女"},
            "family_profiles": [{"name": "小明", "gender": "男", "relation": "儿子"}],
            "memories": [{"content": "去年中秋小明陪妈妈在院子里赏月。"}],
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "imported": {
            "persona": 1,
            "elder_profile": 1,
            "family_profiles": 1,
            "memories": 1,
        },
    }
    assert db.load_persona()["role_label"] == "儿子小明"
    assert db.load_elder()["full_name"] == "宋桂兰"
    assert db.load_all_family_profiles()[0]["name"] == "小明"
    assert db.load_all_family_profiles()[0]["gender"] == "男"
    assert db.load_all_memories()[0]["content"] == "去年中秋小明陪妈妈在院子里赏月。"


def test_imported_data_is_used_by_chat_endpoint_prompt(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from api.main import app

    monkeypatch.chdir(tmp_path)
    captured_prompts: list[str] = []

    def fake_chat(system_prompt: str, user_prompt: str, temperature: float = 0.7):
        captured_prompts.append(system_prompt)
        if len(captured_prompts) == 1:
            return '{"intent":"怀念","emotion":"思念","confidence":0.95,"keywords":["中秋"],"talk_to":"儿子小明","mentioned":["小明"]}'
        return "妈，我也记得去年中秋咱们在院子里赏月，您那天还说桂花香。"

    monkeypatch.setattr("productization.chat_service.llm_client.chat", fake_chat)

    client = TestClient(app)
    import_response = client.post(
        "/api/import",
        json={
            "family_id": "local",
            "persona": {
                "role_label": "儿子小明",
                "relation": "儿子",
                "appellation": "妈",
                "personality": ["细心"],
                "speech_style": ["说话慢一点"],
                "comfort_style": ["分享式", "安慰式", "唠家常"],
            },
            "elder_profile": {
                "full_name": "宋桂兰",
                "gender": "女",
                "personality": ["温和"],
                "preferences": ["听秦腔"],
                "health_notes": ["血压偏高"],
                "speech_traits": ["喜欢讲庆阳老家的事"],
            },
            "family_profiles": [
                {
                    "name": "小明",
                    "gender": "男",
                    "relation": "儿子",
                    "personality": ["稳重"],
                    "preferences": ["做饭"],
                    "habits": ["周末回家看妈妈"],
                }
            ],
            "memories": [
                {
                    "content": "去年中秋小明陪妈妈在院子里赏月，妈妈说桂花香。",
                    "memory_type": "节日",
                    "subject": "小明",
                    "family_members": ["小明"],
                    "emotion_tags": ["温馨"],
                    "topic_tags": ["中秋"],
                    "intimacy_weight": 0.9,
                }
            ],
        },
    )
    assert import_response.status_code == 200

    chat_response = client.post(
        "/api/chat",
        json={
            "family_id": "local",
            "elder_id": "elder-1",
            "persona_id": "persona-1",
            "text": "小明，你还记得去年中秋吗？",
        },
    )

    assert chat_response.status_code == 200
    response_json = chat_response.json()
    assert response_json["text"].startswith("妈，我也记得")
    assert response_json["debug"]["top_memories"][0]["content"].startswith("去年中秋")

    response_prompt = captured_prompts[1]
    assert "宋桂兰" in response_prompt
    assert "听秦腔" in response_prompt
    assert "小明是老人的儿子" in response_prompt
    assert "性别男" in response_prompt
    assert "去年中秋小明陪妈妈在院子里赏月" in response_prompt


def test_response_prompt_guides_family_like_memory_expression():
    from llm.prompts import build_response_system

    prompt = build_response_system(
        role_label="儿子小明",
        appellation="妈",
        personality=["细心"],
        speech_style=["说话慢一点"],
        comfort_style=["分享式"],
        strategy="分享式",
        memory_context="主语：小明\n类型：节日\n内容：去年中秋小明陪妈妈赏月。",
    )

    assert "像家人一起回忆" in prompt
    assert "先安慰，再提一条温暖记忆" in prompt
    assert "不要每次强行回忆" in prompt


def test_chat_auto_switches_persona_when_elder_calls_family_member(tmp_path, monkeypatch):
    from engine import db
    from productization.chat_service import generate_chat_reply

    monkeypatch.chdir(tmp_path)
    db.init_db()
    db.save_persona(
        {
            "role_label": "儿子小明",
            "relation": "儿子",
            "appellation": "妈",
            "personality": ["稳重"],
            "speech_style": ["慢慢说"],
            "comfort_style": ["唠家常"],
        }
    )
    db.save_persona(
        {
            "role_label": "女儿小红",
            "relation": "女儿",
            "appellation": "妈",
            "personality": ["细心"],
            "speech_style": ["温柔一点"],
            "comfort_style": ["安慰式", "唠家常"],
        }
    )

    captured_prompts: list[str] = []

    def fake_chat(system_prompt: str, user_prompt: str, temperature: float = 0.7):
        captured_prompts.append(system_prompt)
        if len(captured_prompts) == 1:
            return '{"intent":"思念家人","emotion":"思念","confidence":0.92,"keywords":[],"talk_to":"陪伴者","mentioned":["小红"]}'
        return "妈，我在呢，我也想您。"

    result = generate_chat_reply("小红，我想你了。", chat_fn=fake_chat)

    assert result.text.startswith("妈，我在呢")
    assert "你是一个老年人的女儿小红" in captured_prompts[1]
    assert result.debug["selected_persona"] == "女儿小红"
    assert result.debug["persona_switch_reason"] == "direct_name"
    assert result.debug["persona_switch_confidence"] >= 0.8


def test_chat_auto_switches_persona_when_elder_requests_relation(tmp_path, monkeypatch):
    from engine import db
    from productization.chat_service import generate_chat_reply

    monkeypatch.chdir(tmp_path)
    db.init_db()
    db.save_persona(
        {
            "role_label": "儿子小明",
            "relation": "儿子",
            "appellation": "妈",
            "personality": ["稳重"],
            "speech_style": ["慢慢说"],
            "comfort_style": ["唠家常"],
        }
    )
    db.save_persona(
        {
            "role_label": "老伴刘叔",
            "relation": "配偶",
            "appellation": "桂兰",
            "personality": ["温和"],
            "speech_style": ["像老伴一样说家常话"],
            "comfort_style": ["安慰式", "唠家常"],
        }
    )

    captured_prompts: list[str] = []

    def fake_chat(system_prompt: str, user_prompt: str, temperature: float = 0.7):
        captured_prompts.append(system_prompt)
        if len(captured_prompts) == 1:
            return '{"intent":"思念家人","emotion":"思念","confidence":0.88,"keywords":[],"talk_to":"陪伴者","mentioned":[]}'
        return "桂兰，我在这儿呢，慢慢跟我说。"

    result = generate_chat_reply("我想和老伴说会儿话。", chat_fn=fake_chat)

    assert result.text.startswith("桂兰，我在这儿")
    assert "你是一个老年人的老伴刘叔" in captured_prompts[1]
    assert result.debug["selected_persona"] == "老伴刘叔"
    assert result.debug["persona_switch_reason"] == "relation_request"


def test_chat_does_not_switch_persona_for_third_person_mention(tmp_path, monkeypatch):
    from engine import db
    from productization.chat_service import generate_chat_reply

    monkeypatch.chdir(tmp_path)
    db.init_db()
    db.save_persona(
        {
            "role_label": "儿子小明",
            "relation": "儿子",
            "appellation": "妈",
            "personality": ["稳重"],
            "speech_style": ["慢慢说"],
            "comfort_style": ["唠家常"],
        }
    )
    db.save_persona(
        {
            "role_label": "女儿小红",
            "relation": "女儿",
            "appellation": "妈",
            "personality": ["细心"],
            "speech_style": ["温柔一点"],
            "comfort_style": ["安慰式", "唠家常"],
        }
    )

    captured_prompts: list[str] = []

    def fake_chat(system_prompt: str, user_prompt: str, temperature: float = 0.7):
        captured_prompts.append(system_prompt)
        if len(captured_prompts) == 1:
            return '{"intent":"日常闲聊","emotion":"平静","confidence":0.9,"keywords":[],"talk_to":"陪伴者","mentioned":["小红"]}'
        return "妈，我在呢，小红最近也惦记您。"

    result = generate_chat_reply("小红最近忙吗？", chat_fn=fake_chat)

    assert result.text.startswith("妈，我在呢")
    assert "你是一个老年人的儿子小明" in captured_prompts[1]
    assert result.debug["selected_persona"] == "儿子小明"
    assert result.debug["persona_switch_reason"] == "default"


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
