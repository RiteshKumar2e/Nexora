"""Schemas for the streaming chat endpoint."""
from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """A user turn. If `conversation_id` is omitted a new thread is created."""

    message: str = Field(min_length=1)
    conversation_id: uuid.UUID | None = None
    model: str | None = None
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
