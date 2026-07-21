"""REST endpoints for managing conversations."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.conversation import (
    ConversationCreate,
    ConversationDetail,
    ConversationRead,
    ConversationUpdate,
)
from app.services import conversation_service as svc
from app.auth.routes import get_current_user_optional

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("", response_model=list[ConversationRead])
async def list_conversations(
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user_optional),
):
    user_id = user.id if user else None
    return await svc.list_conversations(db, user_id=user_id)


@router.post("", response_model=ConversationRead, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    body: ConversationCreate,
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user_optional),
):
    user_id = user.id if user else None
    return await svc.create_conversation(db, title=body.title, user_id=user_id)


@router.get("/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user_optional),
):
    user_id = user.id if user else None
    convo = await svc.get_conversation(db, conversation_id, user_id=user_id)
    if convo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    return convo


@router.patch("/{conversation_id}", response_model=ConversationRead)
async def update_conversation(
    conversation_id: uuid.UUID,
    body: ConversationUpdate,
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user_optional),
):
    user_id = user.id if user else None
    convo = await svc.get_conversation(db, conversation_id, user_id=user_id)
    if convo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    return await svc.update_conversation(
        db, convo, title=body.title, pinned=body.pinned
    )


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user_optional),
):
    user_id = user.id if user else None
    convo = await svc.get_conversation(db, conversation_id, user_id=user_id)
    if convo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    await svc.delete_conversation(db, convo)
