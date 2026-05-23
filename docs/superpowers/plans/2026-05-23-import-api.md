# Import API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the parsed profile and memory draft save through a real FastAPI import endpoint into the existing local SQLite archive.

**Architecture:** Keep the first productized version on the current Python/FastAPI plus SQLite boundary. The frontend calls a typed backend helper, the API validates the parsed draft with Pydantic schemas, and the handler writes through `engine.db` so the existing Streamlit prototype and chat service can read the same data.

**Tech Stack:** FastAPI, Pydantic, SQLite through `engine/db.py`, Next.js TypeScript, pytest.

---

### Task 1: Runtime Import Endpoint Contract

**Files:**
- Modify: `tests/test_api_integration.py`
- Verify: `api/main.py`, `api/handlers.py`, `api/schemas.py`

- [ ] **Step 1: Write the route-level test**

Add a test that posts a representative import payload to the FastAPI app and checks the JSON response:

```python
def test_fastapi_import_endpoint_saves_payload(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from api.main import app
    from engine import db

    monkeypatch.chdir(tmp_path)
    client = TestClient(app)

    response = client.post(
        "/api/import",
        json={
            "family_id": "local",
            "persona": {
                "role_label": "儿子小明",
                "relation": "子女",
                "appellation": "妈",
            },
            "elder_profile": {"full_name": "宋桂兰", "gender": "女"},
            "family_profiles": [{"name": "小明", "relation": "儿子"}],
            "memories": [{"content": "去年中秋小明陪妈妈在院子里赏月。"}],
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "imported": {
            "persona": 1,
            "elder_profile": 1,
            "family_profiles": 1,
            "memories": 1,
        },
    }
    assert db.load_persona()["role_label"] == "儿子小明"
    assert db.load_elder()["full_name"] == "宋桂兰"
    assert db.load_all_family_profiles()[0]["name"] == "小明"
    assert db.load_all_memories()[0]["content"] == "去年中秋小明陪妈妈在院子里赏月。"
```

- [ ] **Step 2: Run the focused test**

Run:

```powershell
python -m pytest tests/test_api_integration.py::test_fastapi_import_endpoint_saves_payload -q --basetemp .pytest_tmp_import_route
```

Expected: fail if the route or persistence path is missing; pass if the existing implementation already satisfies the contract.

- [ ] **Step 3: Implement or adjust the API**

If the test fails because `/api/import` is missing, wire `ImportRequest`, `ImportResponse`, and `handle_import` into `api/main.py`. If it fails because data is not persisted, update `api/handlers.py` to call `db.init_db()` and save non-empty `persona`, `elder_profile`, `family_profiles`, and `memories`.

- [ ] **Step 4: Re-run the focused test**

Run:

```powershell
python -m pytest tests/test_api_integration.py::test_fastapi_import_endpoint_saves_payload -q --basetemp .pytest_tmp_import_route
```

Expected: `1 passed`.

### Task 2: Frontend Save Path Verification

**Files:**
- Verify: `web/src/lib/backend-api.ts`
- Verify: `web/src/app/records/page.tsx`
- Test: `tests/test_productization_foundation.py`

- [ ] **Step 1: Confirm frontend helper contract**

Ensure `importParsedData` posts to `/api/import`, returns imported counts, and `records/page.tsx` uses it from the “一键保存” action.

- [ ] **Step 2: Run productization foundation tests**

Run:

```powershell
python -m pytest tests/test_productization_foundation.py -q --basetemp .pytest_tmp_productization
```

Expected: all productization contract tests pass.

### Task 3: End-to-End Local Verification

**Files:**
- Verify: running API at `http://127.0.0.1:8000`
- Verify: Next.js frontend at `http://127.0.0.1:3000`

- [ ] **Step 1: Confirm running API exposes the import route**

Run:

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/openapi.json | Select-String '"/api/import"'
```

Expected: output contains `"/api/import"`.

- [ ] **Step 2: Smoke test the live import endpoint**

Run:

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/api/import -Method POST -ContentType 'application/json' -Body '{"family_id":"local","memories":[{"content":"接口烟测记忆"}]}'
```

Expected: response JSON includes `"ok":true` and `"memories":1`.

- [ ] **Step 3: Run full regression checks**

Run:

```powershell
python -m pytest tests/ -q --basetemp .pytest_tmp_import_full
cd web
pnmp run typecheck
```

If `pnmp` is unavailable in the local shell, use the existing project fallback:

```powershell
npm run typecheck
```

Expected: pytest passes and TypeScript typecheck exits 0.
