from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any, Literal, Protocol
from urllib import request as urlrequest
from urllib.error import HTTPError
from uuid import uuid4

from engine.family import normalize_family_relation

FamilyRole = Literal["owner", "editor", "viewer"]


class FamilyPermissionError(PermissionError):
    """Raised when the current user cannot access a family resource."""


class FamilyNotFoundError(LookupError):
    """Raised when a family or family-scoped record cannot be found."""


class CloudRepository(Protocol):
    def create_family(self, *, name: str, user_id: str) -> dict:
        ...

    def get_current_family(self, *, user_id: str) -> dict:
        ...

    def add_member(self, *, family_id: str, user_id: str, role: FamilyRole) -> dict:
        ...

    def get_elder_current(self, *, family_id: str, user_id: str) -> dict:
        ...

    def upsert_elder_current(self, *, family_id: str, user_id: str, payload: dict) -> dict:
        ...

    def list_family_profiles(self, *, family_id: str, user_id: str) -> list[dict]:
        ...

    def create_family_profile(self, *, family_id: str, user_id: str, payload: dict) -> dict:
        ...

    def update_family_profile(
        self,
        *,
        family_id: str,
        user_id: str,
        profile_id: str,
        payload: dict,
    ) -> dict:
        ...

    def delete_family_profile(self, *, family_id: str, user_id: str, profile_id: str) -> None:
        ...

    def list_memories(self, *, family_id: str, user_id: str) -> list[dict]:
        ...

    def create_memory(self, *, family_id: str, user_id: str, payload: dict) -> dict:
        ...

    def update_memory(self, *, family_id: str, user_id: str, memory_id: str, payload: dict) -> dict:
        ...

    def delete_memory(self, *, family_id: str, user_id: str, memory_id: str) -> None:
        ...

    def list_personas(self, *, family_id: str, user_id: str) -> list[dict]:
        ...

    def create_persona(self, *, family_id: str, user_id: str, payload: dict) -> dict:
        ...

    def update_persona(self, *, family_id: str, user_id: str, persona_id: str, payload: dict) -> dict:
        ...

    def create_voice_sample_upload_intent(
        self,
        *,
        family_id: str,
        user_id: str,
        filename: str,
        sample_source: str,
    ) -> dict:
        ...

    def list_voice_samples(self, *, family_id: str, user_id: str) -> list[dict]:
        ...

    def list_voice_profiles(self, *, family_id: str, user_id: str) -> list[dict]:
        ...

    def create_voice_profile(self, *, family_id: str, user_id: str, payload: dict) -> dict:
        ...


class InMemoryCloudRepository:
    """Deterministic cloud repository used for local API wiring and tests."""

    def __init__(self) -> None:
        self._families: dict[str, dict] = {}
        self._memberships: dict[str, dict] = {}
        self._elders: dict[str, dict] = {}
        self._family_profiles: dict[str, dict] = {}
        self._memories: dict[str, dict] = {}
        self._personas: dict[str, dict] = {}
        self._voice_samples: dict[str, dict] = {}
        self._voice_profiles: dict[str, dict] = {}

    def create_family(self, *, name: str, user_id: str) -> dict:
        family = {"id": uuid4().hex, "name": name.strip() or "我的家庭", "created_by": user_id}
        self._families[family["id"]] = family
        self.add_member(family_id=family["id"], user_id=user_id, role="owner")
        return dict(family)

    def get_current_family(self, *, user_id: str) -> dict:
        memberships = [
            item for item in self._memberships.values() if item["user_id"] == user_id
        ]
        if not memberships:
            raise FamilyNotFoundError("Current user has no family space.")
        membership = sorted(memberships, key=lambda item: item["created_at"])[0]
        family = self._families.get(membership["family_id"])
        if not family:
            raise FamilyNotFoundError("Family space not found.")
        return {"family": dict(family), "membership": dict(membership)}

    def add_member(self, *, family_id: str, user_id: str, role: FamilyRole) -> dict:
        if family_id not in self._families:
            raise FamilyNotFoundError("Family space not found.")
        membership = {
            "id": uuid4().hex,
            "family_id": family_id,
            "user_id": user_id,
            "role": role,
            "created_at": str(len(self._memberships)).zfill(8),
        }
        self._memberships[f"{family_id}:{user_id}"] = membership
        return dict(membership)

    def get_elder_current(self, *, family_id: str, user_id: str) -> dict:
        self._require_member(family_id, user_id)
        return dict(self._elders.get(family_id, {}))

    def upsert_elder_current(self, *, family_id: str, user_id: str, payload: dict) -> dict:
        self._require_editor(family_id, user_id)
        existing = self._elders.get(family_id, {})
        elder = self._with_family_fields({**existing, **payload}, family_id, user_id)
        elder.setdefault("id", uuid4().hex)
        self._elders[family_id] = elder
        return dict(elder)

    def list_family_profiles(self, *, family_id: str, user_id: str) -> list[dict]:
        self._require_member(family_id, user_id)
        return self._list_family_records(self._family_profiles, family_id)

    def create_family_profile(self, *, family_id: str, user_id: str, payload: dict) -> dict:
        self._require_editor(family_id, user_id)
        profile = self._with_family_fields(payload, family_id, user_id)
        profile["id"] = profile.get("id") or uuid4().hex
        profile["relation"] = normalize_family_relation(
            str(profile.get("relation", "")),
            str(profile.get("gender", "")),
        )
        self._family_profiles[profile["id"]] = profile
        return dict(profile)

    def update_family_profile(
        self,
        *,
        family_id: str,
        user_id: str,
        profile_id: str,
        payload: dict,
    ) -> dict:
        self._require_editor(family_id, user_id)
        existing = self._get_family_record(self._family_profiles, family_id, profile_id)
        updated = self._with_family_fields({**existing, **payload}, family_id, user_id)
        updated["id"] = profile_id
        updated["relation"] = normalize_family_relation(
            str(updated.get("relation", "")),
            str(updated.get("gender", "")),
        )
        self._family_profiles[profile_id] = updated
        return dict(updated)

    def delete_family_profile(self, *, family_id: str, user_id: str, profile_id: str) -> None:
        self._require_editor(family_id, user_id)
        self._get_family_record(self._family_profiles, family_id, profile_id)
        del self._family_profiles[profile_id]

    def list_memories(self, *, family_id: str, user_id: str) -> list[dict]:
        self._require_member(family_id, user_id)
        return self._list_family_records(self._memories, family_id)

    def create_memory(self, *, family_id: str, user_id: str, payload: dict) -> dict:
        self._require_editor(family_id, user_id)
        memory = self._with_family_fields(payload, family_id, user_id)
        memory["id"] = memory.get("id") or uuid4().hex
        self._memories[memory["id"]] = memory
        return dict(memory)

    def update_memory(self, *, family_id: str, user_id: str, memory_id: str, payload: dict) -> dict:
        self._require_editor(family_id, user_id)
        existing = self._get_family_record(self._memories, family_id, memory_id)
        updated = self._with_family_fields({**existing, **payload}, family_id, user_id)
        updated["id"] = memory_id
        self._memories[memory_id] = updated
        return dict(updated)

    def delete_memory(self, *, family_id: str, user_id: str, memory_id: str) -> None:
        self._require_editor(family_id, user_id)
        self._get_family_record(self._memories, family_id, memory_id)
        del self._memories[memory_id]

    def list_personas(self, *, family_id: str, user_id: str) -> list[dict]:
        self._require_member(family_id, user_id)
        return self._list_family_records(self._personas, family_id)

    def create_persona(self, *, family_id: str, user_id: str, payload: dict) -> dict:
        self._require_editor(family_id, user_id)
        persona = self._with_family_fields(payload, family_id, user_id)
        persona["id"] = persona.get("id") or uuid4().hex
        self._personas[persona["id"]] = persona
        return dict(persona)

    def update_persona(self, *, family_id: str, user_id: str, persona_id: str, payload: dict) -> dict:
        self._require_editor(family_id, user_id)
        existing = self._get_family_record(self._personas, family_id, persona_id)
        updated = self._with_family_fields({**existing, **payload}, family_id, user_id)
        updated["id"] = persona_id
        self._personas[persona_id] = updated
        return dict(updated)

    def create_voice_sample_upload_intent(
        self,
        *,
        family_id: str,
        user_id: str,
        filename: str,
        sample_source: str,
    ) -> dict:
        self._require_editor(family_id, user_id)
        sample_id = str(uuid4())
        storage_path = f"voice-samples/{family_id}/{user_id}/{sample_id}{_safe_audio_extension(filename)}"
        sample = {
            "id": sample_id,
            "family_id": family_id,
            "voice_profile_id": None,
            "storage_path": storage_path,
            "bucket": "voice-samples",
            "sample_source": sample_source or "upload",
            "created_by": user_id,
            "status": "pending_upload",
        }
        self._voice_samples[sample_id] = sample
        return dict(sample)

    def list_voice_samples(self, *, family_id: str, user_id: str) -> list[dict]:
        self._require_member(family_id, user_id)
        return self._list_family_records(self._voice_samples, family_id)

    def list_voice_profiles(self, *, family_id: str, user_id: str) -> list[dict]:
        self._require_member(family_id, user_id)
        return self._list_family_records(self._voice_profiles, family_id)

    def create_voice_profile(self, *, family_id: str, user_id: str, payload: dict) -> dict:
        self._require_editor(family_id, user_id)
        sample_ids = list(payload.get("sample_ids") or [])
        samples = [self._get_family_record(self._voice_samples, family_id, sample_id) for sample_id in sample_ids]
        if not samples:
            raise FamilyNotFoundError("Voice sample not found.")
        if any(sample.get("created_by") != user_id for sample in samples):
            raise FamilyPermissionError("Users can only clone their own voice samples.")

        profile_id = uuid4().hex
        profile = self._with_family_fields(payload, family_id, user_id)
        profile.pop("sample_ids", None)
        profile["id"] = profile_id
        profile["created_by"] = user_id
        profile.setdefault("status", "ready")
        self._voice_profiles[profile_id] = profile

        for sample in samples:
            sample["voice_profile_id"] = profile_id
            sample["status"] = "ready"
        return dict(profile)

    def _role_for(self, family_id: str, user_id: str) -> FamilyRole | None:
        membership = self._memberships.get(f"{family_id}:{user_id}")
        return membership["role"] if membership else None

    def _require_member(self, family_id: str, user_id: str) -> FamilyRole:
        if family_id not in self._families:
            raise FamilyNotFoundError("Family space not found.")
        role = self._role_for(family_id, user_id)
        if role is None:
            raise FamilyPermissionError("Current user is not a family member.")
        return role

    def _require_editor(self, family_id: str, user_id: str) -> FamilyRole:
        role = self._require_member(family_id, user_id)
        if role not in {"owner", "editor"}:
            raise FamilyPermissionError("Current user cannot write family data.")
        return role

    @staticmethod
    def _with_family_fields(payload: dict, family_id: str, user_id: str) -> dict:
        item = dict(payload)
        item["family_id"] = family_id
        item["updated_by"] = user_id
        return item

    @staticmethod
    def _list_family_records(records: dict[str, dict], family_id: str) -> list[dict]:
        return [dict(item) for item in records.values() if item.get("family_id") == family_id]

    @staticmethod
    def _get_family_record(records: dict[str, dict], family_id: str, record_id: str) -> dict:
        record = records.get(record_id)
        if not record or record.get("family_id") != family_id:
            raise FamilyNotFoundError("Family scoped record not found.")
        return record


@dataclass(frozen=True)
class SupabaseConfig:
    url: str
    service_role_key: str

    @classmethod
    def from_env(cls) -> "SupabaseConfig | None":
        url = os.getenv("SUPABASE_URL") or os.getenv("NEXT_PUBLIC_SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        if not url or not key:
            return None
        return cls(url=url.rstrip("/"), service_role_key=key)


class SupabaseCloudRepository:
    """Small PostgREST-backed implementation for the productization schema."""

    def __init__(self, config: SupabaseConfig) -> None:
        self._config = config

    def create_family(self, *, name: str, user_id: str) -> dict:
        family = self._request(
            "families",
            method="POST",
            payload={"name": name.strip() or "我的家庭", "created_by": user_id},
        )[0]
        self._request(
            "family_memberships",
            method="POST",
            payload={"family_id": family["id"], "user_id": user_id, "role": "owner"},
        )
        return family

    def get_current_family(self, *, user_id: str) -> dict:
        memberships = self._request(
            f"family_memberships?user_id=eq.{user_id}&select=*",
            method="GET",
        )
        if not memberships:
            raise FamilyNotFoundError("Current user has no family space.")
        membership = memberships[0]
        families = self._request(f"families?id=eq.{membership['family_id']}&select=*", method="GET")
        if not families:
            raise FamilyNotFoundError("Family space not found.")
        return {"family": families[0], "membership": membership}

    def add_member(self, *, family_id: str, user_id: str, role: FamilyRole) -> dict:
        return self._request(
            "family_memberships",
            method="POST",
            payload={"family_id": family_id, "user_id": user_id, "role": role},
        )[0]

    def get_elder_current(self, *, family_id: str, user_id: str) -> dict:
        self._require_member(family_id, user_id)
        rows = self._request(f"elders?family_id=eq.{family_id}&select=*", method="GET")
        return rows[0] if rows else {}

    def upsert_elder_current(self, *, family_id: str, user_id: str, payload: dict) -> dict:
        self._require_editor(family_id, user_id)
        rows = self._request(f"elders?family_id=eq.{family_id}&select=id", method="GET")
        data = {**payload, "family_id": family_id, "updated_by": user_id}
        if rows:
            return self._request(f"elders?id=eq.{rows[0]['id']}", method="PATCH", payload=data)[0]
        return self._request("elders", method="POST", payload=data)[0]

    def list_family_profiles(self, *, family_id: str, user_id: str) -> list[dict]:
        self._require_member(family_id, user_id)
        return self._request(f"family_profiles?family_id=eq.{family_id}&select=*", method="GET")

    def create_family_profile(self, *, family_id: str, user_id: str, payload: dict) -> dict:
        self._require_editor(family_id, user_id)
        data = {**payload, "family_id": family_id, "updated_by": user_id}
        data["relation"] = normalize_family_relation(str(data.get("relation", "")), str(data.get("gender", "")))
        return self._request("family_profiles", method="POST", payload=data)[0]

    def update_family_profile(self, *, family_id: str, user_id: str, profile_id: str, payload: dict) -> dict:
        self._require_editor(family_id, user_id)
        data = {**payload, "family_id": family_id, "updated_by": user_id}
        if "relation" in data or "gender" in data:
            data["relation"] = normalize_family_relation(str(data.get("relation", "")), str(data.get("gender", "")))
        return self._request(
            f"family_profiles?id=eq.{profile_id}&family_id=eq.{family_id}",
            method="PATCH",
            payload=data,
        )[0]

    def delete_family_profile(self, *, family_id: str, user_id: str, profile_id: str) -> None:
        self._require_editor(family_id, user_id)
        self._request(f"family_profiles?id=eq.{profile_id}&family_id=eq.{family_id}", method="DELETE")

    def list_memories(self, *, family_id: str, user_id: str) -> list[dict]:
        self._require_member(family_id, user_id)
        return self._request(f"memories?family_id=eq.{family_id}&select=*", method="GET")

    def create_memory(self, *, family_id: str, user_id: str, payload: dict) -> dict:
        self._require_editor(family_id, user_id)
        return self._request(
            "memories",
            method="POST",
            payload={**payload, "family_id": family_id, "updated_by": user_id},
        )[0]

    def update_memory(self, *, family_id: str, user_id: str, memory_id: str, payload: dict) -> dict:
        self._require_editor(family_id, user_id)
        return self._request(
            f"memories?id=eq.{memory_id}&family_id=eq.{family_id}",
            method="PATCH",
            payload={**payload, "family_id": family_id, "updated_by": user_id},
        )[0]

    def delete_memory(self, *, family_id: str, user_id: str, memory_id: str) -> None:
        self._require_editor(family_id, user_id)
        self._request(f"memories?id=eq.{memory_id}&family_id=eq.{family_id}", method="DELETE")

    def list_personas(self, *, family_id: str, user_id: str) -> list[dict]:
        self._require_member(family_id, user_id)
        return self._request(f"personas?family_id=eq.{family_id}&select=*", method="GET")

    def create_persona(self, *, family_id: str, user_id: str, payload: dict) -> dict:
        self._require_editor(family_id, user_id)
        return self._request(
            "personas",
            method="POST",
            payload={**payload, "family_id": family_id, "updated_by": user_id},
        )[0]

    def update_persona(self, *, family_id: str, user_id: str, persona_id: str, payload: dict) -> dict:
        self._require_editor(family_id, user_id)
        return self._request(
            f"personas?id=eq.{persona_id}&family_id=eq.{family_id}",
            method="PATCH",
            payload={**payload, "family_id": family_id, "updated_by": user_id},
        )[0]

    def create_voice_sample_upload_intent(
        self,
        *,
        family_id: str,
        user_id: str,
        filename: str,
        sample_source: str,
    ) -> dict:
        self._require_editor(family_id, user_id)
        sample_id = str(uuid4())
        storage_path = f"voice-samples/{family_id}/{user_id}/{sample_id}{_safe_audio_extension(filename)}"
        return self._request(
            "voice_samples",
            method="POST",
            payload={
                "id": sample_id,
                "family_id": family_id,
                "storage_path": storage_path,
                "sample_source": sample_source or "upload",
                "created_by": user_id,
                "status": "pending_upload",
            },
        )[0] | {"bucket": "voice-samples"}

    def list_voice_samples(self, *, family_id: str, user_id: str) -> list[dict]:
        self._require_member(family_id, user_id)
        return self._request(f"voice_samples?family_id=eq.{family_id}&select=*", method="GET")

    def list_voice_profiles(self, *, family_id: str, user_id: str) -> list[dict]:
        self._require_member(family_id, user_id)
        return self._request(f"voice_profiles?family_id=eq.{family_id}&select=*", method="GET")

    def create_voice_profile(self, *, family_id: str, user_id: str, payload: dict) -> dict:
        self._require_editor(family_id, user_id)
        sample_ids = list(payload.get("sample_ids") or [])
        if not sample_ids:
            raise FamilyNotFoundError("Voice sample not found.")
        quoted_ids = ",".join(sample_ids)
        samples = self._request(
            f"voice_samples?family_id=eq.{family_id}&id=in.({quoted_ids})&select=*",
            method="GET",
        )
        if len(samples) != len(sample_ids):
            raise FamilyNotFoundError("Voice sample not found.")
        if any(sample.get("created_by") != user_id for sample in samples):
            raise FamilyPermissionError("Users can only clone their own voice samples.")

        data = dict(payload)
        data.pop("sample_ids", None)
        data["family_id"] = family_id
        data["created_by"] = user_id
        profile = self._request("voice_profiles", method="POST", payload=data)[0]
        self._request(
            f"voice_samples?family_id=eq.{family_id}&id=in.({quoted_ids})",
            method="PATCH",
            payload={"voice_profile_id": profile["id"], "status": profile.get("status", "ready")},
        )
        return profile

    def _require_member(self, family_id: str, user_id: str) -> FamilyRole:
        rows = self._request(
            f"family_memberships?family_id=eq.{family_id}&user_id=eq.{user_id}&select=role",
            method="GET",
        )
        if not rows:
            raise FamilyPermissionError("Current user is not a family member.")
        return rows[0]["role"]

    def _require_editor(self, family_id: str, user_id: str) -> FamilyRole:
        role = self._require_member(family_id, user_id)
        if role not in {"owner", "editor"}:
            raise FamilyPermissionError("Current user cannot write family data.")
        return role

    def _request(self, path: str, *, method: str, payload: dict | None = None) -> Any:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        req = urlrequest.Request(
            f"{self._config.url}/rest/v1/{path}",
            data=body,
            method=method,
            headers={
                "apikey": self._config.service_role_key,
                "Authorization": f"Bearer {self._config.service_role_key}",
                "Content-Type": "application/json",
                "Prefer": "return=representation",
            },
        )
        try:
            with urlrequest.urlopen(req, timeout=10) as response:
                raw = response.read().decode("utf-8")
        except HTTPError as exc:
            if exc.code in {401, 403}:
                raise FamilyPermissionError("Supabase rejected the request.") from exc
            if exc.code == 404:
                raise FamilyNotFoundError("Supabase resource not found.") from exc
            raise
        return json.loads(raw or "[]")


_cloud_repository: CloudRepository | None = None


def get_cloud_repository() -> CloudRepository:
    global _cloud_repository
    if _cloud_repository is not None:
        return _cloud_repository

    config = SupabaseConfig.from_env()
    _cloud_repository = SupabaseCloudRepository(config) if config else InMemoryCloudRepository()
    return _cloud_repository


def _safe_audio_extension(filename: str) -> str:
    match = re.search(r"\.([a-zA-Z0-9]+)$", filename or "")
    extension = f".{match.group(1).lower()}" if match else ".webm"
    return extension if extension in {".wav", ".mp3", ".m4a", ".webm", ".ogg"} else ".webm"
