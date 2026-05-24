from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ParseRequest(BaseModel):
    family_id: str = Field(default="local")
    text: str
    perspective: Literal["family", "elder"] = "family"


class ParseResponse(BaseModel):
    persona: dict = Field(default_factory=dict)
    memories: list[dict] = Field(default_factory=list)
    family_profiles: list[dict] = Field(default_factory=list)
    elder_profile: dict = Field(default_factory=dict)
    merge_preview: list[str] = Field(default_factory=list)


class ImportRequest(BaseModel):
    family_id: str = Field(default="local")
    persona: dict = Field(default_factory=dict)
    personas: list[dict] = Field(default_factory=list)
    memories: list[dict] = Field(default_factory=list)
    family_profiles: list[dict] = Field(default_factory=list)
    elder_profile: dict = Field(default_factory=dict)
    elder_profiles: list[dict] = Field(default_factory=list)


class ImportCounts(BaseModel):
    persona: int = 0
    elder_profile: int = 0
    family_profiles: int = 0
    memories: int = 0


class ImportResponse(BaseModel):
    ok: bool = True
    imported: ImportCounts = Field(default_factory=ImportCounts)


class RecordsResponse(BaseModel):
    persona: dict = Field(default_factory=dict)
    personas: list[dict] = Field(default_factory=list)
    elder_profile: dict = Field(default_factory=dict)
    elder_profiles: list[dict] = Field(default_factory=list)
    family_profiles: list[dict] = Field(default_factory=list)
    memories: list[dict] = Field(default_factory=list)


class DeleteResponse(BaseModel):
    ok: bool = True


class ChatRequest(BaseModel):
    family_id: str = Field(default="local")
    elder_id: str = ""
    persona_id: str = ""
    text: str
    voice_profile_id: str | None = None


class ChatResponse(BaseModel):
    text: str
    audio_url: str | None = None
    debug: dict = Field(default_factory=dict)
