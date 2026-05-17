"""Persona profile for the companion."""

from dataclasses import dataclass, field


@dataclass
class PersonaProfile:
    """目标陪伴者画像（静态 + 动态）"""

    # 静态属性
    role_label: str = ""  # 如 "儿子小明"
    relation: str = ""  # 子女 | 配偶 | 孙辈 | 朋友 | 护工
    appellation: str = ""  # 对老人的称呼，如 "妈"
    personality: list[str] = field(default_factory=list)  # 温和、幽默、细心...
    speech_style: list[str] = field(default_factory=list)  # 分条说话风格
    comfort_style: list[str] = field(default_factory=list)  # 陪伴行为方式（多选）

    # 动态属性
    mood_preference: dict = field(default_factory=dict)  # {情绪: 最有效策略}
    topic_affinity: dict = field(default_factory=dict)  # {话题: 老人回应积极性}
    sensitivity_map: dict = field(default_factory=dict)  # {话题: 敏感度 0~1}

    def is_complete(self) -> bool:
        return bool(self.role_label and self.relation and self.appellation)

    def comfort_style_list(self) -> list[str]:
        return self.comfort_style if self.comfort_style else ["唠家常"]


# Session-level persona store
_current_persona: PersonaProfile = PersonaProfile()


def set_persona(p: PersonaProfile) -> None:
    global _current_persona
    _current_persona = p


def get_persona() -> PersonaProfile:
    return _current_persona
