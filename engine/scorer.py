"""Five-factor scoring engine: Score = αR + βE + γC + δS − εM"""

import math
import re
from datetime import datetime

from .memory import MemoryUnit
from .persona import PersonaProfile

# === 默认权重（Streamlit 侧边栏可调） ===
DEFAULT_WEIGHTS = {"alpha": 0.30, "beta": 0.25, "gamma": 0.20, "delta": 0.15, "epsilon": 0.10}

# === 关系基础亲密度 ===
RELATION_INTIMACY = {"配偶": 1.0, "子女": 0.9, "孙辈": 0.8, "朋友": 0.5, "护工": 0.4}

# === 风险关键词 ===
RISK_WORDS = ["病", "死", "钱", "遗产", "吵架", "离婚", "去世", "癌症", "手术", "药"]

# === 医学建议模式 ===
MEDICAL_PATTERNS = [
    r"(吃|服|用|抹|涂|注射).*(药|胶囊|片|针)",
    r"(血压|血糖|心脏|肝|肾|胃).*(不好|有问题|要).*",
    r"(你|您).*(应该|得|要|必须).*(治|看|检查)",
]

# === 情感冲突矩阵 ===
# 情绪 × 记忆标签 → 'compatible' | 'caution' | 'blocked'
CONFLICT_MATRIX: dict[str, dict[str, str]] = {
    "难过": {"搞笑": "blocked", "温馨": "compatible", "感动": "caution", "遗憾": "blocked",
             "伤感": "blocked", "兴奋": "caution", "日常": "compatible", "难忘": "compatible"},
    "焦虑": {"搞笑": "compatible", "温馨": "compatible", "感动": "compatible", "遗憾": "blocked",
             "伤感": "blocked", "兴奋": "caution", "日常": "compatible", "难忘": "caution"},
    "孤独": {"搞笑": "compatible", "温馨": "compatible", "感动": "compatible", "遗憾": "caution",
             "伤感": "blocked", "兴奋": "compatible", "日常": "compatible", "难忘": "compatible"},
    "委屈": {"搞笑": "blocked", "温馨": "compatible", "感动": "compatible", "遗憾": "caution",
             "伤感": "caution", "兴奋": "caution", "日常": "compatible", "难忘": "caution"},
    "抱怨": {"搞笑": "blocked", "温馨": "caution", "感动": "compatible", "遗憾": "caution",
             "伤感": "caution", "兴奋": "caution", "日常": "compatible", "难忘": "caution"},
    "思念": {"搞笑": "caution", "温馨": "compatible", "感动": "compatible", "遗憾": "blocked",
             "伤感": "blocked", "兴奋": "compatible", "日常": "compatible", "难忘": "compatible"},
    "怀疑": {"搞笑": "blocked", "温馨": "caution", "感动": "caution", "遗憾": "caution",
             "伤感": "caution", "兴奋": "caution", "日常": "compatible", "难忘": "caution"},
}


def _emotion_conflict(emotion: str, tags: list[str], sensitivity_map: dict) -> tuple[float, bool]:
    """Check emotion-tag conflict. Returns (penalty_multiplier, is_blocked)."""
    if not emotion or emotion in ("开心", "平静", "兴奋"):
        return 1.0, False

    row = CONFLICT_MATRIX.get(emotion, {})
    has_excite_and_funny = "兴奋" in tags and "搞笑" in tags

    for tag in tags:
        level = row.get(tag, "compatible")
        if has_excite_and_funny:
            # 补充约束1: 双标签冲突升级
            if level == "compatible":
                level = "caution"
            elif level == "caution":
                level = "blocked"
        if level == "blocked":
            return 0.0, True

    # Check for deceased family markers
    for topic, sensitivity in sensitivity_map.items():
        if sensitivity >= 1.0 and any(t == topic for t in tags):
            if emotion not in ("思念", "难过"):
                return 0.0, True

    # 补充约束3: 遗憾标签 + 夜间时段
    if "遗憾" in tags:
        hour = datetime.now().hour
        if hour >= 21 or hour < 6:
            return 0.0, True

    # Calculate caution ratio
    caution_count = sum(1 for tag in tags if row.get(tag, "compatible") == "caution")
    if caution_count > 0:
        return 0.4, False  # 降权

    return 1.0, False


def score_r(memory: MemoryUnit, user_input: str, intent: str) -> float:
    """相关性评分"""
    score = 0.0

    # 话题标签匹配 (40%)
    input_words = set(user_input)
    tag_matches = sum(1 for tag in memory.topic_tags if any(w in user_input for w in tag))
    if memory.topic_tags:
        score += 0.4 * (tag_matches / len(memory.topic_tags))

    # 家人提及匹配 (25%)
    member_mentioned = any(
        member_name in user_input
        for member in memory.family_members
        for member_name in member.split("(")[0:1]
    )
    if member_mentioned:
        score += 0.25

    # 时间衰减 (15%)
    if memory.timestamp:
        days_ago = (datetime.now() - memory.timestamp).days
        decay = math.exp(-0.001 * days_ago)
        score += 0.15 * decay

    # 语义相似度暂时用关键词重叠近似 (20%)
    common = input_words & set(memory.content)
    if len(input_words) > 0:
        score += 0.20 * min(len(common) / len(input_words), 1.0)
    else:
        score += 0.20

    return min(score, 1.0)


def score_e(memory: MemoryUnit, emotion: str, persona: PersonaProfile) -> float:
    """共情度评分"""
    score = 0.0

    # 情绪-标签匹配 (40%)
    if emotion and memory.emotion_tags:
        compatible_tags = {"温馨", "难忘", "感动", "日常", "快乐", "搞笑", "兴奋"}
        if emotion in ("难过", "孤独", "思念"):
            compatible_tags = {"温馨", "难忘", "感动", "日常"}
        elif emotion in ("焦虑", "担忧", "委屈"):
            compatible_tags = {"温馨", "感动", "日常"}
        elif emotion in ("抱怨",):
            compatible_tags = {"感动", "日常", "搞笑"}

        match_count = sum(1 for t in memory.emotion_tags if t in compatible_tags)
        if memory.emotion_tags:
            score += 0.4 * (match_count / len(memory.emotion_tags))

    # 历史策略有效性 (35%)
    if persona.mood_preference:
        preferred = persona.mood_preference.get(emotion or "", "")
        if preferred and preferred in persona.comfort_style_list():
            score += 0.35

    # 情感冲突检查 (25%)
    conflict_penalty, is_blocked = _emotion_conflict(
        emotion, memory.emotion_tags, persona.sensitivity_map
    )
    if is_blocked:
        return 0.0
    score += 0.25 * conflict_penalty

    return min(score, 1.0)


def score_c(memory: MemoryUnit, persona: PersonaProfile) -> float:
    """亲密度评分"""
    score = 0.0

    # 关系基础权重 (50%)
    base = RELATION_INTIMACY.get(persona.relation, 0.5)
    score += 0.5 * base

    # 记忆亲密度权重 (30%)
    score += 0.3 * memory.intimacy_weight

    # 访问热度 (20%)
    heat = min(memory.access_count / 10.0, 1.0)
    score += 0.2 * heat

    return min(score, 1.0)


def score_s(memory: MemoryUnit) -> float:
    """安全性评分"""
    score = 1.0

    # 风险关键词 (50%)
    for word in RISK_WORDS:
        if word in memory.content:
            score -= 0.5

    # 敏感话题匹配 (30%)
    sensitive_topics = {"健康": 0.8, "已故亲人": 1.0}
    for topic, sens in sensitive_topics.items():
        if topic in " ".join(memory.topic_tags):
            score -= 0.3 * sens

    # 医学边界 (20%)
    for pattern in MEDICAL_PATTERNS:
        if re.search(pattern, memory.content):
            score = 0.0
            break

    return max(score, 0.0)


def score_m(memory: MemoryUnit) -> float:
    """敏感话题罚分"""
    penalty = 0.0

    # 已故亲人触发
    if "已故亲人" in memory.topic_tags:
        penalty = 0.5

    # 创伤事件触发
    if "遗憾" in memory.emotion_tags or "伤感" in memory.emotion_tags:
        penalty = max(penalty, 0.4)

    # 近期负面事件
    if memory.timestamp:
        days_ago = (datetime.now() - memory.timestamp).days
        if days_ago < 90:
            negative_tags = {"遗憾", "伤感", "难过"}
            if any(t in negative_tags for t in memory.emotion_tags):
                penalty = max(penalty, 0.3)

    return penalty


from dataclasses import dataclass


@dataclass
class ScoreResult:
    memory: MemoryUnit
    score_r: float
    score_e: float
    score_c: float
    score_s: float
    penalty_m: float
    total: float


def score_memories(
    memories: list[MemoryUnit],
    user_input: str,
    intent: str,
    emotion: str,
    persona: PersonaProfile,
    weights: dict | None = None,
) -> list[ScoreResult]:
    """对候选记忆评分并排序，返回 ScoreResult 列表（降序）。"""
    w = weights or DEFAULT_WEIGHTS

    results = []
    for mem in memories:
        r = score_r(mem, user_input, intent)
        e = score_e(mem, emotion, persona)
        if e == 0.0:
            continue  # 情感冲突直接过滤
        c = score_c(mem, persona)
        s = score_s(mem)
        m_val = score_m(mem)

        total = w["alpha"] * r + w["beta"] * e + w["gamma"] * c + w["delta"] * s - w["epsilon"] * m_val
        results.append(ScoreResult(
            memory=mem, score_r=r, score_e=e, score_c=c,
            score_s=s, penalty_m=m_val, total=total,
        ))

    results.sort(key=lambda x: x.total, reverse=True)
    return results


def get_top_memories(
    scored: list[ScoreResult], n: int = 5, min_score: float = 0.3
) -> list[MemoryUnit]:
    """返回评分最高的 top-N 条记忆（按 total 降序）。低于 min_score 的不取。"""
    return [sr.memory for sr in scored[:n] if sr.total >= min_score]
