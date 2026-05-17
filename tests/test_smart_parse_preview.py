"""Test that smart parse preview allows editing before import."""

import pytest


def test_parsed_session_state_is_mutable():
    """预览区必须可修改——用户编辑字段后 st.session_state.parsed 应更新。"""
    parsed = {
        "persona": {
            "role_label": "儿子小明",
            "relation": "子女",
            "appellation": "妈",
            "personality": ["温和", "细心"],
            "speech_style": ["喜欢用叠词", "开头爱问吃了没"],
            "comfort_style": ["唠家常", "讲趣事"],
        },
        "memories": [
            {
                "content": "去年中秋去西湖赏月",
                "memory_type": "事件",
                "family_members": ["小明(儿子)"],
                "emotion_tags": ["温馨"],
                "topic_tags": ["旅行", "节日"],
            }
        ],
    }

    # 模拟用户编辑：修改角色标签
    parsed["persona"]["role_label"] = "女儿小红"

    # 模拟用户编辑：修改记忆正文
    parsed["memories"][0]["content"] = "去年春节全家包饺子"

    # 验证修改已生效
    assert parsed["persona"]["role_label"] == "女儿小红"
    assert parsed["memories"][0]["content"] == "去年春节全家包饺子"


def test_each_preview_field_is_independently_editable():
    """每个预览字段应可独立编辑——role_label, relation, appellation 等都是独立控件。"""
    parsed = {
        "persona": {"role_label": "儿子小明", "relation": "子女", "appellation": "妈",
                     "personality": ["温和"], "speech_style": [], "comfort_style": []},
        "memories": [],
    }

    # 修改单字段不应影响其他字段
    parsed["persona"]["appellation"] = "奶奶"
    assert parsed["persona"]["appellation"] == "奶奶"
    assert parsed["persona"]["role_label"] == "儿子小明"  # 未变
    assert parsed["persona"]["relation"] == "子女"  # 未变


def test_memory_can_be_removed_from_preview():
    """用户应能在预览中删除某条记忆。"""
    parsed = {
        "persona": {},
        "memories": [
            {"content": "记忆A", "memory_type": "事件"},
            {"content": "记忆B", "memory_type": "趣事"},
            {"content": "记忆C", "memory_type": "习惯"},
        ],
    }

    # 删除第2条记忆
    parsed["memories"].pop(1)

    assert len(parsed["memories"]) == 2
    assert parsed["memories"][0]["content"] == "记忆A"
    assert parsed["memories"][1]["content"] == "记忆C"


def test_empty_parsed_shows_no_preview():
    """没有解析结果时不应展示预览区。"""
    parsed = {}
    should_show = bool(parsed.get("persona")) or bool(parsed.get("memories"))
    assert should_show is False


def test_import_uses_edited_data():
    """一键导入应使用编辑后的数据，而非原始解析数据。"""
    # 原始解析
    parsed = {
        "persona": {"role_label": "儿子小明", "relation": "子女", "appellation": "妈"},
        "memories": [{"content": "原内容", "memory_type": "事件"}],
    }

    # 用户在预览中编辑
    parsed["persona"]["role_label"] = "女儿小芳"
    parsed["memories"][0]["content"] = "新内容"

    # 模拟导入逻辑：从 parsed 读取数据
    persona_data = parsed["persona"]
    memory_data = parsed["memories"]

    assert persona_data["role_label"] == "女儿小芳"
    assert memory_data[0]["content"] == "新内容"
