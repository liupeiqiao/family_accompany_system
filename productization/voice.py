from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from typing import Protocol
from urllib import request as urlrequest
from uuid import uuid4


class VoiceConsentError(ValueError):
    """Raised when a voice clone request lacks explicit user confirmation."""


@dataclass(frozen=True)
class VoiceCloneRequest:
    family_id: str
    created_by: str
    sample_paths: list[str]
    consent_confirmed: bool
    sample_source: str


@dataclass(frozen=True)
class VoiceCloneResult:
    provider: str
    provider_voice_id: str
    audit: dict[str, str]


@dataclass(frozen=True)
class TextToSpeechRequest:
    family_id: str
    voice_profile_id: str
    text: str


@dataclass(frozen=True)
class TextToSpeechResult:
    provider: str
    audio_path: str


class VoiceProvider(Protocol):
    provider_name: str

    def create_clone(self, request: VoiceCloneRequest) -> VoiceCloneResult:
        ...

    def synthesize(self, request: TextToSpeechRequest) -> TextToSpeechResult:
        ...


class MockVoiceProvider:
    provider_name = "mock"

    def create_clone(self, request: VoiceCloneRequest) -> VoiceCloneResult:
        if not request.consent_confirmed:
            raise VoiceConsentError("Voice cloning requires consent confirmation.")
        if not request.sample_paths:
            raise ValueError("At least one voice sample is required.")

        return VoiceCloneResult(
            provider=self.provider_name,
            provider_voice_id=f"mock_voice_{uuid4().hex[:12]}",
            audit={
                "family_id": request.family_id,
                "created_by": request.created_by,
                "sample_source": request.sample_source,
            },
        )

    def synthesize(self, request: TextToSpeechRequest) -> TextToSpeechResult:
        if not request.text.strip():
            raise ValueError("TTS text cannot be empty.")
        return TextToSpeechResult(
            provider=self.provider_name,
            audio_path=f"generated-audio/{request.family_id}/{uuid4().hex}.mp3",
        )


@dataclass(frozen=True)
class DoubaoTTSConfig:
    app_id: str
    access_token: str
    default_voice_type: str
    cluster: str = "volcano_tts"
    resource_id: str = "volc.service_type.10029"
    model: str = "seed-tts-1.1"
    endpoint: str = "https://openspeech.bytedance.com/api/v3/tts/unidirectional/sse"
    encoding: str = "mp3"
    speed_ratio: float = 1.0
    rate: int = 24000

    @classmethod
    def from_env(cls) -> "DoubaoTTSConfig | None":
        app_id = os.getenv("DOUBAO_TTS_APP_ID")
        access_token = os.getenv("DOUBAO_TTS_ACCESS_TOKEN")
        voice_type = os.getenv("DOUBAO_TTS_DEFAULT_VOICE_TYPE")
        if not app_id or not access_token or not voice_type:
            return None
        return cls(
            app_id=app_id,
            access_token=access_token,
            default_voice_type=voice_type,
            cluster=os.getenv("DOUBAO_TTS_CLUSTER", "volcano_tts"),
            resource_id=os.getenv("DOUBAO_TTS_RESOURCE_ID", "volc.service_type.10029"),
            model=os.getenv("DOUBAO_TTS_MODEL", "seed-tts-1.1"),
            endpoint=os.getenv(
                "DOUBAO_TTS_ENDPOINT",
                "https://openspeech.bytedance.com/api/v3/tts/unidirectional/sse",
            ).rstrip(),
            encoding=os.getenv("DOUBAO_TTS_ENCODING", "mp3"),
            speed_ratio=float(os.getenv("DOUBAO_TTS_SPEED_RATIO", "1.0")),
            rate=int(os.getenv("DOUBAO_TTS_RATE", "24000")),
        )


class DoubaoVoiceProvider:
    provider_name = "doubao"

    def __init__(
        self,
        config: DoubaoTTSConfig,
        opener=urlrequest.urlopen,
        reqid_factory=lambda: uuid4().hex,
    ) -> None:
        self._config = config
        self._opener = opener
        self._reqid_factory = reqid_factory

    def create_clone(self, request: VoiceCloneRequest) -> VoiceCloneResult:
        raise NotImplementedError(
            "Doubao voice cloning requires the voice-clone API and sample file upload flow."
        )

    def synthesize(self, request: TextToSpeechRequest) -> TextToSpeechResult:
        text = request.text.strip()
        if not text:
            raise ValueError("TTS text cannot be empty.")

        reqid = self._reqid_factory()
        payload = {
            "user": {
                "uid": request.family_id or "family-companion",
            },
            "audio": {
                "voice_type": request.voice_profile_id or self._config.default_voice_type,
                "encoding": self._config.encoding,
                "speed_ratio": self._config.speed_ratio,
                "rate": self._config.rate,
            },
            "request": {
                "reqid": reqid,
                "text": text,
                "operation": "submit",
            },
        }
        if self._config.model:
            payload["request"]["model"] = self._config.model

        http_request = urlrequest.Request(
            self._config.endpoint,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            method="POST",
            headers={
                "X-Api-App-Key": self._config.app_id,
                "X-Api-Access-Key": self._config.access_token,
                "X-Api-Resource-Id": self._config.resource_id,
                "X-Api-Request-Id": reqid,
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
            },
        )
        with self._opener(http_request, timeout=30) as response:
            raw = response.read().decode("utf-8")
        audio_base64 = _parse_doubao_sse_audio(raw)
        return TextToSpeechResult(
            provider=self.provider_name,
            audio_path=f"data:{_audio_mime_type(self._config.encoding)};base64,{audio_base64}",
        )


def get_voice_provider_from_env() -> VoiceProvider:
    provider = os.getenv("VOICE_PROVIDER", "mock").strip().lower()
    if provider in {"doubao", "volcengine"}:
        config = DoubaoTTSConfig.from_env()
        if config is None:
            raise ValueError(
                "DOUBAO_TTS_APP_ID, DOUBAO_TTS_ACCESS_TOKEN, and "
                "DOUBAO_TTS_DEFAULT_VOICE_TYPE are required when VOICE_PROVIDER=doubao."
            )
        return DoubaoVoiceProvider(config)
    return MockVoiceProvider()


def _audio_mime_type(encoding: str) -> str:
    return {
        "mp3": "audio/mpeg",
        "wav": "audio/wav",
        "ogg_opus": "audio/ogg",
        "pcm": "audio/pcm",
    }.get(encoding, "audio/mpeg")


def _parse_doubao_sse_audio(raw: str) -> str:
    chunks: list[bytes] = []
    last_error: dict | None = None

    for line in raw.splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue
        data = line.removeprefix("data:").strip()
        if not data or data == "[DONE]":
            continue
        payload = json.loads(data)
        if payload.get("code") != 3000:
            last_error = payload
            continue
        audio = payload.get("data")
        if audio:
            chunks.append(base64.b64decode(str(audio)))

    if chunks:
        return base64.b64encode(b"".join(chunks)).decode("ascii")
    if last_error is not None:
        raise ValueError(
            f"Doubao TTS failed: {last_error.get('code')} {last_error.get('message', '')}".strip()
        )
    raise ValueError("Doubao TTS failed: empty SSE audio response.")
