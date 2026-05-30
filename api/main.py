from __future__ import annotations

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from .handlers import (
    handle_chat,
    handle_create_cloud_family_profile,
    handle_create_cloud_memory,
    handle_create_cloud_persona,
    handle_create_family,
    handle_create_voice_upload_intent,
    handle_delete_cloud_family_profile,
    handle_delete_cloud_memory,
    handle_delete_elder,
    handle_delete_family_profile,
    handle_delete_memory,
    handle_delete_persona,
    handle_get_voice_status,
    handle_get_cloud_elder_current,
    handle_get_current_family,
    handle_hide_voice_profile,
    handle_import,
    handle_clone_voice,
    handle_list_cloud_family_profiles,
    handle_list_cloud_memories,
    handle_list_cloud_personas,
    handle_list_voice_profiles,
    handle_list_voice_samples,
    handle_parse,
    handle_records,
    handle_tts,
    handle_upgrade_voice,
    handle_update_cloud_family_profile,
    handle_update_cloud_memory,
    handle_update_cloud_persona,
    handle_upsert_cloud_elder_current,
)
from .schemas import (
    ChatRequest,
    ChatResponse,
    DeleteResponse,
    FamilyCreateRequest,
    FamilyCurrentResponse,
    ImportRequest,
    ImportResponse,
    ParseRequest,
    ParseResponse,
    RecordsResponse,
    TextToSpeechCreateRequest,
    TextToSpeechCreateResponse,
    VoiceCloneCreateRequest,
    VoiceManagementRequest,
    VoiceUploadIntentRequest,
)

app = FastAPI(title="亲情陪伴系统 API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/docs")


@app.get("/api/family/current", response_model=FamilyCurrentResponse)
def current_family_endpoint(
    x_user_id: str = Header(default="demo-user", alias="X-User-Id"),
) -> FamilyCurrentResponse:
    return handle_get_current_family(x_user_id)


@app.post("/api/family", response_model=FamilyCurrentResponse)
def create_family_endpoint(
    request: FamilyCreateRequest,
    x_user_id: str = Header(default="demo-user", alias="X-User-Id"),
) -> FamilyCurrentResponse:
    return handle_create_family(request, x_user_id)


@app.get("/api/elders/current", response_model=dict)
def cloud_elder_current_endpoint(
    family_id: str = Query(...),
    x_user_id: str = Header(default="demo-user", alias="X-User-Id"),
) -> dict:
    return handle_get_cloud_elder_current(family_id, x_user_id)


@app.put("/api/elders/current", response_model=dict)
def update_cloud_elder_current_endpoint(
    payload: dict,
    x_user_id: str = Header(default="demo-user", alias="X-User-Id"),
) -> dict:
    return handle_upsert_cloud_elder_current(payload, x_user_id)


@app.get("/api/family-profiles", response_model=list[dict])
def cloud_family_profiles_endpoint(
    family_id: str = Query(...),
    x_user_id: str = Header(default="demo-user", alias="X-User-Id"),
) -> list[dict]:
    return handle_list_cloud_family_profiles(family_id, x_user_id)


@app.post("/api/family-profiles", response_model=dict)
def create_cloud_family_profile_endpoint(
    payload: dict,
    x_user_id: str = Header(default="demo-user", alias="X-User-Id"),
) -> dict:
    return handle_create_cloud_family_profile(payload, x_user_id)


@app.put("/api/family-profiles/{profile_id}", response_model=dict)
def update_cloud_family_profile_endpoint(
    profile_id: str,
    payload: dict,
    x_user_id: str = Header(default="demo-user", alias="X-User-Id"),
) -> dict:
    return handle_update_cloud_family_profile(profile_id, payload, x_user_id)


@app.get("/api/memories", response_model=list[dict])
def cloud_memories_endpoint(
    family_id: str = Query(...),
    x_user_id: str = Header(default="demo-user", alias="X-User-Id"),
) -> list[dict]:
    return handle_list_cloud_memories(family_id, x_user_id)


@app.post("/api/memories", response_model=dict)
def create_cloud_memory_endpoint(
    payload: dict,
    x_user_id: str = Header(default="demo-user", alias="X-User-Id"),
) -> dict:
    return handle_create_cloud_memory(payload, x_user_id)


@app.put("/api/memories/{memory_id}", response_model=dict)
def update_cloud_memory_endpoint(
    memory_id: str,
    payload: dict,
    x_user_id: str = Header(default="demo-user", alias="X-User-Id"),
) -> dict:
    return handle_update_cloud_memory(memory_id, payload, x_user_id)


@app.get("/api/personas", response_model=list[dict])
def cloud_personas_endpoint(
    family_id: str = Query(...),
    x_user_id: str = Header(default="demo-user", alias="X-User-Id"),
) -> list[dict]:
    return handle_list_cloud_personas(family_id, x_user_id)


@app.post("/api/personas", response_model=dict)
def create_cloud_persona_endpoint(
    payload: dict,
    x_user_id: str = Header(default="demo-user", alias="X-User-Id"),
) -> dict:
    return handle_create_cloud_persona(payload, x_user_id)


@app.put("/api/personas/{persona_id}", response_model=dict)
def update_cloud_persona_endpoint(
    persona_id: str,
    payload: dict,
    x_user_id: str = Header(default="demo-user", alias="X-User-Id"),
) -> dict:
    return handle_update_cloud_persona(persona_id, payload, x_user_id)


@app.post("/api/voices/upload-intent", response_model=dict)
def create_voice_upload_intent_endpoint(
    request: VoiceUploadIntentRequest,
    x_user_id: str = Header(default="demo-user", alias="X-User-Id"),
) -> dict:
    return handle_create_voice_upload_intent(request, x_user_id)


@app.get("/api/voices/samples", response_model=list[dict])
def voice_samples_endpoint(
    family_id: str = Query(...),
    x_user_id: str = Header(default="demo-user", alias="X-User-Id"),
) -> list[dict]:
    return handle_list_voice_samples(family_id, x_user_id)


@app.get("/api/voices/profiles", response_model=list[dict])
def voice_profiles_endpoint(
    family_id: str = Query(...),
    x_user_id: str = Header(default="demo-user", alias="X-User-Id"),
) -> list[dict]:
    return handle_list_voice_profiles(family_id, x_user_id)


@app.post("/api/voices/clone", response_model=dict)
def clone_voice_endpoint(
    request: VoiceCloneCreateRequest,
    x_user_id: str = Header(default="demo-user", alias="X-User-Id"),
) -> dict:
    return handle_clone_voice(request, x_user_id)


@app.post("/api/voices/status", response_model=dict)
def voice_status_endpoint(
    request: VoiceManagementRequest,
    x_user_id: str = Header(default="demo-user", alias="X-User-Id"),
) -> dict:
    return handle_get_voice_status(request, x_user_id)


@app.post("/api/voices/upgrade", response_model=dict)
def upgrade_voice_endpoint(
    request: VoiceManagementRequest,
    x_user_id: str = Header(default="demo-user", alias="X-User-Id"),
) -> dict:
    return handle_upgrade_voice(request, x_user_id)


@app.post("/api/tts", response_model=TextToSpeechCreateResponse)
def text_to_speech_endpoint(
    request: TextToSpeechCreateRequest,
    x_user_id: str = Header(default="demo-user", alias="X-User-Id"),
) -> TextToSpeechCreateResponse:
    return handle_tts(request, x_user_id)


@app.post("/api/parse", response_model=ParseResponse)
def parse_endpoint(request: ParseRequest) -> ParseResponse:
    return handle_parse(request)


@app.post("/api/chat", response_model=ChatResponse)
def chat_endpoint(
    request: ChatRequest,
    x_user_id: str = Header(default="demo-user", alias="X-User-Id"),
) -> ChatResponse:
    return handle_chat(request, x_user_id)


@app.post("/api/import", response_model=ImportResponse)
def import_endpoint(request: ImportRequest) -> ImportResponse:
    return handle_import(request)


@app.get("/api/records", response_model=RecordsResponse)
def records_endpoint() -> RecordsResponse:
    return handle_records()


@app.delete("/api/memories/{memory_id}", response_model=DeleteResponse)
def delete_memory_endpoint(
    memory_id: str,
    family_id: str | None = Query(default=None),
    x_user_id: str = Header(default="demo-user", alias="X-User-Id"),
) -> DeleteResponse:
    if family_id:
        return handle_delete_cloud_memory(memory_id, family_id, x_user_id)
    return handle_delete_memory(memory_id)


@app.delete("/api/family-profiles/{name}", response_model=DeleteResponse)
def delete_family_profile_endpoint(
    name: str,
    family_id: str | None = Query(default=None),
    x_user_id: str = Header(default="demo-user", alias="X-User-Id"),
) -> DeleteResponse:
    if family_id:
        return handle_delete_cloud_family_profile(name, family_id, x_user_id)
    return handle_delete_family_profile(name)


@app.delete("/api/voices/profiles/{profile_id}", response_model=DeleteResponse)
def hide_voice_profile_endpoint(
    profile_id: str,
    family_id: str = Query(...),
    x_user_id: str = Header(default="demo-user", alias="X-User-Id"),
) -> DeleteResponse:
    return handle_hide_voice_profile(profile_id, family_id, x_user_id)


@app.delete("/api/elders/{full_name}", response_model=DeleteResponse)
def delete_elder_endpoint(full_name: str) -> DeleteResponse:
    return handle_delete_elder(full_name)


@app.delete("/api/personas/{role_label}", response_model=DeleteResponse)
def delete_persona_endpoint(role_label: str) -> DeleteResponse:
    return handle_delete_persona(role_label)
