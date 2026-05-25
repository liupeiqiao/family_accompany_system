from __future__ import annotations

import base64
import json
import os
import re
from dataclasses import dataclass
from typing import Protocol
from urllib.error import HTTPError, URLError
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
    audio_data_base64: str = ""
    audio_format: str = ""
    speaker_id: str = ""
    custom_speaker_id: str = ""
    text: str = ""
    language: int = 0
    demo_text: str = ""
    enable_audio_denoise: bool | None = None


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
    clone_resource_id: str = "seed-icl-2.0"
    endpoint: str = "https://openspeech.bytedance.com/api/v3/tts/unidirectional/sse"
    clone_endpoint: str = "https://openspeech.bytedance.com/api/v3/tts/voice_clone"
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
            clone_resource_id=os.getenv("DOUBAO_TTS_CLONE_RESOURCE_ID", "seed-icl-2.0"),
            endpoint=os.getenv(
                "DOUBAO_TTS_ENDPOINT",
                "https://openspeech.bytedance.com/api/v3/tts/unidirectional/sse",
            ).rstrip(),
            clone_endpoint=os.getenv(
                "DOUBAO_VOICE_CLONE_ENDPOINT",
                "https://openspeech.bytedance.com/api/v3/tts/voice_clone",
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
        if request.audio_data_base64:
            return self._create_clone_from_audio(request)
        if request.sample_paths:
            raise NotImplementedError("Doubao voice cloning requires inline audio data.")
        return VoiceCloneResult(
            provider=self.provider_name,
            provider_voice_id=self._config.default_voice_type,
            audit={
                "family_id": request.family_id,
                "created_by": request.created_by,
                "sample_source": "preset",
            },
        )

    def _create_clone_from_audio(self, request: VoiceCloneRequest) -> VoiceCloneResult:
        speaker_id = request.speaker_id.strip()
        custom_speaker_id = request.custom_speaker_id.strip()
        if custom_speaker_id and not speaker_id:
            speaker_id = "custom_speaker_id"
        if not speaker_id:
            raise ValueError("Doubao voice cloning requires speaker_id or custom_speaker_id.")
        if custom_speaker_id:
            _validate_doubao_custom_speaker_id(custom_speaker_id)
            speaker_id = "custom_speaker_id"
        elif not _is_doubao_reserved_clone_speaker_id(speaker_id):
            raise ValueError(
                "Invalid Doubao speaker_id. For postpaid custom voices, send "
                'speaker_id="custom_speaker_id" and put the real name in custom_speaker_id.'
            )

        payload: dict[str, object] = {
            "speaker_id": speaker_id,
            "audio": {
                "data": request.audio_data_base64,
                "format": request.audio_format or "wav",
            },
            "language": request.language,
        }
        if custom_speaker_id:
            payload["custom_speaker_id"] = custom_speaker_id
        if request.text.strip():
            payload["text"] = request.text.strip()

        extra_params: dict[str, object] = {}
        if request.demo_text.strip():
            extra_params["demo_text"] = request.demo_text.strip()
        if request.enable_audio_denoise is not None:
            extra_params["enable_audio_denoise"] = request.enable_audio_denoise
        if extra_params:
            payload["extra_params"] = extra_params

        reqid = self._reqid_factory()
        http_request = urlrequest.Request(
            self._config.clone_endpoint,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            method="POST",
            headers={
                "X-Api-Key": self._config.api_key,
                "X-Api-Request-Id": reqid,
                "Content-Type": "application/json",
            },
        )
        try:
            with self._opener(http_request, timeout=60) as response:
                response_payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise ValueError(_format_doubao_http_error("voice clone", exc)) from exc
        except URLError as exc:
            raise ValueError(f"Doubao voice clone network error: {exc.reason}") from exc

        status = response_payload.get("status")
        if status not in {2, 4, "2", "4"}:
            message = response_payload.get("message") or "voice clone did not become ready"
            raise ValueError(f"Doubao voice clone failed: {response_payload.get('code')} {message}".strip())

        provider_voice_id = str(response_payload.get("speaker_id") or custom_speaker_id or speaker_id)
        model_types = [
            str(item.get("model_type"))
            for item in response_payload.get("speaker_status", [])
            if isinstance(item, dict) and item.get("model_type") is not None
        ]
        return VoiceCloneResult(
            provider=self.provider_name,
            provider_voice_id=provider_voice_id,
            audit={
                "family_id": request.family_id,
                "created_by": request.created_by,
                "sample_source": request.sample_source,
                "status": str(status),
                "available_training_times": str(response_payload.get("available_training_times", "")),
                "model_types": ",".join(model_types),
            },
        )

    def synthesize(self, request: TextToSpeechRequest) -> TextToSpeechResult:
        text = request.text.strip()
        if not text:
            raise ValueError("TTS text cannot be empty.")

        reqid = self._reqid_factory()
        speaker = request.voice_profile_id or self._config.default_voice_type
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
                "speaker": speaker,
                "audio_params": audio_params,
            },
        }

        http_request = urlrequest.Request(
            self._config.endpoint,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            method="POST",
            headers={
                "X-Api-Key": self._config.api_key,
                "X-Api-Resource-Id": _doubao_resource_id_for_speaker(speaker, self._config),
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


def _doubao_resource_id_for_speaker(speaker: str, config: DoubaoTTSConfig) -> str:
    normalized = speaker.strip().lower()
    if normalized.startswith(("s_", "icl_", "custom_")):
        return config.clone_resource_id
    return config.resource_id


def _is_doubao_reserved_clone_speaker_id(speaker_id: str) -> bool:
    normalized = speaker_id.strip().lower()
    return normalized.startswith(("s_", "icl_")) or normalized == "custom_speaker_id"


def _validate_doubao_custom_speaker_id(custom_speaker_id: str) -> None:
    if len(custom_speaker_id) < 8:
        raise ValueError("Doubao custom_speaker_id must be at least 8 characters.")
    if len(custom_speaker_id) > 256:
        raise ValueError("Doubao custom_speaker_id must be at most 256 characters.")
    if not re.match(r"^[A-Za-z][A-Za-z0-9_-]*[A-Za-z0-9]$", custom_speaker_id):
        raise ValueError(
            "Doubao custom_speaker_id must start with a letter and contain only letters, "
            "numbers, hyphen, or underscore; it cannot end with hyphen or underscore."
        )
    forbidden = re.compile(
        r"^((s_|icl_|mix_|dit_|bv)|[a-z]{2}_|.*_(bigtts|bigtts_cc|tob|cs_tob|streaming)$)",
        re.IGNORECASE,
    )
    if forbidden.match(custom_speaker_id):
        raise ValueError("Doubao custom_speaker_id conflicts with reserved speaker naming rules.")


def _format_doubao_http_error(operation: str, exc: HTTPError) -> str:
    raw = exc.read().decode("utf-8", errors="replace")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        payload = {}
    code = payload.get("code", exc.code)
    message = payload.get("message", raw or exc.reason)
    return f"Doubao {operation} failed: {code} {message}".strip()


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
