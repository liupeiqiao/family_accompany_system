from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_supabase_schema_defines_family_space_tables_and_rls():
    schema_path = ROOT / "supabase" / "migrations" / "0001_productization_schema.sql"
    sql = schema_path.read_text(encoding="utf-8")

    required_tables = [
        "families",
        "family_memberships",
        "elders",
        "personas",
        "family_profiles",
        "memories",
        "voice_profiles",
        "voice_samples",
        "chat_sessions",
        "chat_messages",
    ]
    for table in required_tables:
        assert f"create table if not exists public.{table}" in sql.lower()
        assert f"alter table public.{table} enable row level security" in sql.lower()

    assert "check (role in ('owner', 'editor', 'viewer'))" in sql.lower()
    assert "with check (public.is_family_editor(family_id))" in sql.lower()
    assert "insert into storage.buckets" in sql.lower()
    assert "voice-samples" in sql
    assert "generated-audio" in sql


def test_family_roles_keep_viewer_read_only():
    from productization.permissions import can_manage_members, can_write_family_data

    assert can_manage_members("owner") is True
    assert can_manage_members("editor") is False
    assert can_manage_members("viewer") is False

    assert can_write_family_data("owner") is True
    assert can_write_family_data("editor") is True
    assert can_write_family_data("viewer") is False


def test_voice_provider_requires_consent_and_returns_auditable_ids():
    from productization.voice import MockVoiceProvider, VoiceCloneRequest

    provider = MockVoiceProvider()
    request = VoiceCloneRequest(
        family_id="family-1",
        created_by="user-1",
        sample_paths=["voice-samples/family-1/user-1/sample.wav"],
        consent_confirmed=True,
        sample_source="upload",
    )

    result = provider.create_clone(request)

    assert result.provider == "mock"
    assert result.provider_voice_id
    assert result.audit["family_id"] == "family-1"
    assert result.audit["created_by"] == "user-1"
    assert result.audit["sample_source"] == "upload"


def test_voice_provider_rejects_missing_consent():
    from productization.voice import MockVoiceProvider, VoiceCloneRequest, VoiceConsentError

    provider = MockVoiceProvider()
    request = VoiceCloneRequest(
        family_id="family-1",
        created_by="user-1",
        sample_paths=["voice-samples/family-1/user-1/sample.wav"],
        consent_confirmed=False,
        sample_source="upload",
    )

    try:
        provider.create_clone(request)
    except VoiceConsentError as exc:
        assert "consent" in str(exc).lower()
    else:
        raise AssertionError("missing consent should be rejected")


def test_python_api_contracts_match_productization_plan():
    from productization.api_contracts import API_ENDPOINTS

    assert API_ENDPOINTS == {
        "parse": "POST /api/parse",
        "chat": "POST /api/chat",
        "voice_clone": "POST /api/voices/clone",
        "tts": "POST /api/tts",
    }


def test_productization_service_clones_and_synthesizes_with_mock_provider():
    from productization.service import ProductizationService
    from productization.voice import MockVoiceProvider

    service = ProductizationService(voice_provider=MockVoiceProvider())
    clone_result = service.clone_voice(
        family_id="family-1",
        created_by="user-1",
        sample_paths=["voice-samples/family-1/user-1/sample.wav"],
        consent_confirmed=True,
        sample_source="upload",
    )
    tts_result = service.synthesize_reply(
        family_id="family-1",
        voice_profile_id=clone_result.provider_voice_id,
        text="妈，我在呢。",
    )

    assert clone_result.provider == "mock"
    assert clone_result.audit["created_by"] == "user-1"
    assert tts_result.audio_path.startswith("generated-audio/family-1/")


def test_nextjs_web_app_scaffold_exists():
    package_path = ROOT / "web" / "package.json"
    app_path = ROOT / "web" / "src" / "app" / "page.tsx"
    elder_chat_path = ROOT / "web" / "src" / "app" / "elder" / "page.tsx"

    package_data = json.loads(package_path.read_text(encoding="utf-8"))
    assert package_data["scripts"]["dev"] == "next dev"
    assert "next" in package_data["dependencies"]
    assert "@supabase/supabase-js" in package_data["dependencies"]

    app_source = app_path.read_text(encoding="utf-8")
    elder_source = elder_chat_path.read_text(encoding="utf-8")
    assert "家庭空间" in app_source
    assert "声音克隆" in app_source
    assert "老人端" in elder_source
    assert "<audio" in elder_source


def test_web_app_has_supabase_and_backend_api_boundaries():
    supabase_source = (ROOT / "web" / "src" / "lib" / "supabase.ts").read_text(
        encoding="utf-8"
    )
    backend_source = (ROOT / "web" / "src" / "lib" / "backend-api.ts").read_text(
        encoding="utf-8"
    )

    assert "createClient" in supabase_source
    assert "NEXT_PUBLIC_SUPABASE_URL" in supabase_source
    assert "NEXT_PUBLIC_SUPABASE_ANON_KEY" in supabase_source

    assert "/api/parse" in backend_source
    assert "/api/chat" in backend_source
    assert "/api/voices/clone" in backend_source
    assert "/api/tts" in backend_source
