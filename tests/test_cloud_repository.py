from __future__ import annotations

import pytest


def test_in_memory_cloud_repository_creates_default_family_with_owner_membership():
    from productization.cloud_repository import InMemoryCloudRepository

    repo = InMemoryCloudRepository()

    family = repo.create_family(name="宋家", user_id="user-owner")
    current = repo.get_current_family(user_id="user-owner")

    assert family["name"] == "宋家"
    assert current["family"]["id"] == family["id"]
    assert current["membership"]["role"] == "owner"


def test_in_memory_cloud_repository_allows_editor_to_write_family_data():
    from productization.cloud_repository import InMemoryCloudRepository

    repo = InMemoryCloudRepository()
    family = repo.create_family(name="宋家", user_id="owner")
    repo.add_member(family_id=family["id"], user_id="editor", role="editor")

    elder = repo.upsert_elder_current(
        family_id=family["id"],
        user_id="editor",
        payload={"full_name": "宋桂兰", "preferences": ["听秦腔"]},
    )
    memory = repo.create_memory(
        family_id=family["id"],
        user_id="editor",
        payload={"content": "去年中秋一起赏月。"},
    )

    assert elder["updated_by"] == "editor"
    assert repo.get_elder_current(family_id=family["id"], user_id="owner")["full_name"] == "宋桂兰"
    assert repo.list_memories(family_id=family["id"], user_id="owner")[0]["id"] == memory["id"]


def test_in_memory_cloud_repository_blocks_viewer_and_non_member_writes():
    from productization.cloud_repository import FamilyPermissionError, InMemoryCloudRepository

    repo = InMemoryCloudRepository()
    family = repo.create_family(name="宋家", user_id="owner")
    repo.add_member(family_id=family["id"], user_id="viewer", role="viewer")

    with pytest.raises(FamilyPermissionError):
        repo.create_family_profile(
            family_id=family["id"],
            user_id="viewer",
            payload={"name": "小明", "relation": "儿子"},
        )

    with pytest.raises(FamilyPermissionError):
        repo.list_family_profiles(family_id=family["id"], user_id="outsider")


def test_in_memory_cloud_repository_crud_keeps_family_data_isolated():
    from productization.cloud_repository import InMemoryCloudRepository

    repo = InMemoryCloudRepository()
    family_a = repo.create_family(name="宋家", user_id="owner-a")
    family_b = repo.create_family(name="刘家", user_id="owner-b")

    profile = repo.create_family_profile(
        family_id=family_a["id"],
        user_id="owner-a",
        payload={"name": "小明", "gender": "男", "relation": "子女"},
    )
    persona = repo.create_persona(
        family_id=family_a["id"],
        user_id="owner-a",
        payload={"role_label": "儿子小明", "relation": "子女", "appellation": "妈"},
    )

    repo.create_family_profile(
        family_id=family_b["id"],
        user_id="owner-b",
        payload={"name": "小红", "relation": "女儿"},
    )

    assert repo.list_family_profiles(family_id=family_a["id"], user_id="owner-a") == [
        {
            **profile,
            "relation": "儿子",
        }
    ]
    assert repo.list_personas(family_id=family_a["id"], user_id="owner-a")[0]["id"] == persona["id"]
    assert repo.list_family_profiles(family_id=family_b["id"], user_id="owner-b")[0]["name"] == "小红"

    updated = repo.update_family_profile(
        family_id=family_a["id"],
        user_id="owner-a",
        profile_id=profile["id"],
        payload={"preferences": ["做饭"]},
    )
    assert updated["preferences"] == ["做饭"]

    repo.delete_family_profile(family_id=family_a["id"], user_id="owner-a", profile_id=profile["id"])
    assert repo.list_family_profiles(family_id=family_a["id"], user_id="owner-a") == []
