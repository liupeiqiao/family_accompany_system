from __future__ import annotations

from uuid import uuid4

from engine import db
from engine.family import normalize_family_relation
from llm.parser import parse_user_text
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


def _normalize_persona_relation(persona: dict) -> str:
    relation = (persona.get("relation") or "").strip()
    role_label = persona.get("role_label") or ""
    if relation in GENERIC_CHILD_RELATIONS:
        if "儿子" in role_label:
            return "儿子"
        if "女儿" in role_label:
            return "女儿"
    return relation


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


def _format_existing_families(families: list[dict]) -> str:
    if not families:
        return ""
    lines = ["## 已有家人档案"]
    for family in families:
        lines.append(
            f"- {family.get('name', '')}（性别：{family.get('gender', '')}，关系：{family.get('relation', '')}）"
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


def _save_persona_payload(persona_payload: dict) -> bool:
    if not persona_payload or not _has_importable_value(persona_payload):
        return False
    persona = dict(persona_payload)
    persona["relation"] = _normalize_persona_relation(persona)
    existing_personas = {item.get("role_label"): item for item in db.load_all_personas()}
    existing = existing_personas.get(persona.get("role_label"))
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


def handle_parse(request: ParseRequest) -> ParseResponse:
    db.init_db()
    existing_families = db.load_all_family_profiles()
    existing_personas = db.load_all_personas()
    parsed = parse_user_text(
        request.text,
        perspective=request.perspective,
        existing_families_text=_format_existing_families(existing_families),
    )
    parsed = _normalize_parsed(parsed)
    return ParseResponse(
        persona=parsed.get("persona", {}),
        memories=parsed.get("memories", []),
        family_profiles=parsed.get("family_profiles", []),
        elder_profile=parsed.get("elder_profile", {}),
        merge_preview=_build_merge_preview(parsed, existing_families, existing_personas),
    )


def _has_importable_value(data: dict) -> bool:
    return any(value not in ("", None, [], {}) for value in data.values())


def handle_import(request: ImportRequest) -> ImportResponse:
    db.init_db()
    counts = ImportCounts()

    persona_payloads = request.personas or ([request.persona] if request.persona else [])
    for persona_payload in persona_payloads:
        if _save_persona_payload(persona_payload):
            counts.persona += 1

    elder_payloads = request.elder_profiles or ([request.elder_profile] if request.elder_profile else [])
    for elder_payload in elder_payloads:
        if _save_elder_payload(elder_payload, merge_into_existing=not request.elder_profiles):
            counts.elder_profile += 1

    existing_families = {item.get("name"): item for item in db.load_all_family_profiles()}
    for profile in request.family_profiles:
        if not profile or not _has_importable_value(profile):
            continue
        profile_to_save = dict(profile)
        profile_to_save["relation"] = normalize_family_relation(
            profile_to_save.get("relation", ""),
            profile_to_save.get("gender", ""),
        )
        existing = existing_families.get(profile_to_save.get("name"))
        merged_profile = _merge_family_profile(existing, profile_to_save) if existing else profile_to_save
        db.save_family_profile(merged_profile)
        existing_families[merged_profile.get("name")] = merged_profile
        counts.family_profiles += 1

    for memory in request.memories:
        if not memory or not memory.get("content"):
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
