"""Streaming chat endpoint (Server-Sent Events) with RAG & Projects integrations."""
from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException, status, Header
from fastapi.responses import StreamingResponse

from app.core.config import settings
from app.core.logging import get_logger
from app.db.session import SessionLocal
from app.llm.factory import get_llm_client
from app.llm.ollama_client import LLMBackendError
from app.schemas.chat import ChatRequest
from app.services import conversation_service as svc
from app.auth.routes import get_current_user_optional

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
async def chat(
    body: ChatRequest,
    authorization: str | None = Header(None),
) -> StreamingResponse:
    requested_model = body.model
    model_label = body.model or settings.llm_backend

    # --- Pre-stream: persist user turn, prepare context (own session) ---
    async with SessionLocal() as db:
        user = None
        if authorization:
            user = await get_current_user_optional(db, authorization)
        user_id = user.id if user else None

        if body.conversation_id is not None:
            convo = await svc.get_conversation(db, body.conversation_id, user_id=user_id)
            if convo is None:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
            is_new = False
        else:
            convo = await svc.create_conversation(
                db, title=svc.derive_title(body.message), model=model_label, user_id=user_id
            )
            is_new = True

        await svc.add_message(
            db, conversation_id=convo.id, role="user", content=body.message
        )
        
        # Resolve project scoping instructions and documents for RAG context
        project_instructions = ""
        rag_context = ""
        citations = []
        
        if convo.project_id:
            from app.models.project import Project
            from app.rag.service import retrieve_rag_context
            
            project = await db.get(Project, convo.project_id)
            if project:
                project_instructions = project.instructions or ""
                
            # Query lexical matching chunks
            rag_context, citations = await retrieve_rag_context(
                db, query=body.message, project_id=convo.project_id, user_id=user_id
            )

        final_system_prompt = SYSTEM_PROMPT
        if project_instructions:
            final_system_prompt += f"\n\nProject Instructions:\n{project_instructions}"
        if rag_context:
            final_system_prompt += f"\n\n{rag_context}"

        context = await svc.build_llm_context(
            db, convo.id, system_prompt=final_system_prompt
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
        
        # Yield retrieval sources if any
        if citations:
            yield _sse("citations", {"citations": citations})

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
