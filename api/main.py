from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from .handlers import (
    handle_chat,
    handle_delete_family_profile,
    handle_delete_memory,
    handle_import,
    handle_parse,
    handle_records,
)
from .schemas import (
    ChatRequest,
    ChatResponse,
    DeleteResponse,
    ImportRequest,
    ImportResponse,
    ParseRequest,
    ParseResponse,
    RecordsResponse,
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


@app.post("/api/parse", response_model=ParseResponse)
def parse_endpoint(request: ParseRequest) -> ParseResponse:
    return handle_parse(request)


@app.post("/api/chat", response_model=ChatResponse)
def chat_endpoint(request: ChatRequest) -> ChatResponse:
    return handle_chat(request)


@app.post("/api/import", response_model=ImportResponse)
def import_endpoint(request: ImportRequest) -> ImportResponse:
    return handle_import(request)


@app.get("/api/records", response_model=RecordsResponse)
def records_endpoint() -> RecordsResponse:
    return handle_records()


@app.delete("/api/memories/{memory_id}", response_model=DeleteResponse)
def delete_memory_endpoint(memory_id: str) -> DeleteResponse:
    return handle_delete_memory(memory_id)


@app.delete("/api/family-profiles/{name}", response_model=DeleteResponse)
def delete_family_profile_endpoint(name: str) -> DeleteResponse:
    return handle_delete_family_profile(name)
