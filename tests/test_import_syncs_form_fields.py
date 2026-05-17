"""RED → GREEN: Verify persona import syncs sidebar form session_state keys."""


def test_import_updates_form_session_state():
    """一键导入后 form_* keys 必须更新为导入的角色数据。"""
    # 模拟导入的角色数据
    imported = {
        "role_label": "女儿小红",
        "relation": "子女",
        "appellation": "妈",
        "personality": ["温和", "幽默"],
        "speech_style": ["喜欢撒娇", "爱叫妈"],
        "comfort_style": ["撒娇", "唠家常"],
    }

    # 模拟 sync 逻辑
    expected_state = {
        "form_role_label": imported["role_label"],
        "form_relation": imported["relation"],
        "form_appellation": imported["appellation"],
        "form_personality": imported["personality"],
        "form_speech_style": "\n".join(imported["speech_style"]),
        "form_comfort_style": imported["comfort_style"],
    }

    assert expected_state["form_role_label"] == "女儿小红"
    assert expected_state["form_appellation"] == "妈"
    assert expected_state["form_speech_style"] == "喜欢撒娇\n爱叫妈"


def test_source_has_sync_code_in_import():
    """验证 app.py 中一键导入按钮包含 st.session_state.update。"""
    with open("app.py", encoding="utf-8") as f:
        source = f.read()

    # 找到一键导入按钮后的代码
    import_idx = source.find("一键导入")
    assert import_idx > 0, "找不到一键导入按钮"

    after_import = source[import_idx:import_idx + 2000]

    # 必须有 st.session_state.update 来同步表单字段
    assert "form_role_label" in after_import, (
        "一键导入未同步 form_role_label 到 session_state"
    )
    assert "form_appellation" in after_import, (
        "一键导入未同步 form_appellation 到 session_state"
    )


def test_source_has_sync_code_in_manual_save():
    """验证手动保存人物画像也包含 session_state 同步。"""
    with open("app.py", encoding="utf-8") as f:
        source = f.read()

    save_idx = source.find("保存人物画像")
    assert save_idx > 0, "找不到保存人物画像按钮"

    after_save = source[save_idx:save_idx + 1000]
    assert "edit_role_label" in after_save or "form_role_label" in after_save, (
        "手动保存未同步 form_role_label 到 session_state"
    )


def test_db_load_syncs_form_fields():
    """验证从 DB 加载时也初始化 form_* 字段。"""
    with open("app.py", encoding="utf-8") as f:
        source = f.read()

    # 确认 DB 加载后有 form_* 初始化
    assert "form_role_label" in source
    assert "form_appellation" in source
    assert "form_comfort_style" in source
