# PostgreSQL CloudRepository Phase B Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. 本仓库禁止自主执行 `git commit`，提交步骤只生成命令，由用户手动执行。

**Goal:** 用 `DATABASE_URL` 驱动的 PostgreSQL 持久化仓库替代默认 InMemory 云端仓库。

**Architecture:** 新增 SQL 初始化脚本定义家庭空间、业务资料、声音资料和认证表；新增 `PostgresCloudRepository` 实现现有同步 `CloudRepository` 协议，保持 `api.handlers` 不改。`get_cloud_repository()` 优先使用 `DATABASE_URL`，否则兼容 Supabase，再回退 InMemory。

**Tech Stack:** FastAPI、psycopg 3、PostgreSQL 16、pytest。

---

### Task 1: Schema 与依赖

**Files:**
- Create: `productization/postgres_schema.sql`
- Modify: `requirements.txt`
- Test: `tests/test_postgres_repository_phase_b.py`

- [ ] **Step 1: Write the failing test**

测试读取 `productization/postgres_schema.sql`，断言存在 `users`、`sms_codes`、`families`、`family_memberships`、`elders`、`family_profiles`、`personas`、`memories`、`voice_profiles`、`voice_samples`、`chat_sessions`、`chat_messages` 表，并包含家庭隔离索引。

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_postgres_repository_phase_b.py -v`

Expected: FAIL，因为 SQL 脚本尚不存在。

- [ ] **Step 3: Write schema and dependency**

创建 PostgreSQL 16 schema，使用 `gen_random_uuid()`、`jsonb`、`timestamptz`，新增 `psycopg[binary]` 到 `requirements.txt`。

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_postgres_repository_phase_b.py -v`

Expected: PASS。

### Task 2: Repository 基础行为

**Files:**
- Create: `productization/postgres_repository.py`
- Test: `tests/test_postgres_repository_phase_b.py`

- [ ] **Step 1: Write a failing integration-style test**

测试在设置 `POSTGRES_TEST_DATABASE_URL` 时创建真实 `PostgresCloudRepository`，初始化 schema，验证家庭创建、成员权限、老人档案、家人档案、记忆、persona CRUD 与家庭隔离。未设置该变量时 skip，避免本地没有数据库时阻塞单元测试。

- [ ] **Step 2: Run test to verify it fails with a real DB, skips without DB**

Run: `python -m pytest tests/test_postgres_repository_phase_b.py -v`

Expected without DB: schema test PASS, integration SKIP。Expected with DB before implementation: FAIL because `productization.postgres_repository` missing.

- [ ] **Step 3: Implement repository**

用 `psycopg.rows.dict_row` 返回 dict；写入 list/dict 字段使用 JSONB；所有写操作前调用 `_require_editor()`；所有读操作前调用 `_require_member()`；错误映射到 `FamilyPermissionError` 或 `FamilyNotFoundError`。

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_postgres_repository_phase_b.py tests/test_cloud_repository.py -v`

Expected: PASS/SKIP when no test DB, PASS when `POSTGRES_TEST_DATABASE_URL` points to a PostgreSQL database。

### Task 3: Repository 工厂切换

**Files:**
- Modify: `productization/cloud_repository.py`
- Test: `tests/test_postgres_repository_phase_b.py`

- [ ] **Step 1: Write failing factory test**

设置 `DATABASE_URL=postgresql://example`，monkeypatch `productization.cloud_repository.PostgresCloudRepository`，断言 `get_cloud_repository()` 优先返回 PostgreSQL 仓库。

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_postgres_repository_phase_b.py::test_cloud_repository_factory_prefers_database_url -v`

Expected: FAIL，因为工厂尚未识别 `DATABASE_URL`。

- [ ] **Step 3: Implement factory switch**

在 `get_cloud_repository()` 中优先读取 `DATABASE_URL`；存在则构造 `PostgresCloudRepository(database_url)`。保留 Supabase 和 InMemory 回退。

- [ ] **Step 4: Run focused tests**

Run: `python -m pytest tests/test_postgres_repository_phase_b.py tests/test_cloud_repository.py -v`

Expected: PASS/SKIP。

### Task 4: Final verification

**Files:**
- Modify only files above.

- [ ] **Step 1: Install/update Python deps**

Run: `python -m pip install -r requirements.txt`

Expected: psycopg available.

- [ ] **Step 2: Run backend regression**

Run: `python -m pytest tests/test_postgres_repository_phase_b.py tests/test_cloud_repository.py tests/test_cloud_api_phase1.py tests/test_auth_phase_a.py -v`

Expected: PASS/SKIP if no `POSTGRES_TEST_DATABASE_URL`。

- [ ] **Step 3: Generate commit message only**

Commit message: `feat(cloud): add postgres repository persistence`

User-run command:

```bash
git add productization/postgres_schema.sql productization/postgres_repository.py productization/cloud_repository.py requirements.txt tests/test_postgres_repository_phase_b.py docs/superpowers/plans/2026-05-30-postgres-cloud-repository-phase-b.md
git commit -m "feat(cloud): add postgres repository persistence"
```
