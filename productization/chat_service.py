from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

from engine.adaptation import (
    build_retry_hint,
    check_elderly_adaptation,
    safety_check,
)
from engine.db import (
    init_db,
    load_all_family_profiles,
    load_all_memories,
    load_all_personas,
    load_elder,
)
from engine.elder import ElderProfile
from engine.family import FamilyProfile
from engine.memory import MemoryUnit
from engine.persona import PersonaProfile
from engine.scorer import DEFAULT_WEIGHTS, get_top_memories, score_memories
from engine.strategy import select_strategy
from llm import client as llm_client
from llm.prompts import (
    INTENT_EMOTION_SYSTEM,
    INTENT_EMOTION_USER,
    RESPONSE_USER,
    build_response_system,
)

ChatFn = Callable[[str, str, float], str]


@dataclass
class ChatResult:
    text: str
    debug: dict = field(default_factory=dict)
    audio_url: str | None = None


@dataclass
class PersonaSelection:
    role_label: str
    reason: str
    confidence: float


def generate_chat_reply(
    user_input: str,
    *,
    chat_fn: ChatFn | None = None,
    weights: dict | None = None,
) -> ChatResult:
    init_db()
    llm = chat_fn or llm_client.chat
    active_weights = weights or DEFAULT_WEIGHTS

    personas = _load_personas()
    persona = _select_default_persona(personas)
    memories = _load_memories()
    families = _load_family_profiles()
    elder = _load_elder()

    intent_result = _analyze_intent(user_input, llm)
    intent = intent_result.get("intent", "日常闲聊")
    emotion = intent_result.get("emotion", "平静")
    mentioned_names = intent_result.get("mentioned", []) or []
    talk_to = intent_result.get("talk_to", "")

    selected = _select_persona_for_turn(
        user_input=user_input,
        talk_to=talk_to,
        mentioned_names=mentioned_names,
        personas=personas,
        default_role_label=persona.role_label,
    )
    if selected.role_label in personas:
        persona = personas[selected.role_label]

    relevant_memories = _filter_memories(memories, mentioned_names, persona)
    scored_list = score_memories(
        relevant_memories,
        user_input,
        intent,
        emotion,
        persona,
        active_weights,
    ) if relevant_memories else []
    top_memories = get_top_memories(scored_list, n=5)
    strategy = select_strategy(intent, emotion, persona)

    memory_context = _build_memory_context(top_memories)
    mentioned_context = _build_mentioned_persona_context(
        mentioned_names,
        personas,
        persona,
        selected.role_label if selected.reason != "default" else None,
    )
    family_context = _build_family_context(elder, families, mentioned_names)

    system_prompt = build_response_system(
        role_label=persona.role_label or "家人",
        appellation=persona.appellation or elder.get_appellation() or "您",
        personality=persona.personality,
        speech_style=persona.speech_style,
        comfort_style=persona.comfort_style,
        strategy=strategy,
        memory_context=memory_context,
        mentioned_persona_context=mentioned_context,
        family_profiles_context=family_context,
    )

    response = _generate_safe_response(user_input, persona, elder, strategy, memory_context, mentioned_context, family_context, llm, system_prompt)

    debug = {
        "intent": intent,
        "emotion": emotion,
        "talk_to": selected.role_label if selected.reason != "default" else talk_to,
        "selected_persona": persona.role_label or "家人",
        "persona_switch_reason": selected.reason,
        "persona_switch_confidence": selected.confidence,
        "mentioned": mentioned_names,
        "strategy": strategy,
        "top_memories": [
            {"subject": m.subject or "老人", "content": m.content[:40]}
            for m in top_memories
        ],
        "scores": [
            {
                "id": sr.memory.id,
                "subject": sr.memory.subject or "-",
                "content": sr.memory.content[:30],
                "R": round(sr.score_r, 3),
                "E": round(sr.score_e, 3),
                "C": round(sr.score_c, 3),
                "S": round(sr.score_s, 3),
                "M": round(sr.penalty_m, 3),
                "total": round(sr.total, 3),
            }
            for sr in scored_list[:5]
        ],
        "confidence": intent_result.get("confidence", 0),
    }
    return ChatResult(text=response, debug=debug)


def _analyze_intent(user_input: str, chat_fn: ChatFn) -> dict:
    try:
        raw = chat_fn(
            INTENT_EMOTION_SYSTEM,
            INTENT_EMOTION_USER.format(user_input=user_input),
            0.3,
        )
        return _parse_json_object(raw)
    except Exception:
        return {
            "intent": "日常闲聊",
            "emotion": "平静",
            "confidence": 0.0,
            "keywords": [],
            "talk_to": "陪伴者",
            "mentioned": [],
        }


def _parse_json_object(raw: str) -> dict:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", raw)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                return {}
    return {}


def _generate_safe_response(
    user_input: str,
    persona: PersonaProfile,
    elder: ElderProfile,
    strategy: str,
    memory_context: str,
    mentioned_context: str,
    family_context: str,
    chat_fn: ChatFn,
    system_prompt: str,
) -> str:
    appellation = persona.appellation or elder.get_appellation() or "您"
    role_label = persona.role_label or "家人"

    for attempt in range(2):
        try:
            response = chat_fn(
                system_prompt,
                RESPONSE_USER.format(user_input=user_input, role_label=role_label),
                0.7,
            )
        except Exception:
            return f"{appellation}，我这边信号不太好，您再说一遍？"

        adapt_result = check_elderly_adaptation(response, appellation)
        safety_issues = safety_check(response)
        if adapt_result["pass"] and not safety_issues:
            return response

        if attempt == 0:
            system_prompt = build_response_system(
                role_label=role_label,
                appellation=appellation,
                personality=persona.personality,
                speech_style=persona.speech_style,
                comfort_style=persona.comfort_style,
                strategy=strategy,
                memory_context=memory_context,
                retry_hint=build_retry_hint(adapt_result["issues"], safety_issues),
                mentioned_persona_context=mentioned_context,
                family_profiles_context=family_context,
            )

    return response


def _load_personas() -> dict[str, PersonaProfile]:
    personas = {}
    for data in load_all_personas():
        persona = PersonaProfile(**data)
        if persona.role_label:
            personas[persona.role_label] = persona
    return personas


def _select_default_persona(personas: dict[str, PersonaProfile]) -> PersonaProfile:
    if personas:
        return personas[sorted(personas.keys())[0]]
    return PersonaProfile()


def _load_memories() -> list[MemoryUnit]:
    result = []
    for data in load_all_memories():
        result.append(
            MemoryUnit(
                id=data.get("id", ""),
                content=data.get("content", ""),
                memory_type=data.get("memory_type", ""),
                subject=data.get("subject", ""),
                family_members=data.get("family_members", []),
                emotion_tags=data.get("emotion_tags", []),
                topic_tags=data.get("topic_tags", []),
                intimacy_weight=data.get("intimacy_weight", 0.5),
                timestamp=datetime.now(),
            )
        )
    return result


def _load_family_profiles() -> dict[str, FamilyProfile]:
    profiles = {}
    for data in load_all_family_profiles():
        profile = FamilyProfile(**data)
        if profile.name:
            profiles[profile.name] = profile
    return profiles


def _load_elder() -> ElderProfile:
    data = load_elder()
    return ElderProfile(**data) if data else ElderProfile()


def _match_persona(talk_to: str, personas: dict[str, PersonaProfile]) -> str | None:
    if not talk_to:
        return None
    if talk_to in personas:
        return talk_to
    for role_label in personas:
        if talk_to in role_label or role_label in talk_to:
            return role_label
    return None


def _select_persona_for_turn(
    *,
    user_input: str,
    talk_to: str,
    mentioned_names: list[str],
    personas: dict[str, PersonaProfile],
    default_role_label: str,
) -> PersonaSelection:
    if not personas:
        return PersonaSelection("", "default", 0.0)

    direct_matches = _match_direct_address(user_input, personas)
    if len(direct_matches) == 1:
        return PersonaSelection(direct_matches[0], "direct_name", 0.95)
    if len(direct_matches) > 1:
        return PersonaSelection(default_role_label, "ambiguous", 0.3)

    relation_matches = _match_relation_request(user_input, personas)
    if len(relation_matches) == 1:
        return PersonaSelection(relation_matches[0], "relation_request", 0.9)
    if len(relation_matches) > 1:
        return PersonaSelection(default_role_label, "ambiguous", 0.3)

    matched_by_talk_to = _match_persona_by_text(talk_to, personas)
    if matched_by_talk_to:
        return PersonaSelection(matched_by_talk_to, "talk_to", 0.8)

    if _looks_like_direct_mentioned_address(user_input, mentioned_names):
        mentioned_matches = _match_mentioned_names(mentioned_names, personas)
        if len(mentioned_matches) == 1:
            return PersonaSelection(mentioned_matches[0], "direct_name", 0.85)
        if len(mentioned_matches) > 1:
            return PersonaSelection(default_role_label, "ambiguous", 0.3)

    return PersonaSelection(default_role_label, "default", 0.0)


def _match_direct_address(
    user_input: str,
    personas: dict[str, PersonaProfile],
) -> list[str]:
    matches = []
    for role_label, persona in personas.items():
        for token in _persona_address_tokens(persona):
            if not token:
                continue
            if _starts_with_address(user_input, token) or _contains_talk_request(user_input, token):
                matches.append(role_label)
                break
    return _unique(matches)


def _match_relation_request(
    user_input: str,
    personas: dict[str, PersonaProfile],
) -> list[str]:
    relation_term = _requested_relation_term(user_input)
    if not relation_term:
        return []

    matches = []
    for role_label, persona in personas.items():
        relation_tokens = _relation_tokens(persona)
        if relation_term in relation_tokens:
            matches.append(role_label)
    return _unique(matches)


def _match_persona_by_text(
    text: str,
    personas: dict[str, PersonaProfile],
) -> str | None:
    if not text or text in {"陪伴者", "家人", "亲人", "不知道", "无"}:
        return None
    if text in personas:
        return text

    matches = []
    for role_label, persona in personas.items():
        tokens = _persona_address_tokens(persona) + _relation_tokens(persona)
        if any(token and (text in token or token in text) for token in tokens):
            matches.append(role_label)

    unique_matches = _unique(matches)
    return unique_matches[0] if len(unique_matches) == 1 else None


def _match_mentioned_names(
    mentioned_names: list[str],
    personas: dict[str, PersonaProfile],
) -> list[str]:
    matches = []
    for name in mentioned_names:
        for role_label, persona in personas.items():
            if name in _persona_address_tokens(persona):
                matches.append(role_label)
    return _unique(matches)


def _persona_address_tokens(persona: PersonaProfile) -> list[str]:
    tokens = [persona.role_label]
    if persona.relation and persona.role_label.startswith(persona.relation):
        tokens.append(persona.role_label.removeprefix(persona.relation))
    for relation_alias in _relation_tokens(persona):
        if persona.role_label.startswith(relation_alias):
            tokens.append(persona.role_label.removeprefix(relation_alias))
    return [token for token in _unique(tokens) if token]


def _relation_tokens(persona: PersonaProfile) -> list[str]:
    relation = persona.relation
    tokens = [relation]
    relation_aliases = {
        "配偶": ["老伴", "爱人", "丈夫", "妻子", "老公", "老婆"],
        "老伴": ["配偶", "爱人", "丈夫", "妻子", "老公", "老婆"],
        "儿子": ["儿子", "孩子"],
        "女儿": ["女儿", "孩子"],
        "子女": ["儿子", "女儿", "孩子"],
    }
    tokens.extend(relation_aliases.get(relation, []))
    for alias in relation_aliases.get("配偶", []):
        if persona.role_label.startswith(alias):
            tokens.append(alias)
    return [token for token in _unique(tokens) if token]


def _starts_with_address(user_input: str, token: str) -> bool:
    return bool(re.match(rf"^\s*{re.escape(token)}[\s,，。！!、：:]", user_input))


def _contains_talk_request(user_input: str, token: str) -> bool:
    return bool(
        re.search(
            rf"(想|要|帮我|让我)?(和|跟|同|找|叫){re.escape(token)}(说|聊|讲话|通话|说会儿话)",
            user_input,
        )
    )


def _requested_relation_term(user_input: str) -> str:
    relation_terms = ["老伴", "配偶", "爱人", "丈夫", "妻子", "老公", "老婆", "儿子", "女儿"]
    for term in relation_terms:
        if _contains_talk_request(user_input, term):
            return term
    return ""


def _looks_like_direct_mentioned_address(
    user_input: str,
    mentioned_names: list[str],
) -> bool:
    return any(_starts_with_address(user_input, name) for name in mentioned_names)


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _filter_memories(
    memories: list[MemoryUnit],
    mentioned_names: list[str],
    persona: PersonaProfile,
) -> list[MemoryUnit]:
    relevant = [
        memory
        for memory in memories
        if memory.subject in mentioned_names or memory.subject == persona.role_label
    ]
    return relevant or list(memories)


def _build_memory_context(memories: list[MemoryUnit]) -> str:
    if not memories:
        return ""
    return "\n---\n".join(
        f"主语：{memory.subject or '老人'}\n类型：{memory.memory_type}\n内容：{memory.content}"
        for memory in memories
    )


def _build_mentioned_persona_context(
    mentioned_names: list[str],
    personas: dict[str, PersonaProfile],
    persona: PersonaProfile,
    matched_persona: str | None,
) -> str:
    context = ""
    for name in mentioned_names:
        other = personas.get(name) or _match_by_partial_name(name, personas)
        if other and other.role_label != persona.role_label:
            parts = [f"{other.role_label}是{other.relation}"]
            if other.personality:
                parts.append(f"性格{'、'.join(other.personality)}")
            if other.speech_style:
                parts.append(f"说话风格{'；'.join(other.speech_style)}")
            context += (
                f"\n## 老人提到的人\n老人提到了{other.role_label}。"
                + "，".join(parts)
                + f"。你可以用你对{other.role_label}的了解来自然地聊到ta。\n"
            )
    if matched_persona and matched_persona != persona.role_label:
        other = personas[matched_persona]
        context += (
            f"\n## 对话对象\n老人正在和{matched_persona}说话。"
            f"{matched_persona}是{other.relation}，性格"
            f"{'、'.join(other.personality) if other.personality else '随和'}。\n"
        )
    return context


def _match_by_partial_name(
    name: str,
    personas: dict[str, PersonaProfile],
) -> PersonaProfile | None:
    for role_label, persona in personas.items():
        if name in role_label or role_label in name:
            return persona
    return None


def _build_family_context(
    elder: ElderProfile,
    families: dict[str, FamilyProfile],
    mentioned_names: list[str],
) -> str:
    elder_context = ""
    if elder.full_name:
        gender_text = {"男": "老爷爷", "女": "老奶奶"}.get(elder.gender, "老人")
        parts = [f"{gender_text}「{elder.full_name}」"]
        if elder.personality:
            parts.append(f"性格{'、'.join(elder.personality)}")
        if elder.preferences:
            parts.append(f"喜好{'、'.join(elder.preferences)}")
        if elder.habits:
            parts.append(f"习惯{'、'.join(elder.habits)}")
        if elder.health_notes:
            parts.append(f"健康注意{'、'.join(elder.health_notes)}")
        if elder.speech_traits:
            parts.append(f"说话特点{'、'.join(elder.speech_traits)}")
        if elder.life_experiences:
            parts.append(f"人生经历{'、'.join(elder.life_experiences)}")
        elder_context = (
            "## 老人画像\n"
            + "，".join(parts)
            + "。请根据老人的性格、健康状况和说话特点来调整你的回复风格。\n\n"
        )

    family_lines = []
    for name in mentioned_names:
        profile = families.get(name)
        if not profile:
            continue
        parts = [f"{profile.name}是老人的{profile.relation}"]
        if profile.personality:
            parts.append(f"性格{'、'.join(profile.personality)}")
        if profile.preferences:
            parts.append(f"喜好{'、'.join(profile.preferences)}")
        if profile.habits:
            parts.append(f"习惯{'、'.join(profile.habits)}")
        family_lines.append(f"- {profile.name}（{'，'.join(parts)}）")
        if profile.relations:
            rel_parts = [
                f"{r.get('person') or r.get('name', '?')}的{r.get('relation', '?')}"
                for r in profile.relations
                if isinstance(r, dict)
            ]
            family_lines.append(f"  关系：{profile.name}是{'，'.join(rel_parts)}")

    family_context = ""
    if family_lines:
        family_context = "## 家人偏好档案\n" + "\n".join(family_lines) + "\n\n"

    return elder_context + family_context
