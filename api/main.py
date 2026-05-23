from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from .handlers import handle_chat, handle_import, handle_parse
from .schemas import (
    ChatRequest,
    ChatResponse,
    ImportRequest,
    ImportResponse,
    ParseRequest,
    ParseResponse,
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
