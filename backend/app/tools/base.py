"""Base class and result wrapper contracts for built-in tools."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict


@dataclass(slots=True)
class ToolResult:
    """Wrapper holding execution logs and outputs."""
    success: bool
    output: str
    error: str | None = None
    execution_time_ms: float = 0.0


class Tool:
    """Standard interface implemented by all assistant actions."""
    name: str = ""
    description: str = ""
    input_schema: Dict[str, Any] = {}

    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        """Run execution task wrapping elapsed time meters."""
        start = time.perf_counter()
        try:
            out = await self._run(arguments)
            elapsed = (time.perf_counter() - start) * 1000.0
            return ToolResult(success=True, output=out, execution_time_ms=elapsed)
        except Exception as e:
            elapsed = (time.perf_counter() - start) * 1000.0
            return ToolResult(success=False, output="", error=str(e), execution_time_ms=elapsed)

    async def _run(self, arguments: Dict[str, Any]) -> str:
        raise NotImplementedError
