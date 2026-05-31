# Memory Candidates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate reviewable long-term memory candidates from chat turns without saving them automatically.

**Architecture:** Add a backend candidate endpoint that receives one chat turn, uses the existing parser path to extract a memory-like structure, and falls back to a deterministic draft when no memory is found. The `/history` page will call this endpoint to prefill the existing manual save panel, keeping final persistence behind the existing user-confirmed `createCloudMemory()` action.

**Tech Stack:** FastAPI, existing `parse_user_text`, existing cloud repository auth, Next.js App Router, TypeScript, pytest.

---

## File Structure

- Modify `api/schemas.py`: add memory candidate request/response models.
- Modify `api/handlers.py`: add `handle_memory_candidate()`.
- Modify `api/main.py`: add `POST /api/chat/memory-candidate`.
- Modify `web/src/lib/backend-api.ts`: add `generateMemoryCandidate()`.
- Modify `web/src/app/history/page.tsx`: add "生成记忆候选" button and fill the memory draft.
- Modify `tests/test_chat_history_phase_c.py`: add backend endpoint behavior test.
- Modify `tests/test_productization_foundation.py`: add frontend static contract checks.

## Task 1: Backend Candidate Endpoint

- [ ] Add a failing test that monkeypatches `parse_user_text()` to return one memory and verifies `POST /api/chat/memory-candidate` returns it without creating a memory record.
- [ ] Add request/response models in `api/schemas.py`.
- [ ] Implement `handle_memory_candidate()` in `api/handlers.py`.
- [ ] Add the FastAPI route in `api/main.py`.
- [ ] Run `python -m pytest tests/test_chat_history_phase_c.py -q`.

## Task 2: Frontend Candidate Flow

- [ ] Add `MemoryCandidateResponse` and `generateMemoryCandidate()` in `backend-api.ts`.
- [ ] Add per-turn "生成记忆候选" action in `/history`.
- [ ] On success, fill the existing `memoryDrafts[turn.id]` panel and show a confirmation message.
- [ ] Keep "确认保存" as the only persistence action.

## Task 3: Verification

- [ ] Run targeted productization tests.
- [ ] Run `cd web; npm run typecheck`.
- [ ] Run `cd web; npm run build`.
- [ ] Run full pytest with a workspace-local temp directory if Windows temp permissions fail.

## Self-Review

- The endpoint returns candidates only; it does not call `create_memory`.
- The UI still requires explicit user confirmation before saving.
- No object storage, deployment, or database migration work is included.
