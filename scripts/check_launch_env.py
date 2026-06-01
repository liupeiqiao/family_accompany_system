from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from urllib.parse import urlparse

from dotenv import load_dotenv


LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


@dataclass
class CheckResult:
    errors: list[str]
    warnings: list[str]


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _env(name: str) -> str:
    return os.getenv(name, "").strip()


def _is_placeholder(value: str) -> bool:
    lowered = value.lower()
    return any(token in lowered for token in ["your-", "replace-with", "替换为", "真实"])


def _check_required_secret(errors: list[str], name: str, *, min_length: int = 1) -> None:
    value = _env(name)
    if not value:
        errors.append(f"{name} is required.")
        return
    if _is_placeholder(value):
        errors.append(f"{name} still looks like a placeholder.")
        return
    if len(value) < min_length:
        errors.append(f"{name} must be at least {min_length} characters.")


def _check_public_url(errors: list[str], warnings: list[str]) -> None:
    public_url = _env("APP_PUBLIC_URL") or _env("PUBLIC_BASE_URL")
    if not public_url:
        errors.append("APP_PUBLIC_URL is required for launch HTTPS checks.")
        return

    parsed = urlparse(public_url)
    host = (parsed.hostname or "").lower()
    if not parsed.scheme or not host:
        errors.append("APP_PUBLIC_URL must be a full URL, for example https://example.com.")
        return

    if host in LOCAL_HOSTS:
        warnings.append("APP_PUBLIC_URL points to localhost; microphone access is only safe for local testing.")
        return

    if parsed.scheme != "https":
        errors.append("APP_PUBLIC_URL must use https for browser microphone access on a domain.")


def _check_login_policy(errors: list[str]) -> None:
    env_name = (_env("COMPANION_ENV") or _env("NODE_ENV") or "development").lower()
    test_login_enabled = _truthy(_env("TEST_LOGIN_ENABLED"))
    sms_enabled = _truthy(_env("SMS_ENABLED"))
    sms_provider = (_env("SMS_PROVIDER") or "none").lower()

    if env_name in {"prod", "production"}:
        if test_login_enabled:
            errors.append("TEST_LOGIN_ENABLED must be false in production.")
        if not sms_enabled or sms_provider in {"", "none"}:
            errors.append("Production login requires SMS_ENABLED=true and a real SMS_PROVIDER.")
        return

    if env_name in {"staging", "stage", "test"} and test_login_enabled:
        if not _env("TEST_LOGIN_CODE"):
            errors.append("TEST_LOGIN_CODE is required when staging test login is enabled.")
        if not _env("TEST_LOGIN_WHITELIST"):
            errors.append("TEST_LOGIN_WHITELIST is required when staging test login is enabled.")


def check_launch_env() -> CheckResult:
    errors: list[str] = []
    warnings: list[str] = []

    _check_public_url(errors, warnings)
    _check_required_secret(errors, "DATABASE_URL")
    _check_required_secret(errors, "JWT_SECRET", min_length=32)
    _check_required_secret(errors, "DEEPSEEK_API_KEY")

    if (_env("VOICE_PROVIDER") or "mock").lower() != "doubao":
        errors.append("VOICE_PROVIDER must be doubao for the launch voice experience.")
    _check_required_secret(errors, "DOUBAO_TTS_API_KEY")
    _check_required_secret(errors, "DOUBAO_TTS_DEFAULT_VOICE_TYPE")
    if not (_env("DOUBAO_ASR_API_KEY") or _env("DOUBAO_TTS_API_KEY")):
        errors.append("DOUBAO_ASR_API_KEY or DOUBAO_TTS_API_KEY is required for speech recognition.")

    if _env("NEXT_PUBLIC_COMPANION_API_URL") not in {"/api", ""}:
        warnings.append("NEXT_PUBLIC_COMPANION_API_URL is not /api; confirm Nginx routes API requests correctly.")

    _check_login_policy(errors)

    if (_env("AUDIO_STORAGE_PROVIDER") or "").lower() != "tos":
        warnings.append("AUDIO_STORAGE_PROVIDER=tos is not configured; generated audio replay may not survive redeploys.")

    return CheckResult(errors=errors, warnings=warnings)


def main() -> int:
    load_dotenv(".env")
    result = check_launch_env()

    for warning in result.warnings:
        print(f"WARN: {warning}")
    for error in result.errors:
        print(f"ERROR: {error}", file=sys.stderr)

    if result.errors:
        print(f"Launch environment check failed: {len(result.errors)} error(s).", file=sys.stderr)
        return 2

    print("Launch environment check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
