from __future__ import annotations

import base64
import os
import re
from dataclasses import dataclass
from uuid import uuid4


_DATA_URL_RE = re.compile(r"^data:(?P<mime>[-\w.+/]+);base64,(?P<data>.+)$", re.DOTALL)


@dataclass(frozen=True)
class TOSAudioStorageConfig:
    access_key_id: str
    secret_access_key: str
    endpoint: str
    region: str
    bucket: str
    public_base_url: str = ""
    prefix: str = "generated-audio"

    @classmethod
    def from_env(cls) -> "TOSAudioStorageConfig | None":
        provider = os.getenv("AUDIO_STORAGE_PROVIDER", "").strip().lower()
        if provider not in {"tos", "volcengine_tos"}:
            return None

        access_key_id = os.getenv("TOS_ACCESS_KEY_ID") or os.getenv("TOS_ACCESS_KEY")
        secret_access_key = os.getenv("TOS_SECRET_ACCESS_KEY") or os.getenv("TOS_SECRET_KEY")
        endpoint = os.getenv("TOS_ENDPOINT")
        region = os.getenv("TOS_REGION")
        bucket = os.getenv("TOS_BUCKET")
        if not all([access_key_id, secret_access_key, endpoint, region, bucket]):
            return None

        return cls(
            access_key_id=str(access_key_id),
            secret_access_key=str(secret_access_key),
            endpoint=str(endpoint).strip(),
            region=str(region).strip(),
            bucket=str(bucket).strip(),
            public_base_url=(
                os.getenv("TOS_PUBLIC_BASE_URL")
                or os.getenv("AUDIO_STORAGE_PUBLIC_BASE_URL")
                or ""
            ).strip(),
            prefix=(os.getenv("TOS_PREFIX") or "generated-audio").strip().strip("/"),
        )

    def public_url_for(self, key: str) -> str:
        if self.public_base_url:
            return f"{self.public_base_url.rstrip('/')}/{key}"
        return f"tos://{self.bucket}/{key}"


class TOSAudioStorage:
    def __init__(
        self,
        config: TOSAudioStorageConfig,
        *,
        client=None,
        object_id_factory=lambda: uuid4().hex,
    ) -> None:
        self._config = config
        self._client = client
        self._object_id_factory = object_id_factory

    def store_data_url(self, *, family_id: str, source_audio_url: str) -> str:
        parsed = _parse_audio_data_url(source_audio_url)
        if parsed is None:
            return source_audio_url

        mime_type, audio_bytes = parsed
        key = self._build_object_key(family_id=family_id, mime_type=mime_type)
        self._get_client().put_object(
            self._config.bucket,
            key,
            content=audio_bytes,
            content_type=mime_type,
        )
        return self._config.public_url_for(key)

    def _build_object_key(self, *, family_id: str, mime_type: str) -> str:
        clean_family_id = _clean_path_part(family_id)
        extension = _extension_for_mime_type(mime_type)
        return f"{self._config.prefix}/{clean_family_id}/{self._object_id_factory()}.{extension}"

    def _get_client(self):
        if self._client is not None:
            return self._client

        import tos

        self._client = tos.TosClientV2(
            self._config.access_key_id,
            self._config.secret_access_key,
            self._config.endpoint,
            self._config.region,
        )
        return self._client


def store_generated_audio_if_configured(*, family_id: str, source_audio_url: str) -> str:
    config = TOSAudioStorageConfig.from_env()
    if config is None:
        return source_audio_url
    try:
        return TOSAudioStorage(config).store_data_url(
            family_id=family_id,
            source_audio_url=source_audio_url,
        )
    except Exception:
        return source_audio_url


def _parse_audio_data_url(source_audio_url: str) -> tuple[str, bytes] | None:
    match = _DATA_URL_RE.match(source_audio_url)
    if not match:
        return None
    return match.group("mime"), base64.b64decode(match.group("data"))


def _extension_for_mime_type(mime_type: str) -> str:
    return {
        "audio/mpeg": "mp3",
        "audio/mp3": "mp3",
        "audio/wav": "wav",
        "audio/x-wav": "wav",
        "audio/webm": "webm",
        "audio/ogg": "ogg",
    }.get(mime_type.lower(), "bin")


def _clean_path_part(value: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip())
    return clean.strip("-") or "unknown-family"
