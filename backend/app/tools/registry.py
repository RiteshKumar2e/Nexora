"""Registry of all built-in tools."""
from __future__ import annotations

from app.tools.calculator import CalculatorTool
from app.tools.python_runner import PythonRunnerTool


class ToolRegistry:
    def __init__(self):
        self.tools = {
            "calculator": CalculatorTool(),
            "python_runner": PythonRunnerTool()
        }
        
    def get_tool(self, name: str):
        return self.tools.get(name)
        
    def list_tools(self):
        return [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.input_schema
            }
            for t in self.tools.values()
        ]

registry = ToolRegistry()
