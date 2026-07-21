"""Aggregate API router. Mount new feature routers here."""
from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import chat, conversations, health, projects, files, artifacts, tools, memories, training, evaluation
from app.auth.routes import router as auth_router

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth_router)
api_router.include_router(projects.router)
api_router.include_router(files.router)
api_router.include_router(artifacts.router)
api_router.include_router(tools.router)
api_router.include_router(memories.router)
api_router.include_router(training.router)
api_router.include_router(evaluation.router)
api_router.include_router(conversations.router)
api_router.include_router(chat.router)
