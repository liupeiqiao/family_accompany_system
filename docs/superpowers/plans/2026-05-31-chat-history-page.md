# Chat History Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a family-facing conversation history page that shows elder voice/chat exchanges as readable turns with filters and replay buttons.

**Architecture:** The backend will keep the existing raw `chat_messages` endpoint and add a turn aggregation endpoint, `GET /api/chat/turns`, pairing user and assistant messages from the same session. The frontend will add typed API support plus a `/history` route that loads the current family, fetches turns, and applies client-side filters for persona, elder, and time range.

**Tech Stack:** FastAPI, existing `CloudRepository`, pytest, Next.js App Router, TypeScript, existing CSS system.

---

## File Structure

- Modify `api/handlers.py`: add `handle_list_chat_turns()` and pairing helpers.
- Modify `api/main.py`: add `GET /api/chat/turns`.
- Modify `web/src/lib/backend-api.ts`: add `ChatTurn` type and `fetchChatTurns()`.
- Create `web/src/app/history/page.tsx`: family-facing history UI with filters and replay.
- Modify `web/src/app/page.tsx`: add "对话历史" dashboard entry.
- Modify `web/src/app/globals.css`: add history page layout styles.
- Modify `tests/test_chat_history_phase_c.py`: add backend turn aggregation tests.
- Modify `tests/test_productization_foundation.py`: add static productization checks for the new page.

## Task 1: Backend Turn Aggregation

- [ ] Write a failing test that records two chat exchanges and expects `GET /api/chat/turns?family_id=...` to return two paired turns in newest-first order.
- [ ] Implement `handle_list_chat_turns()` by grouping raw messages by session and pairing each `user` message with the following `assistant` message.
- [ ] Include these fields in each turn: `id`, `session_id`, `elder_id`, `persona_id`, `voice_profile_id`, `user_text`, `assistant_text`, `audio_url`, `asr_provider`, `tts_provider`, `created_at`.
- [ ] Add FastAPI endpoint `GET /api/chat/turns`.
- [ ] Run `python -m pytest tests/test_chat_history_phase_c.py -q`.

## Task 2: Frontend API Contract

- [ ] Add `ChatTurn` type to `web/src/lib/backend-api.ts`.
- [ ] Add `fetchChatTurns(familyId: string): Promise<ChatTurn[]>`.
- [ ] Update productization static test to assert the new history page and API function exist.

## Task 3: History Page UI

- [ ] Create `web/src/app/history/page.tsx`.
- [ ] Load `fetchCurrentFamily()` and `fetchChatTurns()`.
- [ ] Add filters for persona, elder, and time range: all, today, 7 days, 30 days.
- [ ] Render each turn with elder/user text, AI reply text, metadata, and a replay button when `audio_url` exists.
- [ ] Add homepage dashboard link to `/history`.

## Task 4: Styling and Verification

- [ ] Add `.historyLayout`, `.historyFilters`, `.historyTurn`, `.turnMeta`, and related styles in `globals.css`.
- [ ] Run `python -m pytest tests/test_chat_history_phase_c.py tests/test_productization_foundation.py -q`.
- [ ] Run `cd web; npm run typecheck`.
- [ ] Run `cd web; npm run build`.
- [ ] Smoke test `http://127.0.0.1:3000/history` in the in-app browser.

## Self-Review

- Scope is limited to viewing history; no memory extraction, deletion, search, deployment, or object storage.
- The backend endpoint is additive and does not change the elder voice flow.
- The frontend keeps the elder page simple and moves family-facing review work into a separate route.
