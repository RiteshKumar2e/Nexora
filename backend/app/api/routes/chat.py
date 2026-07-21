"""Streaming chat endpoint (Server-Sent Events).

Flow:
  1. Resolve or create the conversation and persist the user turn.
  2. Build the conversation context and stream tokens from the local LLM.
  3. Accumulate the assistant text, persist it (with usage) when the stream ends.

Sessions are managed explicitly (not via Depends) because a StreamingResponse
generator can outlive the request-scoped dependency, which would otherwise
close the session mid-stream.
"""
from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from app.core.config import settings
from app.core.logging import get_logger
from app.db.session import SessionLocal
from app.llm.factory import get_llm_client
from app.llm.ollama_client import LLMBackendError
from app.schemas.chat import ChatRequest
from app.services import conversation_service as svc

router = APIRouter(prefix="/chat", tags=["chat"])
log = get_logger("chat")

SYSTEM_PROMPT = (
    "You are Nexora, a helpful, precise AI assistant. Answer clearly and "
    "directly, matching the depth of the question. Format every reply in clean "
    "Markdown: use headings, bold, and bullet or numbered lists where they aid "
    "readability. Put code in fenced blocks with a language tag. For math, use "
    "LaTeX with dollar delimiters: inline math as $...$ and display equations as "
    "$$...$$ (do not use \\( \\) or \\[ \\]). Use aligned/array environments "
    "inside $$ blocks for multi-line derivations."
)


def _sse(event: str, data: dict) -> str:
    """Format a single Server-Sent Event frame."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.post("")
async def chat(body: ChatRequest) -> StreamingResponse:
    # Leave the model unset unless the client asks for a specific one, so each
    # backend can choose: Groq walks its best-first discovery/fallback chain,
    # Ollama uses its configured default. `model_label` is only for storage/UI.
    requested_model = body.model
    model_label = body.model or settings.llm_backend

    # --- Pre-stream: persist user turn, prepare context (own session) ---
    async with SessionLocal() as db:
        if body.conversation_id is not None:
            convo = await svc.get_conversation(db, body.conversation_id)
            if convo is None:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
            is_new = False
        else:
            convo = await svc.create_conversation(
                db, title=svc.derive_title(body.message), model=model_label
            )
            is_new = True

        await svc.add_message(
            db, conversation_id=convo.id, role="user", content=body.message
        )
        context = await svc.build_llm_context(
            db, convo.id, system_prompt=SYSTEM_PROMPT
        )
        conversation_id = convo.id
        title = convo.title

    llm = get_llm_client()

    async def event_stream() -> AsyncIterator[str]:
        # Tell the client which conversation this belongs to up front.
        yield _sse(
            "meta",
            {"conversation_id": str(conversation_id), "title": title, "is_new": is_new},
        )

        parts: list[str] = []
        usage = None
        try:
            async for chunk in llm.stream_chat(
                context, model=requested_model, temperature=body.temperature
            ):
                if chunk.delta:
                    parts.append(chunk.delta)
                    yield _sse("token", {"delta": chunk.delta})
                if chunk.done:
                    usage = chunk.usage
        except LLMBackendError as exc:
            log.error("LLM backend error: %s", exc)
            yield _sse("error", {"message": str(exc)})
            return
        except Exception as exc:  # defensive: never leak a raw traceback to SSE
            log.exception("Unexpected error during streaming")
            yield _sse("error", {"message": f"Internal error: {exc}"})
            return

        assistant_text = "".join(parts)

        # --- Post-stream: persist assistant turn in a fresh session ---
        try:
            async with SessionLocal() as db:
                msg = await svc.add_message(
                    db,
                    conversation_id=conversation_id,
                    role="assistant",
                    content=assistant_text,
                    model=model_label,
                    prompt_tokens=usage.prompt_tokens if usage else None,
                    completion_tokens=usage.completion_tokens if usage else None,
                )
                message_id = str(msg.id)
        except Exception:
            log.exception("Failed to persist assistant message")
            message_id = None

        yield _sse(
            "done",
            {
                "conversation_id": str(conversation_id),
                "message_id": message_id,
                "usage": {
                    "prompt_tokens": usage.prompt_tokens if usage else None,
                    "completion_tokens": usage.completion_tokens if usage else None,
                },
            },
        )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable proxy buffering for real streaming
        },
    )
