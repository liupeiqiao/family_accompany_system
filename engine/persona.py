from __future__ import annotations
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
_all_personas: dict[str, PersonaProfile] = {}


def set_persona(p: PersonaProfile) -> None:
    global _current_persona, _all_personas
    _current_persona = p
    if p.is_complete():
        # 清理可能因改名产生的旧 key
        to_remove = [k for k, v in _all_personas.items() if k != p.role_label and v is p]
        for k in to_remove:
            _all_personas.pop(k, None)
        _all_personas[p.role_label] = p


def get_persona() -> PersonaProfile:
    return _current_persona


def get_all_personas() -> dict[str, PersonaProfile]:
    return _all_personas


def add_or_update_persona(p: PersonaProfile) -> None:
    if p.is_complete():
        to_remove = [k for k, v in _all_personas.items() if k != p.role_label and v is p]
        for k in to_remove:
            _all_personas.pop(k, None)
        _all_personas[p.role_label] = p


def remove_persona(role_label: str) -> None:
    global _current_persona
    _all_personas.pop(role_label, None)
    if _current_persona.role_label == role_label:
        keys = list(_all_personas.keys())
        _current_persona = _all_personas[keys[0]] if keys else PersonaProfile()


def switch_persona(role_label: str) -> None:
    global _current_persona
    if role_label in _all_personas:
        _current_persona = _all_personas[role_label]


def merge_persona(existing: PersonaProfile, incoming: dict) -> PersonaProfile:
    """智能合并：空字段填充，列表字段合并去重。"""
    if not incoming.get("role_label"):
        return existing
    existing.role_label = incoming.get("role_label") or existing.role_label
    existing.relation = incoming.get("relation") or existing.relation
    existing.appellation = incoming.get("appellation") or existing.appellation
    # 列表合并去重
    for field in ["personality", "speech_style", "comfort_style"]:
        existing_val = getattr(existing, field, [])
        incoming_val = incoming.get(field, [])
        merged = list(dict.fromkeys(list(existing_val) + list(incoming_val)))
        setattr(existing, field, merged)
    return existing
