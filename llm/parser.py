"""LLM-based smart parser: natural language -> structured persona + memories."""

import json
import re

from .client import chat

PARSER_SYSTEM = """你是一个信息提取助手。用户会用自然语言描述家庭角色和相关记忆。你需要从老人的视角出发，提取结构化信息。

只返回 JSON，不要任何解释或额外文字。"""

PARSER_USER = """请从以下描述中提取人物画像和家庭记忆。请始终以老人的视角进行提取：

"{user_text}"

## 人物画像字段
- role_label: AI 模仿的角色称呼，如"儿子小明"
- relation: 与老人的关系，必须是以下之一：子女 | 配偶 | 孙辈 | 朋友 | 护工
- appellation: 角色对老人的称呼，如"妈""奶奶""王阿姨"
- personality: 性格标签列表，从以下选择：温和 | 幽默 | 细心 | 沉稳 | 话多 | 乐观 | 感性
- speech_style: 说话风格列表（每条一句），如["喜欢用叠词","开头爱问吃了没"]
- comfort_style: 陪伴方式列表，从以下选择：唠家常 | 撒娇 | 讲趣事 | 一起回忆 | 逗开心 | 讲道理 | 转移话题 | 鼓励 | 附和倾听 | 默默陪伴

## 家庭记忆列表
每条记忆需包含：
- content: 记忆正文（一句话描述，以老人视角描述）
- subject: 这条记忆是关于谁的（主角是谁），填入角色名如"儿子小明"。整段描述的主人公是老人且未提其他人时填"老人"
- memory_type: 事件 | 习惯 | 偏好 | 重要日期 | 趣事
- family_members: 涉及家人列表，如["小明(儿子)","小红(孙女)"]
- emotion_tags: 情感标签列表，从以下选择：温馨 | 快乐 | 感动 | 搞笑 | 难忘 | 遗憾 | 伤感 | 兴奋
- topic_tags: 话题标签列表，从以下选择：饮食 | 旅行 | 节日 | 成长 | 健康 | 宠物 | 工作 | 日常

## 家人偏好档案
从描述中提取每个家人的偏好档案（如果描述中没有提及其他家人，此数组可为空）：
- name: 家人名称，如"小明"
- relation: 与老人的关系：儿子 | 女儿 | 配偶 | 孙子 | 孙女 | 朋友
- personality: 性格特点列表，如["温和","爱吃"]
- preferences: 喜好列表，如["吃辣","打篮球"]
- habits: 习惯列表，如["每周回家一次","给妈带辣子鸡"]
- notes: 补充说明（一句话）

## 输出格式（严格JSON）
{{
  "persona": {{
    "role_label": "...",
    "relation": "...",
    "appellation": "...",
    "personality": [...],
    "speech_style": [...],
    "comfort_style": [...]
  }},
  "memories": [
    {{
      "content": "...",
      "subject": "...",
      "memory_type": "...",
      "family_members": [...],
      "emotion_tags": [...],
      "topic_tags": [...]
    }}
  ],
  "family_profiles": [
    {{
      "name": "...",
      "relation": "...",
      "personality": [...],
      "preferences": [...],
      "habits": [...],
      "notes": "..."
    }}
  ]
}}

如果描述中缺少某个字段，使用合理默认值。如果完全没有记忆描述，memories 返回空数组。"""


def parse_user_text(user_text: str) -> dict:
    """解析用户的自然语言描述，返回 {persona: dict, memories: list[dict]}"""
    try:
        raw = chat(PARSER_SYSTEM, PARSER_USER.format(user_text=user_text), temperature=0.3)
    except Exception:
        return {"persona": {}, "memories": []}

    # JSON 解析容错
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # 正则提取
    match = re.search(r"\{[\s\S]*\}", raw)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    # Fallback
    return {"persona": {}, "memories": []}
