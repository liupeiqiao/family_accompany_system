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

CREATE TABLE IF NOT EXISTS chat_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    text TEXT NOT NULL,
    audio_storage_path TEXT DEFAULT '',
    tts_provider TEXT DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_family_memberships_user ON family_memberships(user_id);
CREATE INDEX IF NOT EXISTS idx_family_memberships_family ON family_memberships(family_id);
CREATE INDEX IF NOT EXISTS idx_elders_family ON elders(family_id);
CREATE INDEX IF NOT EXISTS idx_family_profiles_family ON family_profiles(family_id);
CREATE INDEX IF NOT EXISTS idx_personas_family ON personas(family_id);
CREATE INDEX IF NOT EXISTS idx_memories_family ON memories(family_id);
CREATE INDEX IF NOT EXISTS idx_voice_profiles_family ON voice_profiles(family_id);
CREATE INDEX IF NOT EXISTS idx_voice_samples_family ON voice_samples(family_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_session ON chat_messages(session_id);
