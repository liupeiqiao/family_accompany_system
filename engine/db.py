"""SQLite persistence layer for persona and memories."""

import json
import sqlite3
from datetime import datetime

DB_PATH = "companion.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables if not exist. Migrate old schema if needed."""
    conn = _connect()
    # Check for old schema (id-based persona table)
    cursor = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='persona'")
    old_schema = cursor.fetchone()
    if old_schema and "id INTEGER PRIMARY KEY CHECK" in (old_schema[0] or ""):
        # Migrate: drop old table, recreate with role_label as PK
        conn.execute("DROP TABLE persona")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS persona (
            role_label TEXT PRIMARY KEY,
            relation TEXT DEFAULT '',
            appellation TEXT DEFAULT '',
            personality TEXT DEFAULT '[]',
            speech_style TEXT DEFAULT '[]',
            comfort_style TEXT DEFAULT '[]',
            mood_preference TEXT DEFAULT '{}',
            topic_affinity TEXT DEFAULT '{}',
            sensitivity_map TEXT DEFAULT '{}'
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id TEXT PRIMARY KEY,
            content TEXT NOT NULL,
            memory_type TEXT DEFAULT '',
            subject TEXT DEFAULT '',
            family_members TEXT DEFAULT '[]',
            emotion_tags TEXT DEFAULT '[]',
            topic_tags TEXT DEFAULT '[]',
            intimacy_weight REAL DEFAULT 0.5,
            created_at TEXT DEFAULT ''
        )
    """)
    # Migration: add subject column if not exists
    try:
        conn.execute("ALTER TABLE memories ADD COLUMN subject TEXT DEFAULT ''")
    except Exception:
        pass
    conn.commit()
    conn.close()


# ===== Persona =====

def save_persona(persona_dict: dict) -> None:
    conn = _connect()
    conn.execute("""
        INSERT OR REPLACE INTO persona
            (role_label, relation, appellation, personality, speech_style, comfort_style,
             mood_preference, topic_affinity, sensitivity_map)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        persona_dict.get("role_label", ""),
        persona_dict.get("relation", ""),
        persona_dict.get("appellation", ""),
        json.dumps(persona_dict.get("personality", []), ensure_ascii=False),
        json.dumps(persona_dict.get("speech_style", []), ensure_ascii=False),
        json.dumps(persona_dict.get("comfort_style", []), ensure_ascii=False),
        json.dumps(persona_dict.get("mood_preference", {}), ensure_ascii=False),
        json.dumps(persona_dict.get("topic_affinity", {}), ensure_ascii=False),
        json.dumps(persona_dict.get("sensitivity_map", {}), ensure_ascii=False),
    ))
    conn.commit()
    conn.close()


def load_persona() -> dict | None:
    conn = _connect()
    row = conn.execute("SELECT * FROM persona ORDER BY role_label LIMIT 1").fetchone()
    conn.close()
    if row is None:
        return None
    return _row_to_persona_dict(row)


def load_all_personas() -> list[dict]:
    conn = _connect()
    rows = conn.execute("SELECT * FROM persona ORDER BY role_label").fetchall()
    conn.close()
    return [_row_to_persona_dict(r) for r in rows]


def delete_persona(role_label: str) -> None:
    conn = _connect()
    conn.execute("DELETE FROM persona WHERE role_label = ?", (role_label,))
    conn.commit()
    conn.close()


def _row_to_persona_dict(row) -> dict:
    return {
        "role_label": row["role_label"],
        "relation": row["relation"],
        "appellation": row["appellation"],
        "personality": json.loads(row["personality"]),
        "speech_style": json.loads(row["speech_style"]),
        "comfort_style": json.loads(row["comfort_style"]),
        "mood_preference": json.loads(row["mood_preference"]),
        "topic_affinity": json.loads(row["topic_affinity"]),
        "sensitivity_map": json.loads(row["sensitivity_map"]),
    }


# ===== Memories =====

def save_memory(memory_dict: dict) -> None:
    conn = _connect()
    conn.execute("""
        INSERT OR REPLACE INTO memories
            (id, content, memory_type, subject, family_members, emotion_tags, topic_tags, intimacy_weight, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        memory_dict.get("id", ""),
        memory_dict["content"],
        memory_dict.get("memory_type", ""),
        memory_dict.get("subject", ""),
        json.dumps(memory_dict.get("family_members", []), ensure_ascii=False),
        json.dumps(memory_dict.get("emotion_tags", []), ensure_ascii=False),
        json.dumps(memory_dict.get("topic_tags", []), ensure_ascii=False),
        memory_dict.get("intimacy_weight", 0.5),
        datetime.now().isoformat(),
    ))
    conn.commit()
    conn.close()


def delete_memory(memory_id: str) -> None:
    conn = _connect()
    conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
    conn.commit()
    conn.close()


def load_all_memories() -> list[dict]:
    conn = _connect()
    rows = conn.execute("SELECT * FROM memories ORDER BY created_at DESC").fetchall()
    conn.close()
    result = []
    for row in rows:
        result.append({
            "id": row["id"],
            "content": row["content"],
            "memory_type": row["memory_type"],
            "subject": row["subject"] if "subject" in row.keys() else "",
            "family_members": json.loads(row["family_members"]),
            "emotion_tags": json.loads(row["emotion_tags"]),
            "topic_tags": json.loads(row["topic_tags"]),
            "intimacy_weight": row["intimacy_weight"],
        })
    return result
