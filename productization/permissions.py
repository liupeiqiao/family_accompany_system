from __future__ import annotations

from typing import Literal


FamilyRole = Literal["owner", "editor", "viewer"]


def can_manage_members(role: FamilyRole) -> bool:
    return role == "owner"


def can_write_family_data(role: FamilyRole) -> bool:
    return role in {"owner", "editor"}

