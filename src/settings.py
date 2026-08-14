"""Central settings loaded from environment (.env) and config files."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT_DIR / "config"
DATA_DIR = ROOT_DIR / "data"
AGENT_VERSIONS_PATH = CONFIG_DIR / "agent_versions.json"
RUNS_DB_PATH = DATA_DIR / "runs.db"
CANARY_REPORTS_PATH = DATA_DIR / "canary_reports.jsonl"

load_dotenv(ROOT_DIR / ".env")

DATA_DIR.mkdir(exist_ok=True)


@dataclass(frozen=True)
class Settings:
    anthropic_api_key: str | None
    slack_webhook_url: str | None
    latency_alert_ms: float
    max_tool_iterations: int
    cost_alert_usd: float
    canary_min_success_rate: float
    canary_max_latency_regression: float
    phoenix_port: int


def get_settings() -> Settings:
    return Settings(
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY"),
        slack_webhook_url=os.environ.get("SLACK_WEBHOOK_URL") or None,
        latency_alert_ms=float(os.environ.get("LATENCY_ALERT_MS", 15000)),
        max_tool_iterations=int(os.environ.get("MAX_TOOL_ITERATIONS", 6)),
        cost_alert_usd=float(os.environ.get("COST_ALERT_USD", 0.50)),
        canary_min_success_rate=float(os.environ.get("CANARY_MIN_SUCCESS_RATE", 0.85)),
        canary_max_latency_regression=float(os.environ.get("CANARY_MAX_LATENCY_REGRESSION", 1.25)),
        phoenix_port=int(os.environ.get("PHOENIX_PORT", 6006)),
    )


def load_agent_versions() -> dict:
    with open(AGENT_VERSIONS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_agent_versions(data: dict) -> None:
    with open(AGENT_VERSIONS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def get_active_version_name() -> str:
    return load_agent_versions()["active"]


def get_version_config(name: str) -> dict:
    return load_agent_versions()["versions"][name]


def set_active_version(name: str) -> None:
    data = load_agent_versions()
    if name not in data["versions"]:
        raise ValueError(f"Unknown agent version: {name}")
    data["active"] = name
    save_agent_versions(data)
