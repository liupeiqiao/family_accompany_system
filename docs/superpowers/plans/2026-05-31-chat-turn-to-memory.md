# Chat Turn To Memory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let family users manually save valuable chat history turns into the long-term memory library.

**Architecture:** Reuse the existing `POST /api/memories` frontend client (`createCloudMemory`) and keep this feature on the `/history` page. Each turn can open a small editable save panel, prefilled from the turn text, then write a normal memory record with family scope.

**Tech Stack:** Next.js App Router, TypeScript, existing `backend-api.ts`, existing FastAPI memory endpoint, pytest static productization checks.

---

## File Structure

- Modify `web/src/app/history/page.tsx`: add per-turn save panel, memory draft state, and `createCloudMemory()` call.
- Modify `web/src/app/globals.css`: add memory save panel styles.
- Modify `tests/test_productization_foundation.py`: assert the history page can save turns to memories.

## Task 1: Static Contract

- [ ] Add assertions that `/history/page.tsx` imports `createCloudMemory`, tracks `memoryDrafts`, calls `saveTurnAsMemory`, and renders "保存为记忆".
- [ ] Run the targeted productization test and confirm it fails before implementation.

## Task 2: History Page Save Flow

- [ ] Import `createCloudMemory`.
- [ ] Add `MemoryDraft` type with `content`, `memory_type`, `subject`, `family_members`, `emotion_tags`, and `topic_tags`.
- [ ] Add `memoryDrafts`, `savedMemoryTurnIds`, and `memorySaveMessage` state.
- [ ] Add helpers for default draft creation and comma-separated list parsing.
- [ ] Add per-turn "保存为记忆" button, editable panel, and save/cancel actions.
- [ ] Mark a turn as saved after successful creation.

## Task 3: Styling And Verification

- [ ] Add `.memorySavePanel`, `.memorySaveGrid`, and `.savedBadge` styles.
- [ ] Run `python -m pytest tests/test_productization_foundation.py::test_history_page_lists_filterable_chat_turns -q`.
- [ ] Run `cd web; npm run typecheck`.
- [ ] Run `cd web; npm run build`.

## Self-Review

- No automatic memory extraction is introduced.
- No backend schema change is needed.
- The feature remains family-facing and does not add complexity to the elder page.
