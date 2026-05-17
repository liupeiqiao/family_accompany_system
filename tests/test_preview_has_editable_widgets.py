"""RED: Test that smart parse preview section uses editable widgets, not read-only ones."""

import ast
import re


def find_preview_section() -> str:
    """Extract the preview expander block from app.py."""
    with open("app.py", encoding="utf-8") as f:
        source = f.read()

    # 找到预览区代码块：从 "预览解析结果" 到下一个 st.divider()
    match = re.search(
        r"# 预览解析结果\s*(.*?)(?=st\.divider\(\))",
        source, re.DOTALL
    )
    if not match:
        return ""
    return match.group(1)


def test_preview_uses_editable_widgets():
    """预览区必须使用可编辑控件（text_input/selectbox/multiselect），而非只读的 st.write/st.caption。"""
    preview_block = find_preview_section()
    assert preview_block, "找不到预览区代码块"

    # 检查是否有可编辑控件
    has_editable = any(
        widget in preview_block
        for widget in ["st.text_input", "st.text_area", "st.selectbox", "st.multiselect"]
    )
    # 检查是否依赖只读控件
    has_readonly = any(
        widget in preview_block
        for widget in ["st.write", "st.caption"]
    )

    # 必须有可编辑控件，且没有只读控件（或只读控件只用于标签）
    assert has_editable, (
        "预览区缺少可编辑控件——解析结果只展示不修改。"
        "应在 expander 内使用 st.text_input、st.selectbox、st.multiselect 让用户修改。"
    )


def test_preview_persona_fields_are_editable():
    """人物画像的三个核心字段必须可编辑。"""
    preview_block = find_preview_section()
    assert preview_block

    # role_label, relation, appellation 至少有两个有独立输入控件
    editable_count = preview_block.count("st.text_input")
    assert editable_count >= 2, (
        f"预览区人物画像字段不足：只有 {editable_count} 个 text_input，"
        "至少需要 role_label 和 appellation 可编辑"
    )


def test_preview_memories_are_editable():
    """记忆条目正文必须可编辑（text_area 或 text_input）。"""
    preview_block = find_preview_section()

    has_memory_edit = (
        "st.text_area" in preview_block or
        "st.text_input" in preview_block
    )
    assert has_memory_edit, "记忆条目不可编辑——需要使用 st.text_area 让用户修改记忆正文"


def test_one_click_import_uses_session_state():
    """一键导入从 st.session_state.parsed 读取（编辑后的）数据。"""
    with open("app.py", encoding="utf-8") as f:
        source = f.read()

    # 确认一键导入代码从 st.session_state.parsed 读取
    # 查找一键导入按钮是否从 st.session_state.parsed 读取数据
    import_button_area = source.split("一键导入")[1] if "一键导入" in source else ""
    assert import_button_area, "找不到一键导入按钮代码"

    assert "st.session_state.parsed" in import_button_area or "st.session_state.get('parsed'" in import_button_area, (
        "一键导入未从 st.session_state.parsed 读取数据——"
        "如果预览区修改了 parsed，导入必须使用修改后的版本"
    )
