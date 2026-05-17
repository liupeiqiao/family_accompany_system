"""Elder profile — the elderly person's traits, habits, background."""

from dataclasses import dataclass, field


@dataclass
class ElderProfile:
    """老人自己的画像"""
    name: str = ""                      # 称呼/主键
    personality: list[str] = field(default_factory=list)     # 性格
    preferences: list[str] = field(default_factory=list)     # 喜好
    habits: list[str] = field(default_factory=list)          # 习惯
    health_notes: list[str] = field(default_factory=list)    # 健康注意
    speech_traits: list[str] = field(default_factory=list)   # 说话特点
    life_experiences: list[str] = field(default_factory=list)# 人生经历
    important_memories: list[str] = field(default_factory=list) # 重要记忆
    notes: str = ""


# Session-level singleton
_elder: ElderProfile = ElderProfile()


def set_elder(ep: ElderProfile) -> None:
    global _elder
    _elder = ep


def get_elder() -> ElderProfile:
    return _elder
