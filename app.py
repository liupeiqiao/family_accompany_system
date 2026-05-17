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
from llm.parser import parse_user_text
from engine.memory import MemoryUnit, add_memory, remove_memory, get_all_memories, clear_memories
from engine.persona import PersonaProfile, set_persona, get_persona, get_all_personas, remove_persona, switch_persona
from engine.scorer import score_memories, get_best_memory, DEFAULT_WEIGHTS
from engine.strategy import select_strategy
from engine.adaptation import check_elderly_adaptation, safety_check, build_retry_hint
from engine.db import init_db, save_persona as db_save_persona, load_persona as db_load_persona
from engine.db import load_all_personas as db_load_all_personas, delete_persona as db_delete_persona
from engine.db import save_memory as db_save_memory, delete_memory as db_delete_memory, load_all_memories as db_load_memories

st.set_page_config(page_title="亲情陪伴系统", page_icon="❤️", layout="wide")
st.title("❤️ 亲情陪伴系统")
st.caption("基于家庭记忆的适老共情对话原型")

# ===== 初始化 DB + session_state =====
init_db()

if "messages" not in st.session_state:
    st.session_state.messages = []
if "debug" not in st.session_state:
    st.session_state.debug = {}
if "db_loaded" not in st.session_state:
    st.session_state.db_loaded = False

# 首次加载：从 SQLite 恢复到内存
if not st.session_state.db_loaded:
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

    for mdata in db_load_memories():
        mem = MemoryUnit(
            id=mdata["id"],
            content=mdata["content"],
            memory_type=mdata.get("memory_type", ""),
            family_members=mdata.get("family_members", []),
            emotion_tags=mdata.get("emotion_tags", []),
            topic_tags=mdata.get("topic_tags", []),
            intimacy_weight=mdata.get("intimacy_weight", 0.5),
        )
        add_memory(mem)

    # 确保表单字段有初始值
    for key, default in [
        ("form_role_label", "儿子小明"), ("form_relation", "子女"), ("form_appellation", "妈"),
        ("form_personality", ["温和", "细心"]),
        ("form_speech_style", "喜欢用叠词\n开头爱问吃了没"),
        ("form_comfort_style", ["唠家常", "讲趣事", "一起回忆"]),
    ]:
        if key not in st.session_state:
            st.session_state[key] = default

    st.session_state.db_loaded = True


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


def build_memory_context(selected_memory: MemoryUnit | None) -> str:
    if selected_memory is None:
        return ""
    parts = [
        f"事件：{selected_memory.content}",
        f"涉及：{', '.join(selected_memory.family_members)}",
    ]
    if selected_memory.emotion_tags:
        parts.append(f"当时心情：{'、'.join(selected_memory.emotion_tags)}")
    return "\n".join(parts)


# ===== Sidebar =====
with st.sidebar:
    # ===== 智能导入 =====
    st.header("🧠 智能导入")
    st.caption("粘贴一段描述，AI 自动提取人物画像和家庭记忆")

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
                    parsed = parse_user_text(smart_text.strip())
                    st.session_state.parsed = parsed
                    persona_part = parsed.get("persona", {})
                    memories_part = parsed.get("memories", [])
                    st.success(f"解析完成：画像1份 + 记忆{len(memories_part)}条")
            else:
                st.warning("请先输入描述文字")

    with col_s2:
        if st.button("📥 一键导入", use_container_width=True):
            parsed = st.session_state.get("parsed", {})
            if parsed:
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
                    existing = gap().get(p.role_label)
                    if existing:
                        p = merge_persona(existing, persona_part)
                    add_p(p)
                    # 如果没有当前画像，自动切换到刚导入的角色
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
                        family_members=md.get("family_members", []),
                        emotion_tags=md.get("emotion_tags", []),
                        topic_tags=md.get("topic_tags", []),
                    )
                    add_memory(mem)
                    db_save_memory({
                        "id": mem.id,
                        "content": mem.content,
                        "memory_type": mem.memory_type,
                        "family_members": mem.family_members,
                        "emotion_tags": mem.emotion_tags,
                        "topic_tags": mem.topic_tags,
                        "intimacy_weight": mem.intimacy_weight,
                    })
                st.success(f"已导入！画像+{len(parsed.get('memories', []))}条记忆")
                st.session_state.parsed = {}
                st.rerun()
            else:
                st.warning("请先点击「智能解析」")

    # 预览解析结果（可编辑）
    parsed_preview = st.session_state.get("parsed", {})
    if parsed_preview:
        with st.expander("📋 解析预览（可直接修改后导入）", expanded=True):
            st.caption("以下字段均可直接编辑，修改后点「一键导入」即用编辑后的数据入库")

            pp = parsed_preview.get("persona", {})
            if pp:
                st.write("**人物画像**")
                col_p1, col_p2 = st.columns(2)
                with col_p1:
                    pp["role_label"] = st.text_input("角色标签", value=pp.get("role_label", ""), key="prev_role")
                    pp["appellation"] = st.text_input("称呼", value=pp.get("appellation", ""), key="prev_app")
                with col_p2:
                    relation_opts = ["子女", "配偶", "孙辈", "朋友", "护工"]
                    cur_rel = pp.get("relation", "子女")
                    rel_idx = relation_opts.index(cur_rel) if cur_rel in relation_opts else 0
                    pp["relation"] = st.selectbox("关系", relation_opts, index=rel_idx, key="prev_rel")

                all_personality = ["温和", "幽默", "细心", "沉稳", "话多", "乐观", "感性"]
                pp["personality"] = st.multiselect("性格标签", all_personality,
                    default=pp.get("personality", []), key="prev_pers")

                speech_text = "\n".join(pp.get("speech_style", []))
                new_speech = st.text_area("说话风格（一行一条）", value=speech_text, key="prev_speech")
                pp["speech_style"] = [s.strip() for s in new_speech.split("\n") if s.strip()]

                all_comfort = ["唠家常", "撒娇", "讲趣事", "一起回忆", "逗开心",
                               "讲道理", "转移话题", "鼓励", "附和倾听", "默默陪伴"]
                pp["comfort_style"] = st.multiselect("陪伴方式", all_comfort,
                    default=pp.get("comfort_style", []), key="prev_comfort")

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
                                f"情感标签{i+1}", all_emo, default=m.get("emotion_tags", []), key=f"prev_me_{i}"
                            )
                        all_topics = ["饮食", "旅行", "节日", "成长", "健康", "宠物", "工作", "日常"]
                        m["topic_tags"] = st.multiselect(
                            f"话题标签{i+1}", all_topics, default=m.get("topic_tags", []), key=f"prev_mtpc_{i}"
                        )
                        st.divider()

                # 删除标记的记忆
                for idx in sorted(to_delete, reverse=True):
                    mems.pop(idx)
                    st.rerun()

    st.divider()

    # ===== 人物画像 =====
    st.header("👤 人物画像")

    all_personas_dict = get_all_personas()
    persona_labels = list(all_personas_dict.keys())
    current_persona = get_persona()

    # 角色切换下拉框
    if persona_labels:
        current_label = current_persona.role_label if current_persona.is_complete() and current_persona.role_label in persona_labels else persona_labels[0]
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
                        st.session_state.edit_persona = False
                        st.rerun()

        # 画像编辑模式（内联展开）
        if st.session_state.get("edit_persona", False):
            with st.expander("✏️ 编辑人物画像", expanded=True):
                _role = st.text_input("角色标签", key="edit_role_label")
                _rel = st.selectbox("与老人的关系", ["子女","配偶","孙辈","朋友","护工"], key="edit_relation")
                _app = st.text_input("对老人的称呼", key="edit_appellation")
                _pers = st.multiselect("性格标签", ["温和","幽默","细心","沉稳","话多","乐观","感性"], key="edit_personality")
                _sp = st.text_area("说话风格（一行一条）", key="edit_speech_style")
                _sp_list = [s.strip() for s in _sp.split("\n") if s.strip()]
                _comf = st.multiselect("陪伴行为方式", ["唠家常","撒娇","讲趣事","一起回忆","逗开心","讲道理","转移话题","鼓励","附和倾听","默默陪伴"], key="edit_comfort_style")

                c_save, c_cancel = st.columns(2)
                with c_save:
                    if st.button("💾 保存", key="btn_save_persona", use_container_width=True):
                        persona = PersonaProfile(role_label=_role, relation=_rel, appellation=_app, personality=_pers, speech_style=_sp_list, comfort_style=_comf)
                        set_persona(persona)
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
                _npers = st.multiselect("性格标签", ["温和","幽默","细心","沉稳","话多","乐观","感性"], key="new_persona_pers")
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
            _pers = st.multiselect("性格标签", ["温和","幽默","细心","沉稳","话多","乐观","感性"], default=["温和","细心"], key="form_personality")
            _sp = st.text_area("说话风格（一行一条）", value="喜欢用叠词\n开头爱问吃了没", key="form_speech_style")
            _sp_list = [s.strip() for s in _sp.split("\n") if s.strip()]
            _comf = st.multiselect("陪伴行为方式", ["唠家常","撒娇","讲趣事","一起回忆","逗开心","讲道理","转移话题","鼓励","附和倾听","默默陪伴"], default=["唠家常","讲趣事"], key="form_comfort_style")
            if st.button("💾 保存人物画像", key="btn_new_persona"):
                persona = PersonaProfile(role_label=_role, relation=_rel, appellation=_app, personality=_pers, speech_style=_sp_list, comfort_style=_comf)
                set_persona(persona)
                db_save_persona({"role_label":persona.role_label,"relation":persona.relation,"appellation":persona.appellation,"personality":persona.personality,"speech_style":persona.speech_style,"comfort_style":persona.comfort_style,"mood_preference":persona.mood_preference,"topic_affinity":persona.topic_affinity,"sensitivity_map":persona.sensitivity_map})
                st.rerun()

    st.divider()

    # ===== 家庭记忆管理 =====
    st.header("📝 家庭记忆")

    memories = get_all_memories()
    st.caption(f"共 {len(memories)} 条记忆")

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
                        db_save_memory({"id":mem.id,"content":mem.content,"memory_type":mem.memory_type,"family_members":mem.family_members,"emotion_tags":mem.emotion_tags,"topic_tags":mem.topic_tags,"intimacy_weight":mem.intimacy_weight})
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
                db_save_memory({"id":mem.id,"content":mem.content,"memory_type":mem.memory_type,"family_members":mem.family_members,"emotion_tags":mem.emotion_tags,"topic_tags":mem.topic_tags,"intimacy_weight":mem.intimacy_weight})
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
    memories = get_all_memories()

    try:
        raw = chat(INTENT_EMOTION_SYSTEM, INTENT_EMOTION_USER.format(user_input=user_input), temperature=0.3)
        result = parse_llm_json(raw)
    except Exception:
        result = {"intent": "日常闲聊", "emotion": "平静", "confidence": 0.0, "keywords": []}

    intent = result.get("intent", "日常闲聊")
    emotion = result.get("emotion", "平静")

    selected_memory = None
    scored_list = []
    if memories:
        scored_list = score_memories(memories, user_input, intent, emotion, persona, weights)
        selected_memory = get_best_memory(scored_list)

    strategy = select_strategy(intent, emotion, persona)
    memory_context = build_memory_context(selected_memory)

    # 检测是否提及其他已存储角色
    mentioned_context = ""
    all_personas = get_all_personas()
    for name, other_p in all_personas.items():
        if name != persona.role_label and name in user_input:
            parts = [f"{name}是{other_p.relation}"]
            if other_p.personality:
                parts.append(f"性格{'、'.join(other_p.personality)}")
            if other_p.speech_style:
                parts.append(f"说话风格{'；'.join(other_p.speech_style)}")
            mentioned_context = "\n## 老人提到的人\n老人提到了" + name + "。" + "，".join(parts) + "。你可以用你对" + name + "的了解来自然地聊到ta。\n"
            break

    system_prompt = build_response_system(
        role_label=persona.role_label or "家人",
        appellation=persona.appellation or "您",
        personality=persona.personality,
        speech_style=persona.speech_style,
        comfort_style=persona.comfort_style,
        strategy=strategy,
        memory_context=memory_context,
        mentioned_persona_context=mentioned_context,
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
                appellation=persona.appellation or "您",
                personality=persona.personality,
                speech_style=persona.speech_style,
                comfort_style=persona.comfort_style,
                strategy=strategy,
                memory_context=memory_context,
                retry_hint=hint,
                mentioned_persona_context=mentioned_context,
            )

    if selected_memory:
        selected_memory.access_count += 1
        selected_memory.last_accessed = datetime.now()

    st.session_state.debug = {
        "intent": intent,
        "emotion": emotion,
        "strategy": strategy,
        "selected_memory": selected_memory.content[:80] + "..." if selected_memory else "无",
        "memory_id": selected_memory.id if selected_memory else "N/A",
        "scores": [
            {"id": sr.memory.id, "content": sr.memory.content[:40],
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
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("意图", debug.get("intent", "N/A"))
        with col2:
            st.metric("情绪", debug.get("emotion", "N/A"))
        with col3:
            st.metric("策略", debug.get("strategy", "N/A"))
        with col4:
            st.metric("置信度", debug.get("confidence", 0))
        st.write(f"**选中记忆**: {debug.get('selected_memory', 'N/A')}")
        scores = debug.get("scores", [])
        if scores:
            st.write("**评分详情 (Top 5):**")
            st.dataframe(scores, use_container_width=True)
    else:
        st.caption("发送一条消息后查看调试信息")


# ===== 底部提示 =====
st.divider()
if not get_persona().is_complete():
    st.warning("⚠️ 请先在侧边栏填写人物画像并保存，或使用智能导入")
if memory_count() == 0:
    st.info("💡 请先在侧边栏添加家庭记忆，或使用智能导入一键生成")
