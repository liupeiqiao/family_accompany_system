from __future__ import annotations

from uuid import uuid4

from engine import db
from llm.parser import parse_user_text
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
    parsed = parse_user_text(
        request.text,
        perspective=request.perspective,
        existing_families_text="",
    )
    return ParseResponse(
        persona=parsed.get("persona", {}),
        memories=parsed.get("memories", []),
        family_profiles=parsed.get("family_profiles", []),
        elder_profile=parsed.get("elder_profile", {}),
    )


def _has_importable_value(data: dict) -> bool:
    return any(value not in ("", None, [], {}) for value in data.values())


def handle_import(request: ImportRequest) -> ImportResponse:
    db.init_db()
    counts = ImportCounts()

    if request.persona and _has_importable_value(request.persona):
        db.save_persona(request.persona)
        counts.persona = 1

    if request.elder_profile and _has_importable_value(request.elder_profile):
        db.save_elder(request.elder_profile)
        counts.elder_profile = 1

    for profile in request.family_profiles:
        if not profile or not _has_importable_value(profile):
            continue
        db.save_family_profile(profile)
        counts.family_profiles += 1

    for memory in request.memories:
        if not memory or not memory.get("content"):
            continue
        memory_to_save = dict(memory)
        memory_to_save.setdefault("id", uuid4().hex)
        db.save_memory(memory_to_save)
        counts.memories += 1

    return ImportResponse(ok=True, imported=counts)


def handle_chat(request: ChatRequest) -> ChatResponse:
    result = generate_chat_reply(request.text)
    return ChatResponse(
        text=result.text,
        audio_url=result.audio_url,
        debug=result.debug,
    )
