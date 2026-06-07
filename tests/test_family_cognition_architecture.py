from __future__ import annotations

from engine.elder import ElderProfile
from engine.family import FamilyProfile
from engine.memory import MemoryUnit
from engine.memory_event import MemoryEvent, MemoryEventParticipant
from engine.person import Person, Relationship
from engine.persona import PersonaProfile
from engine.family_graph import FamilyGraph
from productization.chat_service import ChatContext, generate_chat_reply
from productization.family_cognition_service import build_family_cognition_context


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
