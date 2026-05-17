"""LLM-based smart parser: natural language -> structured persona + memories + profiles."""

import json
import re

from .client import chat

PARSER_SYSTEM = """你是一个信息提取助手。从用户描述中提取结构化信息。只返回JSON，不要任何解释。"""

PARSER_USER_FAMILY = """从以下「家人回忆」视角的描述中提取信息。

**重要：所有关系 (relation) 都是相对于老人的，不是相对于其他家人的。**
例如"我是张怀粉的丈夫"→张怀粉是儿媳，所以我是儿子→relation应填"子女"，不是"配偶"。

{existing_families_context}
## 用户描述
"{user_text}"

## AI 扮演角色画像 (persona)
- role_label: 角色称呼，如"儿子小明"
- relation: 该角色与老人（不是其他人）的关系：子女 | 儿媳 | 女婿 | 配偶 | 孙辈 | 朋友 | 护工
- appellation: 角色对老人的称呼（单个，如"妈"或"爸"）
- personality: 从以下选：温和 | 幽默 | 细心 | 沉稳 | 话多 | 乐观 | 感性 | 活泼 | 内向 | 开朗 | 随和 | 大条
- speech_style: 说话风格列表
- comfort_style: 唠家常 | 撒娇 | 讲趣事 | 一起回忆 | 逗开心 | 讲道理 | 转移话题 | 鼓励 | 附和倾听 | 默默陪伴

## 家庭记忆 (memories)
每条记忆：
- content: 记忆正文
- subject: 记忆主语
- memory_type: 事件 | 习惯 | 偏好 | 重要日期 | 趣事
- family_members: ["小明(儿子)"]
- emotion_tags: 温馨 | 快乐 | 感动 | 搞笑 | 难忘 | 遗憾 | 伤感 | 兴奋
- topic_tags: 饮食 | 旅行 | 节日 | 成长 | 健康 | 宠物 | 工作 | 日常

## 家人档案 (family_profiles)
- name, relation(与老人关系), personality, preferences, habits, relations, notes

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
- full_name: 老人姓名，如"宋桂兰"
- gender: "男" 或 "女"（从自称"奶奶""母亲"等推断）
- personality: 温和 | 幽默 | 细心 | 沉稳 | 话多 | 乐观 | 感性 | 活泼 | 内向 | 开朗 | 随和 | 大条
- preferences: ["听戏曲","养花"]
- habits: ["早起","饭后散步"]
- health_notes: ["高血压","忌油腻"]
- speech_traits: ["语速慢","爱重复"]
- life_experiences: ["退休教师","带大两个孙子"]
- important_memories: ["儿子考上大学摆了三天酒"]
- notes: 补充

## 家庭记忆 (memories)
每条记忆（老人在回忆中提到的事件、习惯、偏好等）：
- content, subject:"老人", memory_type, family_members, emotion_tags, topic_tags

## 输出JSON
{{
  "elder_profile": {{ "full_name":"...","gender":"男或女","personality":[...],"preferences":[...],"habits":[...],"health_notes":[...],"speech_traits":[...],"life_experiences":[...],"important_memories":[...],"notes":"" }},
  "memories": [ {{ "content":"...","subject":"老人","memory_type":"...","family_members":[...],"emotion_tags":[...],"topic_tags":[...] }} ]
}}

无内容返回空对象/空数组。"""


def parse_user_text(user_text: str, perspective: str = "family",
                    existing_families_text: str = "") -> dict:
    """解析描述，perspective: 'family' 或 'elder'"""
    if perspective == "elder":
        template = PARSER_USER_ELDER
        formatted = template.format(user_text=user_text)
    else:
        template = PARSER_USER_FAMILY
        formatted = template.format(user_text=user_text,
                                     existing_families_context=existing_families_text)
    try:
        raw = chat(PARSER_SYSTEM, formatted, temperature=0.3)
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


DEDUP_SYSTEM = """你是人物去重助手。判断新解析结果中的人物是否与已有数据中的人物相同。只返回JSON。"""

DEDUP_USER = """已有的人物（注意：persona和family_profile中可能存着同一个人）：

## AI 扮演角色 (personas)
{existing_personas}

## 家人档案 (family_profiles)
{existing_families}

新解析结果：
## 新角色 (persona)
{new_persona}

## 新家人 (family_profiles)
{new_families}

判断每个新人物的去重动作。**重要：新角色可能是已有家人档案中的同一个人，反之亦然。要交叉对比。**
例如：已有family中"丈夫(子女)" + 新persona"儿子刘承文(子女)" → 是同一个人 → persona merge + family merge_into。

判断规则：
- 名字包含关系（如"儿子刘承文" vs "刘承文" = 同一人）
- 名字完全相同或部分匹配 + 关系一致 = 同一人
- 通过家庭关系推断（如新角色"张怀粉的丈夫"而张怀粉已知是儿媳 → 此人是儿子，与已有"儿子刘承文"匹配）

返回严格JSON：
{{
  "persona_action": "merge" | "new" | "skip",
  "persona_match": "匹配到的已有角色名或家人名（merge/merge_into时填）",
  "family_actions": [
    {{"new_name":"...", "action":"merge_into", "target":"已有名字"}},
    {{"new_name":"...", "action":"new"}},
    {{"new_name":"...", "action":"skip"}}
  ]
}}

规则：
- 同一个人但名字不同 → merge / merge_into
- 全新人物 → new
- 完全相同无需改 → skip
- 合并时保留旧名字已有信息，新信息补空白字段
- **交叉匹配：新 persona 可能与已有 family_profile 同名；新 family 可能与已有 persona 同名**"""


def dedup_check(
    new_parsed: dict,
    existing_personas: list[dict],
    existing_families: list[dict],
) -> dict:
    """去重检查，返回 {persona_action, persona_match, family_actions}"""
    ep_text = "\n".join(
        f"- {p.get('role_label','')} (关系:{p.get('relation','')}, 称呼:{p.get('appellation','')})"
        for p in existing_personas
    ) if existing_personas else "（无）"

    ef_text = "\n".join(
        f"- {f.get('name','')} (关系:{f.get('relation','')}, 性格:{'、'.join(f.get('personality',[]))})"
        for f in existing_families
    ) if existing_families else "（无）"

    np_text = json.dumps(new_parsed.get("persona", {}), ensure_ascii=False)
    nf_text = json.dumps(new_parsed.get("family_profiles", []), ensure_ascii=False)

    try:
        raw = chat(DEDUP_SYSTEM, DEDUP_USER.format(
            existing_personas=ep_text, existing_families=ef_text,
            new_persona=np_text, new_families=nf_text,
        ), temperature=0.2)
        result = json.loads(raw)
        result.setdefault("family_actions", [])
        result.setdefault("persona_action", "new")
        result.setdefault("persona_match", "")
        return result
    except Exception:
        actions = [{"new_name": f.get("name",""), "action": "new"}
                   for f in new_parsed.get("family_profiles", [])]
        return {"persona_action": "new", "persona_match": "", "family_actions": actions}
