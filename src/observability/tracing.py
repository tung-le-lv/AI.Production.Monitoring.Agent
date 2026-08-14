"""OpenTelemetry/OpenInference tracing setup.

Points every LangChain / LangGraph call at a local Arize Phoenix server via
OpenInference instrumentation, so each agent run shows up as a full span
waterfall (LLM calls, tool calls, latencies, token counts) in the Phoenix UI.

This module only *configures the exporter* — it does not launch Phoenix
itself. Run `python scripts/serve_phoenix.py` in its own terminal once;
Phoenix then persists trace history across every later agent/canary run.
(Auto-launching an embedded Phoenix server per short-lived script invocation
was tried first and is flaky on Windows: the server needs longer than
uvicorn's hard-coded 5s startup window on a cold DB migration, and every
invocation would otherwise fight over the same port.)
"""
from __future__ import annotations

import threading
import urllib.request

from rich.console import Console

console = Console()

_lock = threading.Lock()
_session_url: str | None = None


def setup_tracing(port: int) -> str:
    """Idempotently configure OpenInference/OTEL export to Phoenix. Returns the UI URL."""
    global _session_url

    with _lock:
        if _session_url is not None:
            return _session_url

        from openinference.instrumentation.langchain import LangChainInstrumentor
        from phoenix.otel import register

        url = f"http://localhost:{port}"
        tracer_provider = register(
            project_name="production-monitoring-agent",
            endpoint=f"{url}/v1/traces",
        )
        LangChainInstrumentor().instrument(tracer_provider=tracer_provider)

        try:
            urllib.request.urlopen(url, timeout=1)
        except Exception:  # noqa: BLE001 - tracing must never block/crash the agent
            console.print(
                f"[yellow]Note:[/yellow] Phoenix doesn't seem to be running at {url} yet. "
                f"Start it in another terminal with: python scripts/serve_phoenix.py"
            )

        _session_url = url
        return _session_url
