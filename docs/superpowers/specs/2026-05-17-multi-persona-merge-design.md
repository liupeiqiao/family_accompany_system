# 多角色画像 + 智能合并 — 设计规格

2026-05-17

## 目标

支持存储多个角色画像，导入时自动检测冲突并智能合并，对话时可切换当前角色。

## 数据库变更

`persona` 表：移除 `id=1` 限制，主键改为 `role_label`。

```sql
CREATE TABLE persona (
    role_label TEXT PRIMARY KEY,
    relation TEXT, appellation TEXT,
    personality TEXT, speech_style TEXT, comfort_style TEXT,
    mood_preference TEXT, topic_affinity TEXT, sensitivity_map TEXT
);
```

新增 `delete_persona(role_label)` 和 `load_all_personas() -> list[dict]`。`save_persona` 已有 `INSERT OR REPLACE`，无需改。

## engine/persona.py 变更

- `_current_persona` 保留，新增 `_all_personas: dict[str, PersonaProfile]`
- 新增 `merge_persona(existing: PersonaProfile, incoming: dict) -> PersonaProfile`：
  - 空字段 → 新值填充
  - list 字段 → 合并去重
- 新增 `switch_persona(role_label: str)` 切换当前角色
- 新增 `get_all_personas() -> list[PersonaProfile]`

## 导入逻辑

```
parsed = LLM 解析结果
incoming_label = parsed.persona.role_label
existing = _all_personas.get(incoming_label)

if existing:
  merged = merge_persona(existing, parsed.persona)
  预览区标注 🆕 差异
  用户确认后 save
else:
  直接添加新角色，切换为当前
```

## UI 变更

- 侧边栏画像区顶部增加下拉：`st.selectbox("当前角色", all_labels)`
- 当前角色卡片可 ✏️ 编辑 / 🗑️ 删除
- 删除后自动切换到剩余第一个角色；全部删完显示新增表单

## 记忆

不合并，直接追加（现有逻辑不变）。

## 验证

1. 导入两个不同角色 → 下拉切换正常
2. 导入同角色 → 字段合并，列表去重
3. 编辑/删除角色 → DB + UI 同步
4. 对话时切换角色 → 回复口吻随角色变
