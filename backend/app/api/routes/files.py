"""REST endpoints for uploading and managing workspace files."""
from __future__ import annotations

import os
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.file import UploadedFile
from app.auth.routes import get_current_user_optional
from app.files.parsers import parse_document

router = APIRouter(prefix="/files", tags=["files"])

UPLOAD_DIR = "data/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ── Schemas ──────────────────────────────────────────────────

class FileRead(BaseModel):
    id: uuid.UUID
    filename: str
    file_size: int
    mime_type: str
    created_at: str
    project_id: Optional[uuid.UUID] = None
    # Extracted text (PDF/DOCX/CSV/… parsed server-side), truncated for the chat.
    parsed_text: Optional[str] = None

    class Config:
        from_attributes = True


# ── Routes ───────────────────────────────────────────────────

@router.post("/upload", response_model=FileRead, status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = File(...),
    project_id: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user_optional),
):
    user_id = user.id if user else None
    
    # Validation
    file_bytes = await file.read()
    file_size = len(file_bytes)
    
    if file_size > 10 * 1024 * 1024:  # 10MB limit
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "File exceeds 10MB limit")

    # Generate path
    file_uuid = uuid.uuid4()
    ext = os.path.splitext(file.filename)[1]
    save_filename = f"{file_uuid}{ext}"
    file_path = os.path.join(UPLOAD_DIR, save_filename)
    
    # Save file physically
    with open(file_path, "wb") as f:
        f.write(file_bytes)
        
    # Extract contents
    parsed_text = None
    try:
        parsed_text = parse_document(file.filename, file_bytes)
    except Exception as e:
        # Don't fail the upload, just log and skip parsing
        parsed_text = f"Parsing failed: {e}"

    # Parse project ID if valid
    parsed_project_id = None
    if project_id and project_id != "null" and project_id != "undefined":
        try:
            parsed_project_id = uuid.UUID(project_id)
        except ValueError:
            pass

    # Save to db
    db_file = UploadedFile(
        id=file_uuid,
        filename=file.filename,
        file_path=file_path,
        mime_type=file.content_type or "application/octet-stream",
        file_size=file_size,
        parsed_text=parsed_text,
        project_id=parsed_project_id,
        user_id=user_id
    )
    db.add(db_file)
    await db.commit()
    await db.refresh(db_file)
    
    return FileRead(
        id=db_file.id,
        filename=db_file.filename,
        file_size=db_file.file_size,
        mime_type=db_file.mime_type,
        created_at=db_file.created_at.isoformat(),
        project_id=db_file.project_id,
        parsed_text=(parsed_text or "")[:20000],  # capped for the chat context
    )


@router.get("", response_model=list[FileRead])
async def list_files(
    project_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user_optional),
):
    user_id = user.id if user else None
    stmt = select(UploadedFile)
    
    # User isolation check
    if user_id:
        stmt = stmt.where(UploadedFile.user_id == user_id)
    else:
        stmt = stmt.where(UploadedFile.user_id.is_(None))
        
    if project_id:
        stmt = stmt.where(UploadedFile.project_id == project_id)
        
    stmt = stmt.order_by(UploadedFile.created_at.desc())
    res = await db.execute(stmt)
    files = res.scalars().all()
    
    return [
        FileRead(
            id=f.id,
            filename=f.filename,
            file_size=f.file_size,
            mime_type=f.mime_type,
            created_at=f.created_at.isoformat(),
            project_id=f.project_id
        )
        for f in files
    ]


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(
    file_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user_optional),
):
    user_id = user.id if user else None
    db_file = await db.get(UploadedFile, file_id)
    
    if db_file is None or (db_file.user_id is not None and db_file.user_id != user_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found")
        
    # Delete physically
    if os.path.exists(db_file.file_path):
        try:
            os.remove(db_file.file_path)
        except OSError:
            pass
            
    await db.delete(db_file)
    await db.commit()
