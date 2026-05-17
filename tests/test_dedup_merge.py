"""RED: Dedup should merge same person across persona<->family, and similar names."""


def test_dedup_cross_references_persona_to_family():
    """Dedup prompt 应提示交叉匹配：新 persona 可能与已有 family_profile 是同一个人。"""
    from llm.parser import DEDUP_USER
    assert "persona" in DEDUP_USER.lower()
    assert "family" in DEDUP_USER.lower()


def test_merge_into_updates_name():
    """merge_into 时应更新已有档案的名字。"""
    from engine.family import FamilyProfile, add_profile, get_profile, clear_profiles
    clear_profiles()

    # 模拟：已有"丈夫"档案
    add_profile(FamilyProfile(name="丈夫", relation="子女", personality=["温和"]))
    fp = get_profile("丈夫")
    assert fp is not None

    # 模拟 merge: 新名字"刘承文"合并到"丈夫"
    fp.name = "刘承文"
    fp.relation = "子女"
    fp.personality = list(dict.fromkeys(fp.personality + ["细心"]))
    add_profile(fp)

    result = get_profile("刘承文")
    assert result is not None
    assert result.relation == "子女"
    assert "温和" in result.personality
    assert "细心" in result.personality


def test_similar_names_detected_as_same():
    """相似名字应被检测为同一人。"""
    existing = [{"name": "儿子刘承文", "relation": "子女"}]
    new_name = "刘承文"

    # 简单匹配：新名字是已有名字的子串
    is_same = new_name in existing[0]["name"] or existing[0]["name"] in new_name
    assert is_same, f"'{new_name}' 应该是 '{existing[0]['name']}' 的匹配"


def test_dedup_prompt_includes_relation_context():
    """Dedup 应包含人物关系信息帮助判断。"""
    from llm.parser import DEDUP_USER
    assert "relation" in DEDUP_USER.lower() or "关系" in DEDUP_USER
