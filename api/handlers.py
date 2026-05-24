from __future__ import annotations

import re
from uuid import uuid4

from engine import db
from llm.parser import dedup_check, parse_user_text
from productization.chat_service import generate_chat_reply

from .schemas import (
    ChatRequest,
    ChatResponse,
    ImportCounts,
    ImportRequest,
    ImportResponse,
    ParseRequest,
    ParseResponse,
)


def handle_parse(request: ParseRequest) -> ParseResponse:
    db.init_db()
    existing_personas = db.load_all_personas()
    existing_families = db.load_all_family_profiles()
    existing_memories = db.load_all_memories()
    existing_families_text = _build_existing_families_text(existing_families)

    parsed = parse_user_text(
        request.text,
        perspective=request.perspective,
        existing_families_text=existing_families_text,
    )
    dedup = (
        dedup_check(parsed, existing_personas, existing_families)
        if existing_personas or existing_families
        else {}
    )
    memory_actions = _build_memory_actions(parsed.get("memories", []), existing_memories)
    if memory_actions:
        dedup = dict(dedup)
        dedup["memory_actions"] = memory_actions
    return ParseResponse(
        persona=parsed.get("persona", {}),
        memories=parsed.get("memories", []),
        family_profiles=parsed.get("family_profiles", []),
        elder_profile=parsed.get("elder_profile", {}),
        dedup=dedup,
    )


def _has_importable_value(data: dict) -> bool:
    return any(value not in ("", None, [], {}) for value in data.values())


def _build_existing_families_text(existing_families: list[dict]) -> str:
    if not existing_families:
        return ""
    lines = ["## 已有家人档案"]
    for profile in existing_families:
        gender = f"，性别:{profile.get('gender', '')}" if profile.get("gender") else ""
        lines.append(
            f"- {profile.get('name', '')} (关系:{profile.get('relation', '')}{gender})"
        )
    return "\n".join(lines)


def handle_import(request: ImportRequest) -> ImportResponse:
    db.init_db()
    counts = ImportCounts()

    if request.persona and _has_importable_value(request.persona):
        persona_action = request.dedup.get("persona_action", "")
        if persona_action != "skip":
            if persona_action == "merge":
                target_persona = _find_persona_by_label(
                    request.dedup.get("persona_match", ""),
                    db.load_all_personas(),
                )
                if target_persona:
                    db.save_persona(_merge_persona(target_persona, request.persona))
                else:
                    db.save_persona(request.persona)
            else:
                db.save_persona(request.persona)
            counts.persona = 1

    if request.elder_profile and _has_importable_value(request.elder_profile):
        db.save_elder(request.elder_profile)
        counts.elder_profile = 1

    family_actions = _family_actions_by_name(request.dedup)
    existing_families = _families_by_name(db.load_all_family_profiles())

    for profile in request.family_profiles:
        if not profile or not _has_importable_value(profile):
            continue
        action = family_actions.get(profile.get("name", ""), {})
        if action.get("action") == "skip":
            continue
        if action.get("action") == "merge_into":
            target = action.get("target", "")
            target_profile = existing_families.get(target) or _find_family_by_partial_name(
                target, existing_families
            )
            if target_profile:
                merged = _merge_family_profile(target_profile, profile)
                db.save_family_profile(merged)
                existing_families[merged["name"]] = merged
                counts.family_profiles += 1
                continue
        db.save_family_profile(profile)
        existing_families[profile.get("name", "")] = profile
        counts.family_profiles += 1

    memory_actions = _memory_actions_by_content(request.dedup)
    for memory in request.memories:
        if not memory or not memory.get("content"):
            continue
        action = memory_actions.get(_normalize_memory_content(memory.get("content", "")), {})
        if action.get("action") == "skip":
            continue
        memory_to_save = dict(memory)
        memory_to_save.setdefault("id", uuid4().hex)
        db.save_memory(memory_to_save)
        counts.memories += 1

    return ImportResponse(ok=True, imported=counts)


def _family_actions_by_name(dedup: dict) -> dict[str, dict]:
    return {
        action.get("new_name", ""): action
        for action in dedup.get("family_actions", [])
        if action.get("new_name")
    }


def _memory_actions_by_content(dedup: dict) -> dict[str, dict]:
    return {
        _normalize_memory_content(action.get("new_content", "")): action
        for action in dedup.get("memory_actions", [])
        if action.get("new_content")
    }


def _build_memory_actions(new_memories: list[dict], existing_memories: list[dict]) -> list[dict]:
    if not new_memories or not existing_memories:
        return []

    existing_by_content = {
        _normalize_memory_content(memory.get("content", "")): memory
        for memory in existing_memories
        if memory.get("content")
    }
    actions = []
    for memory in new_memories:
        content = memory.get("content", "") if memory else ""
        normalized = _normalize_memory_content(content)
        if not normalized:
            continue
        existing = existing_by_content.get(normalized)
        if existing:
            actions.append(
                {
                    "new_content": content,
                    "action": "skip",
                    "target": existing.get("id", ""),
                }
            )
    return actions


def _normalize_memory_content(content: str) -> str:
    normalized = re.sub(r"[\s\-_，。,.！？!；;：:、\"“”'‘’（）()]+", "", content or "")
    return normalized.casefold()


def _families_by_name(profiles: list[dict]) -> dict[str, dict]:
    return {profile.get("name", ""): profile for profile in profiles if profile.get("name")}


def _find_family_by_partial_name(target: str, profiles: dict[str, dict]) -> dict | None:
    if not target:
        return None
    for name, profile in profiles.items():
        if target in name or name in target:
            return profile
    return None


def _merge_unique(existing: list, incoming: list) -> list:
    return list(dict.fromkeys(list(existing or []) + list(incoming or [])))


def _find_persona_by_label(target: str, personas: list[dict]) -> dict | None:
    if not target:
        return None
    for persona in personas:
        role_label = persona.get("role_label", "")
        if target == role_label or target in role_label or role_label in target:
            return persona
    return None


def _merge_persona(existing: dict, incoming: dict) -> dict:
    merged = dict(existing)
    merged["relation"] = incoming.get("relation") or existing.get("relation", "")
    merged["appellation"] = incoming.get("appellation") or existing.get("appellation", "")
    merged["personality"] = _merge_unique(
        existing.get("personality", []),
        incoming.get("personality", []),
    )
    merged["speech_style"] = _merge_unique(
        existing.get("speech_style", []),
        incoming.get("speech_style", []),
    )
    merged["comfort_style"] = _merge_unique(
        existing.get("comfort_style", []),
        incoming.get("comfort_style", []),
    )
    merged["mood_preference"] = {
        **existing.get("mood_preference", {}),
        **incoming.get("mood_preference", {}),
    }
    merged["topic_affinity"] = {
        **existing.get("topic_affinity", {}),
        **incoming.get("topic_affinity", {}),
    }
    merged["sensitivity_map"] = {
        **existing.get("sensitivity_map", {}),
        **incoming.get("sensitivity_map", {}),
    }
    return merged


def _merge_family_profile(existing: dict, incoming: dict) -> dict:
    merged = dict(existing)
    merged["gender"] = incoming.get("gender") or existing.get("gender", "")
    merged["relation"] = incoming.get("relation") or existing.get("relation", "")
    merged["personality"] = _merge_unique(
        existing.get("personality", []),
        incoming.get("personality", []),
    )
    merged["preferences"] = _merge_unique(
        existing.get("preferences", []),
        incoming.get("preferences", []),
    )
    merged["habits"] = _merge_unique(existing.get("habits", []), incoming.get("habits", []))
    merged["relations"] = incoming.get("relations") or existing.get("relations", [])
    merged["notes"] = incoming.get("notes") or existing.get("notes", "")
    return merged


def handle_chat(request: ChatRequest) -> ChatResponse:
    result = generate_chat_reply(request.text)
    return ChatResponse(
        text=result.text,
        audio_url=result.audio_url,
        debug=result.debug,
    )
