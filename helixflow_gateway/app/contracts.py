"""Strict Pydantic v2 data models & request/response schemas."""
from pydantic import BaseModel


class StatusResponse(BaseModel):
    status: str
    details: dict | None = None


class StreamRequest(BaseModel):
    model: str
    prompt: str
    max_tokens: int | None = None
