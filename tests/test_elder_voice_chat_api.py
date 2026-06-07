from __future__ import annotations


def test_mock_asr_transcribes_non_empty_audio(monkeypatch):
    from productization.voice import SpeechRecognitionRequest, get_voice_provider_from_env

    monkeypatch.setenv("VOICE_PROVIDER", "mock")

    provider = get_voice_provider_from_env()
    result = provider.transcribe(
        SpeechRecognitionRequest(
            family_id="family-1",
            audio_bytes=b"fake-audio",
            audio_format="webm",
        )
    )

    assert result.provider == "mock"
    assert result.text == "小雨，我今天有点想你"
    assert 0 <= result.confidence <= 1


def test_mock_asr_rejects_empty_audio(monkeypatch):
    import pytest

    from productization.voice import SpeechRecognitionRequest, get_voice_provider_from_env

    monkeypatch.setenv("VOICE_PROVIDER", "mock")

    provider = get_voice_provider_from_env()
    with pytest.raises(ValueError, match="ASR audio cannot be empty"):
        provider.transcribe(
            SpeechRecognitionRequest(
                family_id="family-1",
                audio_bytes=b"",
                audio_format="webm",
            )
        )


def test_doubao_asr_uses_flash_recording_file_recognition(monkeypatch):
    import json

    from productization.voice import (
        DoubaoTTSConfig,
        DoubaoVoiceProvider,
        SpeechRecognitionRequest,
    )

    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps({"result": {"text": "小雨，我今天有点想你"}}).encode("utf-8")

        def getheader(self, name, default=None):
            return {"X-Api-Status-Code": "20000000"}.get(name, default)

    def fake_opener(request, timeout):
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        captured["body"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setenv("DOUBAO_ASR_API_KEY", "test-asr-key")
    provider = DoubaoVoiceProvider(
        DoubaoTTSConfig(api_key="tts-key", default_voice_type="voice"),
        opener=fake_opener,
        reqid_factory=lambda: "request-1",
    )

    result = provider.transcribe(
        SpeechRecognitionRequest(
            family_id="family-1",
            audio_bytes=b"fake-audio",
            audio_format="mp3",
        )
    )

    assert result.text == "小雨，我今天有点想你"
    assert captured["url"] == "https://openspeech.bytedance.com/api/v3/auc/bigmodel/recognize/flash"
    assert captured["headers"]["X-api-key"] == "test-asr-key"
    assert captured["headers"]["X-api-resource-id"] == "volc.bigasr.auc_turbo"
    assert captured["headers"]["X-api-request-id"] == "request-1"
    assert captured["headers"]["X-api-sequence"] == "-1"
    assert captured["headers"]["Content-type"] == "application/json"
    assert captured["body"]["user"]["uid"] == "family-1"
    assert captured["body"]["audio"]["data"]
    assert captured["body"]["request"]["model_name"] == "bigmodel"


def test_doubao_asr_rejects_non_success_status_without_leaking_api_key(monkeypatch):
    import json
    import pytest

    from productization.voice import (
        DoubaoTTSConfig,
        DoubaoVoiceProvider,
        SpeechRecognitionRequest,
    )

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps({"result": {"text": "should-not-use"}}).encode("utf-8")

        def getheader(self, name, default=None):
            return {
                "X-Api-Status-Code": "45001105",
                "X-Api-Message": "audio decode failed",
            }.get(name, default)

    def fake_opener(request, timeout):
        return FakeResponse()

    monkeypatch.setenv("DOUBAO_ASR_API_KEY", "test-asr-key")
    provider = DoubaoVoiceProvider(
        DoubaoTTSConfig(api_key="tts-key", default_voice_type="voice"),
        opener=fake_opener,
    )

    with pytest.raises(ValueError) as exc_info:
        provider.transcribe(
            SpeechRecognitionRequest(
                family_id="family-1",
                audio_bytes=b"fake-audio",
                audio_format="mp3",
            )
        )

    message = str(exc_info.value)
    assert "45001105" in message
    assert "test-asr-key" not in message


def test_doubao_asr_rejects_missing_status_without_leaking_api_key(monkeypatch):
    import json
    import pytest

    from productization.voice import (
        DoubaoTTSConfig,
        DoubaoVoiceProvider,
        SpeechRecognitionRequest,
    )

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps({"result": {"text": "should-not-use"}}).encode("utf-8")

        def getheader(self, name, default=None):
            return default

    def fake_opener(request, timeout):
        return FakeResponse()

    monkeypatch.setenv("DOUBAO_ASR_API_KEY", "test-asr-key")
    provider = DoubaoVoiceProvider(
        DoubaoTTSConfig(api_key="tts-key", default_voice_type="voice"),
        opener=fake_opener,
    )

    with pytest.raises(ValueError) as exc_info:
        provider.transcribe(
            SpeechRecognitionRequest(
                family_id="family-1",
                audio_bytes=b"fake-audio",
                audio_format="mp3",
            )
        )

    message = str(exc_info.value)
    assert "X-Api-Status-Code" in message
    assert "test-asr-key" not in message


def test_doubao_asr_wraps_url_error(monkeypatch):
    import pytest
    from urllib.error import URLError

    from productization.voice import (
        DoubaoTTSConfig,
        DoubaoVoiceProvider,
        SpeechRecognitionRequest,
    )

    def fake_opener(request, timeout):
        raise URLError("temporary failure")

    monkeypatch.setenv("DOUBAO_ASR_API_KEY", "test-asr-key")
    provider = DoubaoVoiceProvider(
        DoubaoTTSConfig(api_key="tts-key", default_voice_type="voice"),
        opener=fake_opener,
    )

    with pytest.raises(ValueError, match="Doubao ASR network error"):
        provider.transcribe(
            SpeechRecognitionRequest(
                family_id="family-1",
                audio_bytes=b"fake-audio",
                audio_format="mp3",
            )
        )


def test_doubao_asr_wraps_http_error_without_leaking_api_key(monkeypatch):
    import pytest
    from io import BytesIO
    from urllib.error import HTTPError

    from productization.voice import (
        DoubaoTTSConfig,
        DoubaoVoiceProvider,
        SpeechRecognitionRequest,
    )

    def fake_opener(request, timeout):
        raise HTTPError(
            request.full_url,
            400,
            "Bad Request",
            {},
            BytesIO(b'{"code":45001105,"message":"audio decode failed"}'),
        )

    monkeypatch.setenv("DOUBAO_ASR_API_KEY", "test-asr-key")
    provider = DoubaoVoiceProvider(
        DoubaoTTSConfig(api_key="tts-key", default_voice_type="voice"),
        opener=fake_opener,
    )

    with pytest.raises(ValueError) as exc_info:
        provider.transcribe(
            SpeechRecognitionRequest(
                family_id="family-1",
                audio_bytes=b"fake-audio",
                audio_format="mp3",
            )
        )

    message = str(exc_info.value)
    assert "45001105" in message
    assert "test-asr-key" not in message


def test_repository_records_voice_chat_exchange_with_metadata():
    from productization.cloud_repository import InMemoryCloudRepository

    repo = InMemoryCloudRepository()
    family = repo.create_family(name="宋家", user_id="owner")
    session = repo.record_voice_chat_exchange(
        family_id=family["id"],
        user_id="owner",
        elder_id="elder-1",
        persona_id="persona-1",
        voice_profile_id="voice-1",
        user_text="小雨，我今天有点想你",
        assistant_text="妈，我也想您。",
        audio_url="generated-audio/family/session/message.mp3",
        asr_provider="mock",
        tts_provider="mock",
        session_id="client-session-1",
    )

    messages = repo.list_chat_messages(family_id=family["id"], user_id="owner")

    assert session["id"] == "client-session-1"
    assert messages[-2]["role"] == "user"
    assert messages[-2]["persona_id"] == "persona-1"
    assert messages[-2]["asr_provider"] == "mock"
    assert messages[-1]["role"] == "assistant"
    assert messages[-1]["voice_profile_id"] == "voice-1"
    assert messages[-1]["audio_storage_path"].endswith(".mp3")


def test_elder_voice_chat_endpoint_runs_asr_chat_tts_and_records(monkeypatch):
    from fastapi.testclient import TestClient

    from api.main import app
    from productization.chat_service import ChatResult
    from productization.cloud_repository import InMemoryCloudRepository

    repo = InMemoryCloudRepository()
    family = repo.create_family(name="宋家", user_id="owner")
    persona = repo.create_persona(
        family_id=family["id"],
        user_id="owner",
        payload={"role_label": "女儿 小雨", "relation": "女儿", "appellation": "妈"},
    )
    voice = repo.create_voice_profile(
        family_id=family["id"],
        user_id="owner",
        payload={
            "display_name": "小雨音色",
            "provider": "mock",
            "provider_voice_id": "mock_voice_xiaoyu",
            "status": "ready",
            "consent_confirmed": True,
            "sample_source": "preset",
            "voice_type": "preset",
            "persona_id": persona["id"],
        },
    )
    repo.upsert_elder_current(family_id=family["id"], user_id="owner", payload={"full_name": "妈妈"})
    monkeypatch.setenv("VOICE_PROVIDER", "mock")
    monkeypatch.setattr("api.handlers.get_cloud_repository", lambda: repo)
    monkeypatch.setattr(
        "api.handlers.generate_chat_reply",
        lambda text, **kwargs: ChatResult(text="妈，我也想您。", debug={"context_source": "cloud"}),
    )

    client = TestClient(app)
    response = client.post(
        "/api/elder/voice-chat",
        data={
            "family_id": family["id"],
            "client_session_id": "11111111-1111-1111-1111-111111111111",
        },
        files={"audio_file": ("speech.webm", b"fake-audio", "audio/webm")},
        headers={"X-User-Id": "owner"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["recognized_text"] == "小雨，我今天有点想你"
    assert body["reply_text"] == "妈，我也想您。"
    assert body["audio_url"]
    assert body["matched_persona"]["persona_id"] == persona["id"]
    assert body["matched_persona"]["display_name"] == "女儿 小雨"
    messages = repo.list_chat_messages(family_id=family["id"], user_id="owner")
    assert len(messages) == 2
    assert messages[-2]["text"] == "小雨，我今天有点想你"
    assert messages[-1]["audio_storage_path"] == body["audio_url"]
    assert messages[-1]["voice_profile_id"] == voice["id"]


def test_elder_voice_chat_endpoint_uses_family_cognition_context(monkeypatch):
    from fastapi.testclient import TestClient

    from api.main import app
    import productization.chat_service as chat_service
    from productization.cloud_repository import InMemoryCloudRepository
    from productization.voice import SpeechRecognitionResult

    class VoiceProviderStub:
        provider_name = "stub"

        def transcribe(self, request):
            return SpeechRecognitionResult(
                provider=self.provider_name,
                text="小雨，小红最近忙吗？还记得春节红烧肉吗？",
                confidence=0.95,
            )

    repo = InMemoryCloudRepository()
    family = repo.create_family(name="宋家", user_id="owner")
    persona = repo.create_persona(
        family_id=family["id"],
        user_id="owner",
        payload={"role_label": "女儿 小雨", "relation": "女儿", "appellation": "妈"},
    )
    repo.upsert_elder_current(
        family_id=family["id"],
        user_id="owner",
        payload={"full_name": "宋桂兰", "gender": "女"},
    )
    repo.create_family_profile(
        family_id=family["id"],
        user_id="owner",
        payload={"name": "小雨", "gender": "女", "relation": "女儿"},
    )
    repo.create_family_profile(
        family_id=family["id"],
        user_id="owner",
        payload={
            "name": "小红",
            "gender": "女",
            "relation": "儿媳",
            "relations": [{"person": "小雨", "relation": "嫂子"}],
        },
    )
    repo.create_family_profile(
        family_id=family["id"],
        user_id="owner",
        payload={"name": "王强", "gender": "男", "relation": "儿子"},
    )
    repo.create_memory(
        family_id=family["id"],
        user_id="owner",
        payload={
            "content": "2025年春节，王强回家给宋桂兰做红烧肉。",
            "memory_type": "事件",
            "subject": "王强",
            "family_members": ["王强", "宋桂兰", "小雨", "小红"],
            "emotion_tags": ["开心"],
            "topic_tags": ["做饭", "红烧肉"],
        },
    )
    prompts: list[str] = []

    def fake_chat(system_prompt: str, user_prompt: str, temperature: float = 0.7):
        prompts.append(system_prompt)
        if "JSON" in system_prompt:
            return '{"intent":"怀念","emotion":"想念","confidence":0.9,"talk_to":"女儿 小雨","mentioned":["小红"]}'
        return "妈，我听说那年春节王强给您做过红烧肉，家里人都记得那份热闹。"

    monkeypatch.setattr("api.handlers.get_cloud_repository", lambda: repo)
    monkeypatch.setattr("api.handlers.get_voice_provider", lambda: VoiceProviderStub())
    monkeypatch.setattr(chat_service.llm_client, "chat", fake_chat)

    client = TestClient(app)
    response = client.post(
        "/api/elder/voice-chat",
        data={"family_id": family["id"]},
        files={"audio_file": ("speech.webm", b"fake-audio", "audio/webm")},
        headers={"X-User-Id": "owner"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["recognized_text"] == "小雨，小红最近忙吗？还记得春节红烧肉吗？"
    assert body["reply_text"].startswith("妈，我听说")
    assert body["matched_persona"]["persona_id"] == persona["id"]
    cognition_debug = body["debug"]["family_cognition"]
    assert cognition_debug["active_person"] == "小雨"
    assert cognition_debug["mentioned_people"] == ["小雨", "小红"]
    assert cognition_debug["memory_events"][0]["first_person_allowed"] is False

    combined_prompt = "\n".join(prompts)
    assert "## 家庭身份认知" in combined_prompt
    assert "当前角色：小雨，是宋桂兰的女儿" in combined_prompt
    assert "小红是宋桂兰的儿媳" in combined_prompt
    assert "小红是小雨的嫂子" in combined_prompt
    assert "## 对话连续状态" in combined_prompt
    assert "老人当前情绪：想念" in combined_prompt
    assert "## 结构化记忆事件" in combined_prompt
    assert "只能转述，不能说成自己亲身经历" in combined_prompt


def test_elder_voice_chat_keeps_conversation_state_across_two_requests(monkeypatch):
    from fastapi.testclient import TestClient

    from api.main import app
    import productization.chat_service as chat_service
    from productization.cloud_repository import InMemoryCloudRepository
    from productization.conversation_state_service import clear_conversation_state_cache
    from productization.voice import SpeechRecognitionResult

    class SequencedVoiceProvider:
        provider_name = "stub"

        def __init__(self):
            self.texts = ["王强最近工作忙不忙？", "他别太累了。"]

        def transcribe(self, request):
            return SpeechRecognitionResult(
                provider=self.provider_name,
                text=self.texts.pop(0),
                confidence=0.95,
            )

    clear_conversation_state_cache()
    repo = InMemoryCloudRepository()
    family = repo.create_family(name="宋家", user_id="owner")
    repo.create_persona(
        family_id=family["id"],
        user_id="owner",
        payload={"role_label": "儿子王强", "relation": "儿子", "appellation": "妈"},
    )
    repo.upsert_elder_current(
        family_id=family["id"],
        user_id="owner",
        payload={"full_name": "宋桂兰", "gender": "女"},
    )
    repo.create_family_profile(
        family_id=family["id"],
        user_id="owner",
        payload={"name": "王强", "gender": "男", "relation": "儿子"},
    )
    provider = SequencedVoiceProvider()
    prompts: list[str] = []

    def fake_chat(system_prompt: str, user_prompt: str, temperature: float = 0.7):
        prompts.append(system_prompt)
        if "JSON" in system_prompt:
            if "他别太累了" in user_prompt:
                return '{"intent":"担忧焦虑","emotion":"担心","confidence":0.9,"talk_to":"陪伴者","mentioned":[]}'
            return '{"intent":"确认事实","emotion":"平静","confidence":0.9,"talk_to":"陪伴者","mentioned":["王强"]}'
        if "他别太累了" in user_prompt:
            return "妈，我会注意别太累，您放心。"
        return "妈，最近工作是有点忙。"

    monkeypatch.setattr("api.handlers.get_cloud_repository", lambda: repo)
    monkeypatch.setattr("api.handlers.get_voice_provider", lambda: provider)
    monkeypatch.setattr(chat_service.llm_client, "chat", fake_chat)

    client = TestClient(app)
    first = client.post(
        "/api/elder/voice-chat",
        data={"family_id": family["id"], "client_session_id": "session-voice-state"},
        files={"audio_file": ("speech.webm", b"fake-audio", "audio/webm")},
        headers={"X-User-Id": "owner"},
    )
    second = client.post(
        "/api/elder/voice-chat",
        data={"family_id": family["id"], "client_session_id": "session-voice-state"},
        files={"audio_file": ("speech.webm", b"fake-audio", "audio/webm")},
        headers={"X-User-Id": "owner"},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["reply_text"].startswith("妈，我会注意")
    second_debug = second.json()["debug"]["family_cognition"]
    assert second_debug["recent_person_ids"] == ["王强"]
    assert second_debug["state_summary"]
    assert "王强" in prompts[-1]
