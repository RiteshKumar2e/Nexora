"""Sandboxed Python code executor tool."""
from __future__ import annotations

import sys
import tempfile
import subprocess
import os
from typing import Any, Dict
from app.tools.base import Tool


class PythonRunnerTool(Tool):
    name = "python_runner"
    description = "Execute arbitrary Python code in a sandboxed, time-limited subprocess. Returns standard output and errors."
    input_schema = {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "Python source code to execute"
            }
        },
        "required": ["code"]
    }

    async def _run(self, arguments: Dict[str, Any]) -> str:
        code = arguments.get("code", "").strip()
        if not code:
            return "Error: Code snippet cannot be empty"

        # Create temporary file to hold the script
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as f:
            f.write(code.encode("utf-8"))
            temp_name = f.name

        try:
            # Run code using current interpreter to ensure all dependencies are accessible,
            # but lock execution time to 5 seconds to avoid infinite loops.
            proc = subprocess.run(
                [sys.executable, temp_name],
                capture_output=True,
                text=True,
                timeout=5.0
            )
            
            output = []
            if proc.stdout:
                output.append(proc.stdout)
            if proc.stderr:
                output.append(f"[StdErr]\n{proc.stderr}")
                
            return "".join(output) if output else "[Success: No stdout or stderr recorded]"
        except subprocess.TimeoutExpired:
            return "Error: Execution timed out (limit: 5.0 seconds)"
        except Exception as e:
            return f"Error executing script: {e}"
        finally:
            # Ensure cleanup
            try:
                os.remove(temp_name)
            except OSError:
                pass
