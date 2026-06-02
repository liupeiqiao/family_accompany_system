"""智能合并账号中已有数据的去重脚本（使用 repository API，避免裸 SQL）.

用法:
    python scripts/dedup_account.py --phone 88888888 [--dry-run]

需要环境变量 DATABASE_URL 指向 PostgreSQL。
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from collections import defaultdict


def _normalize_content(content: str) -> str:
    normalized = re.sub(r"[\s\-_，。,.！？!；;：:、\"“”'‘’（）()]+", "", content or "")
    return normalized.casefold()


def _merge_string(existing: str | None, incoming: str | None) -> str:
    t1 = str(existing or "").strip()
    t2 = str(incoming or "").strip()
    return t1 if t1 else t2


def _merge_list(existing, incoming) -> list:
    items1 = existing if isinstance(existing, list) else ([] if not existing else [existing])
    items2 = incoming if isinstance(incoming, list) else ([] if not incoming else [incoming])
    seen = set()
    result = []
    for item in [*items1, *items2]:
        key = str(item).strip()
        if key and key not in seen:
            seen.add(key)
            result.append(item)
    return result


def _merge_notes(existing, incoming) -> str:
    t1 = str(existing or "").strip()
    t2 = str(incoming or "").strip()
    if not t1:
        return t2
    if not t2 or t2 == t1:
        return t1
    from datetime import date
    return f"{t1}\n{date.today().isoformat()} 合并补充：{t2}"


def dedup_personas(personas: list[dict]) -> tuple[list[dict], list[str]]:
    """同 role_label 合并."""
    by_label: dict[str, list[dict]] = defaultdict(list)
    for p in personas:
        by_label[(p.get("role_label") or "").strip()].append(p)

    merged, log = [], []
    for label, group in by_label.items():
        if len(group) == 1:
            merged.append(group[0])
        else:
            log.append(f"  AI角色「{label}」: {len(group)}条 → 合并")
            base = dict(group[0])
            for dup in group[1:]:
                base["relation"] = _merge_string(base.get("relation"), dup.get("relation"))
                base["appellation"] = _merge_string(base.get("appellation"), dup.get("appellation"))
                base["personality"] = _merge_list(base.get("personality"), dup.get("personality"))
                base["speech_style"] = _merge_list(base.get("speech_style"), dup.get("speech_style"))
                base["comfort_style"] = _merge_list(base.get("comfort_style"), dup.get("comfort_style"))
                for df in ("mood_preference", "topic_affinity", "sensitivity_map"):
                    if isinstance(dup.get(df), dict):
                        base[df] = {**(base.get(df) or {}), **dup[df]}
            merged.append(base)
    return merged, log


def dedup_family_profiles(profiles: list[dict]) -> tuple[list[dict], list[str]]:
    """同 name 合并."""
    by_name: dict[str, list[dict]] = defaultdict(list)
    for fp in profiles:
        by_name[(fp.get("name") or "").strip()].append(fp)

    merged, log = [], []
    for name, group in by_name.items():
        if len(group) == 1:
            merged.append(group[0])
        else:
            log.append(f"  家人档案「{name}」: {len(group)}条 → 合并")
            base = dict(group[0])
            for dup in group[1:]:
                base["gender"] = _merge_string(base.get("gender"), dup.get("gender"))
                base["relation"] = _merge_string(base.get("relation"), dup.get("relation"))
                base["personality"] = _merge_list(base.get("personality"), dup.get("personality"))
                base["preferences"] = _merge_list(base.get("preferences"), dup.get("preferences"))
                base["habits"] = _merge_list(base.get("habits"), dup.get("habits"))
                base["relations"] = _merge_list(base.get("relations"), dup.get("relations"))
                base["notes"] = _merge_notes(base.get("notes"), dup.get("notes"))
            merged.append(base)
    return merged, log


def dedup_memories(memories: list[dict]) -> tuple[list[dict], list[str]]:
    """内容归一化后相同 → 保留一条."""
    by_content: dict[str, list[dict]] = defaultdict(list)
    for m in memories:
        norm = _normalize_content(m.get("content", ""))
        if norm:
            by_content[norm].append(m)

    merged, log = [], []
    for _, group in by_content.items():
        merged.append(group[0])
        if len(group) > 1:
            preview = str(group[0].get("content", ""))[:40]
            log.append(f"  记忆「{preview}」: {len(group)}条 → 保留1条")
    return merged, log


def dedup_elders(elders: list[dict]) -> tuple[dict | None, list[str]]:
    if not elders:
        return None, []
    if len(elders) == 1:
        return elders[0], []

    log = [f"  老人画像: {len(elders)}条 → 合并为1条"]
    base = dict(elders[0])
    for dup in elders[1:]:
        base["gender"] = _merge_string(base.get("gender"), dup.get("gender"))
        for f in ("personality", "preferences", "habits", "health_notes",
                   "speech_traits", "life_experiences", "important_memories"):
            base[f] = _merge_list(base.get(f), dup.get(f))
        base["notes"] = _merge_notes(base.get("notes"), dup.get("notes"))
    return base, log


def run(phone: str, *, dry_run: bool = False) -> None:
    from dotenv import load_dotenv
    load_dotenv()

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("错误: DATABASE_URL 未设置", file=sys.stderr)
        sys.exit(1)

    from productization.postgres_repository import PostgresCloudRepository

    repo = PostgresCloudRepository(database_url)
    repo.init_schema()

    # 查找 user_id
    with repo._connect() as conn:  # noqa: SLF001
        user = conn.execute("SELECT * FROM users WHERE phone = %s", (phone,)).fetchone()
        if not user:
            print(f"错误: 未找到手机号 {phone}", file=sys.stderr)
            sys.exit(1)
        user_id = str(user["id"])
    print(f"用户: {phone} (id={user_id})")

    # 获取家庭空间
    result = repo.get_current_family(user_id=user_id)
    family_id = str(result["family"]["id"])
    print(f"家庭: {result['family']['name']} (id={family_id})")

    # 读取所有数据（使用 repo API）
    elders_raw = repo.get_elder_current(family_id=family_id, user_id=user_id)
    elders = [dict(elders_raw)] if elders_raw and elders_raw.get("id") else []

    personas = repo.list_personas(family_id=family_id, user_id=user_id)
    profiles = repo.list_family_profiles(family_id=family_id, user_id=user_id)
    memories = repo.list_memories(family_id=family_id, user_id=user_id)

    print(f"\n当前数据: 老人画像 {len(elders)}条, AI角色 {len(personas)}个, "
          f"家人档案 {len(profiles)}条, 记忆 {len(memories)}条")

    # 去重分析
    merged_elders, e_log = dedup_elders([dict(e) for e in elders])
    merged_personas, p_log = dedup_personas([dict(p) for p in personas])
    merged_profiles, f_log = dedup_family_profiles([dict(p) for p in profiles])
    merged_memories, m_log = dedup_memories([dict(m) for m in memories])

    all_logs = [*e_log, *p_log, *f_log, *m_log]
    if not all_logs:
        print("\n✅ 没有发现重复数据。")
        return

    print(f"\n发现 {len(all_logs)} 组重复：")
    for l in all_logs:
        print(l)

    if dry_run:
        print(f"\n[Dry-run] 以上重复将被合并。")
        print(f"  老人 {len(elders)}→{1 if merged_elders else 0}, "
              f"角色 {len(personas)}→{len(merged_personas)}, "
              f"家人 {len(profiles)}→{len(merged_profiles)}, "
              f"记忆 {len(memories)}→{len(merged_memories)}")
        return

    # 执行合并：保留第一条，用 update 合并数据，删除其余重复项
    print("\n开始合并...")

    # --- Personas ---
    personas_by_label: dict[str, list[dict]] = defaultdict(list)
    for p in personas:
        personas_by_label[(p.get("role_label") or "").strip()].append(p)

    for label, group in personas_by_label.items():
        if len(group) <= 1:
            continue
        primary = group[0]
        print(f"  合并AI角色「{label}」(保留 {primary['id']}, 删除 {len(group)-1} 条)")
        for dup in group[1:]:
            merged_data = dict(dup)
            # 不覆盖已有的非空值
            for key in list(merged_data.keys()):
                if key in ("id", "created_at", "updated_at", "family_id"):
                    continue
                if primary.get(key):
                    existing_val = primary[key]
                    incoming_val = merged_data[key]
                    if isinstance(existing_val, list) and isinstance(incoming_val, list):
                        merged_data[key] = _merge_list(existing_val, incoming_val)
                    elif isinstance(existing_val, dict) and isinstance(incoming_val, dict):
                        merged_data[key] = {**existing_val, **incoming_val}
                    elif existing_val:
                        continue  # 已有非空值，不覆盖
            repo.update_persona(
                family_id=family_id, user_id=user_id,
                persona_id=str(primary["id"]), payload=merged_data,
            )
            repo.delete_persona(family_id=family_id, user_id=user_id, persona_id=str(dup["id"]))

    # --- Family profiles ---
    profiles_by_name: dict[str, list[dict]] = defaultdict(list)
    for fp in profiles:
        profiles_by_name[(fp.get("name") or "").strip()].append(fp)

    for name, group in profiles_by_name.items():
        if len(group) <= 1:
            continue
        primary = group[0]
        print(f"  合并家人档案「{name}」(保留 {primary['id']}, 删除 {len(group)-1} 条)")
        for dup in group[1:]:
            merged_data = dict(dup)
            for key in list(merged_data.keys()):
                if key in ("id", "created_at", "updated_at", "family_id"):
                    continue
                if primary.get(key):
                    existing_val = primary[key]
                    incoming_val = merged_data[key]
                    if isinstance(existing_val, list) and isinstance(incoming_val, list):
                        merged_data[key] = _merge_list(existing_val, incoming_val)
                    elif existing_val:
                        continue
            repo.update_family_profile(
                family_id=family_id, user_id=user_id,
                profile_id=str(primary["id"]), payload=merged_data,
            )
            repo.delete_family_profile(family_id=family_id, user_id=user_id, profile_id=str(dup["id"]))

    # --- Memories ---
    by_norm: dict[str, list[dict]] = defaultdict(list)
    for m in memories:
        norm = _normalize_content(m.get("content", ""))
        if norm:
            by_norm[norm].append(m)

    for norm, group in by_norm.items():
        if len(group) <= 1:
            continue
        primary = group[0]
        preview = str(primary.get("content", ""))[:40]
        print(f"  跳过重复记忆「{preview}」(保留 {primary['id']}, 删除 {len(group)-1} 条)")
        for dup in group[1:]:
            repo.delete_memory(family_id=family_id, user_id=user_id, memory_id=str(dup["id"]))

    # --- Elder ---
    if len(elders) > 1:
        print(f"  合并老人画像 (保留 {elders[0]['id']})")
        primary = dict(elders[0])
        for dup in elders[1:]:
            merged = dict(dup)
            for key in list(merged.keys()):
                if key in ("id", "created_at", "updated_at", "family_id"):
                    continue
                if primary.get(key):
                    ev = primary[key]
                    iv = merged[key]
                    if isinstance(ev, list) and isinstance(iv, list):
                        merged[key] = _merge_list(ev, iv)
                    elif ev:
                        continue
            repo.upsert_elder_current(family_id=family_id, user_id=user_id, payload=merged)
            # elders 表无单条删除，upsert 后数据已合并到 primary

    print(f"\n✅ 合并完成！刷新 Web 页面即可看到变化。")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="智能合并账号中已有资料的去重数据")
    parser.add_argument("--phone", required=True, help="手机号")
    parser.add_argument("--dry-run", action="store_true", help="仅分析不执行")
    args = parser.parse_args()
    run(args.phone, dry_run=args.dry_run)
