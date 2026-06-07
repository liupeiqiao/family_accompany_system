from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class MemoryEventParticipant:
    person_id: str
    role_in_event: str = "participant"
    perspective: str = "heard_about"
    can_use_first_person: bool = False
    can_mention: bool = True


@dataclass
class MemoryEvent:
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    family_id: str = "local"
    title: str = ""
    summary: str = ""
    event_time_text: str = ""
    event_start_at: datetime | None = None
    event_end_at: datetime | None = None
    location: str = ""
    participants: list[MemoryEventParticipant] = field(default_factory=list)
    emotion_tags: list[str] = field(default_factory=list)
    topic_tags: list[str] = field(default_factory=list)
    source_type: str = "imported"
    source_person_id: str = ""
    truth_status: str = "uncertain"
    sensitivity_level: int = 0

    def participant_for(self, person_id: str) -> MemoryEventParticipant | None:
        for participant in self.participants:
            if participant.person_id == person_id:
                return participant
        return None

    def can_use_first_person(self, person_id: str) -> bool:
        participant = self.participant_for(person_id)
        return bool(participant and participant.can_use_first_person)

    def can_mention(self, person_id: str) -> bool:
        participant = self.participant_for(person_id)
        return bool(participant and participant.can_mention)

    def to_prompt_evidence(self, speaker_person_id: str) -> str:
        participant = self.participant_for(speaker_person_id)
        if not participant:
            return ""
        first_person_rule = (
            "可以用第一人称提起"
            if participant.can_use_first_person
            else "只能转述，不能说成自己亲身经历"
        )
        parts = [
            f"事件：{self.title or self.summary}",
            f"内容：{self.summary}",
            f"当前角色视角：{participant.perspective}，{first_person_rule}",
        ]
        if self.event_time_text:
            parts.append(f"时间：{self.event_time_text}")
        if self.location:
            parts.append(f"地点：{self.location}")
        if self.emotion_tags:
            parts.append(f"情绪：{'、'.join(self.emotion_tags)}")
        if self.topic_tags:
            parts.append(f"主题：{'、'.join(self.topic_tags)}")
        parts.append(f"真实性来源：{self.source_type}/{self.truth_status}")
        return "\n".join(parts)


def title_from_summary(summary: str) -> str:
    summary = (summary or "").strip()
    if not summary:
        return ""
    for sep in ("。", "，", ",", "."):
        if sep in summary:
            return summary.split(sep)[0][:30]
    return summary[:30]
