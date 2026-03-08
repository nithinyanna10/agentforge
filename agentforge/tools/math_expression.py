"""Safe math expression evaluation (no arbitrary code)."""

from __future__ import annotations

import ast
import operator
from typing import Any

from agentforge.tools.base import Tool, ToolResult

_SAFE_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _eval_node(node: ast.AST) -> float:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return float(node.value)
        raise ValueError("Only numeric constants allowed")
    if isinstance(node, ast.UnaryOp):
        op = _SAFE_OPS.get(type(node.op))
        if op is None:
            raise ValueError("Unsupported unary operator")
        return op(_eval_node(node.operand))
    if isinstance(node, ast.BinOp):
        op = _SAFE_OPS.get(type(node.op))
        if op is None:
            raise ValueError("Unsupported binary operator")
        return op(_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name):
            if node.func.id == "abs" and len(node.args) == 1:
                return abs(_eval_node(node.args[0]))
            if node.func.id in ("round", "min", "max") and 1 <= len(node.args) <= 2:
                vals = [_eval_node(a) for a in node.args]
                if node.func.id == "round":
                    return round(vals[0]) if len(vals) == 1 else round(vals[0], int(vals[1]))
                if node.func.id == "min":
                    return min(vals)
                if node.func.id == "max":
                    return max(vals)
        raise ValueError("Only abs(), round(), min(), max() with numbers allowed")
    raise ValueError("Unsupported expression form")


def safe_eval(expression: str) -> float:
    """Evaluate a math expression safely (numbers and +, -, *, /, //, **, abs, round, min, max)."""
    tree = ast.parse(expression.strip(), mode="eval")
    return _eval_node(tree.body)


class MathExpressionTool(Tool):
    """Evaluate a safe math expression and return the result."""

    @property
    def name(self) -> str:
        return "math_expression"

    @property
    def description(self) -> str:
        return (
            "Evaluate a mathematical expression. Supports +, -, *, /, //, **, "
            "parentheses, and functions: abs(), round(), min(), max(). "
            "Example: (10 + 3) * 2 - 1"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "A mathematical expression to evaluate (e.g. '2 * 3.14', 'abs(-5)').",
                },
            },
            "required": ["expression"],
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        expr = (kwargs.get("expression") or "").strip()
        if not expr:
            return ToolResult(success=False, output="", error="'expression' is required")
        try:
            result = safe_eval(expr)
            return ToolResult(
                success=True,
                output=str(result),
                metadata={"expression": expr, "result": result},
            )
        except Exception as exc:
            return ToolResult(success=False, output="", error=str(exc))
