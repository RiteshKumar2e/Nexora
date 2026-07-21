"""File model — uploads representing parsed PDFs, source files, and documents."""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import String, ForeignKey, Uuid, Text, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.project import Project


class UploadedFile(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "uploaded_files"

    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Text contents extracted from doc parsers
    parsed_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    project_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=True,
        index=True
      )

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )

    project: Mapped["Project | None"] = relationship(back_populates="files")
