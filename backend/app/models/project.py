"""Project model — Claude-style workspace context folders."""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import String, ForeignKey, Uuid, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.conversation import Conversation
    from app.models.file import UploadedFile


class Project(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "projects"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Isolation per user
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )

    conversations: Mapped[list["Conversation"]] = relationship(
        back_populates="project",
        lazy="selectin",
    )

    files: Mapped[list["UploadedFile"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
