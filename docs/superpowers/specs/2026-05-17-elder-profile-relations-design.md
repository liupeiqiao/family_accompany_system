# 老人画像 + 家人关系表 — 设计规格

2026-05-17

## 新增数据结构

### ElderProfile（老人画像）

```python
name: str              # 称呼/主键，如"妈"
personality: list[str]
preferences: list[str]
habits: list[str]
health_notes: list[str]
speech_traits: list[str]
life_experiences: list[str]
important_memories: list[str]
notes: str
```

DB: `elder_profiles` 表，`name PRIMARY KEY`。

### FamilyProfile 新增字段

```python
relations: list[dict]  # [{"person":"小红","relation":"妻子"}]
```

DB migration: `ALTER TABLE family_profiles ADD COLUMN relations TEXT DEFAULT '[]'`

## 智能解析

Prompt 新增：
- `elder_profile`: 从描述中提取老人自己的画像（如果描述以老人视角展开）
- FamilyProfile 的 `relations`: 提取家人之间的关系

## Pipeline

每轮回复前注入：
- **老人画像** → 性格/习惯/健康/说话特点，LLM 据此调整回复风格
- **家人关系表** → 提及家人的所有 relations，帮助理解关系网

## 侧边栏

- "👴 老人画像" 卡片（单例，编辑/删除）
- 家人档案卡片编辑时增加 relations 输入区

## 验证

1. 导入老人描述 → elder_profile 被提取
2. 导入家庭描述 → family_profiles 带 relations
3. 对话时 LLM 正确引用老人特点和人物关系
