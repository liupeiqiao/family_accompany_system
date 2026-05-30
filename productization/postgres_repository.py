from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from engine.family import normalize_family_relation

from .cloud_repository import FamilyNotFoundError, FamilyPermissionError, FamilyRole, _safe_audio_extension


JSON_FIELDS = {
    "personality",
    "preferences",
    "habits",
    "health_notes",
    "speech_traits",
    "life_experiences",
    "important_memories",
    "relations",
    "speech_style",
    "comfort_style",
    "topic_affinity",
    "sensitivity_map",
    "family_members",
    "emotion_tags",
    "topic_tags",
}

TABLE_FIELDS = {
    "elders": {
        "full_name",
        "gender",
        "personality",
        "preferences",
        "habits",
        "health_notes",
        "speech_traits",
        "life_experiences",
        "important_memories",
        "notes",
        "created_by",
        "updated_by",
    },
    "family_profiles": {
        "name",
        "gender",
        "relation",
        "personality",
        "preferences",
        "habits",
        "notes",
        "relations",
        "created_by",
        "updated_by",
    },
    "personas": {
        "role_label",
        "relation",
        "appellation",
        "personality",
        "speech_style",
        "comfort_style",
        "mood_preference",
        "topic_affinity",
        "sensitivity_map",
        "created_by",
        "updated_by",
    },
    "memories": {
        "content",
        "memory_type",
        "subject",
        "family_members",
        "emotion_tags",
        "topic_tags",
        "intimacy_weight",
        "created_by",
        "updated_by",
    },
    "voice_profiles": {
        "display_name",
        "provider",
        "provider_voice_id",
        "status",
        "consent_confirmed",
        "sample_source",
        "demo_audio_url",
        "voice_type",
        "created_by",
        "updated_by",
    },
}


class PostgresCloudRepository:
    """PostgreSQL-backed implementation of the synchronous CloudRepository protocol."""

    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    def init_schema(self) -> None:
        schema_path = Path(__file__).with_name("postgres_schema.sql")
        with self._connect() as conn:
            conn.execute(schema_path.read_text(encoding="utf-8"))

    def clear_all_data_for_tests(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                TRUNCATE TABLE
                    chat_messages,
                    chat_sessions,
                    voice_samples,
                    voice_profiles,
                    memories,
                    personas,
                    family_profiles,
                    elders,
                    family_memberships,
                    families,
                    sms_codes,
                    users
                RESTART IDENTITY CASCADE
                """
            )

    def create_family(self, *, name: str, user_id: str) -> dict:
        family = self._fetch_one(
            """
            INSERT INTO families (name, created_by)
            VALUES (%s, %s)
            RETURNING *
            """,
            (name.strip() or "我的家庭", user_id),
        )
        self.add_member(family_id=family["id"], user_id=user_id, role="owner")
        return family

    def get_current_family(self, *, user_id: str) -> dict:
        membership = self._fetch_one(
            """
            SELECT *
            FROM family_memberships
            WHERE user_id = %s
            ORDER BY created_at ASC
            LIMIT 1
            """,
            (user_id,),
            required=False,
        )
        if not membership:
            raise FamilyNotFoundError("Current user has no family space.")
        family = self._fetch_one("SELECT * FROM families WHERE id = %s", (membership["family_id"],), required=False)
        if not family:
            raise FamilyNotFoundError("Family space not found.")
        return {"family": family, "membership": membership}

    def add_member(self, *, family_id: str, user_id: str, role: FamilyRole) -> dict:
        if not self._family_exists(family_id):
            raise FamilyNotFoundError("Family space not found.")
        return self._fetch_one(
            """
            INSERT INTO family_memberships (family_id, user_id, role)
            VALUES (%s, %s, %s)
            ON CONFLICT (family_id, user_id)
            DO UPDATE SET role = EXCLUDED.role
            RETURNING *
            """,
            (family_id, user_id, role),
        )

    def get_elder_current(self, *, family_id: str, user_id: str) -> dict:
        self._require_member(family_id, user_id)
        elder = self._fetch_one("SELECT * FROM elders WHERE family_id = %s", (family_id,), required=False)
        return elder or {}

    def upsert_elder_current(self, *, family_id: str, user_id: str, payload: dict) -> dict:
        self._require_editor(family_id, user_id)
        data = self._record_payload("elders", payload, user_id=user_id, creating=True)
        data["family_id"] = family_id
        return self._upsert_by_family("elders", family_id, data)

    def list_family_profiles(self, *, family_id: str, user_id: str) -> list[dict]:
        self._require_member(family_id, user_id)
        return self._fetch_all("SELECT * FROM family_profiles WHERE family_id = %s ORDER BY created_at ASC", (family_id,))

    def create_family_profile(self, *, family_id: str, user_id: str, payload: dict) -> dict:
        self._require_editor(family_id, user_id)
        data = self._record_payload("family_profiles", payload, user_id=user_id, creating=True)
        data["relation"] = normalize_family_relation(str(data.get("relation", "")), str(data.get("gender", "")))
        return self._insert_family_record("family_profiles", family_id, data)

    def update_family_profile(self, *, family_id: str, user_id: str, profile_id: str, payload: dict) -> dict:
        self._require_editor(family_id, user_id)
        existing = self._get_family_record("family_profiles", family_id, profile_id)
        data = self._record_payload("family_profiles", {**existing, **payload}, user_id=user_id, creating=False)
        data["relation"] = normalize_family_relation(str(data.get("relation", "")), str(data.get("gender", "")))
        return self._update_family_record("family_profiles", family_id, profile_id, data)

    def delete_family_profile(self, *, family_id: str, user_id: str, profile_id: str) -> None:
        self._require_editor(family_id, user_id)
        self._delete_family_record("family_profiles", family_id, profile_id)

    def list_memories(self, *, family_id: str, user_id: str) -> list[dict]:
        self._require_member(family_id, user_id)
        return self._fetch_all("SELECT * FROM memories WHERE family_id = %s ORDER BY created_at ASC", (family_id,))

    def create_memory(self, *, family_id: str, user_id: str, payload: dict) -> dict:
        self._require_editor(family_id, user_id)
        data = self._record_payload("memories", payload, user_id=user_id, creating=True)
        return self._insert_family_record("memories", family_id, data)

    def update_memory(self, *, family_id: str, user_id: str, memory_id: str, payload: dict) -> dict:
        self._require_editor(family_id, user_id)
        existing = self._get_family_record("memories", family_id, memory_id)
        data = self._record_payload("memories", {**existing, **payload}, user_id=user_id, creating=False)
        return self._update_family_record("memories", family_id, memory_id, data)

    def delete_memory(self, *, family_id: str, user_id: str, memory_id: str) -> None:
        self._require_editor(family_id, user_id)
        self._delete_family_record("memories", family_id, memory_id)

    def list_personas(self, *, family_id: str, user_id: str) -> list[dict]:
        self._require_member(family_id, user_id)
        return self._fetch_all("SELECT * FROM personas WHERE family_id = %s ORDER BY created_at ASC", (family_id,))

    def create_persona(self, *, family_id: str, user_id: str, payload: dict) -> dict:
        self._require_editor(family_id, user_id)
        data = self._record_payload("personas", payload, user_id=user_id, creating=True)
        return self._insert_family_record("personas", family_id, data)

    def update_persona(self, *, family_id: str, user_id: str, persona_id: str, payload: dict) -> dict:
        self._require_editor(family_id, user_id)
        existing = self._get_family_record("personas", family_id, persona_id)
        data = self._record_payload("personas", {**existing, **payload}, user_id=user_id, creating=False)
        return self._update_family_record("personas", family_id, persona_id, data)

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
        return self._fetch_one(
            """
            INSERT INTO voice_samples
                (id, family_id, storage_path, bucket, sample_source, status, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (sample_id, family_id, storage_path, "voice-samples", sample_source or "upload", "pending_upload", user_id),
        )

    def list_voice_samples(self, *, family_id: str, user_id: str) -> list[dict]:
        self._require_member(family_id, user_id)
        return self._fetch_all("SELECT * FROM voice_samples WHERE family_id = %s ORDER BY created_at ASC", (family_id,))

    def list_voice_profiles(self, *, family_id: str, user_id: str) -> list[dict]:
        self._require_member(family_id, user_id)
        return self._fetch_all(
            "SELECT * FROM voice_profiles WHERE family_id = %s AND status <> 'hidden' ORDER BY created_at ASC",
            (family_id,),
        )

    def create_voice_profile(self, *, family_id: str, user_id: str, payload: dict) -> dict:
        self._require_editor(family_id, user_id)
        sample_ids = list(payload.get("sample_ids") or [])
        for sample_id in sample_ids:
            sample = self._get_family_record("voice_samples", family_id, sample_id)
            if sample.get("created_by") != user_id:
                raise FamilyPermissionError("Users can only clone their own voice samples.")

        data = self._record_payload("voice_profiles", payload, user_id=user_id, creating=True)
        profile = self._insert_family_record("voice_profiles", family_id, data)
        if sample_ids:
            self._execute(
                """
                UPDATE voice_samples
                SET voice_profile_id = %s, status = %s
                WHERE family_id = %s AND id = ANY(%s::uuid[])
                """,
                (profile["id"], profile.get("status", "ready"), family_id, sample_ids),
            )
        return profile

    def hide_voice_profile(self, *, family_id: str, user_id: str, profile_id: str) -> None:
        self._require_editor(family_id, user_id)
        self._update_family_record("voice_profiles", family_id, profile_id, {"status": "hidden", "updated_by": user_id})

    def delete_voice_profile(self, *, family_id: str, user_id: str, profile_id: str) -> None:
        self._require_editor(family_id, user_id)
        profile = self._get_family_record("voice_profiles", family_id, profile_id)
        if profile.get("voice_type") in {"preset", "prepaid"}:
            self._execute("DELETE FROM voice_samples WHERE family_id = %s AND voice_profile_id = %s", (family_id, profile_id))
            self._delete_family_record("voice_profiles", family_id, profile_id)
        else:
            self.hide_voice_profile(family_id=family_id, user_id=user_id, profile_id=profile_id)

    def _connect(self):
        return psycopg.connect(self._database_url, row_factory=dict_row)

    def _fetch_one(self, sql: str, params: tuple = (), *, required: bool = True) -> dict:
        with self._connect() as conn:
            row = conn.execute(sql, params).fetchone()
        if not row:
            if required:
                raise FamilyNotFoundError("PostgreSQL resource not found.")
            return {}
        return _serialize_row(row)

    def _fetch_all(self, sql: str, params: tuple = ()) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [_serialize_row(row) for row in rows]

    def _execute(self, sql: str, params: tuple = ()) -> None:
        with self._connect() as conn:
            conn.execute(sql, params)

    def _family_exists(self, family_id: str) -> bool:
        with self._connect() as conn:
            return conn.execute("SELECT 1 FROM families WHERE id = %s", (family_id,)).fetchone() is not None

    def _require_member(self, family_id: str, user_id: str) -> FamilyRole:
        if not self._family_exists(family_id):
            raise FamilyNotFoundError("Family space not found.")
        row = self._fetch_one(
            "SELECT role FROM family_memberships WHERE family_id = %s AND user_id = %s",
            (family_id, user_id),
            required=False,
        )
        if not row:
            raise FamilyPermissionError("Current user is not a family member.")
        return row["role"]

    def _require_editor(self, family_id: str, user_id: str) -> FamilyRole:
        role = self._require_member(family_id, user_id)
        if role not in {"owner", "editor"}:
            raise FamilyPermissionError("Current user cannot write family data.")
        return role

    def _get_family_record(self, table: str, family_id: str, record_id: str) -> dict:
        row = self._fetch_one(f"SELECT * FROM {table} WHERE family_id = %s AND id = %s", (family_id, record_id), required=False)
        if not row:
            raise FamilyNotFoundError("Family scoped record not found.")
        return row

    def _insert_family_record(self, table: str, family_id: str, data: dict) -> dict:
        data = {**data, "family_id": family_id}
        columns = list(data)
        placeholders = ", ".join(["%s"] * len(columns))
        return self._fetch_one(
            f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders}) RETURNING *",
            tuple(_adapt_value(column, data[column]) for column in columns),
        )

    def _update_family_record(self, table: str, family_id: str, record_id: str, data: dict) -> dict:
        if not data:
            return self._get_family_record(table, family_id, record_id)
        data = {**data, "updated_at": datetime.utcnow()}
        columns = list(data)
        set_clause = ", ".join(f"{column} = %s" for column in columns)
        row = self._fetch_one(
            f"UPDATE {table} SET {set_clause} WHERE family_id = %s AND id = %s RETURNING *",
            tuple(_adapt_value(column, data[column]) for column in columns) + (family_id, record_id),
            required=False,
        )
        if not row:
            raise FamilyNotFoundError("Family scoped record not found.")
        return row

    def _delete_family_record(self, table: str, family_id: str, record_id: str) -> None:
        with self._connect() as conn:
            deleted = conn.execute(
                f"DELETE FROM {table} WHERE family_id = %s AND id = %s RETURNING id",
                (family_id, record_id),
            ).fetchone()
        if not deleted:
            raise FamilyNotFoundError("Family scoped record not found.")

    def _upsert_by_family(self, table: str, family_id: str, data: dict) -> dict:
        columns = list(data)
        insert_placeholders = ", ".join(["%s"] * len(columns))
        update_columns = [column for column in columns if column != "family_id"]
        update_clause = ", ".join(f"{column} = EXCLUDED.{column}" for column in update_columns)
        return self._fetch_one(
            f"""
            INSERT INTO {table} ({', '.join(columns)})
            VALUES ({insert_placeholders})
            ON CONFLICT (family_id)
            DO UPDATE SET {update_clause}, updated_at = now()
            RETURNING *
            """,
            tuple(_adapt_value(column, data[column]) for column in columns),
        )

    @staticmethod
    def _record_payload(table: str, payload: dict, *, user_id: str, creating: bool) -> dict:
        allowed = TABLE_FIELDS[table]
        data = {key: value for key, value in dict(payload).items() if key in allowed}
        data["updated_by"] = user_id
        if creating:
            data["created_by"] = user_id
        return data


def _adapt_value(column: str, value: Any) -> Any:
    if column in JSON_FIELDS:
        return Jsonb(value if value is not None else ([] if column != "sensitivity_map" else {}))
    return value


def _serialize_row(row: dict) -> dict:
    return {key: _serialize_value(value) for key, value in dict(row).items()}


def _serialize_value(value: Any) -> Any:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime | date):
        return value.isoformat()
    return value
