from __future__ import annotations

import uuid
from dataclasses import dataclass, field


def stable_id(*parts: str) -> str:
    raw = "::".join(part.strip() for part in parts if part is not None)
    return uuid.uuid5(uuid.NAMESPACE_URL, raw).hex


@dataclass(frozen=True)
class Person:
    id: str
    family_id: str = "local"
    full_name: str = ""
    kind: str = "family"
    nicknames: list[str] = field(default_factory=list)
    gender: str = ""
    birth_date: str = ""
    address_terms: dict = field(default_factory=dict)
    traits: list[str] = field(default_factory=list)
    speech_style: list[str] = field(default_factory=list)
    habits: list[str] = field(default_factory=list)
    interests: list[str] = field(default_factory=list)
    experiences: dict = field(default_factory=dict)
    knowledge_boundaries: dict = field(default_factory=dict)
    topic_boundaries: dict = field(default_factory=dict)
    legacy_family_profile_id: str = ""
    legacy_persona_id: str = ""

    def aliases(self) -> list[str]:
        values = [self.id, self.full_name, *self.nicknames]
        return [value for value in dict.fromkeys(values) if value]


@dataclass(frozen=True)
class Relationship:
    family_id: str
    from_person_id: str
    to_person_id: str
    relation_type: str
    display_label: str
    inverse_relation_type: str = ""
    inverse_display_label: str = ""
    confidence: float = 1.0
    source: str = "legacy"
    notes: str = ""
    id: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            object.__setattr__(
                self,
                "id",
                stable_id(
                    self.family_id,
                    self.from_person_id,
                    self.to_person_id,
                    self.relation_type,
                    self.display_label,
                ),
            )

    def inverse(self) -> "Relationship":
        return Relationship(
            id=stable_id(self.family_id, self.to_person_id, self.from_person_id, self.inverse_relation_type, self.inverse_display_label),
            family_id=self.family_id,
            from_person_id=self.to_person_id,
            to_person_id=self.from_person_id,
            relation_type=self.inverse_relation_type or "related",
            display_label=self.inverse_display_label or "亲人",
            inverse_relation_type=self.relation_type,
            inverse_display_label=self.display_label,
            confidence=self.confidence,
            source=self.source,
            notes=self.notes,
        )


@dataclass(frozen=True)
class PersonaRole:
    id: str
    family_id: str
    person_id: str
    role_label: str
    appellation_to_elder: str = ""
    can_speak_as_person: bool = True
    voice_profile_id: str = ""
    comfort_style: list[str] = field(default_factory=list)
    mood_preference: dict = field(default_factory=dict)
    sensitivity_map: dict = field(default_factory=dict)
    legacy_persona_id: str = ""
