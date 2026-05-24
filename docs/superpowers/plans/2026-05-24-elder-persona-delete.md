# 老人画像 & AI 角色删除功能 + 保存逻辑修复 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复新老人画像被错误合并的 bug，为已保存区的老人画像和 AI 角色添加删除按钮。

**Architecture:** 后端按 `full_name` 匹配老人画像（同名合并，异名新增），新增两条 DELETE 路由；前端复用 `SavedProfileList` 已有的 `onDelete` prop 机制。

**Tech Stack:** Python/FastAPI + SQLite, Next.js/TypeScript

---

### Task 1: 修复 `_save_elder_payload` 按名匹配合并

**Files:**
- Modify: `api/handlers.py:171-177`

- [ ] **Step 1: 改成按 `full_name` 查找已有画像再合并**

```python
def _save_elder_payload(elder_payload: dict, *, merge_into_existing: bool) -> bool:
    if not elder_payload or not _has_importable_value(elder_payload):
        return False
    elder_profile = dict(elder_payload)
    existing = None
    if merge_into_existing:
        all_elders = {e.get("full_name"): e for e in db.load_all_elders()}
        existing = all_elders.get(elder_profile.get("full_name"))
    db.save_elder(_merge_elder(existing, elder_profile) if existing else elder_profile)
    return True
```

> 原逻辑：`db.load_elder()` 永远返回第一条记录，不同名字的新老人会被错误合并到第一个已有画像。
> 新逻辑：用 `load_all_elders()` 按 `full_name` 查找。同名 → 合并；异名 → 新增独立条目。

- [ ] **Step 2: 确认 `load_all_elders` 已在 handlers.py 中可用**

`handlers.py` 通过 `from engine import db` 使用，`db.load_all_elders()` 已在 `db.py:303` 定义。无需额外导入。

- [ ] **Step 3: Commit**

```bash
git add api/handlers.py
git commit -m "fix(import): 按 full_name 匹配合并老人画像，避免异名画像被错误合并"
```

---

### Task 2: DB 层 `delete_elder` 增加 `full_name` 参数

**Files:**
- Modify: `engine/db.py:325-329`

- [ ] **Step 1: 添加 WHERE 条件**

```python
def delete_elder(full_name: str) -> None:
    conn = _connect()
    conn.execute("DELETE FROM elder_profile WHERE full_name = ?", (full_name,))
    conn.commit()
    conn.close()
```

- [ ] **Step 2: Commit**

```bash
git add engine/db.py
git commit -m "fix(db): delete_elder 增加 full_name 参数，按名删除单条画像"
```

---

### Task 3: 新增后端删除 handler

**Files:**
- Modify: `api/handlers.py` (追加到文件末尾)

- [ ] **Step 1: 添加 `handle_delete_elder` 和 `handle_delete_persona`**

在 `handle_delete_family_profile` 之后追加：

```python
def handle_delete_elder(full_name: str) -> DeleteResponse:
    db.init_db()
    db.delete_elder(full_name)
    return DeleteResponse(ok=True)


def handle_delete_persona(role_label: str) -> DeleteResponse:
    db.init_db()
    db.delete_persona(role_label)
    return DeleteResponse(ok=True)
```

- [ ] **Step 2: Commit**

```bash
git add api/handlers.py
git commit -m "feat(api): 新增删除老人画像和 AI 角色的 handler"
```

---

### Task 4: 新增 DELETE 路由

**Files:**
- Modify: `api/main.py` (追加到 `delete_family_profile_endpoint` 之后)
- Modify: `api/main.py:7-14` (更新 import)

- [ ] **Step 1: 更新 import**

将第 7-14 行的 import 改为：

```python
from .handlers import (
    handle_chat,
    handle_delete_elder,
    handle_delete_family_profile,
    handle_delete_memory,
    handle_delete_persona,
    handle_import,
    handle_parse,
    handle_records,
)
```

- [ ] **Step 2: 新增两条路由**

在 `delete_family_profile_endpoint` 之后追加：

```python
@app.delete("/api/elders/{full_name}", response_model=DeleteResponse)
def delete_elder_endpoint(full_name: str) -> DeleteResponse:
    return handle_delete_elder(full_name)


@app.delete("/api/personas/{role_label}", response_model=DeleteResponse)
def delete_persona_endpoint(role_label: str) -> DeleteResponse:
    return handle_delete_persona(role_label)
```

- [ ] **Step 3: Commit**

```bash
git add api/main.py
git commit -m "feat(api): 新增 DELETE /api/elders/{full_name} 和 /api/personas/{role_label} 路由"
```

---

### Task 5: 前端 API 层新增删除函数

**Files:**
- Modify: `web/src/lib/backend-api.ts` (在 `deleteFamilyProfile` 之后追加)

- [ ] **Step 1: 添加 `deleteElderProfile` 和 `deletePersona`**

在 `deleteFamilyProfile` 函数之后追加：

```typescript
export function deleteElderProfile(fullName: string): Promise<{ ok: boolean }> {
  return requestJson<{ ok: boolean }>(`/api/elders/${encodeURIComponent(fullName)}`, {
    method: "DELETE",
  });
}

export function deletePersona(roleLabel: string): Promise<{ ok: boolean }> {
  return requestJson<{ ok: boolean }>(`/api/personas/${encodeURIComponent(roleLabel)}`, {
    method: "DELETE",
  });
}
```

- [ ] **Step 2: Commit**

```bash
git add web/src/lib/backend-api.ts
git commit -m "feat(web): 前端 API 层新增删除老人画像和角色的函数"
```

---

### Task 6: 页面层接入删除功能

**Files:**
- Modify: `web/src/app/records/page.tsx:1-15` (更新 import)
- Modify: `web/src/app/records/page.tsx:328-350` (新增删除函数)
- Modify: `web/src/app/records/page.tsx:482-505` (传入 onDelete)

- [ ] **Step 1: 更新 import（第 6-14 行）**

```typescript
import {
  DraftObject,
  ParsedDraft,
  deleteElderProfile as deleteSavedElderProfile,
  deleteFamilyProfile as deleteSavedFamilyProfile,
  deleteMemory as deleteSavedMemory,
  deletePersona as deleteSavedPersona,
  fetchRecords,
  importParsedData,
  parseProfileText,
} from "../../lib/backend-api";
```

- [ ] **Step 2: 添加删除回调函数（在 `deleteMemory` 函数之后）**

```typescript
  async function deleteElderProfile(index: number) {
    const profile = savedDraft.elder_profiles?.[index];
    const fullName = valueToText(profile?.full_name).trim();
    if (!fullName) {
      setRecordsError("这条老人画像缺少姓名，暂时无法删除。");
      return;
    }

    setRecordsError("");
    setRecordsSuccess("");

    try {
      await deleteSavedElderProfile(fullName);
      setSavedDraft((current) => ({
        ...current,
        elder_profiles: (current.elder_profiles ?? []).filter((_, itemIndex) => itemIndex !== index),
      }));
      setExpandedElderIndex(null);
      setRecordsSuccess("已删除老人画像。");
    } catch {
      setRecordsError("删除老人画像失败，请稍后重试。");
    }
  }

  async function deletePersona(index: number) {
    const persona = savedDraft.personas?.[index];
    const roleLabel = valueToText(persona?.role_label).trim();
    if (!roleLabel) {
      setRecordsError("这条角色缺少角色名，暂时无法删除。");
      return;
    }

    setRecordsError("");
    setRecordsSuccess("");

    try {
      await deleteSavedPersona(roleLabel);
      setSavedDraft((current) => ({
        ...current,
        personas: (current.personas ?? []).filter((_, itemIndex) => itemIndex !== index),
      }));
      setExpandedPersonaIndex(null);
      setRecordsSuccess("已删除 AI 角色。");
    } catch {
      setRecordsError("删除 AI 角色失败，请稍后重试。");
    }
  }
```

- [ ] **Step 3: 传入 `onDelete` 到老人画像 `SavedProfileList`（约第 482 行）**

```tsx
            <SavedProfileList
              title="老人画像"
              items={savedDraft.elder_profiles ?? []}
              fields={elderFields}
              expandedIndex={expandedElderIndex}
              onToggle={(index) =>
                setExpandedElderIndex((current) => (current === index ? null : index))
              }
              onChange={(index, key, value) =>
                updateListItem("saved", "elder_profiles", index, key, value)
              }
              onDelete={deleteElderProfile}
            />
```

- [ ] **Step 4: 传入 `onDelete` 到 AI 角色 `SavedProfileList`（约第 494 行）**

```tsx
            <SavedProfileList
              title="AI 扮演角色"
              items={savedDraft.personas ?? []}
              fields={personaFields}
              expandedIndex={expandedPersonaIndex}
              onToggle={(index) =>
                setExpandedPersonaIndex((current) => (current === index ? null : index))
              }
              onChange={(index, key, value) =>
                updateListItem("saved", "personas", index, key, value)
              }
              onDelete={deletePersona}
            />
```

- [ ] **Step 5: Commit**

```bash
git add web/src/app/records/page.tsx
git commit -m "feat(records): 老人画像和 AI 角色栏添加删除按钮"
```

---

### 验证

```bash
# 后端测试
python -m pytest tests/ -v

# 前端构建检查
cd web && npm run build
```
