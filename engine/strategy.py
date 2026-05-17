"""Empathy strategy selector: Intent × Emotion → Strategy mapping."""

from .persona import PersonaProfile

# === 7 种共情策略 ===
STRATEGIES = ["分享式", "安慰式", "转移注意力", "确认式", "鼓励式", "附和式", "唠家常"]

# === 意图×情绪 → 策略 映射矩阵 ===
# 行: 意图, 列: 开心 | 平静 | 难过 | 孤独 | 焦虑 | 思念 | 委屈 | 怀疑 | 兴奋
STRATEGY_MATRIX: dict[str, dict[str, str]] = {
    "怀念": {
        "开心": "分享式", "平静": "分享式", "难过": "安慰式", "孤独": "安慰式",
        "焦虑": "转移注意力", "思念": "分享式", "委屈": "安慰式",
        "怀疑": "分享式", "兴奋": "分享式",
    },
    "抱怨": {
        "开心": "安慰式", "平静": "附和式", "难过": "安慰式", "孤独": "转移注意力",
        "焦虑": "安慰式", "思念": "安慰式", "委屈": "安慰式",
        "怀疑": "附和式", "兴奋": "附和式",
    },
    "思念家人": {
        "开心": "分享式", "平静": "分享式", "难过": "安慰式", "孤独": "安慰式",
        "焦虑": "转移注意力", "思念": "分享式", "委屈": "确认式",
        "怀疑": "分享式", "兴奋": "分享式",
    },
    "表达孤独": {
        "开心": "分享式", "平静": "分享式", "难过": "安慰式", "孤独": "鼓励式",
        "焦虑": "安慰式", "思念": "安慰式", "委屈": "安慰式",
        "怀疑": "鼓励式", "兴奋": "鼓励式",
    },
    "担忧焦虑": {
        "开心": "分享式", "平静": "分享式", "难过": "安慰式", "孤独": "鼓励式",
        "焦虑": "安慰式", "思念": "安慰式", "委屈": "转移注意力",
        "怀疑": "安慰式", "兴奋": "安慰式",
    },
    "日常闲聊": {
        "开心": "分享式", "平静": "唠家常", "难过": "安慰式", "孤独": "鼓励式",
        "焦虑": "安慰式", "思念": "分享式", "委屈": "安慰式",
        "怀疑": "唠家常", "兴奋": "唠家常",
    },
    "确认事实": {
        "开心": "确认式", "平静": "确认式", "难过": "确认式", "孤独": "鼓励式",
        "焦虑": "确认式", "思念": "确认式", "委屈": "确认式",
        "怀疑": "确认式", "兴奋": "确认式",
    },
}

# 默认情绪 fallback
_DEFAULT_EMOTION = "平静"


def select_strategy(intent: str, emotion: str, persona: PersonaProfile) -> str:
    """
    根据意图+情绪查表选择策略。
    约束：策略必须在 persona.comfort_style 集合内。不存在时 fallback 到 comfort_style 第一项。
    """
    intent_row = STRATEGY_MATRIX.get(intent, STRATEGY_MATRIX["日常闲聊"])
    strategy = intent_row.get(emotion, intent_row.get(_DEFAULT_EMOTION, "唠家常"))

    allowed = persona.comfort_style_list()

    # 策略在用户允许的陪伴方式内直接返回
    if strategy in allowed:
        return strategy

    # 不在则找最接近的替代：安慰式→鼓励式→分享式→唠家常
    fallback_order = ["安慰式", "鼓励式", "分享式", "唠家常", "附和式", "转移注意力", "确认式"]
    for fb in fallback_order:
        if fb in allowed:
            return fb

    # 最后兜底
    return allowed[0] if allowed else "唠家常"


def get_all_strategies() -> list[str]:
    return list(STRATEGIES)
