"""Canary evaluation: run stable + canary versions against a fixed eval suite,
compare reliability/latency/cost, and automatically promote or roll back the
`active` pointer in config/agent_versions.json.

This is the "ship to production, not just localhost" piece: config changes
take effect immediately for the next interactive run, no redeploy needed.
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass

from rich.console import Console
from rich.table import Table

from src.agent.runner import run_agent
from src.canary.eval_prompts import EVAL_PROMPTS
from src.settings import CANARY_REPORTS_PATH, get_active_version_name, get_settings, set_active_version

console = Console()


@dataclass
class VersionSummary:
    version: str
    model: str
    n_runs: int
    success_rate: float
    loop_rate: float
    avg_latency_ms: float
    avg_cost_usd: float
    total_cost_usd: float


def _summarize(version: str, results: list[dict]) -> VersionSummary:
    n = len(results)
    successes = sum(1 for r in results if r["success"])
    loops = sum(1 for r in results if r["loop_detected"])
    total_cost = sum(r["cost_usd"] for r in results)
    return VersionSummary(
        version=version,
        model=results[0]["model"] if results else "",
        n_runs=n,
        success_rate=successes / n if n else 0.0,
        loop_rate=loops / n if n else 0.0,
        avg_latency_ms=sum(r["latency_ms"] for r in results) / n if n else 0.0,
        avg_cost_usd=total_cost / n if n else 0.0,
        total_cost_usd=total_cost,
    )


def _decide(stable: VersionSummary, canary: VersionSummary) -> tuple[str, str]:
    settings = get_settings()
    active = get_active_version_name()

    meets_bar = (
        canary.success_rate >= settings.canary_min_success_rate
        and canary.success_rate >= stable.success_rate - 0.05
        and canary.avg_latency_ms <= stable.avg_latency_ms * settings.canary_max_latency_regression
    )

    if meets_bar and active != "canary":
        return "promote", (
            f"canary success_rate={canary.success_rate:.0%} (>= {settings.canary_min_success_rate:.0%} bar, "
            f">= stable-5%) and avg_latency={canary.avg_latency_ms:.0f}ms "
            f"(<= {settings.canary_max_latency_regression:.2f}x stable's {stable.avg_latency_ms:.0f}ms)"
        )
    if not meets_bar and active == "canary":
        return "rollback", (
            f"canary fell below promotion bar: success_rate={canary.success_rate:.0%}, "
            f"avg_latency={canary.avg_latency_ms:.0f}ms vs stable {stable.avg_latency_ms:.0f}ms"
        )
    return "hold", f"active version '{active}' already reflects the evaluation outcome"


def run_canary_evaluation(iterations: int = 1) -> dict:
    results_by_version: dict[str, list[dict]] = {"stable": [], "canary": []}

    for version in ("stable", "canary"):
        for prompt in EVAL_PROMPTS:
            for _ in range(iterations):
                results_by_version[version].append(
                    run_agent(prompt, version_name=version, run_type="canary")
                )

    stable_summary = _summarize("stable", results_by_version["stable"])
    canary_summary = _summarize("canary", results_by_version["canary"])
    decision, reason = _decide(stable_summary, canary_summary)

    if decision == "promote":
        set_active_version("canary")
    elif decision == "rollback":
        set_active_version("stable")

    report = {
        "timestamp": time.time(),
        "stable": asdict(stable_summary),
        "canary": asdict(canary_summary),
        "decision": decision,
        "reason": reason,
        "active_after": get_active_version_name(),
    }

    with open(CANARY_REPORTS_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(report) + "\n")

    _print_report(report)
    return report


def _print_report(report: dict) -> None:
    table = Table(title="Canary Evaluation")
    table.add_column("Version")
    table.add_column("Model")
    table.add_column("Runs")
    table.add_column("Success rate")
    table.add_column("Loop rate")
    table.add_column("Avg latency")
    table.add_column("Total cost")

    for key in ("stable", "canary"):
        s = report[key]
        table.add_row(
            key,
            s["model"],
            str(s["n_runs"]),
            f"{s['success_rate']:.0%}",
            f"{s['loop_rate']:.0%}",
            f"{s['avg_latency_ms']:.0f}ms",
            f"${s['total_cost_usd']:.4f}",
        )

    console.print(table)

    decision_color = {"promote": "green", "rollback": "red", "hold": "yellow"}[report["decision"]]
    console.print(
        f"\nDecision: [{decision_color}]{report['decision'].upper()}[/{decision_color}] — {report['reason']}"
    )
    console.print(f"Active version is now: [bold]{report['active_after']}[/bold]")
