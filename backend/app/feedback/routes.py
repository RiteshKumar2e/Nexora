"""Feedback API — capture ratings/corrections for RLHF, expose collection stats."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.routes import get_current_user_optional
from app.core.config import settings
from app.core.logging import get_logger
from app.db.session import get_db
from app.feedback.schemas import FeedbackCreate, FeedbackResult
from app.feedback.store import append_feedback, stats

router = APIRouter(prefix="/feedback", tags=["feedback"])
log = get_logger("feedback")


@router.post("", response_model=FeedbackResult)
async def create_feedback(
    body: FeedbackCreate,
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
) -> FeedbackResult:
    """Record a 👍/👎 (and optional correction) for one assistant turn.

    The record captures the full turn, the active backend/model, and the user's
    identity (when signed in), then persists to the JSON training file.
    """
    user = None
    if authorization:
        try:
            user = await get_current_user_optional(db, authorization)
        except Exception:  # noqa: BLE001 — feedback must work even for guests
            user = None

    record = append_feedback(
        {
            "user_id": str(user.id) if user else None,
            "username": (getattr(user, "email", None) or getattr(user, "username", None))
            if user
            else None,
            "conversation_id": body.conversation_id,
            "backend": settings.llm_backend,
            "model": body.model,
            "system": body.system,
            "user": body.user_message,
            "assistant": body.assistant_response,
            "rating": body.rating,
            "correction": body.correction,
        }
    )
    log.info(
        "feedback %s (backend=%s, correction=%s)",
        body.rating, settings.llm_backend, bool(body.correction),
    )
    return FeedbackResult(ok=True, id=record["id"])


@router.get("/stats")
async def feedback_stats() -> dict:
    """Counts of collected feedback (used by the training dashboard / RL trainer)."""
    return stats()
