# Profile Memory Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Web import flow that parses family text, lets the user edit profile and memory drafts, and saves them into the existing SQLite store.

**Architecture:** Add a thin `POST /api/import` layer over `engine/db.py`, keeping persistence on the backend. Extend the existing Next.js backend API client and replace the `records` placeholder page with a client-side import workspace.

**Tech Stack:** FastAPI, Pydantic, SQLite via `engine/db.py`, Next.js App Router, TypeScript, pytest, Next typecheck.

---

### Task 1: Backend Import API

**Files:**
- Modify: `api/schemas.py`
- Modify: `api/handlers.py`
- Modify: `api/main.py`
- Test: `tests/test_api_integration.py`

- [ ] **Step 1: Write failing API tests**

Add tests that call `handle_import` with persona, elder profile, family profile, and memory dictionaries, then assert `engine.db` can load them back. Add an empty import test that expects zero counts.

- [ ] **Step 2: Run backend import tests and verify failure**

Run: `python -m pytest tests/test_api_integration.py -q`

Expected: fails because `ImportRequest`, `ImportResponse`, or `handle_import` is missing.

- [ ] **Step 3: Implement schemas, handler, and route**

Add `ImportRequest`, `ImportCounts`, and `ImportResponse` to `api/schemas.py`. Implement `handle_import` in `api/handlers.py` with `db.init_db()`, `db.save_persona`, `db.save_elder`, `db.save_family_profile`, and `db.save_memory`. Add `@app.post("/api/import")` to `api/main.py`.

- [ ] **Step 4: Run backend import tests and verify pass**

Run: `python -m pytest tests/test_api_integration.py -q`

Expected: all tests in the file pass.

### Task 2: Frontend API Client

**Files:**
- Modify: `web/src/lib/backend-api.ts`
- Test: `tests/test_productization_foundation.py`

- [ ] **Step 1: Write failing source-contract test**

Extend the existing frontend boundary test to assert `importParsedData`, `/api/import`, and parse helper naming are present.

- [ ] **Step 2: Run source-contract test and verify failure**

Run: `python -m pytest tests/test_productization_foundation.py -q`

Expected: fails because the import helper does not exist yet.

- [ ] **Step 3: Implement client types and helpers**

Add reusable `ParsedDraft`, `ImportParsedRequest`, `ImportParsedResponse`, `parseProfileText`, and `importParsedData` exports. Keep the existing `parseText` export as an alias to avoid breaking existing callers.

- [ ] **Step 4: Run source-contract test and verify pass**

Run: `python -m pytest tests/test_productization_foundation.py -q`

Expected: all tests in the file pass.

### Task 3: Records Import Page

**Files:**
- Modify: `web/src/app/records/page.tsx`
- Modify: `web/src/app/globals.css`
- Test: `tests/test_productization_foundation.py`

- [ ] **Step 1: Write failing page-contract test**

Add assertions that `records/page.tsx` is a client component, calls `parseProfileText` and `importParsedData`, and includes editable controls plus delete buttons for list items.

- [ ] **Step 2: Run page-contract test and verify failure**

Run: `python -m pytest tests/test_productization_foundation.py -q`

Expected: fails because the page is still a static placeholder.

- [ ] **Step 3: Implement client page**

Replace the placeholder with a controlled form: source textarea, parse button, editable sections for `elder_profile`, `persona`, `family_profiles`, and `memories`, item delete buttons, save button, loading states, success state, and Chinese error copy.

- [ ] **Step 4: Add focused styles**

Extend `globals.css` with import page layout, form grid, list item, status, and action row styles. Keep styling aligned with the existing restrained product UI.

- [ ] **Step 5: Run page-contract test and verify pass**

Run: `python -m pytest tests/test_productization_foundation.py -q`

Expected: all tests in the file pass.

### Task 4: Verification

**Files:**
- No new files.

- [ ] **Step 1: Run Python regression tests**

Run: `python -m pytest tests/ -q --basetemp .pytest_tmp_import`

Expected: all tests pass.

- [ ] **Step 2: Run frontend typecheck**

Run: `npm run typecheck` from `web`.

Expected: TypeScript compiles successfully.

- [ ] **Step 3: Inspect Git status**

Run: `git status --short --untracked-files=all`

Expected: only this feature's files plus pre-existing unrelated `AGENTS.md` and `.gitattributes` are visible.

- [ ] **Step 4: Provide commit message without committing**

Do not run `git commit`. Provide a Conventional Commits message and a copyable command for the user, per `AGENTS.md`.
