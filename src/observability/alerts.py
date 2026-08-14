"""Alert rules evaluated after every agent run, plus pluggable notifiers."""
from __future__ import annotations

from dataclasses import dataclass

import requests
from rich.console import Console

from src.observability.metrics_store import RunRecord, record_alert
from src.settings import get_settings

console = Console()


@dataclass
class Alert:
    severity: str  # "warning" | "critical"
    kind: str  # "failure" | "loop" | "latency" | "cost"
    message: str


def evaluate(run: RunRecord) -> list[Alert]:
    settings = get_settings()
    alerts: list[Alert] = []

    if not run.success:
        alerts.append(Alert("critical", "failure", f"Run failed: {run.error_message}"))

    if run.loop_detected:
        alerts.append(
            Alert(
                "warning",
                "loop",
                f"Possible tool-call loop: {run.iteration_count} LLM iterations "
                f"/ {run.tool_call_count} tool calls in one run",
            )
        )

    if run.latency_ms > settings.latency_alert_ms:
        alerts.append(
            Alert(
                "warning",
                "latency",
                f"Latency {run.latency_ms:.0f}ms exceeded threshold "
                f"{settings.latency_alert_ms:.0f}ms",
            )
        )

    if run.cost_usd > settings.cost_alert_usd:
        alerts.append(
            Alert(
                "warning",
                "cost",
                f"Run cost ${run.cost_usd:.4f} exceeded threshold ${settings.cost_alert_usd:.4f}",
            )
        )

    return alerts


def dispatch(alerts: list[Alert], run_id: int | None, agent_version: str) -> None:
    settings = get_settings()
    for alert in alerts:
        record_alert(run_id, alert.severity, alert.kind, alert.message)

        color = "red" if alert.severity == "critical" else "yellow"
        console.print(
            f"[{color}]ALERT[/{color}] [{alert.severity}] ({alert.kind}, {agent_version}) "
            f"{alert.message}"
        )

        if settings.slack_webhook_url:
            _notify_slack(settings.slack_webhook_url, alert, agent_version)


def _notify_slack(webhook_url: str, alert: Alert, agent_version: str) -> None:
    try:
        requests.post(
            webhook_url,
            json={
                "text": f":rotating_light: *{alert.severity.upper()}* [{alert.kind}] "
                f"({agent_version}) {alert.message}"
            },
            timeout=5,
        )
    except requests.RequestException as exc:  # noqa: BLE001 - alerting must never crash the agent
        console.print(f"[yellow]Failed to deliver Slack alert: {exc}[/yellow]")
