# API Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose the existing LLM parsing and companion chat pipeline through a local Python API for the Next.js frontend.

**Architecture:** Keep Streamlit as a debug UI and move reusable chat orchestration into `productization/chat_service.py`. Add thin API request handlers in `api/handlers.py` and a FastAPI entrypoint in `api/main.py`; the first version uses existing SQLite persistence.

**Tech Stack:** Python, FastAPI, Pydantic, existing `engine/` and `llm/` modules, pytest.

---

### Task 1: Secure LLM Client

**Files:**
- Modify: `llm/client.py`
- Modify: `tests/test_api_error_handling.py`

- [ ] Replace the hardcoded DeepSeek API key with an environment-variable requirement.
- [ ] Update the test to expect a clear missing-key error instead of a bundled key.

### Task 2: Chat Service Extraction

**Files:**
- Create: `productization/chat_service.py`
- Test: `tests/test_api_integration.py`

- [ ] Add tests for deterministic chat generation using an injected fake LLM function.
- [ ] Implement a Streamlit-free chat pipeline that loads persona, memory, family, and elder data from SQLite.
- [ ] Return reply text plus debug metadata.

### Task 3: API Handlers And Entrypoint

**Files:**
- Create: `api/__init__.py`
- Create: `api/schemas.py`
- Create: `api/handlers.py`
- Create: `api/main.py`
- Modify: `requirements.txt`
- Test: `tests/test_api_integration.py`

- [ ] Add request/response schemas for parse and chat.
- [ ] Add handler functions that can be tested without importing FastAPI.
- [ ] Add FastAPI routes for `/api/parse` and `/api/chat`.
- [ ] Add `fastapi` and `uvicorn` to Python requirements.

### Task 4: Verification

**Files:**
- Existing test suite

- [ ] Run targeted API tests.
- [ ] Run the full pytest suite.
