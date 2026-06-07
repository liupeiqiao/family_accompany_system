from __future__ import annotations

import re
from dataclasses import dataclass, field

from engine.conversation_state import ConversationState
from engine.elder import ElderProfile
from engine.family import FamilyProfile
from engine.family_graph import FamilyGraph
from engine.memory import MemoryUnit
from engine.memory_event import MemoryEvent, MemoryEventParticipant, title_from_summary
from engine.person import Person, PersonaRole, Relationship, stable_id
from engine.persona import PersonaProfile


@dataclass
class FamilyCognitionContext:
    graph: FamilyGraph
    elder_person: Person
    persona_roles: dict[str, PersonaRole] = field(default_factory=dict)
    active_persona_role: PersonaRole | None = None
    memory_events: list[MemoryEvent] = field(default_factory=list)
    state: ConversationState = field(default_factory=ConversationState)

    def active_person(self) -> Person | None:
        if not self.active_persona_role:
            return None
        return self.graph.persons.get(self.active_persona_role.person_id)


def build_family_cognition_context(
    *,
    elder: ElderProfile,
    families: dict[str, FamilyProfile],
    personas: dict[str, PersonaProfile],
    memories: list[MemoryUnit],
    active_persona_role_label: str = "",
    family_id: str = "local",
    session_id: str = "default",
) -> FamilyCognitionContext:
    elder_person = _person_from_elder(elder, family_id)
    persons = {elder_person.id: elder_person}
    name_to_id = {elder_person.full_name: elder_person.id} if elder_person.full_name else {}

    for profile in families.values():
        person = _person_from_family_profile(profile, family_id)
        if person.full_name:
            persons[person.id] = person
            name_to_id[person.full_name] = person.id

    relationships: list[Relationship] = []
    for profile in families.values():
        person_id = name_to_id.get(profile.name)
        if not person_id:
            continue
        relationships.append(_relationship_to_elder(family_id, person_id, elder_person.id, profile.relation, elder.gender))
        for relation in profile.relations:
            if not isinstance(relation, dict):
                continue
            other_name = str(relation.get("person") or relation.get("name") or "")
            other_id = name_to_id.get(other_name)
            if other_id:
                relationships.append(
                    _relationship_between(
                        family_id,
                        from_person_id=person_id,
                        to_person_id=other_id,
                        label=str(relation.get("relation") or "亲人"),
                    )
                )

    persona_roles: dict[str, PersonaRole] = {}
    for role_label, persona in personas.items():
        person = _person_for_persona(persona, family_id, persons, name_to_id)
        persons[person.id] = person
        name_to_id.setdefault(person.full_name, person.id)
        if not any(r.from_person_id == person.id and r.to_person_id == elder_person.id for r in relationships):
            relationships.append(_relationship_to_elder(family_id, person.id, elder_person.id, persona.relation, elder.gender))
        role = PersonaRole(
            id=stable_id(family_id, "persona_role", role_label),
            family_id=family_id,
            person_id=person.id,
            role_label=persona.role_label or role_label,
            appellation_to_elder=persona.appellation,
            can_speak_as_person=True,
            comfort_style=persona.comfort_style,
            mood_preference=persona.mood_preference,
            sensitivity_map=persona.sensitivity_map,
            legacy_persona_id=role_label,
        )
        persona_roles[role.role_label] = role

    graph = FamilyGraph(persons=persons, relationships=_dedupe_relationships(relationships))
    active_role = _select_active_role(persona_roles, active_persona_role_label)
    memory_events = [
        _memory_event_from_legacy(memory, family_id, graph, elder_person)
        for memory in memories
        if memory.content
    ]
    state = ConversationState(
        family_id=family_id,
        session_id=session_id,
        elder_person_id=elder_person.id,
        current_persona_role_id=active_role.id if active_role else "",
    )
    return FamilyCognitionContext(
        graph=graph,
        elder_person=elder_person,
        persona_roles=persona_roles,
        active_persona_role=active_role,
        memory_events=memory_events,
        state=state,
    )


def build_turn_cognition_prompt(
    *,
    cognition: FamilyCognitionContext,
    user_input: str,
    mentioned_names: list[str],
    intent: str,
    emotion: str,
    selected_role_label: str,
    top_event_count: int = 5,
) -> tuple[str, list[MemoryEvent], list[Person]]:
    if selected_role_label in cognition.persona_roles:
        cognition.active_persona_role = cognition.persona_roles[selected_role_label]
    speaker = cognition.active_person()
    mentioned_people = _resolve_people(cognition.graph, user_input, mentioned_names)
    if speaker and speaker.id not in {person.id for person in mentioned_people}:
        mentioned_people.insert(0, speaker)

    events = select_memory_events(
        cognition.memory_events,
        speaker_person_id=speaker.id if speaker else "",
        mentioned_person_ids=[person.id for person in mentioned_people],
        user_input=user_input,
        limit=top_event_count,
    )
    relation_focus = _relationship_focus(cognition.graph, speaker, mentioned_people)
    cognition.state.update_turn(
        current_persona_role_id=cognition.active_persona_role.id if cognition.active_persona_role else "",
        mentioned_person_ids=[person.id for person in mentioned_people],
        event_ids=[event.id for event in events],
        elder_emotion=emotion,
        intent=intent,
        ongoing_topic="、".join(_keywords_from_input(user_input)[:3]),
        relationship_focus=relation_focus,
    )
    sections = [
        cognition.graph.build_identity_context(speaker, cognition.elder_person, mentioned_people),
        cognition.graph.relationship_context([cognition.elder_person, *mentioned_people]),
        cognition.state.to_prompt_context(),
        _memory_events_prompt(events, speaker.id if speaker else ""),
        _response_policy_prompt(),
    ]
    return "\n\n".join(section for section in sections if section), events, mentioned_people


def select_memory_events(
    events: list[MemoryEvent],
    *,
    speaker_person_id: str,
    mentioned_person_ids: list[str],
    user_input: str,
    limit: int = 5,
) -> list[MemoryEvent]:
    scored: list[tuple[int, MemoryEvent]] = []
    mentioned = set(mentioned_person_ids)
    for event in events:
        if speaker_person_id and not event.can_mention(speaker_person_id):
            continue
        participant_ids = {participant.person_id for participant in event.participants}
        score = 0
        if speaker_person_id in participant_ids:
            score += 4
        score += 2 * len(participant_ids & mentioned)
        score += sum(1 for tag in event.topic_tags if tag and tag in user_input)
        score += sum(1 for tag in event.emotion_tags if tag and tag in user_input)
        score += len(set(event.summary) & set(user_input)) // 3
        if score > 0:
            scored.append((score, event))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [event for _, event in scored[:limit]]


def check_response_identity_boundaries(
    response: str,
    *,
    events: list[MemoryEvent],
    speaker_person_id: str,
) -> list[str]:
    if not response or not speaker_person_id:
        return []
    issues: list[str] = []
    first_person_markers = ("我上次", "我当时", "我给您", "我给你", "我做", "我带您", "我陪您")
    if not any(marker in response for marker in first_person_markers):
        return []
    for event in events:
        if event.can_use_first_person(speaker_person_id):
            continue
        keywords = _event_keywords(event)
        if keywords and any(keyword in response for keyword in keywords):
            issues.append(f"事件“{event.title or event.summary[:20]}”不允许当前角色用第一人称表述。")
    return issues


def _person_from_elder(elder: ElderProfile, family_id: str) -> Person:
    name = elder.full_name or "老人"
    return Person(
        id=stable_id(family_id, "elder", name),
        family_id=family_id,
        full_name=name,
        kind="elder",
        gender=elder.gender,
        nicknames=[elder.get_appellation()] if elder.get_appellation() else [],
        traits=elder.personality,
        habits=elder.habits,
        interests=elder.preferences,
        speech_style=elder.speech_traits,
        experiences={"life": elder.life_experiences, "important_memories": elder.important_memories},
        topic_boundaries={"health_notes": elder.health_notes},
    )


def _person_from_family_profile(profile: FamilyProfile, family_id: str) -> Person:
    return Person(
        id=stable_id(family_id, "person", profile.name),
        family_id=family_id,
        full_name=profile.name,
        kind="family",
        gender=profile.gender,
        traits=profile.personality,
        habits=profile.habits,
        interests=profile.preferences,
        experiences={"family": [profile.notes] if profile.notes else []},
        legacy_family_profile_id=profile.name,
    )


def _person_for_persona(
    persona: PersonaProfile,
    family_id: str,
    persons: dict[str, Person],
    name_to_id: dict[str, str],
) -> Person:
    role_label = persona.role_label or "家人"
    for name, person_id in name_to_id.items():
        if name and name in role_label:
            existing = persons[person_id]
            return Person(
                id=existing.id,
                family_id=existing.family_id,
                full_name=existing.full_name,
                kind="persona_capable",
                nicknames=existing.nicknames,
                gender=existing.gender,
                address_terms=existing.address_terms,
                traits=persona.personality or existing.traits,
                speech_style=persona.speech_style or existing.speech_style,
                habits=existing.habits,
                interests=existing.interests,
                experiences=existing.experiences,
                knowledge_boundaries=existing.knowledge_boundaries,
                topic_boundaries=persona.sensitivity_map or existing.topic_boundaries,
                legacy_family_profile_id=existing.legacy_family_profile_id,
                legacy_persona_id=role_label,
            )
    name = _strip_relation_prefix(role_label, persona.relation)
    return Person(
        id=stable_id(family_id, "person", name),
        family_id=family_id,
        full_name=name,
        kind="persona_capable",
        traits=persona.personality,
        speech_style=persona.speech_style,
        topic_boundaries=persona.sensitivity_map,
        legacy_persona_id=role_label,
    )


def _relationship_to_elder(
    family_id: str,
    person_id: str,
    elder_id: str,
    relation: str,
    elder_gender: str,
) -> Relationship:
    label = relation or "亲人"
    return Relationship(
        family_id=family_id,
        from_person_id=person_id,
        to_person_id=elder_id,
        relation_type=_relation_type(label),
        display_label=label,
        inverse_relation_type=_inverse_relation_type(label),
        inverse_display_label=_elder_inverse_label(label, elder_gender),
        source="legacy_profile",
    )


def _relationship_between(
    family_id: str,
    *,
    from_person_id: str,
    to_person_id: str,
    label: str,
) -> Relationship:
    return Relationship(
        family_id=family_id,
        from_person_id=from_person_id,
        to_person_id=to_person_id,
        relation_type=_relation_type(label),
        display_label=label,
        inverse_relation_type=_inverse_relation_type(label),
        inverse_display_label=_inverse_label(label),
        source="legacy_profile_relations",
    )


def _memory_event_from_legacy(
    memory: MemoryUnit,
    family_id: str,
    graph: FamilyGraph,
    elder_person: Person,
) -> MemoryEvent:
    participant_ids: list[str] = []
    for value in [memory.subject, *memory.family_members]:
        clean = _clean_member_name(value)
        person = graph.get_person(clean)
        if person:
            participant_ids.append(person.id)
    if elder_person.id not in participant_ids:
        participant_ids.append(elder_person.id)
    participant_ids = list(dict.fromkeys(participant_ids))
    subject_person = graph.get_person(_clean_member_name(memory.subject))
    participants = [
        MemoryEventParticipant(
            person_id=person_id,
            role_in_event="subject" if subject_person and person_id == subject_person.id else "participant",
            perspective="experienced" if person_id in {elder_person.id, subject_person.id if subject_person else ""} else "heard_about",
            can_use_first_person=person_id in {elder_person.id, subject_person.id if subject_person else ""},
            can_mention=True,
        )
        for person_id in participant_ids
    ]
    return MemoryEvent(
        id=memory.id,
        family_id=family_id,
        title=title_from_summary(memory.content),
        summary=memory.content,
        participants=participants,
        emotion_tags=memory.emotion_tags,
        topic_tags=memory.topic_tags,
        source_type="legacy_memory",
        source_person_id=subject_person.id if subject_person else "",
        truth_status="uncertain",
    )


def _resolve_people(graph: FamilyGraph, user_input: str, mentioned_names: list[str]) -> list[Person]:
    people = graph.resolve_mentions(user_input)
    seen = {person.id for person in people}
    for name in mentioned_names:
        person = graph.get_person(name)
        if person and person.id not in seen:
            people.append(person)
            seen.add(person.id)
    return people


def _memory_events_prompt(events: list[MemoryEvent], speaker_person_id: str) -> str:
    lines = ["## 结构化记忆事件"]
    if not events or not speaker_person_id:
        lines.append("- 当前没有可安全引用的结构化记忆事件。")
        return "\n".join(lines)
    for index, event in enumerate(events, start=1):
        evidence = event.to_prompt_evidence(speaker_person_id)
        if evidence:
            lines.append(f"{index}. {evidence}")
    if len(lines) == 1:
        lines.append("- 当前没有符合角色视角边界的记忆事件。")
    return "\n".join(lines)


def _response_policy_prompt() -> str:
    return (
        "## 身份与事实边界\n"
        "- 只能以当前角色说话，不冒充其他家人。\n"
        "- 只有标注“可以用第一人称提起”的事件，才可以说“我当时/我上次/我给您”。\n"
        "- 标注“只能转述”的事件，必须用“我听说/家里人说/我记得您提过”等表达。\n"
        "- 不承诺现实行为，不给医疗诊断或用药建议。"
    )


def _relationship_focus(graph: FamilyGraph, speaker: Person | None, mentioned_people: list[Person]) -> dict:
    if not speaker:
        return {}
    for person in mentioned_people:
        if person.id == speaker.id:
            continue
        relationship = graph.get_relationship(person.id, speaker.id)
        if relationship:
            return {
                "from_person_id": person.id,
                "to_person_id": speaker.id,
                "relation_label": f"{person.full_name}是{speaker.full_name}的{relationship.display_label}",
            }
    return {}


def _keywords_from_input(user_input: str) -> list[str]:
    return [word for word in re.split(r"[\s，。！？,.!?]+", user_input or "") if word]


def _event_keywords(event: MemoryEvent) -> list[str]:
    values = [event.title, *event.topic_tags]
    values.extend(part for part in re.split(r"[\s，。！？,.!?]+", event.summary or "") if len(part) >= 2)
    return [value for value in dict.fromkeys(values) if value]


def _strip_relation_prefix(role_label: str, relation: str) -> str:
    prefixes = [relation, "儿子", "女儿", "儿媳", "女婿", "老伴", "丈夫", "妻子", "孙子", "孙女", "家人"]
    for prefix in prefixes:
        if prefix and role_label.startswith(prefix):
            stripped = role_label.removeprefix(prefix).strip()
            if stripped:
                return stripped
    return role_label


def _clean_member_name(value: str) -> str:
    text = str(value or "").strip()
    if "(" in text:
        text = text.split("(", 1)[0]
    if "（" in text:
        text = text.split("（", 1)[0]
    return text.strip()


def _relation_type(label: str) -> str:
    mapping = {
        "儿子": "son",
        "女儿": "daughter",
        "子女": "child",
        "儿媳": "daughter_in_law",
        "女婿": "son_in_law",
        "妻子": "spouse",
        "丈夫": "spouse",
        "老伴": "spouse",
        "孙子": "grandson",
        "孙女": "granddaughter",
        "母亲": "mother",
        "父亲": "father",
    }
    return mapping.get(label, "related")


def _inverse_relation_type(label: str) -> str:
    mapping = {
        "儿子": "mother_or_father",
        "女儿": "mother_or_father",
        "子女": "mother_or_father",
        "儿媳": "parent_in_law",
        "女婿": "parent_in_law",
        "妻子": "spouse",
        "丈夫": "spouse",
        "老伴": "spouse",
        "孙子": "grandparent",
        "孙女": "grandparent",
        "母亲": "child",
        "父亲": "child",
    }
    return mapping.get(label, "related")


def _elder_inverse_label(label: str, elder_gender: str) -> str:
    if label in {"儿子", "女儿", "子女"}:
        return "母亲" if elder_gender == "女" else ("父亲" if elder_gender == "男" else "长辈")
    if label == "儿媳":
        return "婆婆" if elder_gender == "女" else ("公公" if elder_gender == "男" else "长辈")
    if label == "女婿":
        return "岳母" if elder_gender == "女" else ("岳父" if elder_gender == "男" else "长辈")
    if label in {"孙子", "孙女"}:
        return "奶奶" if elder_gender == "女" else ("爷爷" if elder_gender == "男" else "祖辈")
    if label in {"妻子", "丈夫", "老伴"}:
        return "老伴"
    return "亲人"


def _inverse_label(label: str) -> str:
    mapping = {
        "妻子": "丈夫",
        "丈夫": "妻子",
        "儿子": "母亲",
        "女儿": "母亲",
        "母亲": "子女",
        "父亲": "子女",
    }
    return mapping.get(label, "亲人")


def _dedupe_relationships(relationships: list[Relationship]) -> list[Relationship]:
    result: list[Relationship] = []
    seen = set()
    for relationship in relationships:
        key = (relationship.from_person_id, relationship.to_person_id, relationship.display_label)
        if key not in seen:
            result.append(relationship)
            seen.add(key)
    return result


def _select_active_role(
    persona_roles: dict[str, PersonaRole],
    active_persona_role_label: str,
) -> PersonaRole | None:
    if active_persona_role_label and active_persona_role_label in persona_roles:
        return persona_roles[active_persona_role_label]
    if persona_roles:
        return persona_roles[sorted(persona_roles.keys())[0]]
    return None
