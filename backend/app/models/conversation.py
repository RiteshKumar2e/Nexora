"""Conversation model — a chat thread grouping ordered messages."""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import String, ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.message import Message
    from app.models.project import Project


class Conversation(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "conversations"

    title: Mapped[str] = mapped_column(String(255), nullable=False, default="New chat")
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    pinned: Mapped[bool] = mapped_column(default=False, nullable=False)
    
    # User isolation (optional to support anonymous dev mode)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )

    # Optional project scoping
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
        lazy="selectin",
    )

    project: Mapped["Project | None"] = relationship(back_populates="conversations")
