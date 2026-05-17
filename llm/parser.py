"""LLM-based smart parser: natural language -> structured persona + memories + profiles."""

import json
import re

from .client import chat

PARSER_SYSTEM = """你是一个信息提取助手。从用户描述中提取结构化信息。只返回JSON，不要任何解释。"""

PARSER_USER_FAMILY = """从以下「家人回忆」视角的描述中提取信息：

"{user_text}"

## AI 扮演角色画像 (persona)
提取描述者在与老人对话时，AI 应模仿的角色：
- role_label: 角色称呼，如"儿子小明"
- relation: 与老人的关系：子女 | 配偶 | 孙辈 | 朋友 | 护工
- appellation: 角色对老人的称呼，如"妈""奶奶"
- personality: 性格标签，从以下选：温和 | 幽默 | 细心 | 沉稳 | 话多 | 乐观 | 感性 | 活泼 | 内向 | 开朗 | 随和 | 大条
- speech_style: 说话风格列表，如["喜欢用叠词","开头爱问吃了没"]
- comfort_style: 陪伴方式，从以下选：唠家常 | 撒娇 | 讲趣事 | 一起回忆 | 逗开心 | 讲道理 | 转移话题 | 鼓励 | 附和倾听 | 默默陪伴

## 家庭记忆 (memories)
每条记忆：
- content: 记忆正文
- subject: 记忆主语（主角名字，如"儿子小明"）
- memory_type: 事件 | 习惯 | 偏好 | 重要日期 | 趣事
- family_members: ["小明(儿子)","小红(孙女)"]
- emotion_tags: 温馨 | 快乐 | 感动 | 搞笑 | 难忘 | 遗憾 | 伤感 | 兴奋
- topic_tags: 饮食 | 旅行 | 节日 | 成长 | 健康 | 宠物 | 工作 | 日常

## 家人档案 (family_profiles)
- name: 如"小明"
- relation: 与老人关系
- personality: 同上性格标签
- preferences: ["吃辣","打篮球"]
- habits: ["每周回家"]
- relations: [{{"person":"小红","relation":"妻子"}}]
- notes: 补充

## 输出JSON
{{
  "persona": {{ "role_label":"...","relation":"...","appellation":"...","personality":[...],"speech_style":[...],"comfort_style":[...] }},
  "memories": [ {{ "content":"...","subject":"...","memory_type":"...","family_members":[...],"emotion_tags":[...],"topic_tags":[...] }} ],
  "family_profiles": [ {{ "name":"...","relation":"...","personality":[...],"preferences":[...],"habits":[...],"relations":[],"notes":"" }} ]
}}

无内容返回空对象/空数组。"""

PARSER_USER_ELDER = """从以下「老人回忆」视角的描述中提取信息：

"{user_text}"

## 老人画像 (elder_profile)
- name: 老人称呼，如"妈""奶奶"
- personality: 性格标签：温和 | 幽默 | 细心 | 沉稳 | 话多 | 乐观 | 感性 | 活泼 | 内向 | 开朗 | 随和 | 大条
- preferences: ["听戏曲","养花"]
- habits: ["早起","饭后散步"]
- health_notes: ["高血压","忌油腻"]
- speech_traits: ["语速慢","爱重复"]
- life_experiences: ["退休教师","带大两个孙子"]
- important_memories: ["儿子考上大学摆了三天酒"]
- notes: 补充

## 家庭记忆 (memories)
每条记忆（老人在回忆中提到的事件、习惯、偏好等）：
- content: 记忆正文
- subject: "老人"（因为是老人的记忆）
- memory_type: 事件 | 习惯 | 偏好 | 重要日期 | 趣事
- family_members: ["儿子小明(儿子)","孙女小红(孙女)"]
- emotion_tags: 温馨 | 快乐 | 感动 | 搞笑 | 难忘 | 遗憾 | 伤感 | 兴奋
- topic_tags: 饮食 | 旅行 | 节日 | 成长 | 健康 | 宠物 | 工作 | 日常

## 输出JSON
{{
  "elder_profile": {{ "name":"...","personality":[...],"preferences":[...],"habits":[...],"health_notes":[...],"speech_traits":[...],"life_experiences":[...],"important_memories":[...],"notes":"" }},
  "memories": [ {{ "content":"...","subject":"老人","memory_type":"...","family_members":[...],"emotion_tags":[...],"topic_tags":[...] }} ]
}}

无内容返回空对象/空数组。"""


def parse_user_text(user_text: str, perspective: str = "family") -> dict:
    """解析描述，perspective: 'family'（家人回忆）或 'elder'（老人回忆）"""
    template = PARSER_USER_ELDER if perspective == "elder" else PARSER_USER_FAMILY
    try:
        raw = chat(PARSER_SYSTEM, template.format(user_text=user_text), temperature=0.3)
    except Exception:
        return _empty_result()

    try:
        result = json.loads(raw)
        result.setdefault("family_profiles", [])
        result.setdefault("elder_profile", {})
        result.setdefault("persona", {})
        result.setdefault("memories", [])
        return result
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{[\s\S]*\}", raw)
    if match:
        try:
            result = json.loads(match.group())
            result.setdefault("family_profiles", [])
            result.setdefault("elder_profile", {})
            result.setdefault("persona", {})
            result.setdefault("memories", [])
            return result
        except json.JSONDecodeError:
            pass

    return _empty_result()


def _empty_result() -> dict:
    return {"persona": {}, "memories": [], "family_profiles": [], "elder_profile": {}}
