from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from .person import Person, Relationship


@dataclass
class FamilyGraph:
    persons: dict[str, Person] = field(default_factory=dict)
    relationships: list[Relationship] = field(default_factory=list)

    def get_person(self, query: str) -> Person | None:
        query = (query or "").strip()
        if not query:
            return None
        if query in self.persons:
            return self.persons[query]
        for person in self.persons.values():
            if query in person.aliases():
                return person
        for person in self.persons.values():
            if any(query in alias or alias in query for alias in person.aliases() if alias):
                return person
        return None

    def get_relationship(self, from_person: str, to_person: str) -> Relationship | None:
        from_id = self._person_id(from_person)
        to_id = self._person_id(to_person)
        if not from_id or not to_id:
            return None
        for relationship in self.relationships:
            if relationship.from_person_id == from_id and relationship.to_person_id == to_id:
                return relationship
            if relationship.from_person_id == to_id and relationship.to_person_id == from_id:
                return relationship.inverse()
        return None

    def neighbors(self, person: str, relation_type: str | None = None) -> list[Person]:
        person_id = self._person_id(person)
        if not person_id:
            return []
        result: list[Person] = []
        for relationship in self._all_directional_relationships():
            if relationship.from_person_id != person_id:
                continue
            if relation_type and relationship.relation_type != relation_type:
                continue
            neighbor = self.persons.get(relationship.to_person_id)
            if neighbor:
                result.append(neighbor)
        return result

    def path_between(self, from_person: str, to_person: str, max_depth: int = 3) -> list[str]:
        start = self._person_id(from_person)
        target = self._person_id(to_person)
        if not start or not target:
            return []
        queue = deque([(start, [])])
        visited = {start}
        all_relationships = self._all_directional_relationships()
        while queue:
            current, path = queue.popleft()
            if len(path) >= max_depth:
                continue
            for relationship in all_relationships:
                if relationship.from_person_id != current:
                    continue
                if relationship.to_person_id in visited:
                    continue
                line = self._relationship_sentence(relationship)
                next_path = [*path, line]
                if relationship.to_person_id == target:
                    return next_path
                visited.add(relationship.to_person_id)
                queue.append((relationship.to_person_id, next_path))
        return []

    def resolve_mentions(self, text: str) -> list[Person]:
        text = text or ""
        found: list[tuple[int, Person]] = []
        for person in self.persons.values():
            positions = [text.find(alias) for alias in person.aliases() if alias and alias in text]
            if positions:
                found.append((min(positions), person))
        found.sort(key=lambda item: item[0])
        result: list[Person] = []
        seen = set()
        for _, person in found:
            if person.id not in seen:
                result.append(person)
                seen.add(person.id)
        return result

    def build_identity_context(
        self,
        speaker_person: Person | None,
        elder_person: Person | None,
        mentioned_people: list[Person] | None = None,
    ) -> str:
        if not speaker_person or not elder_person:
            return ""
        lines = ["## 家庭身份认知"]
        speaker_to_elder = self.get_relationship(speaker_person.id, elder_person.id)
        if speaker_to_elder:
            lines.append(
                f"- 当前角色：{speaker_person.full_name}，是{elder_person.full_name}的{speaker_to_elder.display_label}。"
            )
        else:
            lines.append(f"- 当前角色：{speaker_person.full_name}。")
        for person in mentioned_people or []:
            if person.id == speaker_person.id:
                continue
            relation = self.get_relationship(person.id, elder_person.id)
            if relation:
                lines.append(f"- {person.full_name}是{elder_person.full_name}的{relation.display_label}。")
            speaker_relation = self.get_relationship(person.id, speaker_person.id)
            if speaker_relation:
                lines.append(f"- {person.full_name}是{speaker_person.full_name}的{speaker_relation.display_label}。")
        lines.append("- 回复时必须保持当前角色身份，不替其他家人承诺、回忆或发言。")
        return "\n".join(lines)

    def relationship_context(self, people: list[Person]) -> str:
        ids = {person.id for person in people}
        lines: list[str] = []
        for relationship in self._all_directional_relationships():
            if relationship.from_person_id in ids or relationship.to_person_id in ids:
                sentence = self._relationship_sentence(relationship)
                if sentence not in lines:
                    lines.append(sentence)
        if not lines:
            return ""
        return "## 家庭关系图\n" + "\n".join(f"- {line}" for line in lines[:8])

    def _person_id(self, query: str) -> str:
        person = self.get_person(query)
        return person.id if person else ""

    def _all_directional_relationships(self) -> list[Relationship]:
        result: list[Relationship] = []
        seen = set()
        for relationship in self.relationships:
            for item in (relationship, relationship.inverse()):
                key = (item.from_person_id, item.to_person_id, item.display_label)
                if key not in seen:
                    result.append(item)
                    seen.add(key)
        return result

    def _relationship_sentence(self, relationship: Relationship) -> str:
        source = self.persons.get(relationship.from_person_id)
        target = self.persons.get(relationship.to_person_id)
        if not source or not target:
            return ""
        return f"{source.full_name}是{target.full_name}的{relationship.display_label}"
