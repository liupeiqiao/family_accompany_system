"""LLM-based smart parser: natural language -> structured persona + memories + elder + family_profiles."""

import json
import re

from .client import chat

PARSER_SYSTEM = """你是一个信息提取助手。用户会用自然语言描述家庭角色和相关记忆。你需要从老人的视角出发，提取结构化信息。

只返回 JSON，不要任何解释或额外文字。"""

PARSER_USER = """请从以下描述中提取人物画像、家庭记忆、家人档案、老人画像和家庭关系。请始终以老人的视角进行提取：

"{user_text}"

## 判断视角
如果描述以老人为主角（如"我今年70岁…""我退休后…""我喜欢…"），同时提取 elder_profile。
如果描述以家人们为主角（如"我儿子小明…""我女儿小红…"），提取 persona + family_profiles。
两种可以并存。

## 人物画像字段 (persona)
- role_label: AI 模仿的角色称呼，如"儿子小明"
- relation: 与老人的关系：子女 | 配偶 | 孙辈 | 朋友 | 护工
- appellation: 角色对老人的称呼，如"妈""奶奶"
- personality: ["温和","幽默","细心","沉稳","话多","乐观","感性"]
- speech_style: 说话风格列表，如["喜欢用叠词","开头爱问吃了没"]
- comfort_style: ["唠家常","撒娇","讲趣事","一起回忆","逗开心","讲道理","转移话题","鼓励","附和倾听","默默陪伴"]

## 家庭记忆列表 (memories)
每条记忆字段：
- content: 记忆正文
- subject: 记忆主角，如"儿子小明"。老人为主角时填"老人"
- memory_type: 事件 | 习惯 | 偏好 | 重要日期 | 趣事
- family_members: ["小明(儿子)","小红(孙女)"]
- emotion_tags: ["温馨","快乐","感动","搞笑","难忘","遗憾","伤感","兴奋"]
- topic_tags: ["饮食","旅行","节日","成长","健康","宠物","工作","日常"]

## 家人偏好档案 (family_profiles)
- name: 如"小明"
- relation: 与老人关系：儿子 | 女儿 | 配偶 | 孙子 | 孙女 | 朋友
- personality: ["温和","爱吃"]
- preferences: ["吃辣","打篮球"]
- habits: ["每周回家一次"]
- relations: [{"person":"小红","relation":"妻子"}] — 该家人与其他家人的关系
- notes: 补充说明

## 老人画像 (elder_profile)
- name: 老人称呼，如"妈""奶奶"或"老人"
- personality: ["温和","爱操心"]
- preferences: ["听戏曲","养花"]
- habits: ["早起","饭后散步"]
- health_notes: ["高血压","忌油腻"]
- speech_traits: ["语速慢","爱重复"]
- life_experiences: ["退休教师","带大两个孙子"]
- important_memories: ["儿子考上大学摆了三天酒"]
- notes: 补充

## 输出格式（严格JSON）
{{
  "persona": {{ "role_label":"...","relation":"...","appellation":"...","personality":[...],"speech_style":[...],"comfort_style":[...] }},
  "memories": [ {{ "content":"...","subject":"...","memory_type":"...","family_members":[...],"emotion_tags":[...],"topic_tags":[...] }} ],
  "family_profiles": [ {{ "name":"...","relation":"...","personality":[...],"preferences":[...],"habits":[...],"relations":[{{"person":"...","relation":"..."}}],"notes":"..." }} ],
  "elder_profile": {{ "name":"...","personality":[...],"preferences":[...],"habits":[...],"health_notes":[...],"speech_traits":[...],"life_experiences":[...],"important_memories":[...],"notes":"..." }}
}}

缺字段用默认值，无内容返回空数组/空对象。"""


def parse_user_text(user_text: str) -> dict:
    """解析用户的自然语言描述，返回 {persona, memories, family_profiles, elder_profile}"""
    try:
        raw = chat(PARSER_SYSTEM, PARSER_USER.format(user_text=user_text), temperature=0.3)
    except Exception:
        return {"persona": {}, "memories": [], "family_profiles": [], "elder_profile": {}}

    try:
        result = json.loads(raw)
        result.setdefault("family_profiles", [])
        result.setdefault("elder_profile", {})
        return result
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{[\s\S]*\}", raw)
    if match:
        try:
            result = json.loads(match.group())
            result.setdefault("family_profiles", [])
            result.setdefault("elder_profile", {})
            return result
        except json.JSONDecodeError:
            pass

    return {"persona": {}, "memories": [], "family_profiles": [], "elder_profile": {}}
