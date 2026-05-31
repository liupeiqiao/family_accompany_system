# Elder Voice Chat Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first老人端“电话式语音陪伴”闭环: click-to-record, Doubao ASR, session-scoped persona selection, chat reply, TTS playback, persistent AI reply audio replay.

**Architecture:** Add a backend voice-chat orchestration path that accepts multipart audio, transcribes with a provider abstraction, locks the current persona per chat session, reuses the existing chat engine, synthesizes TTS, stores the AI reply audio path, and returns a compact response for the elder UI. The frontend elder page becomes a phone-style state machine with interruptible playback and recent conversation replay.

**Tech Stack:** FastAPI, Pydantic, Python provider classes, existing `CloudRepository`, Next.js App Router, browser `MediaRecorder`, pytest, TypeScript.

**Project constraints:** Do not commit automatically. Use Chinese for user-facing copy and docs. Do not write real API keys into code, tests, logs, or docs.

---

## File Structure

- Modify `productization/voice.py`: add ASR request/result/provider methods and a Doubao ASR implementation behind environment variables.
- Modify `productization/chat_service.py`: expose a helper for LLM persona selection if not already reusable.
- Modify `productization/cloud_repository.py`: extend chat session/message recording for reusable sessions, persona/voice metadata, and AI audio path.
- Modify `productization/postgres_schema.sql`: add minimal nullable columns for voice chat metadata.
- Modify `productization/postgres_repository.py`: persist and list the new chat metadata.
- Modify `api/schemas.py`: add response models for elder voice chat and chat history metadata if needed.
- Modify `api/handlers.py`: add `handle_elder_voice_chat()` orchestration.
- Modify `api/main.py`: add `POST /api/elder/voice-chat` using `UploadFile` and `Form`.
- Modify `web/src/lib/backend-api.ts`: add multipart voice chat client and typed response.
- Replace `web/src/app/elder/page.tsx`: implement phone-style UI state machine.
- Modify `web/src/app/globals.css`: add elder phone UI styles.
- Add/modify tests:
  - `tests/test_elder_voice_chat_api.py`
  - `tests/test_cloud_chat_phase2.py`
  - `tests/test_voice_phase4_tts.py`
  - frontend tests if the existing setup supports them; otherwise use TypeScript build.

---

### Task 1: Backend ASR Provider Abstraction

**Files:**
- Modify: `productization/voice.py`
- Test: `tests/test_elder_voice_chat_api.py`

- [ ] **Step 1: Write failing tests for mock ASR and empty text handling**

Add `tests/test_elder_voice_chat_api.py` with this initial content:

```python
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
    assert result.text
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
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```bash
python -m pytest tests/test_elder_voice_chat_api.py::test_mock_asr_transcribes_non_empty_audio tests/test_elder_voice_chat_api.py::test_mock_asr_rejects_empty_audio -v
```

Expected: fail because `SpeechRecognitionRequest` and `transcribe()` do not exist.

- [ ] **Step 3: Add ASR dataclasses and protocol method**

In `productization/voice.py`, add:

```python
@dataclass(frozen=True)
class SpeechRecognitionRequest:
    family_id: str
    audio_bytes: bytes
    audio_format: str = "webm"


@dataclass(frozen=True)
class SpeechRecognitionResult:
    provider: str
    text: str
    confidence: float = 1.0
```

Extend `VoiceProvider`:

```python
    def transcribe(self, request: SpeechRecognitionRequest) -> SpeechRecognitionResult:
        ...
```

- [ ] **Step 4: Implement mock ASR**

In `MockVoiceProvider`, add:

```python
    def transcribe(self, request: SpeechRecognitionRequest) -> SpeechRecognitionResult:
        if not request.audio_bytes:
            raise ValueError("ASR audio cannot be empty.")
        return SpeechRecognitionResult(
            provider=self.provider_name,
            text="小雨，我今天有点想你",
            confidence=0.95,
        )
```

- [ ] **Step 5: Add Doubao ASR config and provider method**

Add `DoubaoASRConfig` and make `DoubaoVoiceProvider.transcribe()` call it. Use environment variables only:

```python
@dataclass(frozen=True)
class DoubaoASRConfig:
    api_key: str
    endpoint: str = "https://openspeech.bytedance.com/api/v3/auc/bigmodel/recognize/flash"
    resource_id: str = "volc.bigasr.auc_turbo"

    @classmethod
    def from_env(cls) -> "DoubaoASRConfig | None":
        api_key = os.getenv("DOUBAO_ASR_API_KEY") or os.getenv("DOUBAO_TTS_API_KEY")
        if not api_key:
            return None
        return cls(
            api_key=api_key,
            endpoint=os.getenv(
                "DOUBAO_ASR_ENDPOINT",
                "https://openspeech.bytedance.com/api/v3/auc/bigmodel/recognize/flash",
            ).rstrip(),
            resource_id=os.getenv("DOUBAO_ASR_RESOURCE_ID", "volc.bigasr.auc_turbo"),
        )
```

Implement the Volcengine/Doubao recording-file flash recognition request. The HTTP request is JSON, not raw audio bytes: `audio.data` contains base64-encoded recording bytes, `request.model_name` is `bigmodel`, and headers include `X-Api-Key`, `X-Api-Resource-Id=volc.bigasr.auc_turbo`, `X-Api-Request-Id`, and `X-Api-Sequence=-1`.

```python
    def transcribe(self, request: SpeechRecognitionRequest) -> SpeechRecognitionResult:
        if not request.audio_bytes:
            raise ValueError("ASR audio cannot be empty.")
        config = DoubaoASRConfig.from_env()
        if config is None:
            raise ValueError("DOUBAO_ASR_API_KEY is required for Doubao ASR.")
        payload = {
            "user": {
                "uid": config.api_key,
            },
            "audio": {
                "data": base64.b64encode(request.audio_bytes).decode("ascii"),
            },
            "request": {
                "model_name": "bigmodel",
            },
        }
        http_request = urlrequest.Request(
            config.endpoint,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            method="POST",
            headers={
                "X-Api-Key": config.api_key,
                "X-Api-Resource-Id": config.resource_id,
                "X-Api-Request-Id": self._reqid_factory(),
                "X-Api-Sequence": "-1",
                "Content-Type": "application/json",
            },
        )
        with self._opener(http_request, timeout=30) as response:
            status_code = response.getheader("X-Api-Status-Code", "")
            status_message = response.getheader("X-Api-Message", "")
            payload = json.loads(response.read().decode("utf-8"))
        if status_code and status_code != "20000000":
            raise ValueError(f"Doubao ASR failed: {status_code} {status_message}".strip())
        text = _extract_asr_text(payload)
        if not text:
            raise ValueError("Doubao ASR returned empty text.")
        return SpeechRecognitionResult(
            provider=self.provider_name,
            text=text,
            confidence=float(payload.get("confidence", 1.0) or 1.0),
        )
```

Add helper:

```python
def _extract_asr_text(payload: dict) -> str:
    for key in ("text", "result", "transcript"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    result = payload.get("result")
    if isinstance(result, dict):
        for key in ("text", "transcript"):
            value = result.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""
```

- [ ] **Step 6: Run tests**

Run:

```bash
python -m pytest tests/test_elder_voice_chat_api.py::test_mock_asr_transcribes_non_empty_audio tests/test_elder_voice_chat_api.py::test_mock_asr_rejects_empty_audio -v
```

Expected: pass.

---

### Task 2: Chat Session Metadata and Reusable Recording

**Files:**
- Modify: `productization/cloud_repository.py`
- Modify: `productization/postgres_repository.py`
- Modify: `productization/postgres_schema.sql`
- Test: `tests/test_elder_voice_chat_api.py`

- [ ] **Step 1: Write failing repository test**

Append:

```python
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
```

- [ ] **Step 2: Run test and confirm failure**

Run:

```bash
python -m pytest tests/test_elder_voice_chat_api.py::test_repository_records_voice_chat_exchange_with_metadata -v
```

Expected: fail because `record_voice_chat_exchange()` does not exist.

- [ ] **Step 3: Extend protocol**

In `CloudRepository`, add:

```python
    def record_voice_chat_exchange(
        self,
        *,
        family_id: str,
        user_id: str,
        elder_id: str,
        persona_id: str,
        voice_profile_id: str,
        user_text: str,
        assistant_text: str,
        audio_url: str,
        asr_provider: str,
        tts_provider: str,
        session_id: str,
    ) -> dict:
        ...
```

- [ ] **Step 4: Implement in-memory recording**

Add method to `InMemoryCloudRepository`:

```python
    def record_voice_chat_exchange(
        self,
        *,
        family_id: str,
        user_id: str,
        elder_id: str,
        persona_id: str,
        voice_profile_id: str,
        user_text: str,
        assistant_text: str,
        audio_url: str,
        asr_provider: str,
        tts_provider: str,
        session_id: str,
    ) -> dict:
        self._require_member(family_id, user_id)
        actual_session_id = session_id or uuid4().hex
        session = self._chat_sessions.get(actual_session_id)
        if session is None:
            session = {
                "id": actual_session_id,
                "family_id": family_id,
                "elder_id": elder_id or "",
                "persona_id": persona_id or "",
                "voice_profile_id": voice_profile_id or "",
                "created_by": user_id,
                "created_at": str(len(self._chat_sessions)).zfill(8),
            }
            self._chat_sessions[actual_session_id] = session
        self._append_chat_message(
            session_id=actual_session_id,
            role="user",
            text=user_text,
            audio_storage_path="",
            tts_provider="",
            persona_id=persona_id,
            voice_profile_id=voice_profile_id,
            asr_provider=asr_provider,
        )
        self._append_chat_message(
            session_id=actual_session_id,
            role="assistant",
            text=assistant_text,
            audio_storage_path=audio_url or "",
            tts_provider=tts_provider or "",
            persona_id=persona_id,
            voice_profile_id=voice_profile_id,
            asr_provider="",
        )
        return dict(session)
```

Update `_append_chat_message()` signature and message dict:

```python
        persona_id: str = "",
        voice_profile_id: str = "",
        asr_provider: str = "",
```

and fields:

```python
            "persona_id": persona_id or "",
            "voice_profile_id": voice_profile_id or "",
            "asr_provider": asr_provider or "",
```

- [ ] **Step 5: Add Postgres schema columns**

In `productization/postgres_schema.sql`, add nullable columns:

```sql
ALTER TABLE chat_sessions
    ADD COLUMN IF NOT EXISTS persona_id UUID,
    ADD COLUMN IF NOT EXISTS voice_profile_id UUID,
    ADD COLUMN IF NOT EXISTS created_by VARCHAR(128);

ALTER TABLE chat_messages
    ADD COLUMN IF NOT EXISTS persona_id UUID,
    ADD COLUMN IF NOT EXISTS voice_profile_id UUID,
    ADD COLUMN IF NOT EXISTS asr_provider TEXT DEFAULT '';
```

- [ ] **Step 6: Implement Postgres method**

Add to `PostgresCloudRepository`:

```python
    def record_voice_chat_exchange(
        self,
        *,
        family_id: str,
        user_id: str,
        elder_id: str,
        persona_id: str,
        voice_profile_id: str,
        user_text: str,
        assistant_text: str,
        audio_url: str,
        asr_provider: str,
        tts_provider: str,
        session_id: str,
    ) -> dict:
        self._require_member(family_id, user_id)
        existing = None
        if session_id:
            existing = self._fetch_one(
                "SELECT * FROM chat_sessions WHERE id = %s AND family_id = %s",
                (_optional_uuid(session_id), family_id),
                required=False,
            )
        if existing:
            session = existing
        else:
            session = self._fetch_one(
                """
                INSERT INTO chat_sessions (id, family_id, elder_id, persona_id, voice_profile_id, created_by)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (
                    _optional_uuid(session_id) or str(uuid4()),
                    family_id,
                    _optional_uuid(elder_id),
                    _optional_uuid(persona_id),
                    _optional_uuid(voice_profile_id),
                    user_id,
                ),
            )
        self._execute(
            """
            INSERT INTO chat_messages
                (session_id, role, text, audio_storage_path, tts_provider, persona_id, voice_profile_id, asr_provider)
            VALUES
                (%s, %s, %s, %s, %s, %s, %s, %s),
                (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                session["id"], "user", user_text, "", "", _optional_uuid(persona_id), _optional_uuid(voice_profile_id), asr_provider or "",
                session["id"], "assistant", assistant_text, audio_url or "", tts_provider or "", _optional_uuid(persona_id), _optional_uuid(voice_profile_id), "",
            ),
        )
        return session
```

- [ ] **Step 7: Run repository test**

Run:

```bash
python -m pytest tests/test_elder_voice_chat_api.py::test_repository_records_voice_chat_exchange_with_metadata -v
```

Expected: pass.

---

### Task 3: Voice Chat Orchestration Endpoint

**Files:**
- Modify: `api/schemas.py`
- Modify: `api/handlers.py`
- Modify: `api/main.py`
- Test: `tests/test_elder_voice_chat_api.py`

- [ ] **Step 1: Write failing API test for multipart voice chat**

Append:

```python
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
        data={"family_id": family["id"], "client_session_id": "11111111-1111-1111-1111-111111111111"},
        files={"audio_file": ("speech.webm", b"fake-audio", "audio/webm")},
        headers={"X-User-Id": "owner"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["recognized_text"] == "小雨，我今天有点想你"
    assert body["reply_text"] == "妈，我也想您。"
    assert body["audio_url"]
    assert body["matched_persona"]["persona_id"] == persona["id"]
    messages = repo.list_chat_messages(family_id=family["id"], user_id="owner")
    assert messages[-1]["audio_storage_path"] == body["audio_url"]
```

- [ ] **Step 2: Run test and confirm failure**

Run:

```bash
python -m pytest tests/test_elder_voice_chat_api.py::test_elder_voice_chat_endpoint_runs_asr_chat_tts_and_records -v
```

Expected: fail because `/api/elder/voice-chat` is missing.

- [ ] **Step 3: Add schema response models**

In `api/schemas.py`, add:

```python
class MatchedPersonaResponse(BaseModel):
    persona_id: str = ""
    display_name: str = ""
    confidence: float = 0


class ElderVoiceChatResponse(BaseModel):
    recognized_text: str = ""
    reply_text: str = ""
    audio_url: str | None = None
    session_id: str = ""
    message_id: str = ""
    matched_persona: MatchedPersonaResponse = Field(default_factory=MatchedPersonaResponse)
    status: str = "ok"
    debug: dict = Field(default_factory=dict)
```

- [ ] **Step 4: Add persona selection helpers**

In `api/handlers.py`, add helpers:

```python
def _select_voice_chat_persona(*, family_id: str, user_id: str, recognized_text: str, session_persona_id: str = "") -> dict:
    personas = get_cloud_repository().list_personas(family_id=family_id, user_id=user_id)
    if session_persona_id:
        for persona in personas:
            if persona.get("id") == session_persona_id:
                return {"persona": persona, "confidence": 1.0}
    for persona in personas:
        label = str(persona.get("role_label") or "")
        if label and any(part and part in recognized_text for part in label.split()):
            return {"persona": persona, "confidence": 0.9}
    return {"persona": personas[0] if personas else {}, "confidence": 0.5 if personas else 0}
```

This helper is deliberately deterministic for the first implementation and tests. A later task may replace the internals with an LLM call while preserving the function contract.

- [ ] **Step 5: Add voice profile selection helper**

In `api/handlers.py`, add:

```python
def _select_voice_profile_for_persona(*, family_id: str, user_id: str, persona_id: str, requested_voice_profile_id: str = "") -> str:
    profiles = get_cloud_repository().list_voice_profiles(family_id=family_id, user_id=user_id)
    if requested_voice_profile_id:
        for profile in profiles:
            if profile.get("id") == requested_voice_profile_id and profile.get("status") == "ready":
                return str(profile["id"])
    for profile in profiles:
        if str(profile.get("persona_id") or "") == persona_id and profile.get("status") == "ready":
            return str(profile["id"])
    for profile in profiles:
        if profile.get("status") == "ready":
            return str(profile["id"])
    return ""
```

- [ ] **Step 6: Implement handler**

In `api/handlers.py`, import `ElderVoiceChatResponse`, `MatchedPersonaResponse`, and `SpeechRecognitionRequest`. Add:

```python
def handle_elder_voice_chat(
    *,
    family_id: str,
    user_id: str,
    audio_bytes: bytes,
    audio_format: str,
    elder_id: str = "",
    persona_id: str = "",
    voice_profile_id: str = "",
    client_session_id: str = "",
) -> ElderVoiceChatResponse:
    provider = get_voice_provider()
    try:
        asr = provider.transcribe(
            SpeechRecognitionRequest(
                family_id=family_id,
                audio_bytes=audio_bytes,
                audio_format=audio_format,
            )
        )
    except ValueError:
        return ElderVoiceChatResponse(
            status="asr_empty",
            reply_text="刚才没听清，可以再说一遍吗？",
            debug={"asr_provider": getattr(provider, "provider_name", "")},
        )
    selected = _select_voice_chat_persona(
        family_id=family_id,
        user_id=user_id,
        recognized_text=asr.text,
        session_persona_id=persona_id,
    )
    selected_persona = selected["persona"]
    selected_persona_id = str(selected_persona.get("id") or "")
    selected_voice_profile_id = _select_voice_profile_for_persona(
        family_id=family_id,
        user_id=user_id,
        persona_id=selected_persona_id,
        requested_voice_profile_id=voice_profile_id,
    )
    chat = handle_chat(
        ChatRequest(
            family_id=family_id,
            elder_id=elder_id,
            persona_id=selected_persona_id,
            text=asr.text,
            voice_profile_id=selected_voice_profile_id or None,
        ),
        user_id,
    )
    session = get_cloud_repository().record_voice_chat_exchange(
        family_id=family_id,
        user_id=user_id,
        elder_id=elder_id,
        persona_id=selected_persona_id,
        voice_profile_id=selected_voice_profile_id,
        user_text=asr.text,
        assistant_text=chat.text,
        audio_url=chat.audio_url or "",
        asr_provider=asr.provider,
        tts_provider=str(chat.debug.get("tts_provider", "")),
        session_id=client_session_id,
    )
    return ElderVoiceChatResponse(
        recognized_text=asr.text,
        reply_text=chat.text,
        audio_url=chat.audio_url,
        session_id=str(session.get("id") or ""),
        matched_persona=MatchedPersonaResponse(
            persona_id=selected_persona_id,
            display_name=str(selected_persona.get("role_label") or ""),
            confidence=float(selected.get("confidence", 0)),
        ),
        status="ok",
        debug=chat.debug | {"asr_provider": asr.provider},
    )
```

- [ ] **Step 7: Add FastAPI endpoint**

In `api/main.py`, import:

```python
from fastapi import Depends, FastAPI, File, Form, Query, UploadFile
```

Import `handle_elder_voice_chat` and `ElderVoiceChatResponse`.

Add endpoint:

```python
@app.post("/api/elder/voice-chat", response_model=ElderVoiceChatResponse)
async def elder_voice_chat_endpoint(
    family_id: str = Form(...),
    elder_id: str = Form(default=""),
    persona_id: str = Form(default=""),
    voice_profile_id: str = Form(default=""),
    client_session_id: str = Form(default=""),
    audio_format: str = Form(default="webm"),
    audio_file: UploadFile = File(...),
    x_user_id: str = Depends(current_user_id),
) -> ElderVoiceChatResponse:
    audio_bytes = await audio_file.read()
    return handle_elder_voice_chat(
        family_id=family_id,
        user_id=x_user_id,
        elder_id=elder_id,
        persona_id=persona_id,
        voice_profile_id=voice_profile_id,
        client_session_id=client_session_id,
        audio_bytes=audio_bytes,
        audio_format=audio_format,
    )
```

- [ ] **Step 8: Run API test**

Run:

```bash
python -m pytest tests/test_elder_voice_chat_api.py::test_elder_voice_chat_endpoint_runs_asr_chat_tts_and_records -v
```

Expected: pass.

---

### Task 4: Elder Frontend Phone UI and Interruptible Playback

**Files:**
- Modify: `web/src/lib/backend-api.ts`
- Replace: `web/src/app/elder/page.tsx`
- Modify: `web/src/app/globals.css`

- [ ] **Step 1: Add frontend API type and function**

In `web/src/lib/backend-api.ts`, add:

```typescript
export type ElderVoiceChatResponse = {
  recognized_text: string;
  reply_text: string;
  audio_url?: string | null;
  session_id: string;
  message_id?: string;
  matched_persona: {
    persona_id: string;
    display_name: string;
    confidence: number;
  };
  status: "ok" | "asr_empty" | string;
  debug: Record<string, unknown>;
};

export async function sendElderVoiceChat(payload: {
  family_id: string;
  elder_id?: string;
  persona_id?: string;
  voice_profile_id?: string;
  client_session_id?: string;
  audio_format: string;
  audio_file: Blob;
}): Promise<ElderVoiceChatResponse> {
  const formData = new FormData();
  formData.set("family_id", payload.family_id);
  formData.set("elder_id", payload.elder_id ?? "");
  formData.set("persona_id", payload.persona_id ?? "");
  formData.set("voice_profile_id", payload.voice_profile_id ?? "");
  formData.set("client_session_id", payload.client_session_id ?? "");
  formData.set("audio_format", payload.audio_format);
  formData.set("audio_file", payload.audio_file, `elder-speech.${payload.audio_format}`);

  const response = await fetch(`${API_BASE_URL}/api/elder/voice-chat`, {
    method: "POST",
    headers: {
      ...(getAuthToken() ? { "X-User-Token": getAuthToken() as string } : {}),
    },
    body: formData,
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json() as Promise<ElderVoiceChatResponse>;
}
```

- [ ] **Step 2: Replace elder page with state machine**

Replace `web/src/app/elder/page.tsx` with a client component that uses:

```typescript
type CallState =
  | "idle"
  | "recording"
  | "recorded"
  | "understanding"
  | "replying"
  | "playing"
  | "error";
```

Core functions:

```typescript
async function startRecording() {
  stopPlayback();
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  const recorder = new MediaRecorder(stream);
  const chunks: BlobPart[] = [];
  recorder.ondataavailable = (event) => {
    if (event.data.size > 0) chunks.push(event.data);
  };
  recorder.onstop = () => {
    stream.getTracks().forEach((track) => track.stop());
    setRecordedBlob(new Blob(chunks, { type: recorder.mimeType || "audio/webm" }));
    setAudioFormat((recorder.mimeType || "audio/webm").includes("webm") ? "webm" : "mp3");
    setCallState("recorded");
  };
  mediaRecorderRef.current = recorder;
  recorder.start();
  setCallState("recording");
}

function stopRecording() {
  mediaRecorderRef.current?.stop();
}

function stopPlayback() {
  audioRef.current?.pause();
  if (audioRef.current) audioRef.current.currentTime = 0;
}
```

Main button behavior:

```typescript
async function handlePrimaryAction() {
  if (callState === "playing") {
    stopPlayback();
    await startRecording();
    return;
  }
  if (callState === "idle" || callState === "error") {
    await startRecording();
    return;
  }
  if (callState === "recording") {
    stopRecording();
    return;
  }
  if (callState === "recorded") {
    await sendRecordedAudio();
  }
}
```

Send function:

```typescript
async function sendRecordedAudio() {
  if (!recordedBlob) return;
  setCallState("understanding");
  const response = await sendElderVoiceChat({
    family_id: familyContext?.family.id ?? "local",
    client_session_id: clientSessionId,
    persona_id: currentPersonaId,
    audio_format: audioFormat,
    audio_file: recordedBlob,
  });
  setCurrentPersonaId(response.matched_persona.persona_id);
  setCurrentPersonaName(response.matched_persona.display_name || "家人");
  const nextMessage = {
    id: Date.now(),
    userText: response.recognized_text,
    assistantText: response.reply_text,
    audioUrl: response.audio_url ?? "",
  };
  setRecentTurns((turns) => [nextMessage, ...turns].slice(0, 3));
  setRecordedBlob(null);
  if (response.audio_url) {
    playAudio(response.audio_url);
  } else {
    setCallState("idle");
  }
}
```

- [ ] **Step 3: Add interruptible playback**

Use an `audioRef`:

```typescript
function playAudio(url: string) {
  stopPlayback();
  const audio = new Audio(url);
  audioRef.current = audio;
  audio.onended = () => setCallState("idle");
  audio.onerror = () => setCallState("idle");
  setCallState("playing");
  void audio.play();
}
```

Ensure the primary button calls `stopPlayback()` and `startRecording()` when state is `playing`.

- [ ] **Step 4: Add CSS**

In `web/src/app/globals.css`, add:

```css
.elderPhone {
  align-items: center;
  display: grid;
  gap: 24px;
  margin: 0 auto;
  max-width: 680px;
  min-height: calc(100vh - 64px);
  text-align: center;
}

.callTarget {
  display: grid;
  gap: 8px;
}

.callTarget h1 {
  font-size: 28px;
  margin: 0;
}

.callStatus {
  color: #6f6256;
  font-size: 20px;
  margin: 0;
}

.callButton {
  align-items: center;
  aspect-ratio: 1;
  border-radius: 999px;
  display: inline-flex;
  font-size: 24px;
  font-weight: 700;
  justify-content: center;
  justify-self: center;
  max-width: 260px;
  min-height: 0;
  padding: 24px;
  width: min(62vw, 260px);
}

.callButton.recording {
  background: #9b241f;
  border-color: #9b241f;
}

.callButton.playing {
  background: #23613a;
  border-color: #23613a;
}

.callActions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  justify-content: center;
}

.recentTurns {
  display: grid;
  gap: 12px;
  text-align: left;
  width: 100%;
}

.recentTurn {
  background: #fffaf3;
  border: 1px solid #e3d6c5;
  border-radius: 8px;
  padding: 14px;
}
```

- [ ] **Step 5: Run frontend checks**

Run:

```bash
cd web
npm run lint
npm run build
```

Expected: both pass. If `npm run lint` is undefined, record that and run `npm run build`.

---

### Task 5: Verification and Regression Pass

**Files:**
- No planned edits unless tests reveal issues.

- [ ] **Step 1: Run targeted backend tests**

Run:

```bash
python -m pytest tests/test_elder_voice_chat_api.py tests/test_voice_phase4_tts.py tests/test_cloud_chat_phase2.py -v
```

Expected: pass.

- [ ] **Step 2: Run broader backend tests**

Run:

```bash
python -m pytest tests/ -v
```

Expected: pass, or report pre-existing failures with exact test names and failure reason.

- [ ] **Step 3: Run frontend build**

Run:

```bash
cd web
npm run build
```

Expected: pass.

- [ ] **Step 4: Manual browser smoke test**

Start services:

```powershell
$env:DEEPSEEK_API_KEY="test-or-real-env-value"
python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

In another terminal:

```powershell
cd web
$env:NEXT_PUBLIC_COMPANION_API_URL="http://127.0.0.1:8000"
npm run dev -- --hostname 127.0.0.1 --port 3000
```

Open `http://127.0.0.1:3000/elder`. Verify:

- The page shows the phone-style interface.
- Clicking the main button asks for microphone permission.
- Clicking again stops recording and sends audio.
- During playback, clicking the main button stops audio and starts recording.
- Recent 2 to 3 turns show text and replay buttons.

---

## Self-Review

- Spec coverage: The plan covers backend ASR, multipart upload, session role locking, chat/TTS orchestration, AI reply audio persistence path, frontend phone UI, interruptible playback, and replay UI.
- Placeholders: No implementation step relies on an unspecified placeholder; provider details use environment variables and deterministic tests.
- Type consistency: `ElderVoiceChatResponse`, `MatchedPersonaResponse`, `SpeechRecognitionRequest`, `SpeechRecognitionResult`, and `record_voice_chat_exchange()` are introduced before use.
- Scope note: True LLM persona selection internals are represented by a stable helper seam. The first implementation can use deterministic matching for tests and later swap internals to LLM without changing endpoint or UI contracts.
