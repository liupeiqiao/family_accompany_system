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
    api_key: str
    default_voice_type: str
    resource_id: str = "seed-tts-2.0"
    endpoint: str = "https://openspeech.bytedance.com/api/v3/tts/unidirectional/sse"
    encoding: str = "mp3"
    sample_rate: int = 24000
    speech_rate: int = 0

    @classmethod
    def from_env(cls) -> "DoubaoTTSConfig | None":
        api_key = os.getenv("DOUBAO_TTS_API_KEY")
        voice_type = os.getenv("DOUBAO_TTS_DEFAULT_VOICE_TYPE")
        if not api_key or not voice_type:
            return None
        return cls(
            api_key=api_key,
            default_voice_type=voice_type,
            resource_id=os.getenv("DOUBAO_TTS_RESOURCE_ID", "seed-tts-2.0"),
            endpoint=os.getenv(
                "DOUBAO_TTS_ENDPOINT",
                "https://openspeech.bytedance.com/api/v3/tts/unidirectional/sse",
            ).rstrip(),
            encoding=os.getenv("DOUBAO_TTS_ENCODING", "mp3"),
            sample_rate=int(os.getenv("DOUBAO_TTS_SAMPLE_RATE", "24000")),
            speech_rate=int(os.getenv("DOUBAO_TTS_SPEECH_RATE", "0")),
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
        if not request.consent_confirmed:
            raise VoiceConsentError("Voice cloning requires consent confirmation.")
        if request.sample_paths:
            raise NotImplementedError(
                "Doubao voice cloning with real samples requires the voice-clone API and sample file upload flow."
            )
        return VoiceCloneResult(
            provider=self.provider_name,
            provider_voice_id=self._config.default_voice_type,
            audit={
                "family_id": request.family_id,
                "created_by": request.created_by,
                "sample_source": "preset",
            },
        )

    def synthesize(self, request: TextToSpeechRequest) -> TextToSpeechResult:
        text = request.text.strip()
        if not text:
            raise ValueError("TTS text cannot be empty.")

        reqid = self._reqid_factory()
        audio_params = {
            "format": self._config.encoding,
            "sample_rate": self._config.sample_rate,
        }
        if self._config.speech_rate:
            audio_params["speech_rate"] = self._config.speech_rate

        payload = {
            "user": {
                "uid": request.family_id or "family-companion",
            },
            "req_params": {
                "text": text,
                "speaker": request.voice_profile_id or self._config.default_voice_type,
                "audio_params": audio_params,
            },
        }

        http_request = urlrequest.Request(
            self._config.endpoint,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            method="POST",
            headers={
                "X-Api-Key": self._config.api_key,
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
                "DOUBAO_TTS_API_KEY and "
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
        code = payload.get("code")
        if code in {20000000, "20000000"}:
            continue
        if code not in {0, "0", 3000, "3000"}:
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
