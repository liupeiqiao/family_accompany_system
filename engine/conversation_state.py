from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ConversationState:
    family_id: str = "local"
    session_id: str = "default"
    elder_person_id: str = ""
    current_persona_role_id: str = ""
    recent_person_ids: list[str] = field(default_factory=list)
    recent_event_ids: list[str] = field(default_factory=list)
    elder_emotion: str = ""
    ongoing_topic: str = ""
    unfinished_topics: list[str] = field(default_factory=list)
    relationship_focus: dict = field(default_factory=dict)
    last_intent: str = ""
    summary: str = ""
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    updated_at: datetime = field(default_factory=datetime.now)

    def update_turn(
        self,
        *,
        current_persona_role_id: str = "",
        mentioned_person_ids: list[str] | None = None,
        event_ids: list[str] | None = None,
        elder_emotion: str = "",
        intent: str = "",
        ongoing_topic: str = "",
        relationship_focus: dict | None = None,
        summary: str = "",
    ) -> None:
        if current_persona_role_id:
            self.current_persona_role_id = current_persona_role_id
        self.recent_person_ids = _merge_recent(self.recent_person_ids, mentioned_person_ids or [])
        self.recent_event_ids = _merge_recent(self.recent_event_ids, event_ids or [])
        self.elder_emotion = elder_emotion or self.elder_emotion
        self.last_intent = intent or self.last_intent
        self.ongoing_topic = ongoing_topic or self.ongoing_topic
        if relationship_focus:
            self.relationship_focus = relationship_focus
        if summary:
            self.summary = summary
        self.updated_at = datetime.now()

    def to_prompt_context(self) -> str:
        lines = ["## 对话连续状态"]
        if self.elder_emotion:
            lines.append(f"- 老人当前情绪：{self.elder_emotion}")
        if self.last_intent:
            lines.append(f"- 最近意图：{self.last_intent}")
        if self.ongoing_topic:
            lines.append(f"- 持续话题：{self.ongoing_topic}")
        if self.unfinished_topics:
            lines.append(f"- 未完成话题：{'、'.join(self.unfinished_topics)}")
        if self.summary:
            lines.append(f"- 会话摘要：{self.summary}")
        if self.relationship_focus:
            relation = self.relationship_focus.get("relation_label", "")
            if relation:
                lines.append(f"- 关系焦点：{relation}")
        if len(lines) == 1:
            lines.append("- 当前是本轮会话的新上下文，优先根据家庭关系和当前输入回应。")
        return "\n".join(lines)


def _merge_recent(existing: list[str], incoming: list[str], limit: int = 8) -> list[str]:
    values = [value for value in [*incoming, *existing] if value]
    return list(dict.fromkeys(values))[:limit]
