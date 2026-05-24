from __future__ import annotations


def test_fastapi_cloud_family_current_and_create_endpoints(monkeypatch):
    from fastapi.testclient import TestClient

    from api.main import app
    from productization.cloud_repository import InMemoryCloudRepository

    repo = InMemoryCloudRepository()
    monkeypatch.setattr("api.handlers.get_cloud_repository", lambda: repo)

    client = TestClient(app)

    missing = client.get("/api/family/current", headers={"X-User-Id": "u1"})
    assert missing.status_code == 404

    created = client.post(
        "/api/family",
        json={"name": "宋家"},
        headers={"X-User-Id": "u1"},
    )
    assert created.status_code == 200
    assert created.json()["family"]["name"] == "宋家"
    assert created.json()["membership"]["role"] == "owner"

    current = client.get("/api/family/current", headers={"X-User-Id": "u1"})
    assert current.status_code == 200
    assert current.json()["family"]["id"] == created.json()["family"]["id"]


def test_fastapi_cloud_profile_memory_persona_crud_enforces_membership(monkeypatch):
    from fastapi.testclient import TestClient

    from api.main import app
    from productization.cloud_repository import InMemoryCloudRepository

    repo = InMemoryCloudRepository()
    family = repo.create_family(name="宋家", user_id="owner")
    repo.add_member(family_id=family["id"], user_id="editor", role="editor")
    repo.add_member(family_id=family["id"], user_id="viewer", role="viewer")
    monkeypatch.setattr("api.handlers.get_cloud_repository", lambda: repo)

    client = TestClient(app)

    elder = client.put(
        "/api/elders/current",
        json={"family_id": family["id"], "full_name": "宋桂兰"},
        headers={"X-User-Id": "editor"},
    )
    assert elder.status_code == 200
    assert elder.json()["full_name"] == "宋桂兰"

    profile = client.post(
        "/api/family-profiles",
        json={"family_id": family["id"], "name": "小明", "gender": "男", "relation": "子女"},
        headers={"X-User-Id": "editor"},
    )
    assert profile.status_code == 200
    assert profile.json()["relation"] == "儿子"

    memory = client.post(
        "/api/memories",
        json={"family_id": family["id"], "content": "去年中秋一起赏月。"},
        headers={"X-User-Id": "editor"},
    )
    assert memory.status_code == 200
    assert memory.json()["content"] == "去年中秋一起赏月。"

    persona = client.post(
        "/api/personas",
        json={"family_id": family["id"], "role_label": "儿子小明", "relation": "子女"},
        headers={"X-User-Id": "editor"},
    )
    assert persona.status_code == 200

    listed = client.get(
        f"/api/family-profiles?family_id={family['id']}",
        headers={"X-User-Id": "viewer"},
    )
    assert listed.status_code == 200
    assert listed.json()[0]["id"] == profile.json()["id"]

    blocked = client.post(
        "/api/memories",
        json={"family_id": family["id"], "content": "viewer cannot write"},
        headers={"X-User-Id": "viewer"},
    )
    assert blocked.status_code == 403

    outsider = client.get(
        f"/api/personas?family_id={family['id']}",
        headers={"X-User-Id": "outsider"},
    )
    assert outsider.status_code == 403

    updated = client.put(
        f"/api/personas/{persona.json()['id']}",
        json={"family_id": family["id"], "appellation": "妈"},
        headers={"X-User-Id": "owner"},
    )
    assert updated.status_code == 200
    assert updated.json()["appellation"] == "妈"

    deleted = client.delete(
        f"/api/memories/{memory.json()['id']}?family_id={family['id']}",
        headers={"X-User-Id": "owner"},
    )
    assert deleted.status_code == 200
    assert repo.list_memories(family_id=family["id"], user_id="owner") == []
