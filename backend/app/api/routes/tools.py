"""REST endpoints for discovery and execution of built-in tools."""
from __future__ import annotations

from typing import Any, Dict
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.tools.registry import registry as reg

router = APIRouter(prefix="/tools", tags=["tools"])


# ── Schemas ──────────────────────────────────────────────────

class ToolExecutionRequest(BaseModel):
    name: str = Field(min_length=1)
    arguments: Dict[str, Any] = Field(default_factory=dict)


class ToolExecutionResponse(BaseModel):
    success: bool
    output: str
    error: str | None = None
    execution_time_ms: float


# ── Routes ───────────────────────────────────────────────────

@router.get("")
async def list_tools():
    """List details of all available sandbox tools."""
    return reg.list_tools()


@router.post("/execute", response_model=ToolExecutionResponse)
async def execute_tool(body: ToolExecutionRequest):
    """Invoke tool execution and return stdout/error blocks."""
    tool = reg.get_tool(body.name)
    if not tool:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tool '{body.name}' not found"
        )
        
    res = await tool.execute(body.arguments)
    return ToolExecutionResponse(
        success=res.success,
        output=res.output,
        error=res.error,
        execution_time_ms=res.execution_time_ms
    )
