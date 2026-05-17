# 家人偏好档案 — 设计规格

2026-05-17

## 目标

存储每个家人的独立偏好档案（性格、喜好、习惯），智能解析自动提取，Pipeline 自动注入回复。

## 数据结构

```python
@dataclass
class FamilyProfile:
    name: str              # 主键，如"小明"
    relation: str          # "儿子"
    personality: list[str] # ["温和","爱吃"]
    preferences: list[str] # ["吃辣","打篮球"]
    habits: list[str]      # ["每周回家","给妈带辣子鸡"]
    notes: str             # 补充描述
```

## DB 表

```sql
family_profiles: name TEXT PRIMARY KEY, relation TEXT, personality(JSON), preferences(JSON), habits(JSON), notes TEXT
```

## 智能解析

Parser Prompt 新增 `family_profiles` 输出数组，从描述中提取每个人的偏好档案。

## 侧边栏 UI

画像区下方新增 "👥 家人档案"：卡片列表（姓名·关系·性格·喜好·习惯），✏️编辑 / 🗑️删除 / ➕新增。

## Pipeline 注入

识别提及人物 → 查 family_profiles → 构建家人偏好上下文 → 注入回复 Prompt。

## 验证

1. 智能解析一段多人物描述 → 提取到 family_profiles + 记忆（带 subject）
2. 侧边栏可查看/编辑/删除家人档案
3. 聊天时提及家人 → 回复结合其偏好信息
