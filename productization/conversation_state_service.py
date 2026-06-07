from __future__ import annotations

from engine.conversation_state import ConversationState
from engine import db

_STATE_CACHE: dict[tuple[str, str], ConversationState] = {}


def load_conversation_state(
    *,
    family_id: str,
    session_id: str,
    elder_person_id: str = "",
    current_persona_role_id: str = "",
) -> ConversationState:
    key = _state_key(family_id, session_id)
    try:
        db.init_db()
        stored = db.load_conversation_state(key[0], key[1])
        if stored:
            _STATE_CACHE[key] = stored
            return stored
    except Exception:
        cached = _STATE_CACHE.get(key)
        if cached:
            return cached

    state = _STATE_CACHE.get(key) or ConversationState(
        family_id=key[0],
        session_id=key[1],
        elder_person_id=elder_person_id,
        current_persona_role_id=current_persona_role_id,
    )
    if elder_person_id and not state.elder_person_id:
        state.elder_person_id = elder_person_id
    if current_persona_role_id and not state.current_persona_role_id:
        state.current_persona_role_id = current_persona_role_id
    _STATE_CACHE[key] = state
    return state


def save_conversation_state(state: ConversationState) -> None:
    key = _state_key(state.family_id, state.session_id)
    _STATE_CACHE[key] = state
    try:
        db.init_db()
        db.save_conversation_state(state)
    except Exception:
        return


def clear_conversation_state_cache() -> None:
    _STATE_CACHE.clear()


def _state_key(family_id: str, session_id: str) -> tuple[str, str]:
    return (family_id or "local", session_id or "default")
