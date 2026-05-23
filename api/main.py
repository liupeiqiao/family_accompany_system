from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from .handlers import handle_chat, handle_parse
from .schemas import ChatRequest, ChatResponse, ParseRequest, ParseResponse

app = FastAPI(title="亲情陪伴系统 API")


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/docs")


@app.post("/api/parse", response_model=ParseResponse)
def parse_endpoint(request: ParseRequest) -> ParseResponse:
    return handle_parse(request)


@app.post("/api/chat", response_model=ChatResponse)
def chat_endpoint(request: ChatRequest) -> ChatResponse:
    return handle_chat(request)
