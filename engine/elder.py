"""Elder profile — the elderly person's traits, habits, background."""

from dataclasses import dataclass, field


@dataclass
class ElderProfile:
    """老人自己的画像"""
    full_name: str = ""                 # 姓名，如"宋桂兰"
    gender: str = ""                    # 性别："男" | "女"
    personality: list[str] = field(default_factory=list)
    preferences: list[str] = field(default_factory=list)
    habits: list[str] = field(default_factory=list)
    health_notes: list[str] = field(default_factory=list)
    speech_traits: list[str] = field(default_factory=list)
    life_experiences: list[str] = field(default_factory=list)
    important_memories: list[str] = field(default_factory=list)
    notes: str = ""

    def get_appellation(self) -> str:
        """根据性别自动推导称呼"""
        if self.gender == "女":
            return "妈"
        elif self.gender == "男":
            return "爸"
        return ""


# Session-level singleton
_elder: ElderProfile = ElderProfile()


def set_elder(ep: ElderProfile) -> None:
    global _elder
    _elder = ep


def get_elder() -> ElderProfile:
    return _elder
