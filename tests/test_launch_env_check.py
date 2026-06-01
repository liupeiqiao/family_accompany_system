from __future__ import annotations


def _set_valid_launch_env(monkeypatch):
    monkeypatch.setenv("APP_PUBLIC_URL", "https://example.com")
    monkeypatch.setenv("DATABASE_URL", "postgresql://admin:secret@example.com:5432/companion")
    monkeypatch.setenv("JWT_SECRET", "x" * 32)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "deepseek-key")
    monkeypatch.setenv("VOICE_PROVIDER", "doubao")
    monkeypatch.setenv("DOUBAO_TTS_API_KEY", "doubao-key")
    monkeypatch.setenv("DOUBAO_TTS_DEFAULT_VOICE_TYPE", "voice-type")
    monkeypatch.setenv("NEXT_PUBLIC_COMPANION_API_URL", "/api")
    monkeypatch.setenv("AUDIO_STORAGE_PROVIDER", "tos")


def test_launch_env_check_accepts_staging_whitelist_login(monkeypatch):
    from scripts.check_launch_env import check_launch_env

    _set_valid_launch_env(monkeypatch)
    monkeypatch.setenv("COMPANION_ENV", "staging")
    monkeypatch.setenv("TEST_LOGIN_ENABLED", "true")
    monkeypatch.setenv("TEST_LOGIN_CODE", "123456")
    monkeypatch.setenv("TEST_LOGIN_WHITELIST", "13800138000")
    monkeypatch.setenv("SMS_ENABLED", "false")
    monkeypatch.setenv("SMS_PROVIDER", "none")

    result = check_launch_env()

    assert result.errors == []


def test_launch_env_check_rejects_non_https_domain(monkeypatch):
    from scripts.check_launch_env import check_launch_env

    _set_valid_launch_env(monkeypatch)
    monkeypatch.setenv("APP_PUBLIC_URL", "http://example.com")
    monkeypatch.setenv("COMPANION_ENV", "staging")
    monkeypatch.setenv("TEST_LOGIN_ENABLED", "true")
    monkeypatch.setenv("TEST_LOGIN_CODE", "123456")
    monkeypatch.setenv("TEST_LOGIN_WHITELIST", "13800138000")

    result = check_launch_env()

    assert any("https" in error for error in result.errors)


def test_launch_env_check_rejects_production_without_real_sms(monkeypatch):
    from scripts.check_launch_env import check_launch_env

    _set_valid_launch_env(monkeypatch)
    monkeypatch.setenv("COMPANION_ENV", "production")
    monkeypatch.setenv("TEST_LOGIN_ENABLED", "false")
    monkeypatch.setenv("SMS_ENABLED", "false")
    monkeypatch.setenv("SMS_PROVIDER", "none")

    result = check_launch_env()

    assert any("Production login requires" in error for error in result.errors)


def test_launch_env_check_rejects_placeholders_and_short_jwt(monkeypatch):
    from scripts.check_launch_env import check_launch_env

    _set_valid_launch_env(monkeypatch)
    monkeypatch.setenv("COMPANION_ENV", "staging")
    monkeypatch.setenv("TEST_LOGIN_ENABLED", "true")
    monkeypatch.setenv("TEST_LOGIN_CODE", "123456")
    monkeypatch.setenv("TEST_LOGIN_WHITELIST", "13800138000")
    monkeypatch.setenv("JWT_SECRET", "short")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "your-deepseek-api-key")

    result = check_launch_env()

    assert any("JWT_SECRET" in error for error in result.errors)
    assert any("DEEPSEEK_API_KEY" in error for error in result.errors)
