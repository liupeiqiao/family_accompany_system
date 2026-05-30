from __future__ import annotations

import os
import re
from uuid import uuid4

from fastapi import HTTPException

from engine import db
from engine.family import normalize_family_relation
from llm.parser import dedup_check, parse_user_text
from productization.chat_service import generate_chat_reply
from productization.cloud_repository import (
    FamilyNotFoundError,
    FamilyPermissionError,
    get_cloud_repository,
)
from productization.family_context_service import build_family_chat_context
from productization.voice import (
    TextToSpeechRequest,
    VoiceCloneRequest,
    VoiceConsentError,
    VoiceProvider,
    get_voice_provider_from_env,
)

from .schemas import (
    ChatRequest,
    ChatResponse,
    DeleteResponse,
    FamilyCreateRequest,
    FamilyCurrentResponse,
    ImportCounts,
    ImportRequest,
    ImportResponse,
    ParseRequest,
    ParseResponse,
    RecordsResponse,
    TextToSpeechCreateRequest,
    TextToSpeechCreateResponse,
    VoiceCloneCreateRequest,
    VoiceManagementRequest,
    VoiceUploadIntentRequest,
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

_voice_provider: VoiceProvider | None = None
_voice_provider_signature: tuple[str | None, ...] | None = None


def get_voice_provider() -> VoiceProvider:
    global _voice_provider, _voice_provider_signature
    signature = (
        os.getenv("VOICE_PROVIDER"),
        os.getenv("DOUBAO_TTS_API_KEY"),
        os.getenv("DOUBAO_TTS_DEFAULT_VOICE_TYPE"),
        os.getenv("DOUBAO_TTS_RESOURCE_ID"),
        os.getenv("DOUBAO_TTS_CLONE_RESOURCE_ID"),
    )
    if _voice_provider is None or _voice_provider_signature != signature:
        _voice_provider = get_voice_provider_from_env()
        _voice_provider_signature = signature
    return _voice_provider


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


def _raise_cloud_http_error(error: Exception) -> None:
    if isinstance(error, FamilyPermissionError):
        raise HTTPException(status_code=403, detail=str(error)) from error
    if isinstance(error, FamilyNotFoundError):
        raise HTTPException(status_code=404, detail=str(error)) from error
    raise error


def _call_cloud(operation):
    try:
        return operation()
    except Exception as exc:
        _raise_cloud_http_error(exc)


def _extract_family_payload(payload: dict) -> tuple[str, dict]:
    data = dict(payload)
    family_id = str(data.pop("family_id", "")).strip()
    if not family_id:
        raise HTTPException(status_code=400, detail="family_id is required.")
    return family_id, data


def handle_get_current_family(user_id: str) -> FamilyCurrentResponse:
    result = _call_cloud(lambda: get_cloud_repository().get_current_family(user_id=user_id))
    return FamilyCurrentResponse(**result)


def handle_create_family(request: FamilyCreateRequest, user_id: str) -> FamilyCurrentResponse:
    repo = get_cloud_repository()

    def operation():
        family = repo.create_family(name=request.name, user_id=user_id)
        return repo.get_current_family(user_id=user_id) | {"family": family}

    return FamilyCurrentResponse(**_call_cloud(operation))


def handle_get_cloud_elder_current(family_id: str, user_id: str) -> dict:
    return _call_cloud(
        lambda: get_cloud_repository().get_elder_current(family_id=family_id, user_id=user_id)
    )


def handle_upsert_cloud_elder_current(payload: dict, user_id: str) -> dict:
    family_id, data = _extract_family_payload(payload)
    return _call_cloud(
        lambda: get_cloud_repository().upsert_elder_current(
            family_id=family_id,
            user_id=user_id,
            payload=data,
        )
    )


def handle_list_cloud_family_profiles(family_id: str, user_id: str) -> list[dict]:
    return _call_cloud(
        lambda: get_cloud_repository().list_family_profiles(family_id=family_id, user_id=user_id)
    )


def handle_create_cloud_family_profile(payload: dict, user_id: str) -> dict:
    family_id, data = _extract_family_payload(payload)
    return _call_cloud(
        lambda: get_cloud_repository().create_family_profile(
            family_id=family_id,
            user_id=user_id,
            payload=data,
        )
    )


def handle_update_cloud_family_profile(profile_id: str, payload: dict, user_id: str) -> dict:
    family_id, data = _extract_family_payload(payload)
    return _call_cloud(
        lambda: get_cloud_repository().update_family_profile(
            family_id=family_id,
            user_id=user_id,
            profile_id=profile_id,
            payload=data,
        )
    )


def handle_list_cloud_memories(family_id: str, user_id: str) -> list[dict]:
    return _call_cloud(
        lambda: get_cloud_repository().list_memories(family_id=family_id, user_id=user_id)
    )


def handle_create_cloud_memory(payload: dict, user_id: str) -> dict:
    family_id, data = _extract_family_payload(payload)
    return _call_cloud(
        lambda: get_cloud_repository().create_memory(
            family_id=family_id,
            user_id=user_id,
            payload=data,
        )
    )


def handle_update_cloud_memory(memory_id: str, payload: dict, user_id: str) -> dict:
    family_id, data = _extract_family_payload(payload)
    return _call_cloud(
        lambda: get_cloud_repository().update_memory(
            family_id=family_id,
            user_id=user_id,
            memory_id=memory_id,
            payload=data,
        )
    )


def handle_list_cloud_personas(family_id: str, user_id: str) -> list[dict]:
    return _call_cloud(
        lambda: get_cloud_repository().list_personas(family_id=family_id, user_id=user_id)
    )


def handle_create_cloud_persona(payload: dict, user_id: str) -> dict:
    family_id, data = _extract_family_payload(payload)
    return _call_cloud(
        lambda: get_cloud_repository().create_persona(
            family_id=family_id,
            user_id=user_id,
            payload=data,
        )
    )


def handle_update_cloud_persona(persona_id: str, payload: dict, user_id: str) -> dict:
    family_id, data = _extract_family_payload(payload)
    return _call_cloud(
        lambda: get_cloud_repository().update_persona(
            family_id=family_id,
            user_id=user_id,
            persona_id=persona_id,
            payload=data,
        )
    )


def handle_create_voice_upload_intent(request: VoiceUploadIntentRequest, user_id: str) -> dict:
    return _call_cloud(
        lambda: get_cloud_repository().create_voice_sample_upload_intent(
            family_id=request.family_id,
            user_id=user_id,
            filename=request.filename,
            sample_source=request.sample_source,
        )
    )


def handle_list_voice_samples(family_id: str, user_id: str) -> list[dict]:
    return _call_cloud(
        lambda: get_cloud_repository().list_voice_samples(family_id=family_id, user_id=user_id)
    )


def handle_list_voice_profiles(family_id: str, user_id: str) -> list[dict]:
    return _call_cloud(
        lambda: get_cloud_repository().list_voice_profiles(family_id=family_id, user_id=user_id)
    )


def handle_clone_voice(request: VoiceCloneCreateRequest, user_id: str) -> dict:
    repo = get_cloud_repository()

    def operation() -> dict:
        if request.sample_ids:
            samples = repo.list_voice_samples(family_id=request.family_id, user_id=user_id)
            selected_samples = [sample for sample in samples if sample.get("id") in request.sample_ids]
            if len(selected_samples) != len(request.sample_ids):
                raise FamilyNotFoundError("Voice sample not found.")
            if any(sample.get("created_by") != user_id for sample in selected_samples):
                raise FamilyPermissionError("Users can only clone their own voice samples.")
            sample_paths = [str(sample.get("storage_path", "")) for sample in selected_samples]
            sample_source = request.sample_source or str(selected_samples[0].get("sample_source", "upload"))
        else:
            sample_paths = []
            sample_source = "prepaid" if request.sample_source == "prepaid" else "preset"

        if sample_source == "prepaid":
            speaker_id = request.speaker_id.strip()
            if not speaker_id:
                raise ValueError("Prepaid speaker_id is required.")
            if not re.match(r"^(S_|icl_)", speaker_id, flags=re.IGNORECASE):
                raise ValueError("Prepaid speaker_id should start with S_ or icl_.")
            return repo.create_voice_profile(
                family_id=request.family_id,
                user_id=user_id,
                payload={
                    "display_name": request.display_name,
                    "provider": "doubao",
                    "provider_voice_id": speaker_id,
                    "status": "ready",
                    "consent_confirmed": request.consent_confirmed,
                    "sample_source": "prepaid",
                    "sample_ids": [],
                    "demo_audio_url": "",
                    "voice_type": request.voice_type or _derive_voice_type(request, sample_source),
                },
            )

        clone_result = get_voice_provider().create_clone(
            VoiceCloneRequest(
                family_id=request.family_id,
                created_by=user_id,
                sample_paths=sample_paths,
                consent_confirmed=request.consent_confirmed,
                sample_source=sample_source,
                audio_data_base64=request.audio_data_base64,
                audio_format=request.audio_format,
                speaker_id=request.speaker_id,
                custom_speaker_id=request.custom_speaker_id,
                text=request.prompt_text,
                language=request.language,
                demo_text=request.demo_text,
                enable_audio_denoise=request.enable_audio_denoise,
            )
        )
        return repo.create_voice_profile(
            family_id=request.family_id,
            user_id=user_id,
            payload={
                "display_name": request.display_name,
                "provider": clone_result.provider,
                "provider_voice_id": clone_result.provider_voice_id,
                "status": "ready",
                "consent_confirmed": request.consent_confirmed,
                "sample_source": sample_source,
                "sample_ids": request.sample_ids,
                "demo_audio_url": clone_result.demo_audio_url,
                "voice_type": request.voice_type or _derive_voice_type(request, sample_source),
            },
        )

    try:
        return _call_cloud(operation)
    except (VoiceConsentError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _get_voice_profile(family_id: str, user_id: str, voice_profile_id: str) -> dict:
    profiles = get_cloud_repository().list_voice_profiles(family_id=family_id, user_id=user_id)
    for profile in profiles:
        if profile.get("id") == voice_profile_id:
            return profile
    raise FamilyNotFoundError("Voice profile not found.")


def _get_ready_voice_profile(family_id: str, user_id: str, voice_profile_id: str) -> dict:
    profile = _get_voice_profile(family_id, user_id, voice_profile_id)
    if profile.get("status") != "ready":
        raise FamilyPermissionError("Voice profile is not ready.")
    return profile


def handle_get_voice_status(request: VoiceManagementRequest, user_id: str) -> dict:
    try:
        profile = _call_cloud(
            lambda: _get_voice_profile(
                request.family_id,
                user_id,
                request.voice_profile_id,
            )
        )
        provider_voice_id = str(profile.get("provider_voice_id") or "")
        status = get_voice_provider().get_voice_status(provider_voice_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "profile_id": profile.get("id"),
        "provider": profile.get("provider"),
        "provider_voice_id": provider_voice_id,
        "voice_status": status,
    }


def handle_upgrade_voice(request: VoiceManagementRequest, user_id: str) -> dict:
    try:
        profile = _call_cloud(
            lambda: _get_voice_profile(
                request.family_id,
                user_id,
                request.voice_profile_id,
            )
        )
        provider_voice_id = str(profile.get("provider_voice_id") or "")
        status = get_voice_provider().upgrade_voice(provider_voice_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "profile_id": profile.get("id"),
        "provider": profile.get("provider"),
        "provider_voice_id": provider_voice_id,
        "voice_status": status,
    }


def _synthesize_with_profile(*, family_id: str, user_id: str, voice_profile_id: str, text: str) -> dict:
    profile = _get_ready_voice_profile(family_id, user_id, voice_profile_id)
    result = get_voice_provider().synthesize(
        TextToSpeechRequest(
            family_id=family_id,
            voice_profile_id=str(profile.get("provider_voice_id") or ""),
            text=text,
            is_cloned_voice=_is_cloned_voice_profile(profile),
        )
    )
    return {"provider": result.provider, "audio_url": result.audio_path}


def _is_cloned_voice_profile(profile: dict) -> bool:
    if str(profile.get("provider", "")).lower() != "doubao":
        return False
    provider_voice_id = str(profile.get("provider_voice_id") or "")
    if provider_voice_id and provider_voice_id != os.getenv("DOUBAO_TTS_DEFAULT_VOICE_TYPE", ""):
        return True
    return str(profile.get("sample_source", "")).lower() != "preset"


def _derive_voice_type(request: VoiceCloneCreateRequest, sample_source: str) -> str:
    if sample_source == "preset" and not request.audio_data_base64:
        return "preset"
    if request.speaker_id and not request.custom_speaker_id:
        if request.speaker_id.startswith("S_") or request.speaker_id.startswith("icl_"):
            return "prepaid"
    if request.custom_speaker_id:
        return "postpaid"
    if request.audio_data_base64:
        return "postpaid"
    return "prepaid"


def handle_tts(request: TextToSpeechCreateRequest, user_id: str) -> TextToSpeechCreateResponse:
    try:
        result = _call_cloud(
            lambda: _synthesize_with_profile(
                family_id=request.family_id,
                user_id=user_id,
                voice_profile_id=request.voice_profile_id,
                text=request.text,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return TextToSpeechCreateResponse(**result)


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


def handle_delete_cloud_memory(memory_id: str, family_id: str, user_id: str) -> DeleteResponse:
    _call_cloud(
        lambda: get_cloud_repository().delete_memory(
            family_id=family_id,
            user_id=user_id,
            memory_id=memory_id,
        )
    )
    return DeleteResponse(ok=True)


def handle_delete_cloud_family_profile(
    profile_id: str,
    family_id: str,
    user_id: str,
) -> DeleteResponse:
    _call_cloud(
        lambda: get_cloud_repository().delete_family_profile(
            family_id=family_id,
            user_id=user_id,
            profile_id=profile_id,
        )
    )
    return DeleteResponse(ok=True)


def handle_delete_voice_profile(profile_id: str, family_id: str, user_id: str) -> DeleteResponse:
    _call_cloud(
        lambda: get_cloud_repository().delete_voice_profile(
            family_id=family_id,
            user_id=user_id,
            profile_id=profile_id,
        )
    )
    return DeleteResponse(ok=True)


def handle_chat(request: ChatRequest, user_id: str = "demo-user") -> ChatResponse:
    if request.family_id and request.family_id != "local":
        try:
            context = build_family_chat_context(
                repo=get_cloud_repository(),
                family_id=request.family_id,
                user_id=user_id,
            )
        except Exception as exc:
            if isinstance(exc, (FamilyPermissionError, FamilyNotFoundError)):
                return ChatResponse(
                    text="我这边暂时没读到家里的资料，您先慢慢说，我在听。",
                    debug={
                        "context_source": "cloud",
                        "cloud_context_error": str(exc),
                    },
                )
            raise
        result = generate_chat_reply(request.text, context=context)
    else:
        result = generate_chat_reply(request.text)
    debug = dict(result.debug)
    audio_url = result.audio_url
    if request.family_id and request.family_id != "local" and request.voice_profile_id:
        try:
            tts_result = _synthesize_with_profile(
                family_id=request.family_id,
                user_id=user_id,
                voice_profile_id=request.voice_profile_id,
                text=result.text,
            )
            audio_url = tts_result["audio_url"]
            debug["tts_provider"] = tts_result["provider"]
        except Exception as exc:
            debug["tts_error"] = str(exc)
    return ChatResponse(
        text=result.text,
        audio_url=audio_url,
        debug=debug,
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
