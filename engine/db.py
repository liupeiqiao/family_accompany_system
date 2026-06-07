from __future__ import annotations
"""SQLite persistence layer for persona and memories."""

import json
import sqlite3
from datetime import datetime

from .conversation_state import ConversationState
from .family import normalize_family_relation

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
    conn.execute("""
        CREATE TABLE IF NOT EXISTS family_profiles (
            name TEXT PRIMARY KEY,
            gender TEXT DEFAULT '',
            relation TEXT DEFAULT '',
            personality TEXT DEFAULT '[]',
            preferences TEXT DEFAULT '[]',
            habits TEXT DEFAULT '[]',
            notes TEXT DEFAULT '',
            relations TEXT DEFAULT '[]'
        )
    """)
    # Migration: add missing columns
    try:
        conn.execute("ALTER TABLE family_profiles ADD COLUMN relations TEXT DEFAULT '[]'")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE family_profiles ADD COLUMN gender TEXT DEFAULT ''")
    except Exception:
        pass
    # Migration: if elder_profile has old schema (name instead of full_name), rename column
    cursor = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='elder_profile'")
    old_elder = cursor.fetchone()
    if old_elder and "name TEXT PRIMARY KEY" in (old_elder[0] or ""):
        try:
            conn.execute("ALTER TABLE elder_profile RENAME COLUMN name TO full_name")
        except Exception:
            pass  # Already migrated or missing
    conn.execute("""
        CREATE TABLE IF NOT EXISTS elder_profile (
            full_name TEXT PRIMARY KEY,
            gender TEXT DEFAULT '',
            personality TEXT DEFAULT '[]',
            preferences TEXT DEFAULT '[]',
            habits TEXT DEFAULT '[]',
            health_notes TEXT DEFAULT '[]',
            speech_traits TEXT DEFAULT '[]',
            life_experiences TEXT DEFAULT '[]',
            important_memories TEXT DEFAULT '[]',
            notes TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS persons (
            id TEXT PRIMARY KEY,
            family_id TEXT DEFAULT 'local',
            kind TEXT DEFAULT 'family',
            full_name TEXT DEFAULT '',
            nicknames TEXT DEFAULT '[]',
            gender TEXT DEFAULT '',
            birth_date TEXT DEFAULT '',
            address_terms TEXT DEFAULT '{}',
            traits TEXT DEFAULT '[]',
            speech_style TEXT DEFAULT '[]',
            habits TEXT DEFAULT '[]',
            interests TEXT DEFAULT '[]',
            life_experiences TEXT DEFAULT '[]',
            work_experiences TEXT DEFAULT '[]',
            family_experiences TEXT DEFAULT '[]',
            knowledge_boundaries TEXT DEFAULT '{}',
            topic_boundaries TEXT DEFAULT '{}',
            legacy_family_profile_id TEXT DEFAULT '',
            legacy_persona_id TEXT DEFAULT '',
            created_at TEXT DEFAULT '',
            updated_at TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS relationships (
            id TEXT PRIMARY KEY,
            family_id TEXT DEFAULT 'local',
            from_person_id TEXT NOT NULL,
            to_person_id TEXT NOT NULL,
            relation_type TEXT DEFAULT '',
            display_label TEXT DEFAULT '',
            inverse_relation_type TEXT DEFAULT '',
            inverse_display_label TEXT DEFAULT '',
            confidence REAL DEFAULT 1.0,
            source TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TEXT DEFAULT '',
            updated_at TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS persona_roles (
            id TEXT PRIMARY KEY,
            family_id TEXT DEFAULT 'local',
            person_id TEXT NOT NULL,
            role_label TEXT DEFAULT '',
            appellation_to_elder TEXT DEFAULT '',
            can_speak_as_person INTEGER DEFAULT 1,
            voice_profile_id TEXT DEFAULT '',
            comfort_style TEXT DEFAULT '[]',
            mood_preference TEXT DEFAULT '{}',
            sensitivity_map TEXT DEFAULT '{}',
            legacy_persona_id TEXT DEFAULT '',
            created_at TEXT DEFAULT '',
            updated_at TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS memory_events (
            id TEXT PRIMARY KEY,
            family_id TEXT DEFAULT 'local',
            title TEXT DEFAULT '',
            summary TEXT DEFAULT '',
            event_time_text TEXT DEFAULT '',
            event_start_at TEXT DEFAULT '',
            event_end_at TEXT DEFAULT '',
            location TEXT DEFAULT '',
            emotion_tags TEXT DEFAULT '[]',
            topic_tags TEXT DEFAULT '[]',
            source_type TEXT DEFAULT '',
            source_person_id TEXT DEFAULT '',
            truth_status TEXT DEFAULT 'uncertain',
            sensitivity_level INTEGER DEFAULT 0,
            created_at TEXT DEFAULT '',
            updated_at TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS memory_event_participants (
            event_id TEXT NOT NULL,
            person_id TEXT NOT NULL,
            role_in_event TEXT DEFAULT '',
            perspective TEXT DEFAULT 'heard_about',
            can_use_first_person INTEGER DEFAULT 0,
            can_mention INTEGER DEFAULT 1,
            PRIMARY KEY (event_id, person_id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS conversation_states (
            id TEXT PRIMARY KEY,
            family_id TEXT DEFAULT 'local',
            session_id TEXT DEFAULT 'default',
            elder_person_id TEXT DEFAULT '',
            current_persona_role_id TEXT DEFAULT '',
            recent_person_ids TEXT DEFAULT '[]',
            recent_event_ids TEXT DEFAULT '[]',
            elder_emotion TEXT DEFAULT '',
            ongoing_topic TEXT DEFAULT '',
            unfinished_topics TEXT DEFAULT '[]',
            relationship_focus TEXT DEFAULT '{}',
            last_intent TEXT DEFAULT '',
            summary TEXT DEFAULT '',
            updated_at TEXT DEFAULT ''
        )
    """)
    # Migration: elder_profile add gender column
    try:
        conn.execute("ALTER TABLE elder_profile ADD COLUMN gender TEXT DEFAULT ''")
    except Exception:
        pass
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


# ===== Family Profiles =====

def save_family_profile(profile_dict: dict) -> None:
    conn = _connect()
    gender = profile_dict.get("gender", "")
    relation = normalize_family_relation(profile_dict.get("relation", ""), gender)
    conn.execute("""
        INSERT OR REPLACE INTO family_profiles (name, gender, relation, personality, preferences, habits, notes, relations)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        profile_dict.get("name", ""),
        gender,
        relation,
        json.dumps(profile_dict.get("personality", []), ensure_ascii=False),
        json.dumps(profile_dict.get("preferences", []), ensure_ascii=False),
        json.dumps(profile_dict.get("habits", []), ensure_ascii=False),
        profile_dict.get("notes", ""),
        json.dumps(profile_dict.get("relations", []), ensure_ascii=False),
    ))
    conn.commit()
    conn.close()


def delete_family_profile(name: str) -> None:
    conn = _connect()
    conn.execute("DELETE FROM family_profiles WHERE name = ?", (name,))
    conn.commit()
    conn.close()


def load_all_family_profiles() -> list[dict]:
    conn = _connect()
    rows = conn.execute("SELECT * FROM family_profiles ORDER BY name").fetchall()
    conn.close()
    result = []
    for row in rows:
        result.append({
            "name": row["name"],
            "gender": row["gender"] if "gender" in row.keys() else "",
            "relation": row["relation"],
            "personality": json.loads(row["personality"]),
            "preferences": json.loads(row["preferences"]),
            "habits": json.loads(row["habits"]),
            "relations": json.loads(row["relations"]) if "relations" in row.keys() else [],
            "notes": row["notes"],
        })
    return result


# ===== Elder Profile =====

def save_elder(profile_dict: dict) -> None:
    conn = _connect()
    conn.execute("""
        INSERT OR REPLACE INTO elder_profile
            (full_name, gender, personality, preferences, habits, health_notes, speech_traits, life_experiences, important_memories, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        profile_dict.get("full_name", ""),
        profile_dict.get("gender", ""),
        json.dumps(profile_dict.get("personality", []), ensure_ascii=False),
        json.dumps(profile_dict.get("preferences", []), ensure_ascii=False),
        json.dumps(profile_dict.get("habits", []), ensure_ascii=False),
        json.dumps(profile_dict.get("health_notes", []), ensure_ascii=False),
        json.dumps(profile_dict.get("speech_traits", []), ensure_ascii=False),
        json.dumps(profile_dict.get("life_experiences", []), ensure_ascii=False),
        json.dumps(profile_dict.get("important_memories", []), ensure_ascii=False),
        profile_dict.get("notes", ""),
    ))
    conn.commit()
    conn.close()


def load_elder() -> dict | None:
    conn = _connect()
    row = conn.execute("SELECT * FROM elder_profile LIMIT 1").fetchone()
    conn.close()
    if row is None:
        return None
    return _row_to_elder_dict(row)


def load_all_elders() -> list[dict]:
    conn = _connect()
    rows = conn.execute("SELECT * FROM elder_profile ORDER BY full_name").fetchall()
    conn.close()
    return [_row_to_elder_dict(row) for row in rows]


def _row_to_elder_dict(row) -> dict:
    return {
        "full_name": row["full_name"],
        "gender": row["gender"] if "gender" in row.keys() else "",
        "personality": json.loads(row["personality"]),
        "preferences": json.loads(row["preferences"]),
        "habits": json.loads(row["habits"]),
        "health_notes": json.loads(row["health_notes"]),
        "speech_traits": json.loads(row["speech_traits"]),
        "life_experiences": json.loads(row["life_experiences"]),
        "important_memories": json.loads(row["important_memories"]),
        "notes": row["notes"],
    }


def delete_elder(full_name: str) -> None:
    conn = _connect()
    conn.execute("DELETE FROM elder_profile WHERE full_name = ?", (full_name,))
    conn.commit()
    conn.close()


# ===== Conversation State =====

def load_conversation_state(family_id: str, session_id: str) -> ConversationState | None:
    conn = _connect()
    row = conn.execute(
        """
        SELECT * FROM conversation_states
        WHERE family_id = ? AND session_id = ?
        ORDER BY updated_at DESC
        LIMIT 1
        """,
        (family_id, session_id),
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return ConversationState(
        id=row["id"],
        family_id=row["family_id"],
        session_id=row["session_id"],
        elder_person_id=row["elder_person_id"],
        current_persona_role_id=row["current_persona_role_id"],
        recent_person_ids=json.loads(row["recent_person_ids"] or "[]"),
        recent_event_ids=json.loads(row["recent_event_ids"] or "[]"),
        elder_emotion=row["elder_emotion"],
        ongoing_topic=row["ongoing_topic"],
        unfinished_topics=json.loads(row["unfinished_topics"] or "[]"),
        relationship_focus=json.loads(row["relationship_focus"] or "{}"),
        last_intent=row["last_intent"],
        summary=row["summary"],
    )


def save_conversation_state(state: ConversationState) -> None:
    conn = _connect()
    conn.execute(
        """
        INSERT OR REPLACE INTO conversation_states
            (id, family_id, session_id, elder_person_id, current_persona_role_id,
             recent_person_ids, recent_event_ids, elder_emotion, ongoing_topic,
             unfinished_topics, relationship_focus, last_intent, summary, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            state.id,
            state.family_id,
            state.session_id,
            state.elder_person_id,
            state.current_persona_role_id,
            json.dumps(state.recent_person_ids, ensure_ascii=False),
            json.dumps(state.recent_event_ids, ensure_ascii=False),
            state.elder_emotion,
            state.ongoing_topic,
            json.dumps(state.unfinished_topics, ensure_ascii=False),
            json.dumps(state.relationship_focus, ensure_ascii=False),
            state.last_intent,
            state.summary,
            state.updated_at.isoformat(),
        ),
    )
    conn.commit()
    conn.close()
