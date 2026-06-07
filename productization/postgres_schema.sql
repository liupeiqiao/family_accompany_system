CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phone VARCHAR(20) UNIQUE NOT NULL,
    nickname VARCHAR(64) DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT now(),
    last_login TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS sms_codes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phone VARCHAR(20) NOT NULL,
    code VARCHAR(12) NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    used BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS families (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(128) NOT NULL,
    created_by VARCHAR(128) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS family_memberships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id UUID NOT NULL REFERENCES families(id) ON DELETE CASCADE,
    user_id VARCHAR(128) NOT NULL,
    role VARCHAR(16) NOT NULL CHECK (role IN ('owner', 'editor', 'viewer')),
    invited_at TIMESTAMPTZ DEFAULT now(),
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (family_id, user_id)
);

CREATE TABLE IF NOT EXISTS elders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id UUID UNIQUE NOT NULL REFERENCES families(id) ON DELETE CASCADE,
    full_name TEXT DEFAULT '',
    gender TEXT DEFAULT '',
    personality JSONB DEFAULT '[]'::jsonb,
    preferences JSONB DEFAULT '[]'::jsonb,
    habits JSONB DEFAULT '[]'::jsonb,
    health_notes JSONB DEFAULT '[]'::jsonb,
    speech_traits JSONB DEFAULT '[]'::jsonb,
    life_experiences JSONB DEFAULT '[]'::jsonb,
    important_memories JSONB DEFAULT '[]'::jsonb,
    notes TEXT DEFAULT '',
    created_by VARCHAR(128),
    updated_by VARCHAR(128),
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS family_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id UUID NOT NULL REFERENCES families(id) ON DELETE CASCADE,
    name TEXT DEFAULT '',
    gender TEXT DEFAULT '',
    relation TEXT DEFAULT '',
    personality JSONB DEFAULT '[]'::jsonb,
    preferences JSONB DEFAULT '[]'::jsonb,
    habits JSONB DEFAULT '[]'::jsonb,
    notes TEXT DEFAULT '',
    relations JSONB DEFAULT '[]'::jsonb,
    created_by VARCHAR(128),
    updated_by VARCHAR(128),
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS personas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id UUID NOT NULL REFERENCES families(id) ON DELETE CASCADE,
    role_label TEXT DEFAULT '',
    relation TEXT DEFAULT '',
    appellation TEXT DEFAULT '',
    personality JSONB DEFAULT '[]'::jsonb,
    speech_style JSONB DEFAULT '[]'::jsonb,
    comfort_style JSONB DEFAULT '[]'::jsonb,
    mood_preference TEXT DEFAULT '',
    topic_affinity JSONB DEFAULT '[]'::jsonb,
    sensitivity_map JSONB DEFAULT '{}'::jsonb,
    created_by VARCHAR(128),
    updated_by VARCHAR(128),
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS memories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id UUID NOT NULL REFERENCES families(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    memory_type TEXT DEFAULT '',
    subject TEXT DEFAULT '',
    family_members JSONB DEFAULT '[]'::jsonb,
    emotion_tags JSONB DEFAULT '[]'::jsonb,
    topic_tags JSONB DEFAULT '[]'::jsonb,
    intimacy_weight DOUBLE PRECISION DEFAULT 0,
    created_by VARCHAR(128),
    updated_by VARCHAR(128),
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS persons (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id UUID NOT NULL REFERENCES families(id) ON DELETE CASCADE,
    kind TEXT DEFAULT 'family',
    full_name TEXT DEFAULT '',
    nicknames JSONB DEFAULT '[]'::jsonb,
    gender TEXT DEFAULT '',
    birth_date TEXT DEFAULT '',
    address_terms JSONB DEFAULT '{}'::jsonb,
    traits JSONB DEFAULT '[]'::jsonb,
    speech_style JSONB DEFAULT '[]'::jsonb,
    habits JSONB DEFAULT '[]'::jsonb,
    interests JSONB DEFAULT '[]'::jsonb,
    life_experiences JSONB DEFAULT '[]'::jsonb,
    work_experiences JSONB DEFAULT '[]'::jsonb,
    family_experiences JSONB DEFAULT '[]'::jsonb,
    knowledge_boundaries JSONB DEFAULT '{}'::jsonb,
    topic_boundaries JSONB DEFAULT '{}'::jsonb,
    legacy_family_profile_id TEXT DEFAULT '',
    legacy_persona_id TEXT DEFAULT '',
    created_by VARCHAR(128),
    updated_by VARCHAR(128),
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS relationships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id UUID NOT NULL REFERENCES families(id) ON DELETE CASCADE,
    from_person_id UUID NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
    to_person_id UUID NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
    relation_type TEXT DEFAULT '',
    display_label TEXT DEFAULT '',
    inverse_relation_type TEXT DEFAULT '',
    inverse_display_label TEXT DEFAULT '',
    confidence DOUBLE PRECISION DEFAULT 1.0,
    source TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    created_by VARCHAR(128),
    updated_by VARCHAR(128),
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS persona_roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id UUID NOT NULL REFERENCES families(id) ON DELETE CASCADE,
    person_id UUID NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
    role_label TEXT DEFAULT '',
    appellation_to_elder TEXT DEFAULT '',
    can_speak_as_person BOOLEAN DEFAULT true,
    voice_profile_id UUID REFERENCES voice_profiles(id) ON DELETE SET NULL,
    comfort_style JSONB DEFAULT '[]'::jsonb,
    mood_preference JSONB DEFAULT '{}'::jsonb,
    sensitivity_map JSONB DEFAULT '{}'::jsonb,
    legacy_persona_id TEXT DEFAULT '',
    created_by VARCHAR(128),
    updated_by VARCHAR(128),
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS memory_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id UUID NOT NULL REFERENCES families(id) ON DELETE CASCADE,
    title TEXT DEFAULT '',
    summary TEXT DEFAULT '',
    event_time_text TEXT DEFAULT '',
    event_start_at TIMESTAMPTZ,
    event_end_at TIMESTAMPTZ,
    location TEXT DEFAULT '',
    emotion_tags JSONB DEFAULT '[]'::jsonb,
    topic_tags JSONB DEFAULT '[]'::jsonb,
    source_type TEXT DEFAULT '',
    source_person_id UUID REFERENCES persons(id) ON DELETE SET NULL,
    truth_status TEXT DEFAULT 'uncertain',
    sensitivity_level INTEGER DEFAULT 0,
    created_by VARCHAR(128),
    updated_by VARCHAR(128),
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS memory_event_participants (
    event_id UUID NOT NULL REFERENCES memory_events(id) ON DELETE CASCADE,
    person_id UUID NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
    role_in_event TEXT DEFAULT '',
    perspective TEXT DEFAULT 'heard_about',
    can_use_first_person BOOLEAN DEFAULT false,
    can_mention BOOLEAN DEFAULT true,
    PRIMARY KEY (event_id, person_id)
);

CREATE TABLE IF NOT EXISTS voice_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id UUID NOT NULL REFERENCES families(id) ON DELETE CASCADE,
    display_name TEXT DEFAULT '',
    provider TEXT DEFAULT '',
    provider_voice_id TEXT DEFAULT '',
    status TEXT DEFAULT 'ready',
    consent_confirmed BOOLEAN DEFAULT false,
    sample_source TEXT DEFAULT '',
    demo_audio_url TEXT DEFAULT '',
    voice_type TEXT DEFAULT '',
    created_by VARCHAR(128),
    updated_by VARCHAR(128),
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS voice_samples (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id UUID NOT NULL REFERENCES families(id) ON DELETE CASCADE,
    storage_path TEXT NOT NULL,
    bucket TEXT DEFAULT 'voice-samples',
    sample_source TEXT DEFAULT 'upload',
    status TEXT DEFAULT 'pending_upload',
    voice_profile_id UUID REFERENCES voice_profiles(id) ON DELETE SET NULL,
    created_by VARCHAR(128),
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chat_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id UUID NOT NULL REFERENCES families(id) ON DELETE CASCADE,
    elder_id UUID,
    created_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE chat_sessions
    ADD COLUMN IF NOT EXISTS persona_id UUID,
    ADD COLUMN IF NOT EXISTS voice_profile_id UUID,
    ADD COLUMN IF NOT EXISTS created_by VARCHAR(128);

CREATE TABLE IF NOT EXISTS chat_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    text TEXT NOT NULL,
    audio_storage_path TEXT DEFAULT '',
    tts_provider TEXT DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE chat_messages
    ADD COLUMN IF NOT EXISTS persona_id UUID,
    ADD COLUMN IF NOT EXISTS voice_profile_id UUID,
    ADD COLUMN IF NOT EXISTS asr_provider TEXT DEFAULT '';

CREATE TABLE IF NOT EXISTS conversation_states (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id UUID NOT NULL REFERENCES families(id) ON DELETE CASCADE,
    session_id TEXT NOT NULL DEFAULT 'default',
    elder_person_id TEXT DEFAULT '',
    current_persona_role_id TEXT DEFAULT '',
    recent_person_ids JSONB DEFAULT '[]'::jsonb,
    recent_event_ids JSONB DEFAULT '[]'::jsonb,
    elder_emotion TEXT DEFAULT '',
    ongoing_topic TEXT DEFAULT '',
    unfinished_topics JSONB DEFAULT '[]'::jsonb,
    relationship_focus JSONB DEFAULT '{}'::jsonb,
    last_intent TEXT DEFAULT '',
    summary TEXT DEFAULT '',
    updated_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE conversation_states
    DROP CONSTRAINT IF EXISTS conversation_states_session_id_fkey,
    DROP CONSTRAINT IF EXISTS conversation_states_elder_person_id_fkey,
    DROP CONSTRAINT IF EXISTS conversation_states_current_persona_role_id_fkey,
    ALTER COLUMN session_id TYPE TEXT USING COALESCE(session_id::text, 'default'),
    ALTER COLUMN session_id SET DEFAULT 'default',
    ALTER COLUMN session_id SET NOT NULL,
    ALTER COLUMN elder_person_id TYPE TEXT USING COALESCE(elder_person_id::text, ''),
    ALTER COLUMN elder_person_id SET DEFAULT '',
    ALTER COLUMN current_persona_role_id TYPE TEXT USING COALESCE(current_persona_role_id::text, ''),
    ALTER COLUMN current_persona_role_id SET DEFAULT '';

CREATE INDEX IF NOT EXISTS idx_family_memberships_user ON family_memberships(user_id);
CREATE INDEX IF NOT EXISTS idx_family_memberships_family ON family_memberships(family_id);
CREATE INDEX IF NOT EXISTS idx_elders_family ON elders(family_id);
CREATE INDEX IF NOT EXISTS idx_family_profiles_family ON family_profiles(family_id);
CREATE INDEX IF NOT EXISTS idx_personas_family ON personas(family_id);
CREATE INDEX IF NOT EXISTS idx_memories_family ON memories(family_id);
CREATE INDEX IF NOT EXISTS idx_persons_family ON persons(family_id);
CREATE INDEX IF NOT EXISTS idx_relationships_family ON relationships(family_id);
CREATE INDEX IF NOT EXISTS idx_relationships_from ON relationships(from_person_id);
CREATE INDEX IF NOT EXISTS idx_relationships_to ON relationships(to_person_id);
CREATE INDEX IF NOT EXISTS idx_persona_roles_family ON persona_roles(family_id);
CREATE INDEX IF NOT EXISTS idx_memory_events_family ON memory_events(family_id);
CREATE INDEX IF NOT EXISTS idx_memory_event_participants_person ON memory_event_participants(person_id);
CREATE INDEX IF NOT EXISTS idx_voice_profiles_family ON voice_profiles(family_id);
CREATE INDEX IF NOT EXISTS idx_voice_samples_family ON voice_samples(family_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_session ON chat_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_conversation_states_family ON conversation_states(family_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_conversation_states_family_session ON conversation_states(family_id, session_id);
