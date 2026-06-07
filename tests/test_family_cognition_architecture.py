from __future__ import annotations

from engine.elder import ElderProfile
from engine.family import FamilyProfile
from engine.conversation_state import ConversationState
from engine.memory import MemoryUnit
from engine.memory_event import MemoryEvent, MemoryEventParticipant
from engine.person import Person, Relationship
from engine.persona import PersonaProfile
from engine.family_graph import FamilyGraph
from productization.chat_service import ChatContext, generate_chat_reply
from productization.conversation_state_service import (
    clear_conversation_state_cache,
    load_conversation_state,
    save_conversation_state,
)
from productization.family_cognition_service import (
    build_family_cognition_context,
    check_response_identity_boundaries,
)


def test_family_graph_queries_directional_relationships_and_mentions():
    elder = Person(id="elder", family_id="local", full_name="宋桂兰", nicknames=["妈"])
    son = Person(id="son", family_id="local", full_name="王强", nicknames=["强子"])
    wife = Person(id="wife", family_id="local", full_name="小红")

    graph = FamilyGraph(
        persons={person.id: person for person in [elder, son, wife]},
        relationships=[
            Relationship(
                family_id="local",
                from_person_id="son",
                to_person_id="elder",
                relation_type="son",
                display_label="儿子",
                inverse_relation_type="mother",
                inverse_display_label="母亲",
            ),
            Relationship(
                family_id="local",
                from_person_id="wife",
                to_person_id="son",
                relation_type="spouse",
                display_label="妻子",
                inverse_relation_type="spouse",
                inverse_display_label="丈夫",
            ),
        ],
    )

    assert graph.get_person("强子") == son
    assert graph.get_relationship("son", "elder").display_label == "儿子"
    assert graph.get_relationship("elder", "son").display_label == "母亲"
    assert graph.resolve_mentions("我想问问强子和小红最近怎么样") == [son, wife]
    assert graph.path_between("wife", "elder") == ["小红是王强的妻子", "王强是宋桂兰的儿子"]


def test_legacy_context_builds_people_roles_relationships_and_memory_events():
    elder = ElderProfile(full_name="宋桂兰", gender="女")
    families = {
        "王强": FamilyProfile(
            name="王强",
            gender="男",
            relation="儿子",
            relations=[{"person": "小红", "relation": "妻子"}],
        ),
        "小红": FamilyProfile(name="小红", gender="女", relation="儿媳"),
    }
    personas = {
        "儿子王强": PersonaProfile(
            role_label="儿子王强",
            relation="儿子",
            appellation="妈",
            comfort_style=["唠家常"],
        )
    }
    memories = [
        MemoryUnit(
            content="2025年春节，王强回家给宋桂兰做红烧肉。",
            memory_type="事件",
            subject="王强",
            family_members=["王强", "宋桂兰", "小红"],
            emotion_tags=["开心"],
            topic_tags=["做饭", "团圆"],
        )
    ]

    cognition = build_family_cognition_context(
        elder=elder,
        families=families,
        personas=personas,
        memories=memories,
        active_persona_role_label="儿子王强",
    )

    assert cognition.elder_person.full_name == "宋桂兰"
    assert cognition.active_persona_role.person_id == cognition.graph.get_person("王强").id
    assert cognition.graph.get_relationship(
        cognition.graph.get_person("王强").id,
        cognition.elder_person.id,
    ).display_label == "儿子"
    event = cognition.memory_events[0]
    wang = cognition.graph.get_person("王强")
    xiaohong = cognition.graph.get_person("小红")
    elder_person = cognition.graph.get_person("宋桂兰")
    assert event.participant_for(wang.id).can_use_first_person is True
    assert event.participant_for(elder_person.id).perspective == "experienced"
    assert event.participant_for(xiaohong.id).perspective == "heard_about"
    assert event.participant_for(xiaohong.id).can_use_first_person is False


def test_memory_event_filters_first_person_eligibility():
    event = MemoryEvent(
        id="event-1",
        family_id="local",
        title="王强做红烧肉",
        summary="王强给宋桂兰做红烧肉。",
        participants=[
            MemoryEventParticipant(
                person_id="wang",
                role_in_event="cook",
                perspective="experienced",
                can_use_first_person=True,
            ),
            MemoryEventParticipant(
                person_id="hong",
                role_in_event="family",
                perspective="heard_about",
                can_use_first_person=False,
            ),
        ],
    )

    assert event.can_use_first_person("wang") is True
    assert event.can_use_first_person("hong") is False
    assert event.can_mention("hong") is True
    assert "只能转述" in event.to_prompt_evidence("hong")


def test_identity_boundary_checker_rejects_first_person_for_heard_about_event():
    event = MemoryEvent(
        id="event-1",
        family_id="local",
        title="王强做红烧肉",
        summary="2025年春节，王强给宋桂兰做红烧肉。",
        topic_tags=["做饭", "红烧肉"],
        participants=[
            MemoryEventParticipant(
                person_id="wang",
                perspective="experienced",
                can_use_first_person=True,
            ),
            MemoryEventParticipant(
                person_id="hong",
                perspective="heard_about",
                can_use_first_person=False,
            ),
        ],
    )

    assert check_response_identity_boundaries(
        "妈，我上次给您做红烧肉，您吃得很高兴。",
        events=[event],
        speaker_person_id="hong",
    )
    assert check_response_identity_boundaries(
        "妈，我上次给您做红烧肉，您吃得很高兴。",
        events=[event],
        speaker_person_id="wang",
    ) == []
    assert check_response_identity_boundaries(
        "妈，我听说那年春节王强给您做过红烧肉。",
        events=[event],
        speaker_person_id="hong",
    ) == []


def test_conversation_state_keeps_recent_people_events_and_summary_context():
    state = ConversationState(family_id="family-1", session_id="session-1", elder_person_id="elder")

    state.update_turn(
        current_persona_role_id="role-xiaoyu",
        mentioned_person_ids=["xiaoyu", "xiaohong"],
        event_ids=["event-red-pork"],
        elder_emotion="想念",
        intent="怀念",
        ongoing_topic="小红、红烧肉",
        relationship_focus={"relation_label": "小红是小雨的嫂子"},
    )
    state.update_turn(
        mentioned_person_ids=["wangqiang", "xiaoyu"],
        event_ids=["event-work"],
        elder_emotion="担心",
        intent="关心家人",
        ongoing_topic="王强工作",
    )

    assert state.current_persona_role_id == "role-xiaoyu"
    assert state.recent_person_ids == ["wangqiang", "xiaoyu", "xiaohong"]
    assert state.recent_event_ids == ["event-work", "event-red-pork"]
    prompt_context = state.to_prompt_context()
    assert "## 对话连续状态" in prompt_context
    assert "老人当前情绪：担心" in prompt_context
    assert "持续话题：王强工作" in prompt_context
    assert "关系焦点：小红是小雨的嫂子" in prompt_context


def test_conversation_state_service_falls_back_to_memory_when_database_unavailable(monkeypatch):
    import productization.conversation_state_service as state_service

    clear_conversation_state_cache()
    monkeypatch.setattr(state_service.db, "init_db", lambda: (_ for _ in ()).throw(RuntimeError("missing table")))

    state = load_conversation_state(
        family_id="family-fallback",
        session_id="session-fallback",
        elder_person_id="elder",
        current_persona_role_id="role-wang",
    )
    state.update_turn(
        mentioned_person_ids=["wang"],
        event_ids=["event-1"],
        elder_emotion="担心",
        intent="关心家人",
        ongoing_topic="王强工作",
        summary="最近聊到王强",
    )
    save_conversation_state(state)

    loaded = load_conversation_state(family_id="family-fallback", session_id="session-fallback")

    assert loaded.recent_person_ids == ["wang"]
    assert loaded.recent_event_ids == ["event-1"]
    assert loaded.summary == "最近聊到王强"


def test_chat_prompt_uses_family_cognition_context(monkeypatch):
    context = ChatContext(
        personas={
            "儿子王强": PersonaProfile(
                role_label="儿子王强",
                relation="儿子",
                appellation="妈",
                comfort_style=["唠家常"],
            )
        },
        families={
            "王强": FamilyProfile(name="王强", gender="男", relation="儿子"),
            "小红": FamilyProfile(name="小红", gender="女", relation="儿媳"),
        },
        elder=ElderProfile(full_name="宋桂兰", gender="女"),
        memories=[
            MemoryUnit(
                content="2025年春节，王强回家给宋桂兰做红烧肉。",
                memory_type="事件",
                subject="王强",
                family_members=["王强", "宋桂兰"],
                emotion_tags=["开心"],
                topic_tags=["做饭"],
            )
        ],
        active_persona_role_label="儿子王强",
    )
    prompts: list[str] = []

    def fake_chat(system_prompt: str, user_prompt: str, temperature: float = 0.7):
        prompts.append(system_prompt)
        if "JSON" in system_prompt:
            return '{"intent":"怀念","emotion":"平静","confidence":0.9,"talk_to":"儿子王强","mentioned":["小红"]}'
        return "妈，我记得那年春节给您做红烧肉，家里可热闹了。"

    result = generate_chat_reply("小红最近忙吗？还记得春节红烧肉吗？", chat_fn=fake_chat, context=context)

    assert result.text.startswith("妈")
    combined_prompt = "\n".join(prompts)
    assert "## 家庭身份认知" in combined_prompt
    assert "王强是宋桂兰的儿子" in combined_prompt
    assert "小红是宋桂兰的儿媳" in combined_prompt
    assert "## 对话连续状态" in combined_prompt
    assert "## 结构化记忆事件" in combined_prompt
    assert "可以用第一人称提起" in combined_prompt
    assert result.debug["family_cognition"]["active_person"] == "王强"


def test_chat_conversation_state_persists_between_turns(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    clear_conversation_state_cache()
    context = ChatContext(
        personas={
            "儿子王强": PersonaProfile(role_label="儿子王强", relation="儿子", appellation="妈"),
        },
        families={
            "王强": FamilyProfile(name="王强", gender="男", relation="儿子"),
        },
        elder=ElderProfile(full_name="宋桂兰", gender="女"),
        active_persona_role_label="儿子王强",
        family_id="family-state",
        session_id="session-state",
    )
    prompts: list[str] = []

    def fake_chat(system_prompt: str, user_prompt: str, temperature: float = 0.7):
        prompts.append(system_prompt)
        if "JSON" in system_prompt:
            if "他别太累了" in user_prompt:
                return '{"intent":"担忧焦虑","emotion":"担心","confidence":0.9,"talk_to":"陪伴者","mentioned":[]}'
            return '{"intent":"确认事实","emotion":"平静","confidence":0.9,"talk_to":"陪伴者","mentioned":["王强"]}'
        if "他别太累了" in user_prompt:
            return "妈，我会注意别太累，您别担心。"
        return "妈，最近工作是有点忙。"

    first = generate_chat_reply("王强最近工作忙不忙？", chat_fn=fake_chat, context=context)
    second = generate_chat_reply("他别太累了。", chat_fn=fake_chat, context=context)

    assert first.debug["family_cognition"]["recent_person_ids"] == ["王强"]
    assert second.debug["family_cognition"]["recent_person_ids"] == ["王强"]
    assert second.debug["family_cognition"]["state_summary"]
    second_response_prompt = prompts[-1]
    assert "持续话题：他别太累了" in second_response_prompt
    assert "王强" in second_response_prompt


def test_persona_selection_uses_family_graph_for_direct_call_and_keeps_role_for_third_person():
    context = ChatContext(
        personas={
            "儿子王强": PersonaProfile(role_label="儿子王强", relation="儿子", appellation="妈"),
            "儿媳小红": PersonaProfile(role_label="儿媳小红", relation="儿媳", appellation="妈"),
        },
        families={
            "王强": FamilyProfile(name="王强", gender="男", relation="儿子", relations=[{"person": "小红", "relation": "妻子"}]),
            "小红": FamilyProfile(name="小红", gender="女", relation="儿媳"),
        },
        elder=ElderProfile(full_name="宋桂兰", gender="女"),
        active_persona_role_label="儿子王强",
        family_id="family-persona",
        session_id="session-persona",
    )

    def direct_chat(system_prompt: str, user_prompt: str, temperature: float = 0.7):
        if "JSON" in system_prompt:
            return '{"intent":"思念家人","emotion":"思念","confidence":0.9,"talk_to":"陪伴者","mentioned":["小红"]}'
        return "妈，我在呢。"

    direct = generate_chat_reply("让小红跟我说说话。", chat_fn=direct_chat, context=context)
    assert direct.debug["selected_persona"] == "儿媳小红"
    assert direct.debug["persona_switch_reason"] == "family_graph_direct_call"

    third_person_context = ChatContext(
        personas=context.personas,
        families=context.families,
        elder=context.elder,
        active_persona_role_label="儿子王强",
        family_id="family-persona",
        session_id="session-persona-third",
    )

    def third_person_chat(system_prompt: str, user_prompt: str, temperature: float = 0.7):
        if "JSON" in system_prompt:
            return '{"intent":"日常闲聊","emotion":"平静","confidence":0.9,"talk_to":"陪伴者","mentioned":["小红"]}'
        return "妈，小红最近是有点忙，我回头也多问问她。"

    third_person = generate_chat_reply("小红最近是不是很忙？", chat_fn=third_person_chat, context=third_person_context)
    assert third_person.debug["selected_persona"] == "儿子王强"
    assert third_person.debug["persona_switch_reason"] == "conversation_state"
    assert third_person.text.startswith("妈，小红最近")


def test_persona_selection_resolves_nickname_to_person():
    context = ChatContext(
        personas={
            "儿子王强": PersonaProfile(role_label="儿子王强", relation="儿子", appellation="妈"),
        },
        families={
            "王强": FamilyProfile(name="王强", gender="男", relation="儿子", habits=["小名强子"]),
        },
        elder=ElderProfile(full_name="宋桂兰", gender="女"),
        family_id="family-nickname",
        session_id="session-nickname",
    )

    def fake_chat(system_prompt: str, user_prompt: str, temperature: float = 0.7):
        if "JSON" in system_prompt:
            return '{"intent":"思念家人","emotion":"思念","confidence":0.9,"talk_to":"陪伴者","mentioned":[]}'
        return "妈，我在呢。"

    result = generate_chat_reply("我想强子了。", chat_fn=fake_chat, context=context)

    assert result.debug["selected_persona"] == "儿子王强"
    assert result.debug["persona_switch_reason"] == "family_graph_direct_call"


def test_real_dialogue_switches_to_wangqiang_when_elder_misses_him():
    context = ChatContext(
        personas={
            "儿子王强": PersonaProfile(role_label="儿子王强", relation="儿子", appellation="妈"),
            "儿媳小红": PersonaProfile(role_label="儿媳小红", relation="儿媳", appellation="妈"),
        },
        families={
            "王强": FamilyProfile(name="王强", gender="男", relation="儿子"),
            "小红": FamilyProfile(name="小红", gender="女", relation="儿媳"),
        },
        elder=ElderProfile(full_name="宋桂兰", gender="女"),
        active_persona_role_label="儿媳小红",
        family_id="family-dialogue-wang",
        session_id="session-dialogue-wang",
    )

    def fake_chat(system_prompt: str, user_prompt: str, temperature: float = 0.7):
        if "JSON" in system_prompt:
            return '{"intent":"思念家人","emotion":"思念","confidence":0.9,"talk_to":"陪伴者","mentioned":["王强"]}'
        assert "当前角色：王强，是宋桂兰的儿子" in system_prompt
        return "妈，我在呢，也想您。"

    result = generate_chat_reply("我想王强了。", chat_fn=fake_chat, context=context)

    assert result.text.startswith("妈，我在呢")
    assert "AI" not in result.text
    assert result.debug["selected_persona"] == "儿子王强"


def test_real_dialogue_heard_about_event_retries_without_false_first_person():
    context = ChatContext(
        personas={
            "儿媳小红": PersonaProfile(role_label="儿媳小红", relation="儿媳", appellation="妈"),
        },
        families={
            "王强": FamilyProfile(name="王强", gender="男", relation="儿子"),
            "小红": FamilyProfile(name="小红", gender="女", relation="儿媳"),
        },
        elder=ElderProfile(full_name="宋桂兰", gender="女"),
        memories=[
            MemoryUnit(
                content="2025年春节，王强回家给宋桂兰做红烧肉。",
                memory_type="事件",
                subject="王强",
                family_members=["王强", "宋桂兰", "小红"],
                topic_tags=["红烧肉", "做饭"],
            )
        ],
        active_persona_role_label="儿媳小红",
        family_id="family-dialogue-memory",
        session_id="session-dialogue-memory",
    )
    response_attempts = 0

    def fake_chat(system_prompt: str, user_prompt: str, temperature: float = 0.7):
        nonlocal response_attempts
        if "JSON" in system_prompt:
            return '{"intent":"怀念","emotion":"开心","confidence":0.9,"talk_to":"陪伴者","mentioned":[]}'
        response_attempts += 1
        if response_attempts == 1:
            return "妈，我上次给您做红烧肉，您吃得可高兴了。"
        return "妈，我听说那年春节王强给您做过红烧肉，您一直记着这个味道。"

    result = generate_chat_reply("上次你给我做的红烧肉真好吃。", chat_fn=fake_chat, context=context)

    assert response_attempts == 2
    assert result.text.startswith("妈，我听说")
    assert "我上次给您做红烧肉" not in result.text
