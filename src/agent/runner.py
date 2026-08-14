"""Orchestrates a single agent run: invoke -> measure -> record -> alert.

This is the one place every code path (interactive CLI, canary suite) goes
through, so tracing/metrics/alerting stay consistent regardless of caller.
"""
from __future__ import annotations

import time

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from src.agent.graph import build_agent
from src.observability import alerts
from src.observability.cost import estimate_cost_usd
from src.observability.metrics_store import RunRecord, record_run
from src.observability.tracing import setup_tracing
from src.settings import get_active_version_name, get_settings, get_version_config


def run_agent(prompt: str, version_name: str | None = None, run_type: str = "interactive") -> dict:
    """Run the agent for `prompt` against `version_name` ("stable"/"canary",
    defaults to whichever is currently active), recording metrics and firing
    any alerts the run trips."""
    settings = get_settings()
    setup_tracing(settings.phoenix_port)

    version_name = version_name or get_active_version_name()
    version_cfg = get_version_config(version_name)
    model = version_cfg["model"]
    system_prompt = version_cfg["system_prompt"]

    agent = build_agent(model, system_prompt)

    start = time.perf_counter()
    error_message: str | None = None
    success = True
    ai_messages: list[AIMessage] = []
    tool_call_count = 0
    final_text = ""

    try:
        result = agent.invoke({"messages": [HumanMessage(content=prompt)]})
        messages = result["messages"]
        ai_messages = [m for m in messages if isinstance(m, AIMessage)]
        tool_call_count = sum(1 for m in messages if isinstance(m, ToolMessage))
        if ai_messages:
            last = ai_messages[-1]
            final_text = last.content if isinstance(last.content, str) else str(last.content)
    except Exception as exc:  # noqa: BLE001 - this is the failure signal the dashboard alerts on
        success = False
        error_message = f"{type(exc).__name__}: {exc}"

    latency_ms = (time.perf_counter() - start) * 1000

    input_tokens = 0
    output_tokens = 0
    for m in ai_messages:
        usage = getattr(m, "usage_metadata", None) or {}
        input_tokens += usage.get("input_tokens", 0) or 0
        output_tokens += usage.get("output_tokens", 0) or 0

    cost_usd = estimate_cost_usd(model, input_tokens, output_tokens)
    iteration_count = len(ai_messages)
    loop_detected = iteration_count >= settings.max_tool_iterations

    run = RunRecord(
        run_type=run_type,
        agent_version=version_name,
        model=model,
        prompt=prompt,
        success=success,
        error_message=error_message,
        latency_ms=latency_ms,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd,
        iteration_count=iteration_count,
        tool_call_count=tool_call_count,
        loop_detected=loop_detected,
    )
    run_id = record_run(run)

    fired = alerts.evaluate(run)
    if fired:
        alerts.dispatch(fired, run_id, version_name)

    return {
        "run_id": run_id,
        "success": success,
        "answer": final_text,
        "error": error_message,
        "latency_ms": latency_ms,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": cost_usd,
        "iteration_count": iteration_count,
        "tool_call_count": tool_call_count,
        "loop_detected": loop_detected,
        "model": model,
        "agent_version": version_name,
    }
