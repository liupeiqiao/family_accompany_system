# 智能合并导入 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 恢复并增强智能合并机制：前端展示合并预览（新建/合并/跳过/冲突），后端新增统一合并保存端点。

**Architecture:** 新增 `POST /api/import/merge` 端点统一处理合并保存逻辑。前端新增 `MergePreview` 组件展示四类合并动作，`saveDraftToCloud` 改为调用新端点。后端重新读取云端数据后执行 create/merge/skip/conflict，返回结构化结果。

**Tech Stack:** Python (FastAPI + Pydantic), TypeScript (Next.js React), PostgreSQL (via cloud_repository)

---

### Task 1: 扩展 dedup 数据结构

**Files:**
- Modify: `llm/parser.py:167-199`
- Modify: `api/handlers.py:85-114`

将 `dedup_check` 的输出标准化为含 `items` 的格式，并在 `handle_parse` 中组装。

- [ ] **Step 1: 改造 `dedup_check` 返回标准化 items**

将 `llm/parser.py` 中 `dedup_check` 函数的返回值改为包含 `items` 数组：

```python
def dedup_check(
    new_parsed: dict,
    existing_personas: list[dict],
    existing_families: list[dict],
) -> dict:
    """去重检查，返回 {items: [{type, action, source_temp_id, target_name, confidence, reason, fields_to_merge, conflict_fields}]}"""
    ep_text = "\n".join(
        f"- {p.get('role_label','')} (关系:{p.get('relation','')}, 称呼:{p.get('appellation','')}, id:{p.get('id','')})"
        for p in existing_personas
    ) if existing_personas else "（无）"

    ef_text = "\n".join(
        f"- {f.get('name','')} (关系:{f.get('relation','')}, 性格:{'、'.join(f.get('personality',[]))}, id:{f.get('id','')})"
        for f in existing_families
    ) if existing_families else "（无）"

    np_text = json.dumps(new_parsed.get("persona", {}), ensure_ascii=False)
    nf_text = json.dumps(new_parsed.get("family_profiles", []), ensure_ascii=False)

    try:
        raw = chat(DEDUP_SYSTEM, DEDUP_USER.format(
            existing_personas=ep_text, existing_families=ef_text,
            new_persona=np_text, new_families=nf_text,
        ), temperature=0.2)
        llm_result = json.loads(raw)
        llm_result.setdefault("family_actions", [])
        llm_result.setdefault("persona_action", "new")
        llm_result.setdefault("persona_match", "")
    except Exception:
        llm_result = {
            "persona_action": "new", "persona_match": "",
            "family_actions": [
                {"new_name": f.get("name",""), "action": "new"}
                for f in new_parsed.get("family_profiles", [])
            ]
        }

    items: list[dict] = []

    # persona item
    persona_action = llm_result.get("persona_action", "new")
    if persona_action in ("merge", "merge_into"):
        persona = new_parsed.get("persona", {})
        target_name = llm_result.get("persona_match", "")
        target = _find_persona_target(target_name, existing_personas)
        items.append({
            "type": "persona",
            "action": persona_action,
            "source_temp_id": _source_id(persona),
            "target_id": target.get("id", "") if target else "",
            "target_name": target_name,
            "confidence": 0.85,
            "reason": f"角色名称匹配：{target_name}",
            "fields_to_merge": _diff_fields(target, persona) if target else list(persona.keys()),
            "conflict_fields": [],
        })

    # family profile items
    for action in llm_result.get("family_actions", []):
        item = {
            "type": "family_profile",
            "action": action.get("action", "new"),
            "source_temp_id": f"temp_{action.get('new_name', '')}",
            "target_id": "",
            "target_name": action.get("target", ""),
            "confidence": 0.85,
            "reason": "",
            "fields_to_merge": [],
            "conflict_fields": [],
        }
        if action.get("action") in ("merge_into", "merge"):
            target = _find_family_target(action.get("target", ""), existing_families)
            item["target_id"] = target.get("id", "") if target else ""
            item["reason"] = f"姓名匹配：{action.get('target', '')}"
            new_family = _find_new_family(action.get("new_name", ""), new_parsed.get("family_profiles", []))
            item["fields_to_merge"] = _diff_fields(target, new_family) if target and new_family else []
        items.append(item)

    return {"items": items}


def _source_id(item: dict) -> str:
    return item.get("role_label") or item.get("name") or item.get("content", "")[:20]


def _find_persona_target(target_name: str, existing: list[dict]) -> dict | None:
    for p in existing:
        if target_name in p.get("role_label", "") or p.get("role_label", "") in target_name:
            return p
    return None


def _find_family_target(target_name: str, existing: list[dict]) -> dict | None:
    for f in existing:
        if target_name in f.get("name", "") or f.get("name", "") in target_name:
            return f
    return None


def _find_new_family(name: str, families: list[dict]) -> dict | None:
    for f in families:
        if name in f.get("name", "") or f.get("name", "") in name:
            return f
    return None


def _diff_fields(existing: dict | None, incoming: dict | None) -> list[str]:
    if not existing or not incoming:
        return list(incoming.keys()) if incoming else []
    fields = []
    for key, val in incoming.items():
        if key in ("id",):
            continue
        existing_val = existing.get(key)
        if isinstance(val, list) and isinstance(existing_val, list):
            new_items = [v for v in val if v not in existing_val]
            if new_items:
                fields.append(key)
        elif isinstance(val, str) and val and not existing_val:
            fields.append(key)
    return fields
```

- [ ] **Step 2: 更新 `handle_parse` 中的 dedup 组装逻辑**

将 `api/handlers.py:97-114` 中的 dedup 处理改为传递已有数据中带 id 的信息，并添加 memory actions：

```python
def handle_parse(request: ParseRequest) -> ParseResponse:
    db.init_db()
    existing_personas = db.load_all_personas()
    existing_families = db.load_all_family_profiles()
    existing_memories = db.load_all_memories()

    parsed = parse_user_text(
        request.text,
        perspective=request.perspective,
        existing_families_text=_build_existing_families_text(existing_families),
    )
    parsed = _normalize_parsed(parsed)
    dedup = (
        dedup_check(parsed, existing_personas, existing_families)
        if existing_personas or existing_families
        else {"items": []}
    )
    memory_actions = _build_memory_dedup_items(parsed.get("memories", []), existing_memories)
    if memory_actions:
        dedup["items"].extend(memory_actions)

    return ParseResponse(
        persona=parsed.get("persona", {}),
        memories=parsed.get("memories", []),
        family_profiles=parsed.get("family_profiles", []),
        elder_profile=parsed.get("elder_profile", {}),
        dedup=dedup,
        merge_preview=_build_merge_preview(parsed, existing_families, existing_personas),
    )
```

- [ ] **Step 3: 新增 `_build_memory_dedup_items` 辅助函数**

在 `api/handlers.py` 中添加（替换旧的 `_build_memory_actions`）：

```python
def _build_memory_dedup_items(new_memories: list[dict], existing_memories: list[dict]) -> list[dict]:
    if not new_memories or not existing_memories:
        return []

    existing_by_content = {
        _normalize_memory_content(memory.get("content", "")): memory
        for memory in existing_memories
        if memory.get("content")
    }
    items = []
    for memory in new_memories:
        content = memory.get("content", "") if memory else ""
        normalized = _normalize_memory_content(content)
        if not normalized:
            continue
        existing = existing_by_content.get(normalized)
        if existing:
            items.append({
                "type": "memory",
                "action": "skip",
                "source_temp_id": _source_id(memory),
                "target_id": existing.get("id", ""),
                "target_name": content[:40],
                "confidence": 0.95,
                "reason": "相似记忆已存在",
                "fields_to_merge": [],
                "conflict_fields": [],
            })
    return items
```

- [ ] **Step 4: 同步更新旧 `dedup_check` 兼容性**

保持旧返回值的兼容性（`persona_action`、`persona_match`、`family_actions` 仍可通过 items 推导），确保 `handle_import`（本地 SQLite 导入）不报错。检查 `_family_actions_by_name`、`_memory_actions_by_content` 等旧辅助函数是否需要适配。

- [ ] **Step 5: 验证**

Run: `python -m pytest tests/ -v -k "parse or import"`
Expected: 现有 parse/import 相关测试通过

- [ ] **Step 6: Commit**

```bash
git add llm/parser.py api/handlers.py
git commit -m "feat(parser): 标准化 dedup 输出为 items 数组结构"
```

---

### Task 2: 新增后端统一合并保存端点

**Files:**
- Modify: `api/schemas.py` — 新增 request/response 模型
- Modify: `api/main.py` — 新增路由
- Modify: `api/handlers.py` — 新增 `handle_merge_import` 处理函数

- [ ] **Step 1: 新增 schemas**

在 `api/schemas.py` 末尾添加：

```python
class MergeImportItem(BaseModel):
    type: str = ""                 # family_profile | memory | persona | elder_profile
    action: str = "create"         # create | merge | merge_into | skip | conflict
    source_temp_id: str = ""
    target_id: str = ""
    target_name: str = ""
    confidence: float = 0.0
    reason: str = ""
    fields_to_merge: list[str] = Field(default_factory=list)
    conflict_fields: list[str] = Field(default_factory=list)


class MergeImportRequest(BaseModel):
    family_id: str
    draft: dict = Field(default_factory=dict)
    dedup: dict = Field(default_factory=dict)


class MergeImportResultItem(BaseModel):
    type: str = ""
    name: str = ""
    id: str = ""
    action: str = ""               # created | merged | skipped | conflict
    fields: list[str] = Field(default_factory=list)
    reason: str = ""


class MergeImportResponse(BaseModel):
    created: list[MergeImportResultItem] = Field(default_factory=list)
    merged: list[MergeImportResultItem] = Field(default_factory=list)
    skipped: list[MergeImportResultItem] = Field(default_factory=list)
    conflicts: list[MergeImportResultItem] = Field(default_factory=list)
```

- [ ] **Step 2: 新增路由**

在 `api/main.py` 中添加：

```python
@app.post("/api/import/merge", response_model=MergeImportResponse)
def merge_import_endpoint(
    request: MergeImportRequest,
    x_user_id: str = Depends(current_user_id),
) -> MergeImportResponse:
    return handle_merge_import(request, x_user_id)
```

记得在文件顶部 import 中添加：
```python
from .schemas import (
    # ... existing imports ...
    MergeImportRequest,
    MergeImportResponse,
)
from .handlers import (
    # ... existing imports ...
    handle_merge_import,
)
```

- [ ] **Step 3: 实现 `handle_merge_import` 核心逻辑**

在 `api/handlers.py` 中添加完整的合并保存处理函数：

```python
def handle_merge_import(request, user_id: str):
    """统一合并保存：重新读取云端数据 → 校验 dedup → 执行 create/merge/skip/conflict → 返回结果"""
    family_id = request.family_id
    repo = get_cloud_repository()
    dedup_items = request.dedup.get("items", []) if request.dedup else []
    draft = request.draft or {}

    # 重新读取云端已有数据
    existing_personas = _call_cloud(lambda: repo.list_personas(family_id=family_id, user_id=user_id))
    existing_families = _call_cloud(lambda: repo.list_family_profiles(family_id=family_id, user_id=user_id))
    existing_memories = _call_cloud(lambda: repo.list_memories(family_id=family_id, user_id=user_id))
    existing_elder = _call_cloud(lambda: repo.get_elder_current(family_id=family_id, user_id=user_id))

    # 构建索引
    persona_by_id = {str(p.get("id", "")): p for p in existing_personas if p.get("id")}
    persona_by_label = {str(p.get("role_label", "")): p for p in existing_personas}
    family_by_id = {str(f.get("id", "")): f for f in existing_families if f.get("id")}
    family_by_name = {str(f.get("name", "")): f for f in existing_families}
    memory_by_content = {
        _normalize_memory_content(m.get("content", "")): m
        for m in existing_memories if m.get("content")
    }

    created: list[dict] = []
    merged: list[dict] = []
    skipped: list[dict] = []
    conflicts: list[dict] = []

    # 构建 dedup 索引
    dedup_by_type_source: dict[str, dict] = {}
    for item in dedup_items:
        key = f"{item.get('type','')}:{item.get('source_temp_id','')}"
        dedup_by_type_source[key] = item

    # ---- 处理 persona ----
    persona_payloads = draft.get("personas") or ([draft.get("persona")] if draft.get("persona") else [])
    for persona in persona_payloads:
        if not _has_importable_value(persona):
            continue
        source_id = _source_id(persona)
        dedup_item = dedup_by_type_source.get(f"persona:{source_id}")
        action = dedup_item.get("action", "create") if dedup_item else "create"

        if action == "skip":
            skipped.append({"type": "persona", "name": str(persona.get("role_label", "")), "reason": "dedup 建议跳过"})
            continue

        if action in ("merge", "merge_into") and dedup_item:
            target_id = dedup_item.get("target_id", "")
            target = persona_by_id.get(target_id)
            if target is None:
                # target_id 失效，降级为 create
                created_item = _call_cloud(lambda: repo.create_persona(family_id=family_id, user_id=user_id, payload=dict(persona)))
                created.append({"type": "persona", "name": str(created_item.get("role_label", "")), "id": str(created_item.get("id", ""))})
                continue
            merged_persona = _merge_persona(target, persona)
            updated = _call_cloud(lambda: repo.update_persona(family_id=family_id, user_id=user_id, persona_id=target_id, payload=merged_persona))
            merged.append({
                "type": "persona", "name": str(updated.get("role_label", "")),
                "id": str(updated.get("id", "")),
                "fields": dedup_item.get("fields_to_merge", []),
            })
        else:
            created_item = _call_cloud(lambda: repo.create_persona(family_id=family_id, user_id=user_id, payload=dict(persona)))
            created.append({"type": "persona", "name": str(created_item.get("role_label", "")), "id": str(created_item.get("id", ""))})

    # ---- 处理 family_profiles ----
    for profile in draft.get("family_profiles", []):
        if not _has_importable_value(profile):
            continue
        source_id = _source_id(profile)
        dedup_item = dedup_by_type_source.get(f"family_profile:{source_id}")
        action = dedup_item.get("action", "create") if dedup_item else "create"

        if action == "skip":
            skipped.append({"type": "family_profile", "name": str(profile.get("name", "")), "reason": "dedup 建议跳过"})
            continue

        if action in ("merge", "merge_into") and dedup_item:
            target_id = dedup_item.get("target_id", "")
            target = family_by_id.get(target_id)
            if target is None:
                target = family_by_name.get(dedup_item.get("target_name", ""))
            if target is None:
                created_item = _call_cloud(lambda: repo.create_family_profile(family_id=family_id, user_id=user_id, payload=dict(profile)))
                created.append({"type": "family_profile", "name": str(created_item.get("name", "")), "id": str(created_item.get("id", ""))})
                continue
            merged_profile, profile_conflicts = _merge_family_profile_with_conflicts(target, profile)
            if profile_conflicts:
                conflicts.append({
                    "type": "family_profile", "name": str(profile.get("name", "")),
                    "id": str(target.get("id", "")), "fields": profile_conflicts,
                    "reason": "字段冲突，保留已有值",
                })
            updated = _call_cloud(lambda: repo.update_family_profile(family_id=family_id, user_id=user_id, profile_id=str(target.get("id", "")), payload=merged_profile))
            merged.append({
                "type": "family_profile", "name": str(updated.get("name", "")),
                "id": str(updated.get("id", "")),
                "fields": dedup_item.get("fields_to_merge", []),
            })
        else:
            created_item = _call_cloud(lambda: repo.create_family_profile(family_id=family_id, user_id=user_id, payload=dict(profile)))
            created.append({"type": "family_profile", "name": str(created_item.get("name", "")), "id": str(created_item.get("id", ""))})

    # ---- 处理 memories ----
    for memory in draft.get("memories", []):
        content = str(memory.get("content", "")).strip()
        if not content:
            continue
        normalized = _normalize_memory_content(content)
        existing = memory_by_content.get(normalized)
        if existing:
            skipped.append({"type": "memory", "name": content[:40], "id": str(existing.get("id", "")), "reason": "相似记忆已存在"})
            continue
        created_mem = _call_cloud(lambda: repo.create_memory(family_id=family_id, user_id=user_id, payload=dict(memory)))
        created.append({"type": "memory", "name": content[:40], "id": str(created_mem.get("id", ""))})

    # ---- 处理 elder_profile ----
    elder_payloads = draft.get("elder_profiles") or ([draft.get("elder_profile")] if draft.get("elder_profile") else [])
    for elder in elder_payloads:
        if not _has_importable_value(elder):
            continue
        if existing_elder and existing_elder.get("id"):
            merged_elder, elder_conflicts = _merge_elder_with_conflicts(existing_elder, elder)
            if elder_conflicts:
                conflicts.append({
                    "type": "elder_profile", "name": str(elder.get("full_name", "")),
                    "fields": elder_conflicts, "reason": "字段冲突，保留已有值",
                })
            updated = _call_cloud(lambda: repo.upsert_elder_current(family_id=family_id, user_id=user_id, payload=merged_elder))
            merged.append({"type": "elder_profile", "name": str(updated.get("full_name", "")), "id": str(updated.get("id", ""))})
        else:
            updated = _call_cloud(lambda: repo.upsert_elder_current(family_id=family_id, user_id=user_id, payload=dict(elder)))
            created.append({"type": "elder_profile", "name": str(updated.get("full_name", "")), "id": str(updated.get("id", ""))})

    return MergeImportResponse(created=created, merged=merged, skipped=skipped, conflicts=conflicts)
```

- [ ] **Step 4: 新增带冲突检测的合并辅助函数**

在 `api/handlers.py` 中添加：

```python

CORE_IDENTITY_FIELDS = {"name", "relation", "nickname", "phone", "identity", "gender", "full_name", "role_label", "appellation"}

def _merge_family_profile_with_conflicts(existing: dict, incoming: dict) -> tuple[dict, list[str]]:
    """合并家人档案，返回 (merged_dict, conflict_fields)。核心身份字段冲突时不覆盖。"""
    merged = dict(existing)
    conflict_fields: list[str] = []

    for field in ("name", "relation", "gender", "nickname", "phone", "identity"):
        existing_val = str(existing.get(field, "")).strip()
        incoming_val = str(incoming.get(field, "")).strip()
        if not existing_val and incoming_val:
            merged[field] = incoming_val
        elif existing_val and incoming_val and existing_val != incoming_val:
            if field in CORE_IDENTITY_FIELDS:
                conflict_fields.append(field)
            else:
                merged[field] = incoming_val

    for field in FAMILY_LIST_FIELDS:
        merged[field] = _merge_list(existing.get(field, []), incoming.get(field, []))

    merged["notes"] = _merge_notes(existing.get("notes", ""), incoming.get("notes", ""))
    return merged, conflict_fields


def _merge_elder_with_conflicts(existing: dict, incoming: dict) -> tuple[dict, list[str]]:
    """合并老人画像，返回 (merged_dict, conflict_fields)"""
    merged = dict(existing)
    conflict_fields: list[str] = []

    for field in ("full_name", "gender"):
        existing_val = str(existing.get(field, "")).strip()
        incoming_val = str(incoming.get(field, "")).strip()
        if not existing_val and incoming_val:
            merged[field] = incoming_val
        elif existing_val and incoming_val and existing_val != incoming_val:
            conflict_fields.append(field)

    for field in ELDER_LIST_FIELDS:
        merged[field] = _merge_list(existing.get(field, []), incoming.get(field, []))

    merged["notes"] = _merge_notes(existing.get("notes", ""), incoming.get("notes", ""))
    return merged, conflict_fields
```

- [ ] **Step 5: 注册 import**

在 `api/main.py` 的 import 块中加入新 schema 和 handler：

```python
from .schemas import (
    # ... existing ...
    MergeImportRequest,
    MergeImportResponse,
)
from .handlers import (
    # ... existing ...
    handle_merge_import,
)
```

- [ ] **Step 6: 验证**

Run: `python -c "from api.main import app; print('Routes:', [r.path for r in app.routes])"`
Expected: `/api/import/merge` 出现在路由列表中

- [ ] **Step 7: Commit**

```bash
git add api/schemas.py api/main.py api/handlers.py
git commit -m "feat(api): 新增 POST /api/import/merge 统一合并保存端点"
```

---

### Task 3: 前端 API 层新增类型和请求函数

**Files:**
- Modify: `web/src/lib/backend-api.ts`

- [ ] **Step 1: 更新 `DedupSuggestion` 类型，新增响应类型**

将 `web/src/lib/backend-api.ts` 中第 8 行的 `DedupSuggestion` 类型替换为：

```typescript
export type DedupItem = {
  type: "family_profile" | "memory" | "persona" | "elder_profile";
  action: "create" | "merge" | "merge_into" | "skip" | "conflict";
  source_temp_id: string;
  target_id: string;
  target_name: string;
  confidence: number;
  reason: string;
  fields_to_merge: string[];
  conflict_fields: string[];
};

export type DedupSuggestion = {
  items: DedupItem[];
  // 向后兼容旧字段
  persona_action?: "skip" | "merge" | "new" | "";
  persona_match?: string;
  family_actions?: {
    new_name: string;
    action: "skip" | "merge_into" | "new";
    target?: string;
  }[];
  memory_actions?: {
    new_content: string;
    action: "skip" | "new";
    target?: string;
  }[];
};
```

- [ ] **Step 2: 新增 `MergeImportResponse` 类型和 `MergeImportResultItem` 类型**

```typescript
export type MergeImportResultItem = {
  type: string;
  name: string;
  id: string;
  action?: string;
  fields?: string[];
  reason?: string;
};

export type MergeImportResponse = {
  created: MergeImportResultItem[];
  merged: MergeImportResultItem[];
  skipped: MergeImportResultItem[];
  conflicts: MergeImportResultItem[];
};
```

- [ ] **Step 3: 新增 `mergeImportParsedData` 函数**

```typescript
export function mergeImportParsedData(payload: {
  family_id: string;
  draft: ParsedDraft;
  dedup: DedupSuggestion;
}): Promise<MergeImportResponse> {
  return requestJson<MergeImportResponse>(
    "/api/import/merge",
    withUser({
      method: "POST",
      body: JSON.stringify(payload),
    }),
  );
}
```

- [ ] **Step 4: 验证**

Run: `cd web && npx tsc --noEmit`
Expected: 类型检查通过，无新增错误

- [ ] **Step 5: Commit**

```bash
git add web/src/lib/backend-api.ts
git commit -m "feat(api-client): 新增 MergeImport 请求类型和客户端函数"
```

---

### Task 4: 前端 records 页面新增 MergePreview 组件

**Files:**
- Modify: `web/src/app/records/page.tsx`

- [ ] **Step 1: 更新 import，引入新类型**

在 `web/src/app/records/page.tsx` 顶部 import 中添加：

```typescript
import {
  // ... existing imports ...
  mergeImportParsedData,
  type MergeImportResponse,
  type MergeImportResultItem,
} from "../../lib/backend-api";
```

- [ ] **Step 2: 添加 `mergeResult` 状态和结果摘要展示逻辑**

在组件 state 声明区域（第 274-288 行附近）添加：

```typescript
const [mergeResult, setMergeResult] = useState<MergeImportResponse | null>(null);
```

在 JSX return 中，在保存按钮后面（第 639 行 error/success 提示之后）添加结果摘要展示：

```tsx
{mergeResult ? (
  <section className="recordsMergeResult">
    <h3>保存结果</h3>
    {mergeResult.created.length > 0 ? (
      <div className="mergeResultGroup">
        <span className="mergeTag created">新建 {mergeResult.created.length} 条</span>
        <ul>
          {mergeResult.created.map((item, i) => (
            <li key={`created-${i}`}>{labelForType(item.type)}：{item.name}</li>
          ))}
        </ul>
      </div>
    ) : null}
    {mergeResult.merged.length > 0 ? (
      <div className="mergeResultGroup">
        <span className="mergeTag merged">合并 {mergeResult.merged.length} 条</span>
        <ul>
          {mergeResult.merged.map((item, i) => (
            <li key={`merged-${i}`)}>{labelForType(item.type)}：{item.name}{item.fields?.length ? `（补充：${item.fields.join("、")}）` : ""}</li>
          ))}
        </ul>
      </div>
    ) : null}
    {mergeResult.skipped.length > 0 ? (
      <div className="mergeResultGroup">
        <span className="mergeTag skipped">跳过 {mergeResult.skipped.length} 条</span>
        <ul>
          {mergeResult.skipped.map((item, i) => (
            <li key={`skipped-${i}`)}>{labelForType(item.type)}：{item.name} — {item.reason}</li>
          ))}
        </ul>
      </div>
    ) : null}
    {mergeResult.conflicts.length > 0 ? (
      <div className="mergeResultGroup">
        <span className="mergeTag conflicts">冲突 {mergeResult.conflicts.length} 条</span>
        <ul>
          {mergeResult.conflicts.map((item, i) => (
            <li key={`conflict-${i}`)}>{labelForType(item.type)}：{item.name} — 字段 {item.fields?.join("、")} 与已有数据不一致，已保留原值</li>
          ))}
        </ul>
      </div>
    ) : null}
  </section>
) : null}
```

- [ ] **Step 3: 添加 `labelForType` 辅助函数**

```typescript
function labelForType(type: string): string {
  switch (type) {
    case "persona": return "AI 角色";
    case "elder_profile": return "老人画像";
    case "family_profile": return "家人档案";
    case "memory": return "家庭记忆";
    default: return type;
  }
}
```

- [ ] **Step 4: 新增 `MergePreview` 组件**

在 `EditableList` 组件定义之前（约第 838 行）添加：

```tsx
function MergePreview({ dedup, draft }: { dedup: DedupSuggestion; draft: ParsedDraft }) {
  const items = dedup?.items ?? [];
  if (items.length === 0) return null;

  const grouped = {
    create: items.filter((item) => item.action === "create"),
    merge: items.filter((item) => item.action === "merge" || item.action === "merge_into"),
    skip: items.filter((item) => item.action === "skip"),
    conflict: items.filter((item) => item.action === "conflict"),
  };

  const hasAny = Object.values(grouped).some((g) => g.length > 0);
  if (!hasAny) return null;

  return (
    <section className="mergePreview">
      <h3>智能合并预览</h3>

      {grouped.create.length > 0 ? (
        <div className="mergeGroup">
          <span className="mergeGroupLabel create">将新建</span>
          <ul>
            {grouped.create.map((item, i) => (
              <li key={`create-${i}`}>
                将新建{typeLabel(item.type)}：<strong>{item.target_name || item.source_temp_id}</strong>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {grouped.merge.length > 0 ? (
        <div className="mergeGroup">
          <span className="mergeGroupLabel merge">将合并</span>
          <ul>
            {grouped.merge.map((item, i) => (
              <li key={`merge-${i}`}>
                检测到「{item.source_temp_id}」可能是已有{typeLabel(item.type)}，将合并到
                <strong>「{item.target_name}」</strong>
                {item.fields_to_merge.length > 0 ? (
                  <span className="mergeFields">（补充：{item.fields_to_merge.join("、")}）</span>
                ) : null}
                {item.reason ? <span className="mergeReason"> — {item.reason}</span> : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {grouped.skip.length > 0 ? (
        <div className="mergeGroup">
          <span className="mergeGroupLabel skip">将跳过</span>
          <ul>
            {grouped.skip.map((item, i) => (
              <li key={`skip-${i}`}>
                已存在相似{typeLabel(item.type)}，跳过：<strong>{item.target_name}</strong>
                {item.reason ? <span className="mergeReason"> — {item.reason}</span> : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {grouped.conflict.length > 0 ? (
        <div className="mergeGroup">
          <span className="mergeGroupLabel conflict">需确认</span>
          <ul>
            {grouped.conflict.map((item, i) => (
              <li key={`conflict-${i}`}>
                <strong>{item.target_name}</strong> 的字段
                「{item.conflict_fields.join("、")}」与已有资料不一致，需确认
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}

function typeLabel(type: string): string {
  switch (type) {
    case "persona": return "AI 角色";
    case "family_profile": return "家人档案";
    case "memory": return "家庭记忆";
    case "elder_profile": return "老人画像";
    default: return type;
  }
}
```

- [ ] **Step 5: 在解析预览区渲染 `MergePreview`**

在 JSX 的 `recordsDraftPreview` section 中（第 647 行附近），在 `<h3>解析预览</h3>` 之后、`EditableObject` 之前插入：

```tsx
{hasDraft(draft) ? (
  <section className="recordsDraftPreview">
    <h3>解析预览</h3>
    <MergePreview dedup={draft.dedup ?? { items: [] }} draft={draft} />
    <EditableObject title="老人画像" ... />
    ...
  </section>
) : (
```

- [ ] **Step 6: 改造 `saveDraftToCloud` 使用新端点**

替换 `saveDraftToCloud` 函数（第 350-406 行）：

```typescript
async function saveDraftToCloud() {
  if (!familyContext) {
    setError("请先创建或进入家庭空间。");
    return;
  }
  if (!hasDraft(draft)) {
    setError("当前没有可保存的档案或记忆。");
    return;
  }
  setIsSaving(true);
  setError("");
  setSuccess("");
  setMergeResult(null);
  try {
    const result = await mergeImportParsedData({
      family_id: familyContext.family.id,
      draft,
      dedup: draft.dedup ?? { items: [] },
    });
    setMergeResult(result);
    const total = result.created.length + result.merged.length;
    const parts: string[] = [];
    if (result.created.length > 0) parts.push(`新建 ${result.created.length} 条`);
    if (result.merged.length > 0) parts.push(`合并 ${result.merged.length} 条`);
    if (result.skipped.length > 0) parts.push(`跳过 ${result.skipped.length} 条`);
    if (result.conflicts.length > 0) parts.push(`${result.conflicts.length} 条需人工确认`);
    setSuccess(`保存完成：${parts.join("，")}。`);
    setDraft(emptyDraft);
    await loadSavedRecords();
  } catch (err) {
    setError(err instanceof Error ? err.message : "保存失败，请稍后重试。");
  } finally {
    setIsSaving(false);
  }
}
```

- [ ] **Step 7: 验证**

Run: `cd web && npx tsc --noEmit`
Expected: 类型检查通过

- [ ] **Step 8: Commit**

```bash
git add web/src/app/records/page.tsx
git commit -m "feat(records): 新增 MergePreview 组件，改造保存流程为统一合并导入"
```

---

### Task 5: 端到端验证

- [ ] **Step 1: 启动后端和前端**

```bash
# Terminal 1: 启动 API
python -m uvicorn api.main:app --reload --port 8000

# Terminal 2: 启动前端
cd web && npm run dev
```

- [ ] **Step 2: 测试智能解析 → 合并预览 → 保存流程**

1. 打开 `http://localhost:3000/records`
2. 粘贴一段包含与已有资料相似内容的文本
3. 点击"智能解析"
4. 确认 MergePreview 组件正确显示新建/合并/跳过/冲突
5. 点击"保存云端"
6. 确认保存结果摘要正确展示

- [ ] **Step 3: 验证已有资料未被误覆盖**

检查云端已有的家人档案、记忆、角色在保存后字段未被错误覆盖。

- [ ] **Step 4: 运行全量测试**

```bash
cd web && npx tsc --noEmit
python -m pytest tests/ -v
```

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore: 端到端验证通过，合并导入功能恢复正常"
```
