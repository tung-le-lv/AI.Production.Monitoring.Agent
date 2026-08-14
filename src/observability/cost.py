"""Token -> USD cost calculation for Claude models.

Prices are $ per million tokens (input, output). Update this table when
Anthropic pricing changes; see platform.claude.com/docs/en/pricing.
"""
from __future__ import annotations

PRICING_PER_MTOK: dict[str, tuple[float, float]] = {
    "claude-opus-5": (5.00, 25.00),
    "claude-sonnet-5": (3.00, 15.00),
    "claude-haiku-4-5": (1.00, 5.00),
    "claude-opus-4-8": (5.00, 25.00),
    "claude-opus-4-7": (5.00, 25.00),
    "claude-sonnet-4-6": (3.00, 15.00),
}

_DEFAULT_RATE = (5.00, 25.00)  # conservative fallback if a model isn't in the table


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    input_rate, output_rate = PRICING_PER_MTOK.get(model, _DEFAULT_RATE)
    return (input_tokens / 1_000_000) * input_rate + (output_tokens / 1_000_000) * output_rate
