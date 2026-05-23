from __future__ import annotations

from llm.parser import parse_user_text
from productization.chat_service import generate_chat_reply

from .schemas import ChatRequest, ChatResponse, ParseRequest, ParseResponse


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


def handle_chat(request: ChatRequest) -> ChatResponse:
    result = generate_chat_reply(request.text)
    return ChatResponse(
        text=result.text,
        audio_url=result.audio_url,
        debug=result.debug,
    )
