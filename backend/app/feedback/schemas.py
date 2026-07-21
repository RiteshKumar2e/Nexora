"""Request/response schemas for the feedback API."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class FeedbackCreate(BaseModel):
    user_message: str = Field(..., description="The user's prompt for this turn")
    assistant_response: str = Field(..., description="The assistant reply being rated")
    rating: Literal["up", "down"]
    correction: str | None = Field(
        default=None,
        description="Optional better answer the user provides — used as the "
        "preferred SFT target during RL fine-tuning.",
    )
    conversation_id: str | None = None
    model: str | None = None
    system: str | None = None


class FeedbackResult(BaseModel):
    ok: bool = True
    id: str
