"""Data-access + business logic for conversations and messages.

Keeps SQL out of the route handlers (repository/service pattern). Routes call
these functions; these functions own the ORM.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.base import ChatMessage
from app.models.conversation import Conversation
from app.models.message import Message


async def list_conversations(db: AsyncSession) -> list[Conversation]:
    result = await db.execute(
        select(Conversation).order_by(
            Conversation.pinned.desc(), Conversation.updated_at.desc()
        )
    )
    return list(result.scalars().all())


async def get_conversation(
    db: AsyncSession, conversation_id: uuid.UUID
) -> Conversation | None:
    return await db.get(Conversation, conversation_id)


async def create_conversation(
    db: AsyncSession, *, title: str = "New chat", model: str | None = None
) -> Conversation:
    convo = Conversation(title=title, model=model)
    db.add(convo)
    await db.commit()
    await db.refresh(convo)
    return convo


async def update_conversation(
    db: AsyncSession,
    convo: Conversation,
    *,
    title: str | None = None,
    pinned: bool | None = None,
) -> Conversation:
    if title is not None:
        convo.title = title
    if pinned is not None:
        convo.pinned = pinned
    await db.commit()
    await db.refresh(convo)
    return convo


async def delete_conversation(db: AsyncSession, convo: Conversation) -> None:
    await db.delete(convo)
    await db.commit()


async def add_message(
    db: AsyncSession,
    *,
    conversation_id: uuid.UUID,
    role: str,
    content: str,
    model: str | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
) -> Message:
    msg = Message(
        conversation_id=conversation_id,
        role=role,
        content=content,
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    )
    db.add(msg)
    await db.commit()
    await db.refresh(msg)
    return msg


async def build_llm_context(
    db: AsyncSession, conversation_id: uuid.UUID, *, system_prompt: str | None = None
) -> list[ChatMessage]:
    """Materialize a conversation's history as LLM-ready messages."""
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    )
    history = [
        ChatMessage(role=m.role, content=m.content)  # type: ignore[arg-type]
        for m in result.scalars().all()
        if m.role in ("system", "user", "assistant")
    ]
    if system_prompt:
        history.insert(0, ChatMessage(role="system", content=system_prompt))
    return history


def derive_title(first_message: str, *, max_len: int = 60) -> str:
    """Cheap, deterministic title from the first user message (no LLM call)."""
    text = " ".join(first_message.strip().split())
    return text[: max_len - 1] + "…" if len(text) > max_len else text or "New chat"
