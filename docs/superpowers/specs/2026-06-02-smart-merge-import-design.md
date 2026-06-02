# 智能合并导入 — 设计规格

2026-06-02

## 背景

`档案与记忆` 页面在 UI 大改版（`1fbb878`）时，智能合并预览 UI 和后端统一导入逻辑丢失：
- `DedupPreview` 组件被删除，`merge_preview` 和 `dedup` 数据虽返回但不渲染
- 保存流程从 `POST /api/import`（后端统一处理合并）改为多个独立云端 CRUD API，每次直接新建，无合并去重

## 目标

恢复并增强智能合并机制：前端展示合并预览，后端统一处理合并保存。

## 核心原则

前端负责展示和确认，后端负责最终判断和落库。

## 整体流程

1. 用户输入资料 → 点击"智能解析"
2. 后端返回 parse 结果 + `merge_preview` 文案 + `dedup` 结构化合并建议
3. 前端在解析预览区顶部展示 `MergePreview` 组件（新建/合并/跳过/冲突四类）
4. 用户确认 → 点击"保存云端"
5. 前端将 draft + dedup 提交给 `POST /api/import/merge`
6. 后端重新读取云端数据，校验 dedup 是否仍有效
7. 后端执行 create / merge / skip / conflict
8. 返回 `{ created, merged, skipped, conflicts }`
9. 前端展示保存结果摘要

## 后端改动

### 新端点：`POST /api/import/merge`

请求体 (`MergeImportRequest`)：
- `family_id`: str
- `draft`: ParsedDraft（含 persona/elder_profile/family_profiles/memories/personas/elder_profiles）
- `dedup`: DedupSuggestion（含 items 数组）

响应体 (`MergeImportResponse`)：
```json
{
  "created": [{"type": "family_profile", "name": "李阿姨", "id": "uuid"}],
  "merged": [{"type": "family_profile", "name": "张三", "id": "uuid", "fields": ["birthday", "hobbies"]}],
  "skipped": [{"type": "memory", "title": "2024年春节聚餐", "reason": "相似记忆已存在"}],
  "conflicts": [{"type": "family_profile", "name": "张三", "fields": ["nickname"], "existing_value": "...", "incoming_value": "..."}]
}
```

### Dedup 结构标准化

```json
{
  "items": [
    {
      "type": "family_profile",
      "action": "merge",
      "source_temp_id": "temp_001",
      "target_id": "existing_uuid",
      "target_name": "张三",
      "confidence": 0.92,
      "reason": "姓名相同，关系相同",
      "fields_to_merge": ["birthday", "hobbies", "notes"],
      "conflict_fields": []
    }
  ]
}
```

- `type`: `family_profile` | `memory` | `persona` | `elder_profile`
- `action`: `create` | `merge` | `merge_into` | `skip` | `conflict`
- items 中仅包含非 create 项（create 是默认行为，无需显式列出）

### 合并规则

**家人档案：**
- 核心身份字段（name/relation/nickname/phone）冲突时不覆盖，写入 conflict_fields
- 已有空 + 新有值 → 补充
- 列表字段（personality/preferences/habits/relations）合并去重
- notes 追加带时间戳：`2026-06-02 智能解析补充：...`

**家庭记忆：**
- content 高度相似（归一化后匹配）→ skip
- 主题相同但有新增细节 → merge
- 完全不同 → create

**AI 角色/画像：**
- 已存在相同 role_label → merge 补充空字段
- 关系冲突 → conflict，不覆盖
- 不删除已有角色

**老人画像：**
- 始终 merge（只有一个）
- 列表字段合并去重

### 处理函数 `handle_merge_import`

```
1. 从云端重新读取已有数据（personas/family_profiles/memories/elders）
2. 构建已有数据的索引（by id, by name, by role_label）
3. 遍历 dedup.items，校验 target_id 仍存在
4. 对于每个 item：
   - create: 调用 cloud create API
   - merge/merge_into: 找到 target，执行合并规则，调用 cloud update API
   - skip: 跳过
   - conflict: 收集到 conflicts 列表
5. 对于没有出现在 dedup.items 中的 draft 条目（纯新建）：
   - 检查是否与已有数据意外重复
   - 调用 create API
6. 汇总 created/merged/skipped/conflicts 并返回
```

## 前端改动

### 文件：`web/src/app/records/page.tsx`

**新增 `MergePreview` 组件：**

Props: `{ dedup: DedupSuggestion; mergePreview: string[] }`

按 action 分组展示：
- 🆕 新建：将新建家人档案/角色/记忆 xxx
- 🔄 合并：检测到 xxx 可能是已有资料，将合并到「target_name」
- ⏭️ 跳过：已存在相似内容，跳过重复保存
- ⚠️ 冲突：xxx 字段与已有资料不一致，需确认

**改造 `saveDraftToCloud`：**

```typescript
async function saveDraftToCloud() {
  const response = await mergeImportParsedData({
    family_id: familyContext.family.id,
    draft,
    dedup: draft.dedup,
  });
  // 展示结果摘要
  setMergeResult(response);
  setDraft(emptyDraft);
  await loadSavedRecords();
}
```

### 文件：`web/src/lib/backend-api.ts`

- 新增 `MergeImportResponse` 类型
- 新增 `mergeImportParsedData()` 函数 → `POST /api/import/merge`

## 数据安全

1. 后端必须重新读取云端数据，不信任前端 dedup
2. 核心身份字段冲突不自动覆盖
3. 合并前检查 target_id 是否仍存在
4. 写操作使用云端 update API（非覆盖式）
5. 冲突项返回前端，由用户决定

## 非目标

- 不改造现有独立 CRUD API（createCloudPersona 等保留）
- 不改变 `POST /api/parse` 的响应结构（仅扩展 dedup 字段）
- 不重构 `llm/parser.py` 的 prompt 模板
- 不改变 Streamlit 原型

## 测试

- `POST /api/import/merge` 新建记录正确写入云端
- `POST /api/import/merge` 合并记录正确更新已有记录
- `POST /api/import/merge` 跳过重复记忆
- `POST /api/import/merge` 冲突字段不覆盖，返回 conflicts
- 前端 MergePreview 渲染四种状态
- 空 draft 不崩溃
- 已有单元测试全部通过

## 验收标准

- 用户在档案与记忆页面粘贴资料 → 智能解析 → 看到合并预览
- 点击保存云端 → 新建/合并/跳过/冲突均正确处理
- 保存后展示结果摘要
- 不产生重复数据
- 已有资料的字段不被误覆盖
