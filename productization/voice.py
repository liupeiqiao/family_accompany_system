from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
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

