"""RED: Memory section must have a delete-all button."""


def test_source_has_delete_all_memories_button():
    with open("app.py", encoding="utf-8") as f:
        source = f.read()

    assert "btn_clear_all_mem" in source, (
        "记忆区缺少全部删除按钮"
    )


def test_clear_all_memories_works():
    from engine.memory import MemoryUnit, add_memory, get_all_memories, clear_memories

    clear_memories()
    add_memory(MemoryUnit(content="test1", memory_type="事件"))
    add_memory(MemoryUnit(content="test2", memory_type="趣事"))
    assert len(get_all_memories()) == 2

    clear_memories()
    assert len(get_all_memories()) == 0
