from __future__ import annotations

from datetime import datetime

from engine.elder import ElderProfile
from engine.family import FamilyProfile
from engine.memory import MemoryUnit
from engine.persona import PersonaProfile

from .chat_service import ChatContext
from .cloud_repository import CloudRepository


def build_family_chat_context(
    *,
    repo: CloudRepository,
    family_id: str,
    user_id: str,
) -> ChatContext:
    elder = _elder_from_record(repo.get_elder_current(family_id=family_id, user_id=user_id))
    families = {
        profile.name: profile
        for profile in (
            _family_profile_from_record(item)
            for item in repo.list_family_profiles(family_id=family_id, user_id=user_id)
        )
        if profile.name
    }
    memories = [
        _memory_from_record(item)
        for item in repo.list_memories(family_id=family_id, user_id=user_id)
        if item.get("content")
    ]
    personas = {
        persona.role_label: persona
        for persona in (
            _persona_from_record(item)
            for item in repo.list_personas(family_id=family_id, user_id=user_id)
        )
        if persona.role_label
    }
    return ChatContext(
        personas=personas,
        memories=memories,
        families=families,
        elder=elder,
    )


def _list_value(record: dict, key: str) -> list:
    value = record.get(key, [])
    return value if isinstance(value, list) else ([] if value in ("", None) else [value])


def _dict_value(record: dict, key: str) -> dict:
    value = record.get(key, {})
    return value if isinstance(value, dict) else {}


def _elder_from_record(record: dict) -> ElderProfile:
    return ElderProfile(
        full_name=str(record.get("full_name", "")),
        gender=str(record.get("gender", "")),
        personality=_list_value(record, "personality"),
        preferences=_list_value(record, "preferences"),
        habits=_list_value(record, "habits"),
        health_notes=_list_value(record, "health_notes"),
        speech_traits=_list_value(record, "speech_traits"),
        life_experiences=_list_value(record, "life_experiences"),
        important_memories=_list_value(record, "important_memories"),
        notes=str(record.get("notes", "")),
    )


def _family_profile_from_record(record: dict) -> FamilyProfile:
    return FamilyProfile(
        name=str(record.get("name", "")),
        gender=str(record.get("gender", "")),
        relation=str(record.get("relation", "")),
        personality=_list_value(record, "personality"),
        preferences=_list_value(record, "preferences"),
        habits=_list_value(record, "habits"),
        relations=_list_value(record, "relations"),
        notes=str(record.get("notes", "")),
    )


def _memory_from_record(record: dict) -> MemoryUnit:
    return MemoryUnit(
        id=str(record.get("id", "")),
        content=str(record.get("content", "")),
        memory_type=str(record.get("memory_type", "")),
        subject=str(record.get("subject", "")),
        family_members=_list_value(record, "family_members"),
        emotion_tags=_list_value(record, "emotion_tags"),
        topic_tags=_list_value(record, "topic_tags"),
        intimacy_weight=float(record.get("intimacy_weight", 0.5) or 0.5),
        timestamp=datetime.now(),
    )


def _persona_from_record(record: dict) -> PersonaProfile:
    return PersonaProfile(
        role_label=str(record.get("role_label", "")),
        relation=str(record.get("relation", "")),
        appellation=str(record.get("appellation", "")),
        personality=_list_value(record, "personality"),
        speech_style=_list_value(record, "speech_style"),
        comfort_style=_list_value(record, "comfort_style"),
        mood_preference=_dict_value(record, "mood_preference"),
        topic_affinity=_dict_value(record, "topic_affinity"),
        sensitivity_map=_dict_value(record, "sensitivity_map"),
    )
