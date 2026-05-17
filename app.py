"""亲情陪伴系统 — Streamlit 主入口"""

import json
import re
import streamlit as st
from datetime import datetime

from llm.client import chat
from llm.prompts import (
    INTENT_EMOTION_SYSTEM,
    INTENT_EMOTION_USER,
    RESPONSE_USER,
    build_response_system,
)
from llm.parser import parse_user_text, dedup_check
from engine.memory import MemoryUnit, add_memory, remove_memory, get_all_memories, clear_memories
from engine.persona import PersonaProfile, set_persona, get_persona, get_all_personas, remove_persona, switch_persona
from engine.family import FamilyProfile, add_profile, remove_profile, get_all_profiles, clear_profiles, get_profile
from engine.elder import ElderProfile, set_elder, get_elder
from engine.scorer import score_memories, get_top_memories, DEFAULT_WEIGHTS
from engine.strategy import select_strategy
from engine.adaptation import check_elderly_adaptation, safety_check, build_retry_hint
from engine.db import init_db, save_persona as db_save_persona, load_persona as db_load_persona
from engine.db import load_all_personas as db_load_all_personas, delete_persona as db_delete_persona
from engine.db import save_memory as db_save_memory, delete_memory as db_delete_memory, load_all_memories as db_load_memories
from engine.db import save_family_profile as db_save_family, delete_family_profile as db_delete_family, load_all_family_profiles as db_load_families
from engine.db import save_elder as db_save_elder, load_elder as db_load_elder, delete_elder as db_delete_elder

st.set_page_config(page_title="亲情陪伴系统", page_icon="❤️", layout="wide")
st.title("❤️ 亲情陪伴系统")
st.caption("基于家庭记忆的适老共情对话原型")

# ===== 初始化 DB + session_state =====
init_db()

if "messages" not in st.session_state:
    st.session_state.messages = []
if "debug" not in st.session_state:
    st.session_state.debug = {}
# 每次重载时，若内存为空则从 SQLite 恢复
if not st.session_state.get("db_loaded", False) or not get_all_personas():
    all_pdata = db_load_all_personas()
    if all_pdata:
        for pdata in all_pdata:
            persona = PersonaProfile(
                role_label=pdata["role_label"],
                relation=pdata["relation"],
                appellation=pdata["appellation"],
                personality=pdata.get("personality", []),
                speech_style=pdata.get("speech_style", []),
                comfort_style=pdata.get("comfort_style", []),
                mood_preference=pdata.get("mood_preference", {}),
                topic_affinity=pdata.get("topic_affinity", {}),
                sensitivity_map=pdata.get("sensitivity_map", {}),
            )
            from engine.persona import add_or_update_persona
            add_or_update_persona(persona)
        first = all_pdata[0]
        if not get_persona().is_complete():
            set_persona(PersonaProfile(
                role_label=first["role_label"], relation=first["relation"],
                appellation=first["appellation"], personality=first.get("personality",[]),
                speech_style=first.get("speech_style",[]), comfort_style=first.get("comfort_style",[]),
            ))
        st.session_state.update({
            "form_role_label": first["role_label"],
            "form_relation": first["relation"],
            "form_appellation": first["appellation"],
            "form_personality": first.get("personality", []),
            "form_speech_style": "\n".join(first.get("speech_style", [])),
            "form_comfort_style": first.get("comfort_style", []),
        })

if not get_all_memories():
    for mdata in db_load_memories():
        mem = MemoryUnit(
            id=mdata["id"],
            content=mdata["content"],
            memory_type=mdata.get("memory_type", ""),
            subject=mdata.get("subject", ""),
            family_members=mdata.get("family_members", []),
            emotion_tags=mdata.get("emotion_tags", []),
            topic_tags=mdata.get("topic_tags", []),
            intimacy_weight=mdata.get("intimacy_weight", 0.5),
        )
        add_memory(mem)

if not get_all_profiles():
    for fdata in db_load_families():
        fp = FamilyProfile(
            name=fdata["name"], relation=fdata.get("relation",""),
            personality=fdata.get("personality",[]), preferences=fdata.get("preferences",[]),
            habits=fdata.get("habits",[]), relations=fdata.get("relations",[]),
            notes=fdata.get("notes",""),
        )
        add_profile(fp)

if not get_elder().full_name:
    edata = db_load_elder()
    if edata and edata.get("full_name"):
        set_elder(ElderProfile(
            full_name=edata["full_name"], gender=edata.get("gender",""),
            personality=edata.get("personality",[]),
            preferences=edata.get("preferences",[]), habits=edata.get("habits",[]),
            health_notes=edata.get("health_notes",[]), speech_traits=edata.get("speech_traits",[]),
            life_experiences=edata.get("life_experiences",[]),
            important_memories=edata.get("important_memories",[]), notes=edata.get("notes",""),
        ))

st.session_state.db_loaded = True

# 确保表单字段有初始值
for key, default in [
    ("form_role_label", "儿子小明"), ("form_relation", "子女"), ("form_appellation", "妈"),
    ("form_personality", ["温和", "细心"]),
    ("form_speech_style", "喜欢用叠词\n开头爱问吃了没"),
    ("form_comfort_style", ["唠家常", "讲趣事", "一起回忆"]),
]:
    if key not in st.session_state:
        st.session_state[key] = default


# ===== 辅助函数 =====

def memory_count() -> int:
    from engine.memory import memory_count as mc
    return mc()


def parse_llm_json(raw: str) -> dict:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{[^{}]*\}", raw)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return {"intent": "日常闲聊", "emotion": "平静", "confidence": 0.5, "keywords": []}


def build_memory_context(top_memories: list[MemoryUnit]) -> str:
    if not top_memories:
        return ""
    blocks = []
    for i, mem in enumerate(top_memories):
        parts = [f"记忆{i+1}：{mem.content}"]
        subject_label = mem.subject or "老人"
        parts.append(f"主语：{subject_label}")
        if mem.family_members:
            parts.append(f"涉及：{', '.join(mem.family_members)}")
        if mem.emotion_tags:
            parts.append(f"情感：{'、'.join(mem.emotion_tags)}")
        if mem.topic_tags:
            parts.append(f"话题：{'、'.join(mem.topic_tags)}")
        blocks.append("\n".join(parts))
    return "\n---\n".join(blocks)


# ===== Sidebar =====
with st.sidebar:
    # ===== 智能导入 =====
    st.header("🧠 智能导入")
    st.caption("粘贴一段描述，选择视角后 AI 自动提取")

    perspective = st.radio("描述视角", ["👨‍👩‍👧 家人回忆（描述家人）", "👵 老人回忆（老人自述）"],
                           index=0, key="parser_perspective", horizontal=True)

    smart_text = st.text_area(
        "描述文字",
        key="smart_text",
        placeholder="比如：我儿子叫小明，性格温和细心，喜欢叫我妈，常说叠词。去年中秋我们全家去西湖赏月，小明给我剥螃蟹…",
    )

    col_s1, col_s2 = st.columns(2)
    with col_s1:
        if st.button("🔍 智能解析", use_container_width=True):
            if smart_text.strip():
                with st.spinner("AI 解析中..."):
                    persp = "elder" if "老人" in perspective else "family"
                    # 构建已有家人上下文
                    ef_context = ""
                    if persp == "family":
                        existing_families = get_all_profiles()
                        if existing_families:
                            ef_lines = ["## 已知的家人（作为关系推断参考）"]
                            for fp in existing_families.values():
                                ef_lines.append(f"- {fp.name}：与老人的关系是{fp.relation}")
                            ef_context = "\n".join(ef_lines) + "\n"
                    parsed = parse_user_text(smart_text.strip(), perspective=persp, existing_families_text=ef_context)
                    # 去重检查
                    existing_p = [{"role_label": pp.role_label, "relation": pp.relation, "appellation": pp.appellation}
                                  for pp in get_all_personas().values() if pp.is_complete()]
                    existing_f = [{"name": fp.name, "relation": fp.relation, "personality": fp.personality,
                                   "preferences": fp.preferences, "habits": fp.habits}
                                  for fp in get_all_profiles().values()]
                    dedup = dedup_check(parsed, existing_p, existing_f) if (existing_p or existing_f) else {}
                    st.session_state.parsed = parsed
                    st.session_state.dedup = dedup
                    p_count = 1 if parsed.get("persona",{}).get("role_label") else 0
                    m_count = len(parsed.get("memories", []))
                    e_count = 1 if parsed.get("elder_profile",{}).get("full_name") else 0
                    f_count = len(parsed.get("family_profiles", []))
                    d_count = sum(1 for a in dedup.get("family_actions",[]) if a.get("action")=="merge_into")
                    parts = []
                    if p_count: parts.append("画像1份")
                    if m_count: parts.append(f"记忆{m_count}条")
                    if e_count: parts.append("老人画像")
                    if f_count: parts.append(f"家人{f_count}人")
                    if d_count: parts.append(f"🔀合并{d_count}人")
                    st.success(f"解析完成：{' + '.join(parts) if parts else '无有效数据'}")
            else:
                st.warning("请先输入描述文字")

    with col_s2:
        if st.button("📥 一键导入", use_container_width=True):
            parsed = st.session_state.get("parsed", {})
            if parsed:
                dedup_result = st.session_state.get("dedup", {})
                persona_part = parsed.get("persona", {})
                if persona_part.get("role_label"):
                    p = PersonaProfile(
                        role_label=persona_part.get("role_label", ""),
                        relation=persona_part.get("relation", ""),
                        appellation=persona_part.get("appellation", ""),
                        personality=persona_part.get("personality", []),
                        speech_style=persona_part.get("speech_style", []),
                        comfort_style=persona_part.get("comfort_style", []),
                    )
                    from engine.persona import get_all_personas as gap, merge_persona, add_or_update_persona as add_p
                    def _find_persona(name: str):
                        """模糊查找：名字包含或等于 role_label"""
                        all_p = gap()
                        if not name:
                            return None
                        if name in all_p:
                            return all_p[name]
                        for k, v in all_p.items():
                            if name in k or k in name:
                                return v
                        return None
                    # 优先通过 dedup 合并，兜底用模糊名匹配
                    paction = dedup_result.get("persona_action", "")
                    pmatch = dedup_result.get("persona_match", "")
                    merged = False
                    if paction == "merge" and pmatch:
                        existing = _find_persona(pmatch)
                        if existing:
                            old_label = existing.role_label
                            p = merge_persona(existing, persona_part)
                            if p.role_label != old_label:
                                db_delete_persona(old_label)
                            merged = True
                    if not merged:
                        existing = _find_persona(p.role_label)
                        if existing:
                            old_label = existing.role_label
                            p = merge_persona(existing, persona_part)
                            if p.role_label != old_label:
                                db_delete_persona(old_label)  # 改名后删旧 DB 行
                    add_p(p)
                    if not get_persona().is_complete():
                        set_persona(p)
                    db_save_persona({
                        "role_label": p.role_label,
                        "relation": p.relation,
                        "appellation": p.appellation,
                        "personality": p.personality,
                        "speech_style": p.speech_style,
                        "comfort_style": p.comfort_style,
                        "mood_preference": p.mood_preference,
                        "topic_affinity": p.topic_affinity,
                        "sensitivity_map": p.sensitivity_map,
                    })

                for md in parsed.get("memories", []):
                    mem = MemoryUnit(
                        content=md.get("content", ""),
                        memory_type=md.get("memory_type", "事件"),
                        subject=md.get("subject", ""),
                        family_members=md.get("family_members", []),
                        emotion_tags=md.get("emotion_tags", []),
                        topic_tags=md.get("topic_tags", []),
                    )
                    add_memory(mem)
                    db_save_memory({
                        "id": mem.id, "content": mem.content,
                        "memory_type": mem.memory_type, "subject": mem.subject,
                        "family_members": mem.family_members, "emotion_tags": mem.emotion_tags,
                        "topic_tags": mem.topic_tags, "intimacy_weight": mem.intimacy_weight,
                    })
                # 导入老人画像
                ed = parsed.get("elder_profile", {})
                if ed.get("full_name"):
                    ep = ElderProfile(full_name=ed["full_name"], gender=ed.get("gender",""),
                        personality=ed.get("personality",[]), preferences=ed.get("preferences",[]),
                        habits=ed.get("habits",[]), health_notes=ed.get("health_notes",[]),
                        speech_traits=ed.get("speech_traits",[]), life_experiences=ed.get("life_experiences",[]),
                        important_memories=ed.get("important_memories",[]), notes=ed.get("notes",""))
                    set_elder(ep)
                    db_save_elder({"full_name":ep.full_name,"gender":ep.gender,"personality":ep.personality,"preferences":ep.preferences,"habits":ep.habits,"health_notes":ep.health_notes,"speech_traits":ep.speech_traits,"life_experiences":ep.life_experiences,"important_memories":ep.important_memories,"notes":ep.notes})

                # 导入家人偏好档案（处理去重合并）
                family_actions = {a["new_name"]: a for a in dedup_result.get("family_actions", [])}
                for fd in parsed.get("family_profiles", []):
                    fname = fd.get("name", "")
                    if not fname:
                        continue
                    fa = family_actions.get(fname, {})
                    if fa.get("action") == "skip":
                        continue
                    elif fa.get("action") == "merge_into":
                        target = fa.get("target", "")
                        existing_fp = get_profile(target) if target else None
                        if not existing_fp and target:
                            # 模糊查找
                            for k, v in get_all_profiles().items():
                                if target in k or k in target:
                                    existing_fp = v
                                    break
                        if existing_fp:
                            existing_fp.relation = fd.get("relation") or existing_fp.relation
                            existing_fp.personality = list(dict.fromkeys(existing_fp.personality + fd.get("personality", [])))
                            existing_fp.preferences = list(dict.fromkeys(existing_fp.preferences + fd.get("preferences", [])))
                            existing_fp.habits = list(dict.fromkeys(existing_fp.habits + fd.get("habits", [])))
                            existing_fp.relations = fd.get("relations") or existing_fp.relations
                            existing_fp.notes = fd.get("notes") or existing_fp.notes
                            add_profile(existing_fp)
                            db_save_family({"name":existing_fp.name,"relation":existing_fp.relation,"personality":existing_fp.personality,"preferences":existing_fp.preferences,"habits":existing_fp.habits,"relations":existing_fp.relations,"notes":existing_fp.notes})
                        else:
                            # target 不存在，当新档案添加
                            fp = FamilyProfile(name=fname, relation=fd.get("relation",""),
                                personality=fd.get("personality",[]), preferences=fd.get("preferences",[]),
                                habits=fd.get("habits",[]), relations=fd.get("relations",[]), notes=fd.get("notes",""))
                            add_profile(fp)
                            db_save_family({"name":fp.name,"relation":fp.relation,"personality":fp.personality,"preferences":fp.preferences,"habits":fp.habits,"relations":fp.relations,"notes":fp.notes})
                    else:
                        fp = FamilyProfile(name=fname, relation=fd.get("relation",""),
                            personality=fd.get("personality",[]), preferences=fd.get("preferences",[]),
                            habits=fd.get("habits",[]), relations=fd.get("relations",[]), notes=fd.get("notes",""))
                        add_profile(fp)
                        db_save_family({"name":fp.name,"relation":fp.relation,"personality":fp.personality,"preferences":fp.preferences,"habits":fp.habits,"relations":fp.relations,"notes":fp.notes})

                elder_msg = "+老人画像" if parsed.get("elder_profile",{}).get("full_name") else ""
                st.success(f"已导入！画像+{len(parsed.get('memories', []))}条记忆+{len(parsed.get('family_profiles', []))}人档案{elder_msg}")
                st.session_state.parsed = {}
                st.rerun()
            else:
                st.warning("请先点击「智能解析」")

    # 预览解析结果（可编辑）
    parsed_preview = st.session_state.get("parsed", {})
    if parsed_preview:
        # 检查是否有任何有效数据
        has_persona = bool(parsed_preview.get("persona", {}).get("role_label"))
        has_memories = bool(parsed_preview.get("memories", []))
        has_elder = bool(parsed_preview.get("elder_profile", {}).get("full_name"))
        has_family = bool(parsed_preview.get("family_profiles", []))
        has_content = has_persona or has_memories or has_elder or has_family
        if not has_content:
            st.warning("解析结果为空，请调整描述后重试")
        else:
            with st.expander("📋 解析预览（可直接修改后导入）", expanded=True):
                st.caption("以下字段均可直接编辑，修改后点「一键导入」即用编辑后的数据入库")

            # 去重结果概览
            dedup_result = st.session_state.get("dedup", {})
            if dedup_result:
                pa = dedup_result.get("persona_action", "")
                pm = dedup_result.get("persona_match", "")
                fa = dedup_result.get("family_actions", [])
                merges = [a for a in fa if a.get("action") == "merge_into"]
                news = [a for a in fa if a.get("action") == "new"]
                if pa == "merge" and pm:
                    st.info(f"🔄 角色「{parsed_preview.get('persona',{}).get('role_label','')}」将合并到已有的「{pm}」")
                if merges:
                    for mg in merges:
                        st.info(f"🔄 家人「{mg.get('new_name','')}」将合并到已有的「{mg.get('target','')}」")
                if news:
                    names = [n.get('new_name','') for n in news if n.get('new_name')]
                    if names: st.success(f"🆕 新增家人：{'、'.join(names)}")

            # 老人画像预览
            ep = parsed_preview.get("elder_profile", {})
            if ep and ep.get("full_name"):
                st.write("**👴 老人画像**")
                ep["full_name"] = st.text_input("姓名", value=ep.get("full_name",""), key="prev_elder_name")
                ep_gender_cur = ep.get("gender","女")
                ep["gender"] = st.selectbox("性别", ["女","男"],
                    index=0 if ep_gender_cur=="女" else 1, key="prev_elder_gender")
                ep_name = ep.get("full_name","")
                ep_pers = st.text_input("性格（、分隔）", value="、".join(ep.get("personality",[])), key="prev_elder_pers")
                ep["personality"] = [x.strip() for x in ep_pers.split("、") if x.strip()]
                ep_prefs = st.text_input("喜好（、分隔）", value="、".join(ep.get("preferences",[])), key="prev_elder_prefs")
                ep["preferences"] = [x.strip() for x in ep_prefs.split("、") if x.strip()]
                ep_hab = st.text_input("习惯（、分隔）", value="、".join(ep.get("habits",[])), key="prev_elder_hab")
                ep["habits"] = [x.strip() for x in ep_hab.split("、") if x.strip()]
                ep_health = st.text_input("健康（、分隔）", value="、".join(ep.get("health_notes",[])), key="prev_elder_health")
                ep["health_notes"] = [x.strip() for x in ep_health.split("、") if x.strip()]
                ep_speech = st.text_input("说话特点（、分隔）", value="、".join(ep.get("speech_traits",[])), key="prev_elder_speech")
                ep["speech_traits"] = [x.strip() for x in ep_speech.split("、") if x.strip()]

            pp = parsed_preview.get("persona", {})
            if pp and pp.get("role_label"):
                st.write("**人物画像**")
                col_p1, col_p2 = st.columns(2)
                with col_p1:
                    pp["role_label"] = st.text_input("角色标签", value=pp.get("role_label", ""), key="prev_role")
                    pp["appellation"] = st.text_input("称呼", value=pp.get("appellation", ""), key="prev_app")
                with col_p2:
                    relation_opts = ["子女", "儿媳", "女婿", "配偶", "孙辈", "朋友", "护工"]
                    cur_rel = pp.get("relation", "子女")
                    rel_idx = relation_opts.index(cur_rel) if cur_rel in relation_opts else 0
                    pp["relation"] = st.selectbox("关系", relation_opts, index=rel_idx, key="prev_rel")

                all_personality = ["温和", "幽默", "细心", "沉稳", "话多", "乐观", "感性", "活泼", "内向", "开朗", "随和", "大条"]
                pp["personality"] = st.multiselect("性格标签", all_personality,
                    default=[v for v in pp.get("personality", []) if v in all_personality], key="prev_pers")

                speech_text = "\n".join(pp.get("speech_style", []))
                new_speech = st.text_area("说话风格（一行一条）", value=speech_text, key="prev_speech")
                pp["speech_style"] = [s.strip() for s in new_speech.split("\n") if s.strip()]

                all_comfort = ["唠家常", "撒娇", "讲趣事", "一起回忆", "逗开心",
                               "讲道理", "转移话题", "鼓励", "附和倾听", "默默陪伴"]
                pp["comfort_style"] = st.multiselect("陪伴方式", all_comfort,
                    default=[v for v in pp.get("comfort_style", []) if v in all_comfort], key="prev_comfort")

            mems = parsed_preview.get("memories", [])
            if mems:
                st.write(f"**记忆条目 ({len(mems)}条)**")
                to_delete = []
                for i, m in enumerate(mems):
                    with st.container():
                        col_m1, col_m2, col_m3 = st.columns([3, 1, 1])
                        with col_m1:
                            m["content"] = st.text_input(
                                f"记忆{i+1}正文", value=m.get("content", ""), key=f"prev_mc_{i}"
                            )
                        with col_m2:
                            mem_types = ["事件", "习惯", "偏好", "重要日期", "趣事"]
                            cur_mt = m.get("memory_type", "事件")
                            mt_idx = mem_types.index(cur_mt) if cur_mt in mem_types else 0
                            m["memory_type"] = st.selectbox(
                                f"类型{i+1}", mem_types, index=mt_idx, key=f"prev_mt_{i}"
                            )
                        with col_m3:
                            if st.button(f"🗑️{i+1}", key=f"prev_del_{i}"):
                                to_delete.append(i)

                        col_f1, col_f2 = st.columns(2)
                        with col_f1:
                            fam_text = ", ".join(m.get("family_members", []))
                            new_fam = st.text_input(
                                f"涉及家人{i+1}（逗号分隔）", value=fam_text, key=f"prev_mf_{i}"
                            )
                            m["family_members"] = [x.strip() for x in new_fam.split(",") if x.strip()]
                        with col_f2:
                            all_emo = ["温馨", "快乐", "感动", "搞笑", "难忘", "遗憾", "伤感", "兴奋"]
                            m["emotion_tags"] = st.multiselect(
                                f"情感标签{i+1}", all_emo, default=[v for v in m.get("emotion_tags", []) if v in all_emo], key=f"prev_me_{i}"
                            )
                        all_topics = ["饮食", "旅行", "节日", "成长", "健康", "宠物", "工作", "日常"]
                        m["topic_tags"] = st.multiselect(
                            f"话题标签{i+1}", all_topics, default=[v for v in m.get("topic_tags", []) if v in all_topics], key=f"prev_mtpc_{i}"
                        )
                        st.divider()

                # 删除标记的记忆
                for idx in sorted(to_delete, reverse=True):
                    mems.pop(idx)
                    st.rerun()

    st.divider()

    # ===== 老人画像 =====
    st.header("👴 老人画像")

    elder = get_elder()
    elder_has_data = bool(elder.full_name)
    edit_elder_key = "edit_elder"

    if elder_has_data:
        if not st.session_state.get(edit_elder_key, False):
            with st.container(border=True):
                gender_label = {"男":"👴","女":"👵"}.get(elder.gender,"")
                st.caption(f"{gender_label} **{elder.full_name}** · {elder.gender}")
                if elder.personality: st.caption(f"性格：{'、'.join(elder.personality)}")
                if elder.preferences: st.caption(f"喜好：{'、'.join(elder.preferences)}")
                if elder.habits: st.caption(f"习惯：{'、'.join(elder.habits)}")
                if elder.health_notes: st.caption(f"健康：{'、'.join(elder.health_notes)}")
                if elder.speech_traits: st.caption(f"说话：{'、'.join(elder.speech_traits)}")
                if elder.life_experiences: st.caption(f"经历：{'、'.join(elder.life_experiences[:2])}{'...' if len(elder.life_experiences)>2 else ''}")
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("✏️ 编辑", key="btn_edit_elder", use_container_width=True):
                        st.session_state[edit_elder_key] = True
                        for field, val in [
                            ("e_full_name", elder.full_name), ("e_gender", elder.gender),
                            ("e_personality", "、".join(elder.personality)),
                            ("e_preferences", "、".join(elder.preferences)), ("e_habits", "、".join(elder.habits)),
                            ("e_health", "、".join(elder.health_notes)), ("e_speech", "、".join(elder.speech_traits)),
                            ("e_life", "、".join(elder.life_experiences)), ("e_memories", "、".join(elder.important_memories)),
                            ("e_notes", elder.notes),
                        ]:
                            st.session_state[field] = val
                        st.rerun()
                with c2:
                    if st.button("🗑️ 删除", key="btn_del_elder", use_container_width=True):
                        set_elder(ElderProfile())
                        db_delete_elder()
                        for k in list(st.session_state.keys()):
                            if k.startswith("e_") or k.startswith("prev_elder"): st.session_state.pop(k, None)
                        st.rerun()
        else:
            with st.expander("✏️ 编辑老人画像", expanded=True):
                e_full_name = st.text_input("姓名", key="e_full_name")
                e_gender = st.selectbox("性别", ["女","男"], index=0 if elder.gender=="女" else 1, key="e_gender")
                e_pers = st.text_input("性格（、分隔）", key="e_personality")
                e_prefs = st.text_input("喜好（、分隔）", key="e_preferences")
                e_hab = st.text_input("习惯（、分隔）", key="e_habits")
                e_health = st.text_input("健康注意（、分隔）", key="e_health")
                e_speech = st.text_input("说话特点（、分隔）", key="e_speech")
                e_life = st.text_input("人生经历（、分隔）", key="e_life")
                e_mem = st.text_input("重要记忆（、分隔）", key="e_memories")
                e_notes = st.text_input("备注", key="e_notes")
                cs, cc = st.columns(2)
                with cs:
                    if st.button("💾 保存", key="btn_save_elder", use_container_width=True):
                        ep = ElderProfile(full_name=e_full_name.strip(), gender=e_gender,
                            personality=[x.strip() for x in e_pers.split("、") if x.strip()],
                            preferences=[x.strip() for x in e_prefs.split("、") if x.strip()],
                            habits=[x.strip() for x in e_hab.split("、") if x.strip()],
                            health_notes=[x.strip() for x in e_health.split("、") if x.strip()],
                            speech_traits=[x.strip() for x in e_speech.split("、") if x.strip()],
                            life_experiences=[x.strip() for x in e_life.split("、") if x.strip()],
                            important_memories=[x.strip() for x in e_mem.split("、") if x.strip()],
                            notes=e_notes.strip())
                        set_elder(ep)
                        db_save_elder({"full_name":ep.full_name,"gender":ep.gender,"personality":ep.personality,"preferences":ep.preferences,"habits":ep.habits,"health_notes":ep.health_notes,"speech_traits":ep.speech_traits,"life_experiences":ep.life_experiences,"important_memories":ep.important_memories,"notes":ep.notes})
                        st.session_state[edit_elder_key] = False
                        st.rerun()
                with cc:
                    if st.button("取消", key="btn_cancel_elder", use_container_width=True):
                        st.session_state[edit_elder_key] = False
                        st.rerun()
    else:
        with st.expander("➕ 新增老人画像", expanded=True):
            e_full_name = st.text_input("姓名", key="e_full_name")
            e_gender = st.selectbox("性别", ["女","男"], key="e_gender")
            e_pers = st.text_input("性格（、分隔）", key="e_personality")
            e_prefs = st.text_input("喜好（、分隔）", key="e_preferences")
            e_hab = st.text_input("习惯（、分隔）", key="e_habits")
            e_health = st.text_input("健康注意（、分隔）", key="e_health")
            e_speech = st.text_input("说话特点（、分隔）", key="e_speech")
            e_life = st.text_input("人生经历（、分隔）", key="e_life")
            e_mem = st.text_input("重要记忆（、分隔）", key="e_memories")
            e_notes = st.text_input("备注", key="e_notes")
            if st.button("💾 保存", key="btn_new_elder"):
                ep = ElderProfile(full_name=e_full_name.strip(), gender=e_gender,
                    personality=[x.strip() for x in e_pers.split("、") if x.strip()],
                    preferences=[x.strip() for x in e_prefs.split("、") if x.strip()],
                    habits=[x.strip() for x in e_hab.split("、") if x.strip()],
                    health_notes=[x.strip() for x in e_health.split("、") if x.strip()],
                    speech_traits=[x.strip() for x in e_speech.split("、") if x.strip()],
                    life_experiences=[x.strip() for x in e_life.split("、") if x.strip()],
                    important_memories=[x.strip() for x in e_mem.split("、") if x.strip()],
                    notes=e_notes.strip())
                set_elder(ep)
                db_save_elder({"full_name":ep.full_name,"gender":ep.gender,"personality":ep.personality,"preferences":ep.preferences,"habits":ep.habits,"health_notes":ep.health_notes,"speech_traits":ep.speech_traits,"life_experiences":ep.life_experiences,"important_memories":ep.important_memories,"notes":ep.notes})
                st.rerun()

    st.divider()

    # ===== 人物画像 =====
    st.header("👤 人物画像")

    all_personas_dict = get_all_personas()
    persona_labels = list(all_personas_dict.keys())
    current_persona = get_persona()

    # 角色切换下拉框
    if persona_labels:
        # 自动同步：如果 pipeline 切换了角色，下拉框跟随
        auto_switched = st.session_state.pop("auto_switched", "")
        current_label = auto_switched if auto_switched in persona_labels else (
            current_persona.role_label if current_persona.is_complete() and current_persona.role_label in persona_labels else persona_labels[0])
        selected_label = st.selectbox("当前角色", persona_labels,
            index=persona_labels.index(current_label) if current_label in persona_labels else 0,
            key="persona_selector")
        if selected_label != current_persona.role_label:
            switch_persona(selected_label)
            st.rerun()
        current_persona = get_persona()

    persona_has_data = current_persona.is_complete()

    if persona_has_data:
        # 画像读模式卡片
        if not st.session_state.get("edit_persona", False):
            with st.container(border=True):
                st.caption(f"**{current_persona.role_label}** · {current_persona.relation} · 称呼「{current_persona.appellation}」")
                if current_persona.personality:
                    st.caption(f"性格：{'、'.join(current_persona.personality)}")
                if current_persona.speech_style:
                    st.caption(f"说话：{'；'.join(current_persona.speech_style[:3])}{'...' if len(current_persona.speech_style)>3 else ''}")
                if current_persona.comfort_style:
                    st.caption(f"陪伴：{'、'.join(current_persona.comfort_style)}")
                c1, c2, c3 = st.columns(3)
                with c1:
                    if st.button("✏️ 编辑", key="btn_edit_persona", use_container_width=True):
                        st.session_state.edit_persona = True
                        st.session_state.update({
                            "edit_role_label": current_persona.role_label,
                            "edit_relation": current_persona.relation,
                            "edit_appellation": current_persona.appellation,
                            "edit_personality": current_persona.personality,
                            "edit_speech_style": "\n".join(current_persona.speech_style),
                            "edit_comfort_style": current_persona.comfort_style,
                        })
                        st.rerun()
                with c2:
                    if st.button("🗑️ 删除", key="btn_del_persona", use_container_width=True):
                        db_delete_persona(current_persona.role_label)
                        remove_persona(current_persona.role_label)
                        st.session_state.edit_persona = False
                        st.rerun()
                with c3:
                    if st.button("➕ 新增", key="btn_add_new_persona", use_container_width=True, help="添加一个全新角色"):
                        st.session_state.edit_persona = False
                        st.session_state.show_new_persona_form = True
                        st.rerun()

        # 画像编辑模式（内联展开）
        if st.session_state.get("edit_persona", False):
            with st.expander("✏️ 编辑人物画像", expanded=True):
                _role = st.text_input("角色标签", key="edit_role_label")
                _rel = st.selectbox("与老人的关系", ["子女","配偶","孙辈","朋友","护工"], key="edit_relation")
                _app = st.text_input("对老人的称呼", key="edit_appellation")
                _pers = st.multiselect("性格标签", ["温和","幽默","细心","沉稳","话多","乐观","感性","活泼","内向","开朗","随和","大条"], key="edit_personality")
                _sp = st.text_area("说话风格（一行一条）", key="edit_speech_style")
                _sp_list = [s.strip() for s in _sp.split("\n") if s.strip()]
                _comf = st.multiselect("陪伴行为方式", ["唠家常","撒娇","讲趣事","一起回忆","逗开心","讲道理","转移话题","鼓励","附和倾听","默默陪伴"], key="edit_comfort_style")

                c_save, c_cancel = st.columns(2)
                with c_save:
                    if st.button("💾 保存", key="btn_save_persona", use_container_width=True):
                        old_label = current_persona.role_label
                        persona = PersonaProfile(role_label=_role, relation=_rel, appellation=_app, personality=_pers, speech_style=_sp_list, comfort_style=_comf)
                        set_persona(persona)
                        if old_label and old_label != persona.role_label:
                            remove_persona(old_label)
                            db_delete_persona(old_label)
                        db_save_persona({"role_label":persona.role_label,"relation":persona.relation,"appellation":persona.appellation,"personality":persona.personality,"speech_style":persona.speech_style,"comfort_style":persona.comfort_style,"mood_preference":persona.mood_preference,"topic_affinity":persona.topic_affinity,"sensitivity_map":persona.sensitivity_map})
                        st.session_state.edit_persona = False
                        st.rerun()
                with c_cancel:
                    if st.button("取消", key="btn_cancel_persona", use_container_width=True):
                        st.session_state.edit_persona = False
                        st.rerun()

        # 手动新增角色表单（独立于编辑/已有画像）
        if st.session_state.get("show_new_persona_form", False):
            with st.expander("➕ 新增角色", expanded=True):
                _nrole = st.text_input("角色标签", key="new_persona_role", placeholder="如：女儿小红")
                _nrel = st.selectbox("与老人的关系", ["子女","配偶","孙辈","朋友","护工"], key="new_persona_rel")
                _napp = st.text_input("对老人的称呼", key="new_persona_app", placeholder="如：妈")
                _npers = st.multiselect("性格标签", ["温和","幽默","细心","沉稳","话多","乐观","感性","活泼","内向","开朗","随和","大条"], key="new_persona_pers")
                _nsp = st.text_area("说话风格（一行一条）", key="new_persona_speech", placeholder="喜欢用叠词")
                _nsp_list = [s.strip() for s in _nsp.split("\n") if s.strip()]
                _ncomf = st.multiselect("陪伴行为方式", ["唠家常","撒娇","讲趣事","一起回忆","逗开心","讲道理","转移话题","鼓励","附和倾听","默默陪伴"], key="new_persona_comf")
                ns, nc = st.columns(2)
                with ns:
                    if st.button("💾 保存新角色", key="btn_save_new_persona", use_container_width=True):
                        if _nrole.strip():
                            new_p = PersonaProfile(role_label=_nrole.strip(), relation=_nrel, appellation=_napp, personality=_npers, speech_style=_nsp_list, comfort_style=_ncomf)
                            set_persona(new_p)
                            from engine.persona import add_or_update_persona
                            add_or_update_persona(new_p)
                            db_save_persona({"role_label":new_p.role_label,"relation":new_p.relation,"appellation":new_p.appellation,"personality":new_p.personality,"speech_style":new_p.speech_style,"comfort_style":new_p.comfort_style,"mood_preference":new_p.mood_preference,"topic_affinity":new_p.topic_affinity,"sensitivity_map":new_p.sensitivity_map})
                            st.session_state.show_new_persona_form = False
                            st.rerun()
                with nc:
                    if st.button("取消", key="btn_cancel_new_persona", use_container_width=True):
                        st.session_state.show_new_persona_form = False
                        st.rerun()
    else:
        # 无画像时显示新增表单
        with st.expander("➕ 新增人物画像", expanded=True):
            _role = st.text_input("角色标签", value="儿子小明", key="form_role_label")
            _rel = st.selectbox("与老人的关系", ["子女","配偶","孙辈","朋友","护工"], key="form_relation")
            _app = st.text_input("对老人的称呼", value="妈", key="form_appellation")
            _pers = st.multiselect("性格标签", ["温和","幽默","细心","沉稳","话多","乐观","感性","活泼","内向","开朗","随和","大条"], default=["温和","细心"], key="form_personality")
            _sp = st.text_area("说话风格（一行一条）", value="喜欢用叠词\n开头爱问吃了没", key="form_speech_style")
            _sp_list = [s.strip() for s in _sp.split("\n") if s.strip()]
            _comf = st.multiselect("陪伴行为方式", ["唠家常","撒娇","讲趣事","一起回忆","逗开心","讲道理","转移话题","鼓励","附和倾听","默默陪伴"], default=["唠家常","讲趣事"], key="form_comfort_style")
            if st.button("💾 保存人物画像", key="btn_new_persona"):
                persona = PersonaProfile(role_label=_role, relation=_rel, appellation=_app, personality=_pers, speech_style=_sp_list, comfort_style=_comf)
                set_persona(persona)
                db_save_persona({"role_label":persona.role_label,"relation":persona.relation,"appellation":persona.appellation,"personality":persona.personality,"speech_style":persona.speech_style,"comfort_style":persona.comfort_style,"mood_preference":persona.mood_preference,"topic_affinity":persona.topic_affinity,"sensitivity_map":persona.sensitivity_map})
                st.rerun()

    st.divider()

    # ===== 家人偏好档案 =====
    st.header("👥 家人档案")

    family_profiles = get_all_profiles()
    st.caption(f"共 {len(family_profiles)} 人")

    for fname, fp in list(family_profiles.items()):
        edit_fp_key = f"edit_fp_{fname}"
        if not st.session_state.get(edit_fp_key, False):
            with st.container(border=True):
                st.caption(f"**{fp.name}** · {fp.relation}")
                if fp.personality:
                    st.caption(f"性格：{'、'.join(fp.personality)}")
                if fp.preferences:
                    st.caption(f"喜好：{'、'.join(fp.preferences)}")
                if fp.habits:
                    st.caption(f"习惯：{'、'.join(fp.habits)}")
                if fp.relations:
                    rel_text = "；".join(f"{r.get('person') or r.get('name','?')}→{r.get('relation','?')}" for r in fp.relations if isinstance(r, dict))
                    st.caption(f"家人关系：{rel_text}")
                if fp.notes:
                    st.caption(fp.notes)
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("✏️", key=f"btn_edit_fp_{fname}", help="编辑"):
                        st.session_state[edit_fp_key] = True
                        st.rerun()
                with c2:
                    if st.button("🗑️", key=f"btn_del_fp_{fname}", help="删除"):
                        remove_profile(fname)
                        db_delete_family(fname)
                        st.rerun()
        else:
            with st.expander(f"✏️ {fp.name}", expanded=True):
                new_name = st.text_input("姓名", value=fp.name, key=f"edit_fp_name_{fname}")
                new_rel = st.text_input("关系", value=fp.relation, key=f"edit_fp_rel_{fname}")
                new_pers = st.text_input("性格（逗号分隔）", value="、".join(fp.personality), key=f"edit_fp_pers_{fname}")
                new_prefs = st.text_input("喜好（逗号分隔）", value="、".join(fp.preferences), key=f"edit_fp_prefs_{fname}")
                new_habits = st.text_input("习惯（逗号分隔）", value="、".join(fp.habits), key=f"edit_fp_hab_{fname}")
                default_rels = "、".join(f"{r.get('person') or r.get('name','?')}→{r.get('relation','?')}" for r in fp.relations if isinstance(r, dict))
                new_rels = st.text_input("家人关系（人→关系，、分隔）", value=default_rels, key=f"edit_fp_rels_{fname}", placeholder="小红→妻子、小花→女儿")
                new_notes = st.text_input("备注", value=fp.notes, key=f"edit_fp_notes_{fname}")
                cs, cc = st.columns(2)
                with cs:
                    if st.button("💾 保存", key=f"btn_save_fp_{fname}", use_container_width=True):
                        fp.name = new_name.strip()
                        fp.relation = new_rel.strip()
                        fp.personality = [x.strip() for x in new_pers.split("、") if x.strip()]
                        fp.preferences = [x.strip() for x in new_prefs.split("、") if x.strip()]
                        fp.habits = [x.strip() for x in new_habits.split("、") if x.strip()]
                        fp.relations = []
                        for r in [x.strip() for x in new_rels.split("、") if x.strip()]:
                            parts = r.split("→", 1)
                            if len(parts)==2: fp.relations.append({"person":parts[0].strip(),"relation":parts[1].strip()})
                        fp.notes = new_notes.strip()
                        add_profile(fp)
                        db_save_family({"name":fp.name,"relation":fp.relation,"personality":fp.personality,"preferences":fp.preferences,"habits":fp.habits,"relations":fp.relations,"notes":fp.notes})
                        if fp.name != fname: remove_profile(fname); db_delete_family(fname)
                        st.session_state[edit_fp_key] = False
                        st.rerun()
                with cc:
                    if st.button("取消", key=f"btn_cancel_fp_{fname}", use_container_width=True):
                        st.session_state[edit_fp_key] = False
                        st.rerun()

    with st.expander("➕ 新增家人", expanded=len(family_profiles)==0):
        nf_name = st.text_input("姓名", key="new_fp_name", placeholder="如：小明")
        nf_rel = st.text_input("关系", key="new_fp_rel", placeholder="如：儿子")
        nf_pers = st.text_input("性格（逗号分隔）", key="new_fp_pers")
        nf_prefs = st.text_input("喜好（逗号分隔）", key="new_fp_prefs")
        nf_habits = st.text_input("习惯（逗号分隔）", key="new_fp_hab")
        nf_notes = st.text_input("备注", key="new_fp_notes")
        if st.button("➕ 添加家人", key="btn_add_fp"):
            if nf_name.strip():
                fp = FamilyProfile(
                    name=nf_name.strip(), relation=nf_rel.strip(),
                    personality=[x.strip() for x in nf_pers.split("、") if x.strip()],
                    preferences=[x.strip() for x in nf_prefs.split("、") if x.strip()],
                    habits=[x.strip() for x in nf_habits.split("、") if x.strip()],
                    notes=nf_notes.strip(),
                )
                add_profile(fp)
                db_save_family({"name":fp.name,"relation":fp.relation,"personality":fp.personality,"preferences":fp.preferences,"habits":fp.habits,"relations":fp.relations,"notes":fp.notes})
                for k in ["new_fp_name","new_fp_rel","new_fp_pers","new_fp_prefs","new_fp_hab","new_fp_notes"]:
                    st.session_state.pop(k, None)
                st.rerun()

    st.divider()

    # ===== 家庭记忆管理 =====
    st.header("📝 家庭记忆")

    memories = get_all_memories()
    c_count, c_clear = st.columns([3, 1])
    with c_count:
        st.caption(f"共 {len(memories)} 条记忆")
    with c_clear:
        if memories and st.button("🗑️ 全部删除", key="btn_clear_all_mem", use_container_width=True):
            from engine.memory import _memory_store
            for m in list(_memory_store):
                db_delete_memory(m.id)
            clear_memories()
            st.rerun()

    for i, mem in enumerate(memories):
        edit_key = f"edit_mem_{mem.id}"
        if not st.session_state.get(edit_key, False):
            # 读模式卡片
            with st.container(border=True):
                c_title, c_btn1, c_btn2 = st.columns([3, 1, 1])
                with c_title:
                    st.caption(f"**{mem.memory_type}** · {mem.content[:40]}{'...' if len(mem.content)>40 else ''}")
                with c_btn1:
                    if st.button("✏️", key=f"btn_edit_{mem.id}", help="编辑"):
                        st.session_state[edit_key] = True
                        st.rerun()
                with c_btn2:
                    if st.button("🗑️", key=f"btn_del_{mem.id}", help="删除"):
                        remove_memory(mem.id)
                        db_delete_memory(mem.id)
                        st.rerun()
                if mem.family_members:
                    st.caption(f"家人：{', '.join(mem.family_members)}")
                tags_text = " · ".join(mem.emotion_tags[:3] + mem.topic_tags[:2])
                if tags_text:
                    st.caption(tags_text)
        else:
            # 编辑模式
            with st.expander(f"✏️ {mem.memory_type} · {mem.content[:20]}...", expanded=True):
                new_content = st.text_input("记忆正文", value=mem.content, key=f"edit_content_{mem.id}")
                new_type = st.selectbox("记忆类型", ["事件","习惯","偏好","重要日期","趣事"],
                    index=["事件","习惯","偏好","重要日期","趣事"].index(mem.memory_type) if mem.memory_type in ["事件","习惯","偏好","重要日期","趣事"] else 0,
                    key=f"edit_type_{mem.id}")
                fam_text = ", ".join(mem.family_members)
                new_fam = st.text_input("涉及家人（逗号分隔）", value=fam_text, key=f"edit_fam_{mem.id}")
                new_emo = st.multiselect("情感标签", ["温馨","快乐","感动","搞笑","难忘","遗憾","伤感","兴奋"],
                    default=mem.emotion_tags, key=f"edit_emo_{mem.id}")
                new_topic = st.multiselect("话题标签", ["饮食","旅行","节日","成长","健康","宠物","工作","日常"],
                    default=mem.topic_tags, key=f"edit_topic_{mem.id}")
                new_intimacy = st.slider("亲密度权重", 0.0, 1.0, mem.intimacy_weight, 0.1, key=f"edit_int_{mem.id}")

                cs, cc = st.columns(2)
                with cs:
                    if st.button("💾 保存", key=f"btn_save_{mem.id}", use_container_width=True):
                        mem.content = new_content
                        mem.memory_type = new_type
                        mem.family_members = [x.strip() for x in new_fam.split(",") if x.strip()]
                        mem.emotion_tags = new_emo
                        mem.topic_tags = new_topic
                        mem.intimacy_weight = new_intimacy
                        db_save_memory({"id":mem.id,"content":mem.content,"memory_type":mem.memory_type,"subject":mem.subject,"family_members":mem.family_members,"emotion_tags":mem.emotion_tags,"topic_tags":mem.topic_tags,"intimacy_weight":mem.intimacy_weight})
                        st.session_state[edit_key] = False
                        st.rerun()
                with cc:
                    if st.button("取消", key=f"btn_cancel_{mem.id}", use_container_width=True):
                        st.session_state[edit_key] = False
                        st.rerun()

    # 新增记忆（可折叠）
    with st.expander("➕ 添加新记忆", expanded=len(memories)==0):
        new_content = st.text_area("记忆正文", key="new_mem_content", placeholder="如：去年中秋全家去西湖赏月，小明给奶奶剥螃蟹")
        new_type = st.selectbox("记忆类型", ["事件","习惯","偏好","重要日期","趣事"], key="new_mem_type")
        new_fam = st.text_input("涉及家人（逗号分隔）", key="new_mem_family", placeholder="小明(儿子), 小红(孙女)")
        new_emo = st.multiselect("情感标签", ["温馨","快乐","感动","搞笑","难忘","遗憾","伤感","兴奋"], key="new_mem_emo")
        new_topic = st.multiselect("话题标签", ["饮食","旅行","节日","成长","健康","宠物","工作","日常"], key="new_mem_topic")
        new_intimacy = st.slider("亲密度权重", 0.0, 1.0, 0.5, 0.1, key="new_mem_intimacy")
        if st.button("➕ 添加", key="btn_add_mem"):
            if new_content.strip():
                members = [m.strip() for m in new_fam.split(",") if m.strip()]
                mem = MemoryUnit(content=new_content.strip(), memory_type=new_type, family_members=members, emotion_tags=new_emo, topic_tags=new_topic, intimacy_weight=new_intimacy)
                add_memory(mem)
                db_save_memory({"id":mem.id,"content":mem.content,"memory_type":mem.memory_type,"subject":mem.subject,"family_members":mem.family_members,"emotion_tags":mem.emotion_tags,"topic_tags":mem.topic_tags,"intimacy_weight":mem.intimacy_weight})
                for k in ["new_mem_content","new_mem_type","new_mem_family","new_mem_emo","new_mem_topic","new_mem_intimacy"]:
                    st.session_state.pop(k, None)
                st.rerun()

    st.divider()

    # ===== 评分权重 =====
    st.header("⚖️ 评分权重")
    alpha = st.slider("α 相关性", 0.0, 1.0, DEFAULT_WEIGHTS["alpha"], 0.05)
    beta = st.slider("β 共情度", 0.0, 1.0, DEFAULT_WEIGHTS["beta"], 0.05)
    gamma = st.slider("γ 亲密度", 0.0, 1.0, DEFAULT_WEIGHTS["gamma"], 0.05)
    delta = st.slider("δ 安全性", 0.0, 1.0, DEFAULT_WEIGHTS["delta"], 0.05)
    epsilon = st.slider("ε 罚分", 0.0, 1.0, DEFAULT_WEIGHTS["epsilon"], 0.05)
    weights = {"alpha": alpha, "beta": beta, "gamma": gamma, "delta": delta, "epsilon": epsilon}


# ===== 核心 Pipeline =====

def run_pipeline(user_input: str) -> str:
    persona = get_persona()
    all_memories = get_all_memories()

    # Step 1: LLM 识别意图+情绪+对话对象+提及人物
    try:
        raw = chat(INTENT_EMOTION_SYSTEM, INTENT_EMOTION_USER.format(user_input=user_input), temperature=0.3)
        result = parse_llm_json(raw)
    except Exception:
        result = {"intent": "日常闲聊", "emotion": "平静", "confidence": 0.0, "keywords": [], "talk_to": "陪伴者", "mentioned": []}

    intent = result.get("intent", "日常闲聊")
    emotion = result.get("emotion", "平静")
    mentioned_names = result.get("mentioned", [])

    # 自动切换人物画像：检测老人正在和谁说话
    talk_to = result.get("talk_to", "")
    all_personas = get_all_personas()
    # 模糊匹配：LLM 返回"小明"可匹配"儿子小明"
    matched_persona = None
    if talk_to:
        if talk_to in all_personas:
            matched_persona = talk_to
        else:
            for k in all_personas:
                if talk_to in k or k in talk_to:
                    matched_persona = k
                    break
    if matched_persona:
        if persona.role_label != matched_persona:
            switch_persona(matched_persona)
            persona = get_persona()
            st.session_state.auto_switched = matched_persona  # 下次渲染时同步下拉框
    # 没提到具体角色 → 保持当前 persona（可能为空，走通用模式）

    # Step 2: 根据提及人物 + 对话对象检索相关记忆
    relevant_memories = []
    for mem in all_memories:
        # 记忆被提及人物匹配，或记忆主语是当前角色
        if mem.subject in mentioned_names or mem.subject == persona.role_label:
            relevant_memories.append(mem)
    # 如果没匹配到特定记忆，用全部记忆
    if not relevant_memories:
        relevant_memories = list(all_memories)

    # Step 3: 评分 → 过滤(S/M) → 排序(R+C) → top-5
    top_memories = []
    scored_list = []
    if relevant_memories:
        scored_list = score_memories(relevant_memories, user_input, intent, emotion, persona, weights)
        top_memories = get_top_memories(scored_list, n=5)

    # Step 4: 策略选择
    strategy = select_strategy(intent, emotion, persona)

    # Step 5: 构建提及人物画像上下文
    mentioned_context = ""
    all_personas = get_all_personas()
    for name in mentioned_names:
        other_p = all_personas.get(name)
        if other_p and name != persona.role_label:
            parts = [f"{name}是{other_p.relation}"]
            if other_p.personality:
                parts.append(f"性格{'、'.join(other_p.personality)}")
            if other_p.speech_style:
                parts.append(f"说话风格{'；'.join(other_p.speech_style)}")
            mentioned_context += "\n## 老人提到的人\n老人提到了" + name + "。" + "，".join(parts) + "。你可以用你对" + name + "的了解来自然地聊到ta。\n"

    # 如果老人在和某个已存储角色说话，注入该角色画像
    if matched_persona and matched_persona != persona.role_label:
        tp = all_personas[matched_persona]
        mentioned_context += f"\n## 对话对象\n老人正在和{matched_persona}说话。{matched_persona}是{tp.relation}，性格{'、'.join(tp.personality) if tp.personality else '随和'}。\n"

    # Step 6: 构建上下文（老人画像 + 家人偏好 + 关系表）
    elder_context = ""
    elder = get_elder()
    if elder.full_name:
        gender_text = {"男":"老爷爷","女":"老奶奶"}.get(elder.gender,"老人")
        parts = [f"{gender_text}「{elder.full_name}」"]
        if elder.personality: parts.append(f"性格{'、'.join(elder.personality)}")
        if elder.preferences: parts.append(f"喜好{'、'.join(elder.preferences)}")
        if elder.habits: parts.append(f"习惯{'、'.join(elder.habits)}")
        if elder.health_notes: parts.append(f"健康注意{'、'.join(elder.health_notes)}")
        if elder.speech_traits: parts.append(f"说话特点{'、'.join(elder.speech_traits)}")
        if elder.life_experiences: parts.append(f"人生经历{'、'.join(elder.life_experiences)}")
        elder_context = "## 老人画像\n" + "，".join(parts) + "。请根据老人的性格、健康状况和说话特点来调整你的回复风格。\n\n"

    family_context = ""
    all_families = get_all_profiles()
    for name in mentioned_names:
        fp = all_families.get(name)
        if fp:
            parts = [f"{fp.name}是老人的{fp.relation}"]
            if fp.personality: parts.append(f"性格{'、'.join(fp.personality)}")
            if fp.preferences: parts.append(f"喜好{'、'.join(fp.preferences)}")
            if fp.habits: parts.append(f"习惯{'、'.join(fp.habits)}")
            family_context += f"- {fp.name}（{'，'.join(parts)}）\n"
            # 家人关系表
            if fp.relations:
                rel_parts = [f"{r.get('person') or r.get('name','?')}的{r.get('relation','?')}" for r in fp.relations if isinstance(r, dict)]
                family_context += f"  关系：{fp.name}是{'，'.join(rel_parts)}\n"
    if family_context:
        family_context = "## 家人偏好档案\n" + family_context + "\n"

    family_context = elder_context + family_context

    # Step 7: LLM 生成回复
    memory_context = build_memory_context(top_memories)
    system_prompt = build_response_system(
        role_label=persona.role_label or "家人",
        appellation=persona.appellation or get_elder().get_appellation() or "您",
        personality=persona.personality,
        speech_style=persona.speech_style,
        comfort_style=persona.comfort_style,
        strategy=strategy,
        memory_context=memory_context,
        mentioned_persona_context=mentioned_context,
        family_profiles_context=family_context,
    )

    max_retries = 2
    response = ""
    for attempt in range(max_retries):
        try:
            response = chat(system_prompt, RESPONSE_USER.format(user_input=user_input, role_label=persona.role_label or "家人"), temperature=0.7)
        except Exception:
            response = f"{persona.appellation or '您'}，我这边信号不太好，您再说一遍？"
            break

        adapt_result = check_elderly_adaptation(response, persona.appellation or "")
        safety_issues = safety_check(response)

        if adapt_result["pass"] and not safety_issues:
            break

        if attempt < max_retries - 1:
            hint = build_retry_hint(adapt_result["issues"], safety_issues)
            system_prompt = build_response_system(
                role_label=persona.role_label or "家人",
                appellation=persona.appellation or get_elder().get_appellation() or "您",
                personality=persona.personality,
                speech_style=persona.speech_style,
                comfort_style=persona.comfort_style,
                strategy=strategy,
                memory_context=memory_context,
                retry_hint=hint,
                mentioned_persona_context=mentioned_context,
                family_profiles_context=family_context,
            )

    # 更新记忆访问记录
    for mem in top_memories[:3]:
        mem.access_count += 1
        mem.last_accessed = datetime.now()

    st.session_state.debug = {
        "intent": intent,
        "emotion": emotion,
        "talk_to": matched_persona or talk_to,
        "mentioned": mentioned_names,
        "strategy": strategy,
        "top_memories": [
            {"subject": m.subject or "老人", "content": m.content[:40]}
            for m in top_memories
        ],
        "scores": [
            {"id": sr.memory.id, "subject": sr.memory.subject or "-",
             "content": sr.memory.content[:30],
             "R": round(sr.score_r, 3), "E": round(sr.score_e, 3),
             "C": round(sr.score_c, 3), "S": round(sr.score_s, 3),
             "M": round(sr.penalty_m, 3), "total": round(sr.total, 3)}
            for sr in scored_list[:5]
        ],
        "confidence": result.get("confidence", 0),
    }

    return response


# ===== 对话界面 =====

for msg in st.session_state.messages:
    with st.chat_message(msg["role"], avatar=msg.get("avatar")):
        st.write(msg["content"])

if user_input := st.chat_input("在这里输入老人的话..."):
    st.session_state.messages.append({"role": "user", "content": user_input, "avatar": "👵"})
    with st.chat_message("user", avatar="👵"):
        st.write(user_input)

    with st.spinner("思考中..."):
        response = run_pipeline(user_input)

    st.session_state.messages.append({"role": "assistant", "content": response, "avatar": "❤️"})
    with st.chat_message("assistant", avatar="❤️"):
        st.write(response)


# ===== 调试面板 =====
with st.expander("🔍 调试面板", expanded=False):
    debug = st.session_state.debug
    if debug:
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1: st.metric("意图", debug.get("intent", "N/A"))
        with col2: st.metric("情绪", debug.get("emotion", "N/A"))
        with col3: st.metric("对话对象", debug.get("talk_to", "N/A"))
        with col4: st.metric("策略", debug.get("strategy", "N/A"))
        with col5: st.metric("置信度", debug.get("confidence", 0))
        mentioned = debug.get("mentioned", [])
        if mentioned:
            st.write(f"**提及人物**: {', '.join(mentioned)}")
        top = debug.get("top_memories", [])
        if top:
            st.write("**Top 记忆**:")
            st.dataframe(top, use_container_width=True)
        scores = debug.get("scores", [])
        if scores:
            st.write("**评分详情**:")
            st.dataframe(scores, use_container_width=True)
    else:
        st.caption("发送一条消息后查看调试信息")


# ===== 底部提示 =====
st.divider()
if not get_persona().is_complete():
    st.warning("⚠️ 请先在侧边栏填写人物画像并保存，或使用智能导入")
if memory_count() == 0:
    st.info("💡 请先在侧边栏添加家庭记忆，或使用智能导入一键生成")
