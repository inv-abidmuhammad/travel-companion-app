"""
calculator tool — Phase 1's one tool.

Deliberately narrow: it parses arithmetic via Python's ast module rather
than eval(), so it can't execute arbitrary code no matter what the LLM
passes in. This is the "keep tools small and deterministic" principle
from the blueprint — the graph decides *when* to calculate, this just
does the arithmetic.
"""
import ast
import operator

from langchain_core.tools import tool

_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _eval_node(node: ast.AST) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval_node(node.operand))
    raise ValueError(f"Unsupported expression element: {ast.dump(node)}")


@tool
def calculator(expression: str) -> dict:
    """Evaluate a basic arithmetic expression, e.g. budget math like
    '25000 / 4' or '(180 * 3) + 500'. Supports + - * / ** and
    parentheses only. Use this for budget splits, per-day cost
    estimates, and simple comparisons.
    """
    try:
        tree = ast.parse(expression, mode="eval")
        result = _eval_node(tree.body)
        return {"expression": expression, "result": result, "error": None}
    except Exception as exc:  # noqa: BLE001 — deliberately broad, reported to the agent
        return {"expression": expression, "result": None, "error": str(exc)}
