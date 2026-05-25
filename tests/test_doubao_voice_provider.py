from __future__ import annotations

import json
from urllib.error import HTTPError

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
            b'data: {"code":0,"message":"","data":"ZmFrZQ=="}\n\n'
            b'event: message\n'
            b'data: {"code":0,"message":"","data":"LW1wMw=="}\n\n'
            b'event: message\n'
            b'data: {"code":20000000,"message":"OK","data":null}\n\n'
        )

    provider = DoubaoVoiceProvider(
        DoubaoTTSConfig(
            api_key="api-key",
            resource_id="seed-tts-2.0",
            default_voice_type="zh_female_vv_uranus_bigtts",
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
    assert normalized_headers["x-api-key"] == "api-key"
    assert "x-api-app-key" not in normalized_headers
    assert "x-api-app-id" not in normalized_headers
    assert "x-api-access-key" not in normalized_headers
    assert normalized_headers["x-api-resource-id"] == "seed-tts-2.0"
    assert normalized_headers["accept"] == "text/event-stream"
    assert captured["body"]["user"]["uid"] == "family-1"
    assert captured["body"]["req_params"]["speaker"] == "zh_female_vv_uranus_bigtts"
    assert captured["body"]["req_params"]["audio_params"]["format"] == "mp3"
    assert captured["body"]["req_params"]["audio_params"]["sample_rate"] == 24000
    assert captured["body"]["req_params"]["text"] == "妈，我在呢。"
    assert "audio" not in captured["body"]
    assert "request" not in captured["body"]
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
            api_key="api-key",
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


def test_doubao_provider_uses_icl_resource_for_cloned_speaker():
    from productization.voice import DoubaoTTSConfig, DoubaoVoiceProvider, TextToSpeechRequest

    captured = {}

    def fake_urlopen(request, timeout):
        captured["headers"] = dict(request.header_items())
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse(
            b'event: message\n'
            b'data: {"code":0,"message":"","data":"ZmFrZQ=="}\n\n'
            b'event: message\n'
            b'data: {"code":20000000,"message":"OK","data":null}\n\n'
        )

    provider = DoubaoVoiceProvider(
        DoubaoTTSConfig(
            api_key="api-key",
            resource_id="seed-tts-2.0",
            clone_resource_id="seed-icl-2.0",
            default_voice_type="zh_female_vv_uranus_bigtts",
        ),
        opener=fake_urlopen,
        reqid_factory=lambda: "local-reqid",
    )

    result = provider.synthesize(
        TextToSpeechRequest(
            family_id="family-1",
            voice_profile_id="S_clone_speaker_123",
            text="hello",
        )
    )

    normalized_headers = {key.lower(): value for key, value in captured["headers"].items()}
    assert normalized_headers["x-api-resource-id"] == "seed-icl-2.0"
    assert captured["body"]["req_params"]["speaker"] == "S_clone_speaker_123"
    assert result.audio_path == "data:audio/mpeg;base64,ZmFrZQ=="


def test_doubao_provider_uses_icl_resource_for_custom_cloned_speaker():
    from productization.voice import DoubaoTTSConfig, DoubaoVoiceProvider, TextToSpeechRequest

    captured = {}

    def fake_urlopen(request, timeout):
        captured["headers"] = dict(request.header_items())
        return FakeResponse(
            b'event: message\n'
            b'data: {"code":0,"message":"","data":"ZmFrZQ=="}\n\n'
            b'event: message\n'
            b'data: {"code":20000000,"message":"OK","data":null}\n\n'
        )

    provider = DoubaoVoiceProvider(
        DoubaoTTSConfig(
            api_key="api-key",
            resource_id="seed-tts-2.0",
            clone_resource_id="seed-icl-2.0",
            default_voice_type="zh_female_vv_uranus_bigtts",
        ),
        opener=fake_urlopen,
    )

    provider.synthesize(
        TextToSpeechRequest(
            family_id="family-1",
            voice_profile_id="custom_family_voice_001",
            text="hello",
        )
    )

    normalized_headers = {key.lower(): value for key, value in captured["headers"].items()}
    assert normalized_headers["x-api-resource-id"] == "seed-icl-2.0"


def test_doubao_provider_creates_voice_clone_with_v3_api():
    from productization.voice import DoubaoTTSConfig, DoubaoVoiceProvider, VoiceCloneRequest

    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["method"] = request.get_method()
        captured["headers"] = dict(request.header_items())
        captured["body"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return FakeResponse(
            json.dumps(
                {
                    "speaker_id": "custom_family_voice_001",
                    "status": 2,
                    "available_training_times": 14,
                    "speaker_status": [{"model_type": 4, "demo_audio": "https://example.test/demo.wav"}],
                }
            ).encode("utf-8")
        )

    provider = DoubaoVoiceProvider(
        DoubaoTTSConfig(
            api_key="api-key",
            default_voice_type="zh_female_vv_uranus_bigtts",
            clone_endpoint="https://example.test/voice_clone",
        ),
        opener=fake_urlopen,
        reqid_factory=lambda: "clone-reqid",
    )

    result = provider.create_clone(
        VoiceCloneRequest(
            family_id="family-1",
            created_by="owner",
            sample_paths=[],
            consent_confirmed=True,
            sample_source="upload",
            audio_data_base64="ZmFrZS13YXY=",
            audio_format="wav",
            speaker_id="custom_speaker_id",
            custom_speaker_id="custom_family_voice_001",
            text="这是一段用于声音复刻的本人授权录音。",
            language=0,
            demo_text="妈，我在呢。",
            enable_audio_denoise=False,
        )
    )

    normalized_headers = {key.lower(): value for key, value in captured["headers"].items()}
    assert captured["url"] == "https://example.test/voice_clone"
    assert captured["method"] == "POST"
    assert normalized_headers["x-api-key"] == "api-key"
    assert normalized_headers["x-api-request-id"] == "clone-reqid"
    assert captured["body"]["speaker_id"] == "custom_speaker_id"
    assert captured["body"]["custom_speaker_id"] == "custom_family_voice_001"
    assert captured["body"]["audio"] == {"data": "ZmFrZS13YXY=", "format": "wav"}
    assert captured["body"]["text"] == "这是一段用于声音复刻的本人授权录音。"
    assert captured["body"]["language"] == 0
    assert captured["body"]["extra_params"]["demo_text"] == "妈，我在呢。"
    assert captured["body"]["extra_params"]["enable_audio_denoise"] is False
    assert captured["timeout"] == 60
    assert result.provider == "doubao"
    assert result.provider_voice_id == "custom_family_voice_001"
    assert result.audit["status"] == "2"
    assert result.audit["model_types"] == "4"


def test_doubao_provider_reports_voice_clone_http_error_body():
    from io import BytesIO

    from productization.voice import DoubaoTTSConfig, DoubaoVoiceProvider, VoiceCloneRequest

    def fake_urlopen(request, timeout):
        raise HTTPError(
            request.full_url,
            400,
            "Bad Request",
            {},
            BytesIO(b'{"code":45001105,"message":"audio decode failed"}'),
        )

    provider = DoubaoVoiceProvider(
        DoubaoTTSConfig(api_key="api-key", default_voice_type="zh_female_vv_uranus_bigtts"),
        opener=fake_urlopen,
    )

    with pytest.raises(ValueError, match="45001105"):
        provider.create_clone(
            VoiceCloneRequest(
                family_id="family-1",
                created_by="owner",
                sample_paths=[],
                consent_confirmed=True,
                sample_source="upload",
                audio_data_base64="bad-audio",
                audio_format="mp3",
                custom_speaker_id="custom_family_voice_001",
            )
        )


def test_voice_provider_factory_uses_mock_by_default(monkeypatch):
    from productization.voice import MockVoiceProvider, get_voice_provider_from_env

    monkeypatch.delenv("VOICE_PROVIDER", raising=False)
    monkeypatch.delenv("DOUBAO_TTS_API_KEY", raising=False)

    assert isinstance(get_voice_provider_from_env(), MockVoiceProvider)


def test_voice_provider_factory_uses_doubao_when_configured(monkeypatch):
    from productization.voice import DoubaoVoiceProvider, get_voice_provider_from_env

    monkeypatch.setenv("VOICE_PROVIDER", "doubao")
    monkeypatch.setenv("DOUBAO_TTS_API_KEY", "api-key")
    monkeypatch.setenv("DOUBAO_TTS_DEFAULT_VOICE_TYPE", "voice-type")

    assert isinstance(get_voice_provider_from_env(), DoubaoVoiceProvider)
