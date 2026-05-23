from __future__ import annotations

from .voice import (
    TextToSpeechRequest,
    TextToSpeechResult,
    VoiceCloneRequest,
    VoiceCloneResult,
    VoiceProvider,
)


class ProductizationService:
    """Thin service facade for productized API handlers."""

    def __init__(self, voice_provider: VoiceProvider) -> None:
        self._voice_provider = voice_provider

    def clone_voice(
        self,
        *,
        family_id: str,
        created_by: str,
        sample_paths: list[str],
        consent_confirmed: bool,
        sample_source: str,
    ) -> VoiceCloneResult:
        request = VoiceCloneRequest(
            family_id=family_id,
            created_by=created_by,
            sample_paths=sample_paths,
            consent_confirmed=consent_confirmed,
            sample_source=sample_source,
        )
        return self._voice_provider.create_clone(request)

    def synthesize_reply(
        self,
        *,
        family_id: str,
        voice_profile_id: str,
        text: str,
    ) -> TextToSpeechResult:
        request = TextToSpeechRequest(
            family_id=family_id,
            voice_profile_id=voice_profile_id,
            text=text,
        )
        return self._voice_provider.synthesize(request)

