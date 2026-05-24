# 老人画像 & AI 角色删除功能 + 保存逻辑修复

## 问题

1. 导入新老人画像时，不同 `full_name` 的画像被错误合并到第一个已有画像，而非作为独立条目保存
2. 已保存档案区中，老人画像和 AI 扮演角色缺少删除按钮（家人档案已有）

## 改动

### DB 层 (`engine/db.py`)

- `delete_elder()` 增加 `full_name` 参数，按名删除单条（当前是 DELETE 全表）

### Handler 层 (`api/handlers.py`)

- `_save_elder_payload()`：`merge_into_existing=True` 时改用 `load_all_elders()` 按 `full_name` 匹配合并，匹配不到则新增
- 新增 `handle_delete_elder(full_name)` 和 `handle_delete_persona(role_label)`

### 路由层 (`api/main.py`)

- 新增 `DELETE /api/elders/{full_name}`
- 新增 `DELETE /api/personas/{role_label}`

### 前端 API (`web/src/lib/backend-api.ts`)

- 新增 `deleteElderProfile(full_name)` 和 `deletePersona(role_label)`

### 页面 (`web/src/app/records/page.tsx`)

- 实现 `deleteElderProfile` 和 `deletePersona` 回调，传入已保存区的两个 `SavedProfileList`
- 删除后重置对应展开状态

## 设计原则

- 删除函数签名与已有的 `deleteFamilyProfile(name)`、`deleteMemory(id)` 保持一致
- `SavedProfileList` 已支持 `onDelete?: (index: number) => void`，无需改动组件
- 后续如需扩展参数（如 `family_id`），在 handler 签名和路由路径中自然追加即可
