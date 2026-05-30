from __future__ import annotations

import importlib
import os
from pathlib import Path

import pytest


def test_postgres_schema_defines_cloud_tables_and_indexes():
    schema = Path("productization/postgres_schema.sql").read_text(encoding="utf-8")

    for table in [
        "users",
        "sms_codes",
        "families",
        "family_memberships",
        "elders",
        "family_profiles",
        "personas",
        "memories",
        "voice_profiles",
        "voice_samples",
        "chat_sessions",
        "chat_messages",
    ]:
        assert f"CREATE TABLE IF NOT EXISTS {table}" in schema

    for index in [
        "idx_family_memberships_user",
        "idx_family_memberships_family",
        "idx_elders_family",
        "idx_family_profiles_family",
        "idx_personas_family",
        "idx_memories_family",
        "idx_voice_profiles_family",
        "idx_voice_samples_family",
        "idx_chat_messages_session",
    ]:
        assert f"CREATE INDEX IF NOT EXISTS {index}" in schema


def test_cloud_repository_factory_prefers_database_url(monkeypatch):
    import productization.cloud_repository as cloud_repository

    class FakePostgresCloudRepository:
        def __init__(self, database_url: str) -> None:
            self.database_url = database_url
            self.init_called = False

        def init_schema(self) -> None:
            self.init_called = True

    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@example.test:5432/companion")
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("NEXT_PUBLIC_SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.setattr(cloud_repository, "_cloud_repository", None)
    monkeypatch.setattr(cloud_repository, "PostgresCloudRepository", FakePostgresCloudRepository)

    repo = cloud_repository.get_cloud_repository()

    assert isinstance(repo, FakePostgresCloudRepository)
    assert repo.database_url == "postgresql://user:pass@example.test:5432/companion"
    assert repo.init_called is True


@pytest.mark.skipif(
    not os.getenv("POSTGRES_TEST_DATABASE_URL"),
    reason="POSTGRES_TEST_DATABASE_URL is not configured.",
)
def test_postgres_cloud_repository_persists_family_data_and_permissions():
    from productization.cloud_repository import FamilyPermissionError
    from productization.postgres_repository import PostgresCloudRepository

    repo = PostgresCloudRepository(os.environ["POSTGRES_TEST_DATABASE_URL"])
    repo.init_schema()
    repo.clear_all_data_for_tests()

    family = repo.create_family(name="宋家", user_id="owner")
    repo.add_member(family_id=family["id"], user_id="editor", role="editor")
    repo.add_member(family_id=family["id"], user_id="viewer", role="viewer")
    other_family = repo.create_family(name="刘家", user_id="other-owner")

    elder = repo.upsert_elder_current(
        family_id=family["id"],
        user_id="editor",
        payload={"full_name": "宋桂兰", "preferences": ["听秦腔"]},
    )
    profile = repo.create_family_profile(
        family_id=family["id"],
        user_id="editor",
        payload={"name": "小明", "gender": "男", "relation": "子女"},
    )
    memory = repo.create_memory(
        family_id=family["id"],
        user_id="editor",
        payload={"content": "去年中秋一起赏月。", "emotion_tags": ["开心"]},
    )
    persona = repo.create_persona(
        family_id=family["id"],
        user_id="editor",
        payload={"role_label": "儿子小明", "relation": "子女", "appellation": "妈"},
    )
    repo.create_family_profile(
        family_id=other_family["id"],
        user_id="other-owner",
        payload={"name": "小红", "relation": "女儿"},
    )

    assert repo.get_current_family(user_id="owner")["family"]["id"] == family["id"]
    assert elder["preferences"] == ["听秦腔"]
    assert repo.get_elder_current(family_id=family["id"], user_id="viewer")["full_name"] == "宋桂兰"
    assert repo.list_family_profiles(family_id=family["id"], user_id="viewer")[0]["relation"] == "儿子"
    assert repo.list_memories(family_id=family["id"], user_id="viewer")[0]["id"] == memory["id"]
    assert repo.list_personas(family_id=family["id"], user_id="viewer")[0]["id"] == persona["id"]
    assert repo.list_family_profiles(family_id=other_family["id"], user_id="other-owner")[0]["name"] == "小红"

    updated = repo.update_family_profile(
        family_id=family["id"],
        user_id="owner",
        profile_id=profile["id"],
        payload={"preferences": ["做饭"]},
    )
    assert updated["preferences"] == ["做饭"]

    with pytest.raises(FamilyPermissionError):
        repo.create_memory(family_id=family["id"], user_id="viewer", payload={"content": "viewer cannot write"})

    with pytest.raises(FamilyPermissionError):
        repo.list_memories(family_id=family["id"], user_id="outsider")

    repo.delete_memory(family_id=family["id"], user_id="owner", memory_id=memory["id"])
    assert repo.list_memories(family_id=family["id"], user_id="owner") == []
