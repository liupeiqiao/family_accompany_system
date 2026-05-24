from __future__ import annotations

import re
from uuid import uuid4

from engine import db
from engine.family import normalize_family_relation
from llm.parser import dedup_check, parse_user_text
from productization.chat_service import generate_chat_reply

from .schemas import (
    ChatRequest,
    ChatResponse,
    DeleteResponse,
    ImportCounts,
    ImportRequest,
    ImportResponse,
    ParseRequest,
    ParseResponse,
    RecordsResponse,
)

GENERIC_CHILD_RELATIONS = {"子女", "儿女", "孩子"}
FAMILY_LIST_FIELDS = ("personality", "preferences", "habits", "relations")
PERSONA_LIST_FIELDS = ("personality", "speech_style", "comfort_style")
ELDER_LIST_FIELDS = (
    "personality",
    "preferences",
    "habits",
    "health_notes",
    "speech_traits",
    "life_experiences",
    "important_memories",
)


def handle_parse(request: ParseRequest) -> ParseResponse:
    db.init_db()
    existing_personas = db.load_all_personas()
    existing_families = db.load_all_family_profiles()
    existing_memories = db.load_all_memories()

    parsed = parse_user_text(
        request.text,
        perspective=request.perspective,
        existing_families_text=_build_existing_families_text(existing_families),
    )
    parsed = _normalize_parsed(parsed)
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
        merge_preview=_build_merge_preview(parsed, existing_families, existing_personas),
    )


def handle_import(request: ImportRequest) -> ImportResponse:
    db.init_db()
    counts = ImportCounts()

    persona_payloads = request.personas or ([request.persona] if request.persona else [])
    for persona_payload in persona_payloads:
        if _save_persona_payload(persona_payload, request.dedup):
            counts.persona += 1

    elder_payloads = request.elder_profiles or ([request.elder_profile] if request.elder_profile else [])
    for elder_payload in elder_payloads:
        if _save_elder_payload(elder_payload, merge_into_existing=not request.elder_profiles):
            counts.elder_profile += 1

    family_actions = _family_actions_by_name(request.dedup)
    existing_families = _families_by_name(db.load_all_family_profiles())
    for profile in request.family_profiles:
        if not profile or not _has_importable_value(profile):
            continue
        action = family_actions.get(profile.get("name", ""), {})
        if action.get("action") == "skip":
            continue
        profile_to_save = dict(profile)
        profile_to_save["relation"] = normalize_family_relation(
            profile_to_save.get("relation", ""),
            profile_to_save.get("gender", ""),
        )
        target_profile = None
        if action.get("action") == "merge_into":
            target = action.get("target", "")
            target_profile = existing_families.get(target) or _find_family_by_partial_name(
                target,
                existing_families,
            )
        if target_profile is None:
            target_profile = existing_families.get(profile_to_save.get("name"))
        merged_profile = (
            _merge_family_profile(target_profile, profile_to_save)
            if target_profile
            else profile_to_save
        )
        db.save_family_profile(merged_profile)
        existing_families[merged_profile.get("name", "")] = merged_profile
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


def handle_records() -> RecordsResponse:
    db.init_db()
    personas = db.load_all_personas()
    elder_profiles = db.load_all_elders()
    return RecordsResponse(
        persona=personas[0] if personas else {},
        personas=personas,
        elder_profile=elder_profiles[0] if elder_profiles else {},
        elder_profiles=elder_profiles,
        family_profiles=db.load_all_family_profiles(),
        memories=db.load_all_memories(),
    )


def handle_delete_memory(memory_id: str) -> DeleteResponse:
    db.init_db()
    db.delete_memory(memory_id)
    return DeleteResponse(ok=True)


def handle_delete_family_profile(name: str) -> DeleteResponse:
    db.init_db()
    db.delete_family_profile(name)
    return DeleteResponse(ok=True)


def handle_delete_elder(full_name: str) -> DeleteResponse:
    db.init_db()
    db.delete_elder(full_name)
    return DeleteResponse(ok=True)


def handle_delete_persona(role_label: str) -> DeleteResponse:
    db.init_db()
    db.delete_persona(role_label)
    return DeleteResponse(ok=True)


def handle_chat(request: ChatRequest) -> ChatResponse:
    result = generate_chat_reply(request.text)
    return ChatResponse(
        text=result.text,
        audio_url=result.audio_url,
        debug=result.debug,
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


def _build_merge_preview(parsed: dict, existing_families: list[dict], existing_personas: list[dict]) -> list[str]:
    messages: list[str] = []
    family_names = {family.get("name", "") for family in existing_families if family.get("name")}
    persona_labels = {
        persona.get("role_label", "") for persona in existing_personas if persona.get("role_label")
    }

    for profile in parsed.get("family_profiles", []):
        name = profile.get("name", "")
        if name and name in family_names:
            messages.append(f"家人档案「{name}」将合并到已有档案")

    persona = parsed.get("persona", {})
    role_label = persona.get("role_label", "")
    if role_label:
        if role_label in persona_labels:
            messages.append(f"AI 角色「{role_label}」将合并到已有角色")
        for family_name in family_names:
            if family_name and family_name in role_label:
                messages.append(f"AI 角色「{role_label}」将合并到已有家人档案「{family_name}」")
                break

    return messages


def _normalize_parsed(parsed: dict) -> dict:
    normalized = dict(parsed)
    persona = dict(normalized.get("persona") or {})
    if persona:
        persona["relation"] = _normalize_persona_relation(persona)
        normalized["persona"] = persona

    family_profiles = []
    for profile in normalized.get("family_profiles", []):
        item = dict(profile)
        item["relation"] = normalize_family_relation(item.get("relation", ""), item.get("gender", ""))
        family_profiles.append(item)
    normalized["family_profiles"] = family_profiles
    return normalized


def _normalize_persona_relation(persona: dict) -> str:
    relation = (persona.get("relation") or "").strip()
    role_label = persona.get("role_label") or ""
    if relation in GENERIC_CHILD_RELATIONS:
        if "儿子" in role_label:
            return "儿子"
        if "女儿" in role_label:
            return "女儿"
    return relation


def _save_persona_payload(persona_payload: dict, dedup: dict) -> bool:
    if not persona_payload or not _has_importable_value(persona_payload):
        return False
    persona = dict(persona_payload)
    persona["relation"] = _normalize_persona_relation(persona)

    persona_action = dedup.get("persona_action", "")
    if persona_action == "skip":
        return False

    existing_personas = db.load_all_personas()
    existing = None
    if persona_action == "merge":
        existing = _find_persona_by_label(dedup.get("persona_match", ""), existing_personas)
    if existing is None:
        existing = {item.get("role_label"): item for item in existing_personas}.get(
            persona.get("role_label")
        )

    db.save_persona(_merge_persona(existing, persona) if existing else persona)
    return True


def _save_elder_payload(elder_payload: dict, *, merge_into_existing: bool) -> bool:
    if not elder_payload or not _has_importable_value(elder_payload):
        return False
    elder_profile = dict(elder_payload)
    existing = None
    if merge_into_existing:
        all_elders = {e.get("full_name"): e for e in db.load_all_elders()}
        existing = all_elders.get(elder_profile.get("full_name"))
    db.save_elder(_merge_elder(existing, elder_profile) if existing else elder_profile)
    return True


def _merge_list(existing: object, incoming: object) -> list:
    existing_items = existing if isinstance(existing, list) else ([] if not existing else [existing])
    incoming_items = incoming if isinstance(incoming, list) else ([] if not incoming else [incoming])
    return list(dict.fromkeys([*existing_items, *incoming_items]))


def _merge_notes(existing: object, incoming: object) -> str:
    existing_text = str(existing or "").strip()
    incoming_text = str(incoming or "").strip()
    if not existing_text:
        return incoming_text
    if not incoming_text or incoming_text == existing_text:
        return existing_text
    return f"{existing_text}\n{incoming_text}"


def _merge_family_profile(existing: dict, incoming: dict) -> dict:
    merged = dict(existing)
    merged["name"] = existing.get("name") or incoming.get("name", "")
    merged["gender"] = existing.get("gender") or incoming.get("gender", "")

    incoming_relation = normalize_family_relation(incoming.get("relation", ""), incoming.get("gender", ""))
    existing_relation = normalize_family_relation(existing.get("relation", ""), merged.get("gender", ""))
    if existing_relation in GENERIC_CHILD_RELATIONS and incoming_relation not in GENERIC_CHILD_RELATIONS:
        merged["relation"] = incoming_relation
    else:
        merged["relation"] = existing_relation or incoming_relation

    for field in FAMILY_LIST_FIELDS:
        merged[field] = _merge_list(existing.get(field, []), incoming.get(field, []))
    merged["notes"] = _merge_notes(existing.get("notes", ""), incoming.get("notes", ""))
    return merged


def _merge_persona(existing: dict, incoming: dict) -> dict:
    merged = dict(existing)
    merged["role_label"] = existing.get("role_label") or incoming.get("role_label", "")
    incoming_relation = _normalize_persona_relation(incoming)
    existing_relation = _normalize_persona_relation(existing)
    if existing_relation in GENERIC_CHILD_RELATIONS and incoming_relation not in GENERIC_CHILD_RELATIONS:
        merged["relation"] = incoming_relation
    else:
        merged["relation"] = existing_relation or incoming_relation
    merged["appellation"] = existing.get("appellation") or incoming.get("appellation", "")
    for field in PERSONA_LIST_FIELDS:
        merged[field] = _merge_list(existing.get(field, []), incoming.get(field, []))
    for field in ("mood_preference", "topic_affinity", "sensitivity_map"):
        merged[field] = {**(existing.get(field) or {}), **(incoming.get(field) or {})}
    return merged


def _merge_elder(existing: dict, incoming: dict) -> dict:
    merged = dict(existing)
    for field in ("full_name", "gender"):
        merged[field] = existing.get(field) or incoming.get(field, "")
    for field in ELDER_LIST_FIELDS:
        merged[field] = _merge_list(existing.get(field, []), incoming.get(field, []))
    merged["notes"] = _merge_notes(existing.get("notes", ""), incoming.get("notes", ""))
    return merged


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


def _find_persona_by_label(target: str, personas: list[dict]) -> dict | None:
    if not target:
        return None
    for persona in personas:
        role_label = persona.get("role_label", "")
        if target == role_label or target in role_label or role_label in target:
            return persona
    return None
