"""Safe mathematical expression calculator tool."""
from __future__ import annotations

import math
from typing import Any, Dict
from app.tools.base import Tool


class CalculatorTool(Tool):
    name = "calculator"
    description = "Safely evaluate mathematical expressions. Accepts basic operations and functions like sin, cos, log, sqrt, etc."
    input_schema = {
        "type": "object",
        "properties": {
            "expression": {
                "type": "string",
                "description": "Mathematical expression to evaluate, e.g. '2 * (3.5 + 4) / sqrt(16)'"
            }
        },
        "required": ["expression"]
    }

    async def _run(self, arguments: Dict[str, Any]) -> str:
        expr = arguments.get("expression", "").strip()
        if not expr:
            return "Error: Expression cannot be empty"
            
        # Security: whitelist characters to prevent shell/python injections
        allowed_chars = set("0123456789.+-*/() %")
        # Add basic math function names
        math_funcs = ["sin", "cos", "tan", "log", "sqrt", "pi", "e", "pow", "abs"]
        
        # Strip function words and check remainder characters
        expr_check = expr
        for f in math_funcs:
            expr_check = expr_check.replace(f, "")
            
        if not all(c in allowed_chars for c in expr_check):
            return "Error: Unsafe expression detected. Only basic operators and standard math functions allowed."
            
        # Setup clean math namespace
        safe_dict = {
            "sin": math.sin,
            "cos": math.cos,
            "tan": math.tan,
            "log": math.log,
            "sqrt": math.sqrt,
            "pow": math.pow,
            "abs": math.fabs,
            "pi": math.pi,
            "e": math.e,
        }
        
        # Evaluate safely
        try:
            val = eval(expr, {"__builtins__": None}, safe_dict)
            return str(val)
        except Exception as e:
            return f"Error evaluating expression: {e}"
