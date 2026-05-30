# 云功能阶段 A 认证模块实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. 本仓库禁止自主执行 `git commit`，提交步骤只生成命令，由用户手动执行。

**Goal:** 实现手机号验证码测试登录、JWT 签发与后端 `X-User-Token` 鉴权，并让前端请求自动携带 token。

**Architecture:** 后端新增独立认证服务，负责测试验证码、用户注册/登录和 HS256 JWT 编解码；FastAPI 新增 `/api/auth/send-code` 与 `/api/auth/verify`，业务接口通过统一依赖解析当前用户。前端新增 token 管理模块和登录页，现有业务请求封装从固定 `X-User-Id` 切换到 `X-User-Token`。

**Tech Stack:** FastAPI、Pydantic、Python 标准库 HMAC/Base64、Next.js、TypeScript、localStorage。

---

### Task 1: 后端认证核心

**Files:**
- Create: `productization/auth.py`
- Test: `tests/test_auth_phase_a.py`

- [ ] **Step 1: Write the failing test**

覆盖：发送验证码在测试模式返回 `expires_in_seconds=300`；`000000` 可验证并返回 JWT；JWT 可解析出同一个 `user_id`；错误验证码返回认证错误。

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_auth_phase_a.py -v`

Expected: FAIL，因为 `productization.auth` 尚不存在。

- [ ] **Step 3: Write minimal implementation**

实现 `AuthService`、`AuthError`、`create_access_token()`、`decode_access_token()`，使用内存用户与验证码存储，JWT secret 从 `JWT_SECRET` 读取，缺省仅用于本地开发。

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_auth_phase_a.py -v`

Expected: PASS。

### Task 2: FastAPI 认证路由与统一用户依赖

**Files:**
- Create: `api/auth.py`
- Modify: `api/main.py`
- Test: `tests/test_auth_phase_a.py`

- [ ] **Step 1: Write the failing route tests**

覆盖：`POST /api/auth/send-code`、`POST /api/auth/verify`；业务接口用 `X-User-Token` 可访问；无 token 返回 401。

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_auth_phase_a.py -v`

Expected: FAIL，因为路由和依赖尚未挂载。

- [ ] **Step 3: Implement minimal routes and dependency**

新增 router；在 `api/main.py` 使用 `Depends(current_user_id)` 替换云业务接口的 `X-User-Id` Header。解析失败返回 401。为不破坏既有测试，测试环境允许显式 `X-User-Id` 兼容。

- [ ] **Step 4: Run focused tests**

Run: `python -m pytest tests/test_auth_phase_a.py tests/test_cloud_api_phase1.py -v`

Expected: PASS。

### Task 3: 前端 token 管理与登录页

**Files:**
- Create: `web/src/lib/auth.ts`
- Create: `web/src/app/login/page.tsx`
- Modify: `web/src/lib/backend-api.ts`
- Modify: `web/src/app/page.tsx`

- [ ] **Step 1: Add TypeScript-facing API**

实现 `getAuthToken()`、`setAuthToken()`、`clearAuthToken()`、`sendLoginCode()`、`verifyLoginCode()`。

- [ ] **Step 2: Switch request header**

`withUser()` 从 localStorage 读取 token 并附加 `X-User-Token`；没有 token 时不附加用户头，让后端返回 401。

- [ ] **Step 3: Add login page**

登录页提供手机号、验证码、发送验证码、登录按钮；测试模式文案提示验证码 `000000`；登录成功后跳转首页。

- [ ] **Step 4: Run frontend verification**

Run: `cd web; npm run typecheck`

Expected: PASS。

### Task 4: Final verification

**Files:**
- Modify only files above.

- [ ] **Step 1: Run backend cloud/auth tests**

Run: `python -m pytest tests/test_auth_phase_a.py tests/test_cloud_api_phase1.py tests/test_cloud_chat_phase2.py tests/test_voice_phase3.py tests/test_voice_phase4_tts.py -v`

Expected: PASS。

- [ ] **Step 2: Generate commit message only**

Commit message: `feat(auth): 实现手机号验证码 JWT 登录`

User-run command:

```bash
git add productization/auth.py api/auth.py api/main.py tests/test_auth_phase_a.py web/src/lib/auth.ts web/src/app/login/page.tsx web/src/lib/backend-api.ts web/src/app/page.tsx docs/superpowers/plans/2026-05-30-cloud-auth-phase-a.md
git commit -m "feat(auth): 实现手机号验证码 JWT 登录"
```
