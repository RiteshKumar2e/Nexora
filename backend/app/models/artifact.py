"""Artifact model — Claude-style sandbox containers for generated files (React, diagrams, etc)."""
from __future__ import annotations

import uuid
from sqlalchemy import String, ForeignKey, Uuid, Text, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class Artifact(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "artifacts"

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(String(50), nullable=False) # e.g., html, python, react, markdown, mermaid
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )
