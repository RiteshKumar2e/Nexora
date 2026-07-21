"""REST endpoints for creating and versioning artifacts."""
from __future__ import annotations

import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.artifact import Artifact
from app.auth.routes import get_current_user_optional

router = APIRouter(prefix="/artifacts", tags=["artifacts"])


# ── Schemas ──────────────────────────────────────────────────

class ArtifactCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    content: str
    language: str = "text"
    conversation_id: Optional[uuid.UUID] = None


class ArtifactUpdate(BaseModel):
    content: str
    title: Optional[str] = None


class ArtifactRead(BaseModel):
    id: uuid.UUID
    title: str
    content: str
    language: str
    version: int
    created_at: str
    conversation_id: Optional[uuid.UUID] = None

    class Config:
        from_attributes = True


# ── Routes ───────────────────────────────────────────────────

@router.post("", response_model=ArtifactRead, status_code=status.HTTP_201_CREATED)
async def create_artifact(
    body: ArtifactCreate,
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user_optional),
):
    user_id = user.id if user else None
    
    art = Artifact(
        title=body.title,
        content=body.content,
        language=body.language,
        conversation_id=body.conversation_id,
        user_id=user_id,
        version=1
    )
    db.add(art)
    await db.commit()
    await db.refresh(art)
    
    return ArtifactRead(
        id=art.id,
        title=art.title,
        content=art.content,
        language=art.language,
        version=art.version,
        created_at=art.created_at.isoformat(),
        conversation_id=art.conversation_id
    )


@router.patch("/{artifact_id}", response_model=ArtifactRead)
async def update_artifact(
    artifact_id: uuid.UUID,
    body: ArtifactUpdate,
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user_optional),
):
    user_id = user.id if user else None
    art = await db.get(Artifact, artifact_id)
    if art is None or (art.user_id is not None and art.user_id != user_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Artifact not found")
        
    art.content = body.content
    if body.title:
        art.title = body.title
    art.version += 1
    
    await db.commit()
    await db.refresh(art)
    
    return ArtifactRead(
        id=art.id,
        title=art.title,
        content=art.content,
        language=art.language,
        version=art.version,
        created_at=art.created_at.isoformat(),
        conversation_id=art.conversation_id
    )


@router.get("/{artifact_id}", response_model=ArtifactRead)
async def get_artifact(
    artifact_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user_optional),
):
    user_id = user.id if user else None
    art = await db.get(Artifact, artifact_id)
    if art is None or (art.user_id is not None and art.user_id != user_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Artifact not found")
    return ArtifactRead(
        id=art.id,
        title=art.title,
        content=art.content,
        language=art.language,
        version=art.version,
        created_at=art.created_at.isoformat(),
        conversation_id=art.conversation_id
    )


@router.get("", response_model=list[ArtifactRead])
async def list_artifacts(
    conversation_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user_optional),
):
    user_id = user.id if user else None
    stmt = select(Artifact)
    
    if user_id:
        stmt = stmt.where(Artifact.user_id == user_id)
    else:
        stmt = stmt.where(Artifact.user_id.is_(None))
        
    if conversation_id:
        stmt = stmt.where(Artifact.conversation_id == conversation_id)
        
    stmt = stmt.order_by(Artifact.updated_at.desc())
    res = await db.execute(stmt)
    artifacts = res.scalars().all()
    
    return [
        ArtifactRead(
            id=art.id,
            title=art.title,
            content=art.content,
            language=art.language,
            version=art.version,
            created_at=art.created_at.isoformat(),
            conversation_id=art.conversation_id
        )
        for art in artifacts
    ]
