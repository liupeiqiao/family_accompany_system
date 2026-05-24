from __future__ import annotations

import json

import pytest


class FakeResponse:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def read(self) -> bytes:
        return self._body


def test_doubao_provider_synthesizes_audio_data_url():
    from productization.voice import DoubaoTTSConfig, DoubaoVoiceProvider, TextToSpeechRequest

    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["method"] = request.get_method()
        captured["headers"] = dict(request.header_items())
        captured["body"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return FakeResponse(
            b'event: message\n'
            b'data: {"code":3000,"message":"Success","sequence":1,"data":"ZmFrZQ=="}\n\n'
            b'event: message\n'
            b'data: {"code":3000,"message":"Success","sequence":-1,"data":"LW1wMw=="}\n\n'
        )

    provider = DoubaoVoiceProvider(
        DoubaoTTSConfig(
            app_id="app-id",
            access_token="access-token",
            cluster="volcano_tts",
            resource_id="volc.service_type.10029",
            default_voice_type="zh_female_vv_uranus_bigtts",
            model="seed-tts-1.1",
        ),
        opener=fake_urlopen,
        reqid_factory=lambda: "local-reqid",
    )

    result = provider.synthesize(
        TextToSpeechRequest(
            family_id="family-1",
            voice_profile_id="zh_female_vv_uranus_bigtts",
            text="妈，我在呢。",
        )
    )

    normalized_headers = {key.lower(): value for key, value in captured["headers"].items()}
    assert captured["url"] == "https://openspeech.bytedance.com/api/v3/tts/unidirectional/sse"
    assert captured["method"] == "POST"
    assert normalized_headers["x-api-app-key"] == "app-id"
    assert normalized_headers["x-api-access-key"] == "access-token"
    assert normalized_headers["x-api-resource-id"] == "volc.service_type.10029"
    assert normalized_headers["accept"] == "text/event-stream"
    assert captured["body"]["user"]["uid"] == "family-1"
    assert captured["body"]["audio"]["voice_type"] == "zh_female_vv_uranus_bigtts"
    assert captured["body"]["audio"]["encoding"] == "mp3"
    assert captured["body"]["request"]["reqid"] == "local-reqid"
    assert captured["body"]["request"]["text"] == "妈，我在呢。"
    assert captured["body"]["request"]["operation"] == "submit"
    assert captured["body"]["request"]["model"] == "seed-tts-1.1"
    assert captured["timeout"] == 30
    assert result.provider == "doubao"
    assert result.audio_path == "data:audio/mpeg;base64,ZmFrZS1tcDM="


def test_doubao_provider_rejects_failed_response():
    from productization.voice import DoubaoTTSConfig, DoubaoVoiceProvider, TextToSpeechRequest

    def fake_urlopen(request, timeout):
        return FakeResponse(
            b'event: error\n'
            b'data: {"code":3050,"message":"voice type not found"}\n\n'
        )

    provider = DoubaoVoiceProvider(
        DoubaoTTSConfig(
            app_id="app-id",
            access_token="access-token",
            default_voice_type="voice-type",
        ),
        opener=fake_urlopen,
    )

    with pytest.raises(ValueError, match="3050"):
        provider.synthesize(
            TextToSpeechRequest(
                family_id="family-1",
                voice_profile_id="voice-type",
                text="hello",
            )
        )


def test_voice_provider_factory_uses_mock_by_default(monkeypatch):
    from productization.voice import MockVoiceProvider, get_voice_provider_from_env

    monkeypatch.delenv("VOICE_PROVIDER", raising=False)
    monkeypatch.delenv("DOUBAO_TTS_APP_ID", raising=False)
    monkeypatch.delenv("DOUBAO_TTS_ACCESS_TOKEN", raising=False)

    assert isinstance(get_voice_provider_from_env(), MockVoiceProvider)


def test_voice_provider_factory_uses_doubao_when_configured(monkeypatch):
    from productization.voice import DoubaoVoiceProvider, get_voice_provider_from_env

    monkeypatch.setenv("VOICE_PROVIDER", "doubao")
    monkeypatch.setenv("DOUBAO_TTS_APP_ID", "app-id")
    monkeypatch.setenv("DOUBAO_TTS_ACCESS_TOKEN", "access-token")
    monkeypatch.setenv("DOUBAO_TTS_DEFAULT_VOICE_TYPE", "voice-type")

    assert isinstance(get_voice_provider_from_env(), DoubaoVoiceProvider)
