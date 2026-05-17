"""Family profile — each family member's traits, preferences, habits."""

from dataclasses import dataclass, field


@dataclass
class FamilyProfile:
    """一个家人的偏好档案"""
    name: str = ""              # 主键，如"小明"
    relation: str = ""          # 与老人关系："儿子"
    personality: list[str] = field(default_factory=list)  # ["温和","爱吃"]
    preferences: list[str] = field(default_factory=list)  # ["吃辣","打篮球"]
    habits: list[str] = field(default_factory=list)       # ["每周回家"]
    relations: list[dict] = field(default_factory=list)   # [{"person":"小红","relation":"妻子"}]
    notes: str = ""             # 补充描述


# Session-level store
_family_profiles: dict[str, FamilyProfile] = {}


def add_profile(fp: FamilyProfile) -> None:
    if fp.name:
        _family_profiles[fp.name] = fp


def remove_profile(name: str) -> None:
    _family_profiles.pop(name, None)


def get_profile(name: str) -> FamilyProfile | None:
    return _family_profiles.get(name)


def get_all_profiles() -> dict[str, FamilyProfile]:
    return dict(_family_profiles)


def clear_profiles() -> None:
    _family_profiles.clear()
