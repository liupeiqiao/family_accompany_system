"""智能合并账号中已有数据的去重脚本.

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
    """归一化记忆内容用于相似度比较."""
    normalized = re.sub(r"[\s\-_，。,.！？!；;：:、\"“”'‘’（）()]+", "", content or "")
    return normalized.casefold()


def _merge_string(existing: str | None, incoming: str | None) -> str:
    """已有值优先，空则补新值."""
    existing_text = str(existing or "").strip()
    incoming_text = str(incoming or "").strip()
    if not existing_text and incoming_text:
        return incoming_text
    return existing_text


def _merge_list(existing, incoming) -> list:
    """列表合并去重."""
    existing_items = existing if isinstance(existing, list) else ([] if not existing else [existing])
    incoming_items = incoming if isinstance(incoming, list) else ([] if not incoming else [incoming])
    seen = set()
    result = []
    for item in [*existing_items, *incoming_items]:
        key = str(item).strip()
        if key and key not in seen:
            seen.add(key)
            result.append(item)
    return result


def _merge_notes(existing, incoming) -> str:
    """notes 追加（带来源标记）."""
    existing_text = str(existing or "").strip()
    incoming_text = str(incoming or "").strip()
    if not existing_text:
        return incoming_text
    if not incoming_text or incoming_text == existing_text:
        return existing_text
    from datetime import date
    tag = date.today().isoformat()
    return f"{existing_text}\n{tag} 智能合并补充：{incoming_text}"


def dedup_personas(personas: list[dict]) -> tuple[list[dict], list[str]]:
    """合并重复的 AI 角色（同 role_label 视为重复）."""
    by_label: dict[str, list[dict]] = defaultdict(list)
    for p in personas:
        label = (p.get("role_label") or "").strip()
        by_label[label].append(p)

    merged = []
    log: list[str] = []
    for label, group in by_label.items():
        if len(group) == 1:
            merged.append(group[0])
        else:
            log.append(f"  AI角色「{label}」: {len(group)} 条重复 → 合并为 1 条")
            base = dict(group[0])
            for dup in group[1:]:
                base["relation"] = _merge_string(base.get("relation"), dup.get("relation"))
                base["appellation"] = _merge_string(base.get("appellation"), dup.get("appellation"))
                base["personality"] = _merge_list(base.get("personality"), dup.get("personality"))
                base["speech_style"] = _merge_list(base.get("speech_style"), dup.get("speech_style"))
                base["comfort_style"] = _merge_list(base.get("comfort_style"), dup.get("comfort_style"))
                # mood_preference, topic_affinity, sensitivity_map 合并
                for json_field in ("mood_preference", "topic_affinity", "sensitivity_map"):
                    existing_val = base.get(json_field) or {}
                    incoming_val = dup.get(json_field) or {}
                    if isinstance(existing_val, dict) and isinstance(incoming_val, dict):
                        base[json_field] = {**existing_val, **incoming_val}
            merged.append(base)
    return merged, log


def dedup_family_profiles(profiles: list[dict]) -> tuple[list[dict], list[str]]:
    """合并重复的家人档案（同 name 视为重复）."""
    by_name: dict[str, list[dict]] = defaultdict(list)
    for fp in profiles:
        name = (fp.get("name") or "").strip()
        by_name[name].append(fp)

    merged = []
    log: list[str] = []
    for name, group in by_name.items():
        if len(group) == 1:
            merged.append(group[0])
        else:
            log.append(f"  家人档案「{name}」: {len(group)} 条重复 → 合并为 1 条")
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
    """合并/跳过重复的家庭记忆（内容高度相似视为重复）."""
    by_content: dict[str, list[dict]] = defaultdict(list)
    for m in memories:
        normalized = _normalize_content(m.get("content", ""))
        if normalized:
            by_content[normalized].append(m)

    merged = []
    log: list[str] = []
    seen_similar: dict[str, list[dict]] = defaultdict(list)

    # 第二层：按 subject + memory_type 相似度再聚合
    for normalized, group in by_content.items():
        if len(group) == 1:
            merged.append(group[0])
        else:
            content_preview = str(group[0].get("content", ""))[:40]
            log.append(f"  记忆「{content_preview}」: {len(group)} 条重复 → 保留 1 条，跳过其余")
            merged.append(group[0])

    return merged, log


def dedup_elders(elders: list[dict]) -> tuple[dict | None, list[str]]:
    """合并多个老人画像（应该只有一个，多余的合并进来）."""
    if not elders:
        return None, []
    if len(elders) == 1:
        return elders[0], []

    log = [f"  老人画像: {len(elders)} 条 → 合并为 1 条"]
    base = dict(elders[0])
    json_list_fields = (
        "personality", "preferences", "habits", "health_notes",
        "speech_traits", "life_experiences", "important_memories",
    )
    for dup in elders[1:]:
        base["gender"] = _merge_string(base.get("gender"), dup.get("gender"))
        for field in json_list_fields:
            base[field] = _merge_list(base.get(field), dup.get(field))
        base["notes"] = _merge_notes(base.get("notes"), dup.get("notes"))
    return base, log


def run(phone: str, *, dry_run: bool = False) -> None:
    from dotenv import load_dotenv
    load_dotenv()

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("错误: 请设置 DATABASE_URL 环境变量", file=sys.stderr)
        sys.exit(1)

    from productization.postgres_repository import PostgresCloudRepository

    SKIP_COLS = {"id", "created_at", "updated_at", "family_id"}

    # JSON 字段列表（与 postgres_repository.py 保持一致）
    JSON_FIELDS = {
        "personality", "preferences", "habits", "health_notes",
        "speech_traits", "life_experiences", "important_memories",
        "relations", "speech_style", "comfort_style",
        "topic_affinity", "sensitivity_map", "family_members",
        "emotion_tags", "topic_tags",
    }

    def _norm(value, field_name=""):
        """规范化值：确保 JSON 字段是合法的 Python list/dict."""
        if field_name in JSON_FIELDS:
            if value is None or value == "":
                return []
            if isinstance(value, str):
                # 数据库里可能存了裸字符串，包成单元素列表
                return [value] if value.strip() else []
            if isinstance(value, (list, dict)):
                return value
            return []
        return value

    repo = PostgresCloudRepository(database_url)
    repo.init_schema()

    # 1. 查找用户
    with repo._connect() as conn:  # noqa: SLF001
        user = conn.execute("SELECT * FROM users WHERE phone = %s", (phone,)).fetchone()
        if not user:
            print(f"错误: 未找到手机号 {phone} 对应的用户", file=sys.stderr)
            sys.exit(1)
        user_id = str(user["id"])
        print(f"用户: {user['phone']} (id={user_id})")

        # 2. 获取家庭空间
        membership = conn.execute(
            "SELECT * FROM family_memberships WHERE user_id = %s ORDER BY created_at ASC LIMIT 1",
            (user_id,),
        ).fetchone()
        if not membership:
            print("错误: 该用户没有家庭空间", file=sys.stderr)
            sys.exit(1)
        family_id = str(membership["family_id"])
        family = conn.execute("SELECT * FROM families WHERE id = %s", (family_id,)).fetchone()
        print(f"家庭: {family['name']} (id={family_id})")

        # 3. 读取所有数据
        elders = conn.execute(
            "SELECT * FROM elders WHERE family_id = %s ORDER BY created_at ASC", (family_id,)
        ).fetchall()
        personas = conn.execute(
            "SELECT * FROM personas WHERE family_id = %s ORDER BY created_at ASC", (family_id,)
        ).fetchall()
        family_profiles = conn.execute(
            "SELECT * FROM family_profiles WHERE family_id = %s ORDER BY created_at ASC", (family_id,)
        ).fetchall()
        memories = conn.execute(
            "SELECT * FROM memories WHERE family_id = %s ORDER BY created_at ASC", (family_id,)
        ).fetchall()

        print(f"\n当前数据: 老人画像 {len(elders)} 条, AI角色 {len(personas)} 个, "
              f"家人档案 {len(family_profiles)} 条, 记忆 {len(memories)} 条")

        # 4. 去重分析
        all_logs: list[str] = []

        merged_elders, elder_log = dedup_elders([dict(e) for e in elders])
        all_logs.extend(elder_log)

        merged_personas, persona_log = dedup_personas([dict(p) for p in personas])
        all_logs.extend(persona_log)

        merged_profiles, profile_log = dedup_family_profiles([dict(p) for p in family_profiles])
        all_logs.extend(profile_log)

        merged_memories, memory_log = dedup_memories([dict(m) for m in memories])
        all_logs.extend(memory_log)

        if not all_logs:
            print("\n✅ 没有发现重复数据，无需合并。")
            return

        print(f"\n发现 {len(all_logs)} 组重复：")
        for log in all_logs:
            print(log)

        if dry_run:
            print(f"\n[Dry-run] 以上重复将被合并。实际执行请去掉 --dry-run。")
            print(f"统计: 老人 {len(elders)}→{1 if merged_elders else 0}, "
                  f"角色 {len(personas)}→{len(merged_personas)}, "
                  f"家人 {len(family_profiles)}→{len(merged_profiles)}, "
                  f"记忆 {len(memories)}→{len(merged_memories)}")
            return

        # 5. 执行合并写入
        print("\n开始合并...")

        # 删除旧的，写入合并后的
        conn.execute("DELETE FROM elders WHERE family_id = %s", (family_id,))
        conn.execute("DELETE FROM personas WHERE family_id = %s", (family_id,))
        conn.execute("DELETE FROM family_profiles WHERE family_id = %s", (family_id,))
        conn.execute("DELETE FROM memories WHERE family_id = %s", (family_id,))

        if merged_elders:
            cols = sorted(merged_elders.keys() - SKIP_COLS)
            insert_cols = ["family_id", *cols]
            placeholders = ["%s"] * len(insert_cols)
            values = [family_id, *(_norm(merged_elders.get(c), c) for c in cols)]
            conn.execute(
                f"INSERT INTO elders ({', '.join(insert_cols)}) VALUES ({', '.join(placeholders)})",
                values,
            )

        for persona in merged_personas:
            cols = sorted(persona.keys() - SKIP_COLS)
            insert_cols = ["family_id", *cols]
            placeholders = ["%s"] * len(insert_cols)
            values = [family_id, *(_norm(persona.get(c), c) for c in cols)]
            conn.execute(
                f"INSERT INTO personas ({', '.join(insert_cols)}) VALUES ({', '.join(placeholders)})",
                values,
            )

        for profile in merged_profiles:
            cols = sorted(profile.keys() - SKIP_COLS)
            insert_cols = ["family_id", *cols]
            placeholders = ["%s"] * len(insert_cols)
            values = [family_id, *(_norm(profile.get(c), c) for c in cols)]
            conn.execute(
                f"INSERT INTO family_profiles ({', '.join(insert_cols)}) VALUES ({', '.join(placeholders)})",
                values,
            )

        for memory in merged_memories:
            cols = sorted(memory.keys() - SKIP_COLS)
            insert_cols = ["family_id", *cols]
            placeholders = ["%s"] * len(insert_cols)
            values = [family_id, *(_norm(memory.get(c), c) for c in cols)]
            conn.execute(
                f"INSERT INTO memories ({', '.join(insert_cols)}) VALUES ({', '.join(placeholders)})",
                values,
            )

        conn.commit()

        print(f"\n✅ 合并完成！")
        print(f"老人画像: {len(elders)} → {1 if merged_elders else 0}")
        print(f"AI 角色: {len(personas)} → {len(merged_personas)}")
        print(f"家人档案: {len(family_profiles)} → {len(merged_profiles)}")
        print(f"家庭记忆: {len(memories)} → {len(merged_memories)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="智能合并账号中已有资料的重复数据")
    parser.add_argument("--phone", required=True, help="手机号，如 88888888")
    parser.add_argument("--dry-run", action="store_true", help="仅分析不实际执行")
    args = parser.parse_args()
    run(args.phone, dry_run=args.dry_run)
