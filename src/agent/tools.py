"""Tools available to the monitored agent.

`inventory_lookup` is deliberately unreliable (random errors + occasional slow
responses) so the observability stack has real failure and latency signal to
alert on — it stands in for a flaky downstream microservice.
"""
from __future__ import annotations

import ast
import operator
import random
import time

from langchain_core.tools import tool

_ALLOWED_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.Mod: operator.mod,
}


def _safe_eval(node: ast.AST) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_OPERATORS:
        return _ALLOWED_OPERATORS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_OPERATORS:
        return _ALLOWED_OPERATORS[type(node.op)](_safe_eval(node.operand))
    raise ValueError(f"Unsupported expression: {ast.dump(node)}")


@tool
def calculator(expression: str) -> str:
    """Evaluate a basic arithmetic expression (+, -, *, /, %, **).

    Args:
        expression: A math expression, e.g. "12 * (4 + 3) / 2".
    """
    try:
        tree = ast.parse(expression, mode="eval")
        result = _safe_eval(tree.body)
        return str(result)
    except Exception as exc:  # noqa: BLE001 - surfaced back to the model as a tool error
        return f"Error evaluating expression: {exc}"


@tool
def web_search(query: str) -> str:
    """Search the public web for current information and return brief results.

    Args:
        query: The search query.
    """
    try:
        from ddgs import DDGS

        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=3))
        if not results:
            return "No results found."
        lines = [f"- {r['title']}: {r['body'][:200]} ({r['href']})" for r in results]
        return "\n".join(lines)
    except Exception as exc:  # noqa: BLE001
        return f"Search failed: {exc}"


@tool
def inventory_lookup(sku: str) -> str:
    """Look up stock quantity and warehouse location for a product SKU
    from the internal inventory service.

    Args:
        sku: The product SKU to look up, e.g. "SKU-1042".
    """
    # Simulated production flakiness: ~25% error rate, ~15% slow-response tail.
    roll = random.random()
    if roll < 0.25:
        raise RuntimeError(f"inventory-service: upstream timeout looking up {sku}")
    if roll < 0.40:
        time.sleep(random.uniform(3, 6))

    qty = random.randint(0, 500)
    warehouse = random.choice(["US-EAST-1", "US-WEST-2", "EU-CENTRAL-1"])
    return f"{sku}: {qty} units in stock at {warehouse}"


ALL_TOOLS = [calculator, web_search, inventory_lookup]
