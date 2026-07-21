"""Liveness/readiness endpoints."""
from __future__ import annotations

from fastapi import APIRouter

from app.core.config import settings
from app.llm.factory import get_llm_client

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    """Liveness — the process is up."""
    return {"status": "ok", "app": settings.app_name, "environment": settings.environment}


@router.get("/health/ready")
async def readiness() -> dict:
    """Readiness — dependencies the app needs to serve requests."""
    llm = get_llm_client()
    llm_ok = await llm.health()
    is_nano = settings.llm_backend.lower() != "ollama"
    model_name = "nano-llm (own model)" if is_nano else settings.llm_model
    return {
        "status": "ok" if llm_ok else "degraded",
        "llm": {"backend": settings.llm_backend, "ready": llm_ok, "model": model_name},
    }
