"""RED: Elder-perspective text should extract elder_profile + memories."""


def test_preview_shows_elder_profile():
    """预览区在 elder_profile 有数据时也应可见。"""
    with open("app.py", encoding="utf-8") as f:
        source = f.read()

    # 预览区检查 elder_profile
    assert "elder_profile" in source, "preview doesn't check elder_profile"


def test_parser_fallback_has_all_keys():
    """解析结果的字典必须有四个 key。"""
    from llm.parser import parse_user_text
    result = parse_user_text("")
    for key in ["persona", "memories", "family_profiles", "elder_profile"]:
        assert key in result, f"parser fallback missing key: {key}"


def test_preview_shows_elder_profile_in_parsed_data():
    """预览区应展示 elder_profile 的内容，不依赖 persona 是否存在。"""
    with open("app.py", encoding="utf-8") as f:
        source = f.read()

    section_start = source.find("parsed_preview")
    assert section_start > 0
    # 在 parsed_preview 附近的代码块中搜 elder
    preview_block = source[section_start:section_start + 2000]
    assert "elder_profile" in preview_block, (
        "预览区缺少 elder_profile 展示——老人视角描述只有 elder_profile 时，预览为空"
    )


def test_parser_has_both_perspectives():
    """Parser 应有家人回忆和老人回忆两种视角的 prompt。"""
    from llm.parser import PARSER_USER_FAMILY, PARSER_USER_ELDER
    assert "家人回忆" in PARSER_USER_FAMILY
    assert "老人回忆" in PARSER_USER_ELDER
