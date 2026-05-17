"""Family memory unit and in-memory storage."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class MemoryUnit:
    """一条家庭记忆"""

    content: str
    memory_type: str  # 事件 | 习惯 | 偏好 | 重要日期 | 趣事
    subject: str = ""  # 这条记忆是关于谁的，如 "儿子小明"
    family_members: list[str] = field(default_factory=list)
    emotion_tags: list[str] = field(default_factory=list)
    topic_tags: list[str] = field(default_factory=list)
    intimacy_weight: float = 0.5
    timestamp: datetime | None = None
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    access_count: int = 0
    last_accessed: datetime | None = None


# Session-level memory store (no persistence)
_memory_store: list[MemoryUnit] = []


def add_memory(m: MemoryUnit) -> None:
    if not any(existing.id == m.id for existing in _memory_store):
        _memory_store.append(m)


def remove_memory(memory_id: str) -> None:
    global _memory_store
    _memory_store = [m for m in _memory_store if m.id != memory_id]


def get_all_memories() -> list[MemoryUnit]:
    return list(_memory_store)


def clear_memories() -> None:
    _memory_store.clear()


def memory_count() -> int:
    return len(_memory_store)
