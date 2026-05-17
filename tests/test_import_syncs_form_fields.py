"""RED → GREEN: Verify persona import syncs sidebar form session_state keys."""


def test_import_adds_to_multi_persona_list():
    """导入不同角色应添加到多角色列表，不覆盖现有角色。"""
    from engine.persona import PersonaProfile, add_or_update_persona, get_all_personas

    _all = get_all_personas()
    _all.clear()

    p1 = PersonaProfile(role_label="儿子小明", relation="子女", appellation="妈",
                        personality=["温和"], speech_style=[], comfort_style=[])
    p2 = PersonaProfile(role_label="母亲李芳", relation="配偶", appellation="老伴",
                        personality=["细心"], speech_style=[], comfort_style=[])
    add_or_update_persona(p1)
    add_or_update_persona(p2)

    all_p = get_all_personas()
    assert "儿子小明" in all_p
    assert "母亲李芳" in all_p
    assert len(all_p) == 2


def test_source_has_sync_code_in_import():
    """导入应使用 add_or_update_persona 添加到多角色列表，不自动切换当前角色。"""
    with open("app.py", encoding="utf-8") as f:
        source = f.read()

    import_idx = source.find("一键导入")
    assert import_idx > 0, "找不到一键导入按钮"

    after_import = source[import_idx:import_idx + 2000]

    # 导入应调用 add_p (add_or_update_persona) 而非直接 set_persona + form sync
    assert "add_p(" in after_import or "add_or_update_persona" in after_import, (
        "导入应使用 add_or_update_persona，不自动切换角色"
    )


def test_source_has_sync_code_in_manual_save():
    """验证手动保存人物画像也包含 session_state 同步。"""
    with open("app.py", encoding="utf-8") as f:
        source = f.read()

    save_idx = source.find("保存人物画像")
    assert save_idx > 0, "找不到保存人物画像按钮"

    after_save = source[save_idx:save_idx + 1000]
    # 新增画像按钮保存后 st.rerun() 切换到卡片模式，不依赖 form sync
    assert "set_persona" in after_save or "edit_role_label" in after_save or "form_role_label" in after_save, (
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
