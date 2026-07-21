"""REST endpoints for managing user preferences and semantic memory entries."""
from __future__ import annotations

import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.memory import Memory
from app.auth.routes import get_current_user_optional

router = APIRouter(prefix="/memories", tags=["memories"])


# ── Schemas ──────────────────────────────────────────────────

class MemoryCreate(BaseModel):
    key: str = Field(min_length=1, max_length=100)
    value: str
    category: str = "user_preference"
    project_id: Optional[uuid.UUID] = None


class MemoryRead(BaseModel):
    id: uuid.UUID
    key: str
    value: str
    category: str
    created_at: str
    project_id: Optional[uuid.UUID] = None

    class Config:
        from_attributes = True


# ── Routes ───────────────────────────────────────────────────

@router.post("", response_model=MemoryRead, status_code=status.HTTP_201_CREATED)
async def create_memory(
    body: MemoryCreate,
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user_optional),
):
    user_id = user.id if user else None
    
    mem = Memory(
        key=body.key,
        value=body.value,
        category=body.category,
        project_id=body.project_id,
        user_id=user_id
    )
    db.add(mem)
    await db.commit()
    await db.refresh(mem)
    
    return MemoryRead(
        id=mem.id,
        key=mem.key,
        value=mem.value,
        category=mem.category,
        created_at=mem.created_at.isoformat(),
        project_id=mem.project_id
    )


@router.get("", response_model=list[MemoryRead])
async def list_memories(
    project_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user_optional),
):
    user_id = user.id if user else None
    stmt = select(Memory)
    
    if user_id:
        stmt = stmt.where(Memory.user_id == user_id)
    else:
        stmt = stmt.where(Memory.user_id.is_(None))
        
    if project_id:
        stmt = stmt.where(Memory.project_id == project_id)
        
    stmt = stmt.order_by(Memory.created_at.desc())
    res = await db.execute(stmt)
    memories = res.scalars().all()
    
    return [
        MemoryRead(
            id=mem.id,
            key=mem.key,
            value=mem.value,
            category=mem.category,
            created_at=mem.created_at.isoformat(),
            project_id=mem.project_id
        )
        for mem in memories
    ]


@router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory(
    memory_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user_optional),
):
    user_id = user.id if user else None
    mem = await db.get(Memory, memory_id)
    if mem is None or (mem.user_id is not None and mem.user_id != user_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Memory not found")
        
    await db.delete(mem)
    await db.commit()
