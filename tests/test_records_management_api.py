from __future__ import annotations


def test_records_handler_loads_saved_records(tmp_path, monkeypatch):
    from api.handlers import handle_records
    from engine import db

    monkeypatch.chdir(tmp_path)
    db.init_db()
    db.save_persona({"role_label": "son", "relation": "child", "appellation": "mom"})
    db.save_elder({"full_name": "elder", "gender": "female"})
    db.save_family_profile({"name": "ming", "gender": "male", "relation": "son"})
    db.save_memory({"id": "mem-1", "content": "moon festival", "memory_type": "event"})

    result = handle_records()

    assert result.persona["role_label"] == "son"
    assert result.elder_profile["full_name"] == "elder"
    assert result.family_profiles[0]["name"] == "ming"
    assert result.memories[0]["id"] == "mem-1"


def test_records_handler_loads_all_saved_personas_and_elder_profiles(tmp_path, monkeypatch):
    from api.handlers import handle_records
    from engine import db

    monkeypatch.chdir(tmp_path)
    db.init_db()
    db.save_persona({"role_label": "daughter", "relation": "daughter", "appellation": "mom"})
    db.save_persona({"role_label": "son", "relation": "son", "appellation": "mom"})
    db.save_elder({"full_name": "elder-a", "gender": "female"})
    db.save_elder({"full_name": "elder-b", "gender": "male"})

    result = handle_records()

    assert [persona["role_label"] for persona in result.personas] == ["daughter", "son"]
    assert [elder["full_name"] for elder in result.elder_profiles] == ["elder-a", "elder-b"]


def test_import_handler_saves_multiple_personas_and_elder_profiles(tmp_path, monkeypatch):
    from api.handlers import handle_import
    from api.schemas import ImportRequest
    from engine import db

    monkeypatch.chdir(tmp_path)

    result = handle_import(
        ImportRequest(
            family_id="local",
            personas=[
                {"role_label": "daughter", "relation": "daughter", "appellation": "mom"},
                {"role_label": "son", "relation": "son", "appellation": "mom"},
            ],
            elder_profiles=[
                {"full_name": "elder-a", "gender": "female"},
                {"full_name": "elder-b", "gender": "male"},
            ],
        )
    )

    assert result.imported.persona == 2
    assert result.imported.elder_profile == 2
    assert [persona["role_label"] for persona in db.load_all_personas()] == ["daughter", "son"]
    assert [elder["full_name"] for elder in db.load_all_elders()] == ["elder-a", "elder-b"]


def test_delete_memory_handler_removes_saved_memory(tmp_path, monkeypatch):
    from api.handlers import handle_delete_memory
    from engine import db

    monkeypatch.chdir(tmp_path)
    db.init_db()
    db.save_memory({"id": "mem-1", "content": "moon festival"})

    result = handle_delete_memory("mem-1")

    assert result.ok is True
    assert db.load_all_memories() == []


def test_delete_family_profile_handler_removes_saved_profile(tmp_path, monkeypatch):
    from api.handlers import handle_delete_family_profile
    from engine import db

    monkeypatch.chdir(tmp_path)
    db.init_db()
    db.save_family_profile({"name": "ming", "gender": "male", "relation": "son"})

    result = handle_delete_family_profile("ming")

    assert result.ok is True
    assert db.load_all_family_profiles() == []
