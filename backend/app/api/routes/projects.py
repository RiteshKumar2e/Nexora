"""REST endpoints for managing projects (workspaces)."""
from __future__ import annotations

import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.project import Project
from app.auth.routes import get_current_user_optional

router = APIRouter(prefix="/projects", tags=["projects"])


# ── Schemas ──────────────────────────────────────────────────

class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    instructions: Optional[str] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    instructions: Optional[str] = None


class ProjectRead(BaseModel):
    id: uuid.UUID
    name: str
    instructions: Optional[str] = None
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


# ── Routes ───────────────────────────────────────────────────

@router.get("", response_model=list[ProjectRead])
async def list_projects(
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user_optional),
):
    user_id = user.id if user else None
    stmt = select(Project)
    if user_id:
        stmt = stmt.where(Project.user_id == user_id)
    else:
        stmt = stmt.where(Project.user_id.is_(None))
        
    stmt = stmt.order_by(Project.updated_at.desc())
    res = await db.execute(stmt)
    projects = res.scalars().all()
    
    # Fast format dates to string
    return [
        ProjectRead(
            id=p.id,
            name=p.name,
            instructions=p.instructions,
            created_at=p.created_at.isoformat(),
            updated_at=p.updated_at.isoformat(),
        )
        for p in projects
    ]


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
async def create_project(
    body: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user_optional),
):
    user_id = user.id if user else None
    p = Project(name=body.name, instructions=body.instructions, user_id=user_id)
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return ProjectRead(
        id=p.id,
        name=p.name,
        instructions=p.instructions,
        created_at=p.created_at.isoformat(),
        updated_at=p.updated_at.isoformat(),
    )


@router.get("/{project_id}", response_model=ProjectRead)
async def get_project(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user_optional),
):
    user_id = user.id if user else None
    p = await db.get(Project, project_id)
    if p is None or (p.user_id is not None and p.user_id != user_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    return ProjectRead(
        id=p.id,
        name=p.name,
        instructions=p.instructions,
        created_at=p.created_at.isoformat(),
        updated_at=p.updated_at.isoformat(),
    )


@router.patch("/{project_id}", response_model=ProjectRead)
async def update_project(
    project_id: uuid.UUID,
    body: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user_optional),
):
    user_id = user.id if user else None
    p = await db.get(Project, project_id)
    if p is None or (p.user_id is not None and p.user_id != user_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
        
    if body.name is not None:
        p.name = body.name
    if body.instructions is not None:
        p.instructions = body.instructions
        
    await db.commit()
    await db.refresh(p)
    return ProjectRead(
        id=p.id,
        name=p.name,
        instructions=p.instructions,
        created_at=p.created_at.isoformat(),
        updated_at=p.updated_at.isoformat(),
    )


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user_optional),
):
    user_id = user.id if user else None
    p = await db.get(Project, project_id)
    if p is None or (p.user_id is not None and p.user_id != user_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
        
    await db.delete(p)
    await db.commit()
