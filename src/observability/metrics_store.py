"""SQLite-backed store for per-run metrics and alerts.

Kept deliberately simple (stdlib sqlite3, no ORM) since this is a single-writer
local monitoring setup, not a production telemetry backend.
"""
from __future__ import annotations

import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass, field

from src.settings import RUNS_DB_PATH

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    run_type TEXT NOT NULL,        -- 'interactive' | 'canary'
    agent_version TEXT NOT NULL,   -- 'stable' | 'canary'
    model TEXT NOT NULL,
    prompt TEXT NOT NULL,
    success INTEGER NOT NULL,
    error_message TEXT,
    latency_ms REAL NOT NULL,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    cost_usd REAL NOT NULL,
    iteration_count INTEGER NOT NULL,
    tool_call_count INTEGER NOT NULL,
    loop_detected INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    run_id INTEGER,
    severity TEXT NOT NULL,   -- 'warning' | 'critical'
    kind TEXT NOT NULL,       -- 'failure' | 'loop' | 'latency' | 'cost'
    message TEXT NOT NULL
);
"""


@contextmanager
def _connect():
    conn = sqlite3.connect(RUNS_DB_PATH)
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.executescript(_SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


@dataclass
class RunRecord:
    run_type: str
    agent_version: str
    model: str
    prompt: str
    success: bool
    latency_ms: float
    input_tokens: int
    output_tokens: int
    cost_usd: float
    iteration_count: int
    tool_call_count: int
    loop_detected: bool
    error_message: str | None = None
    ts: float = field(default_factory=time.time)


def record_run(run: RunRecord) -> int:
    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO runs (
                ts, run_type, agent_version, model, prompt, success, error_message,
                latency_ms, input_tokens, output_tokens, cost_usd,
                iteration_count, tool_call_count, loop_detected
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run.ts,
                run.run_type,
                run.agent_version,
                run.model,
                run.prompt,
                int(run.success),
                run.error_message,
                run.latency_ms,
                run.input_tokens,
                run.output_tokens,
                run.cost_usd,
                run.iteration_count,
                run.tool_call_count,
                int(run.loop_detected),
            ),
        )
        return cur.lastrowid


def record_alert(run_id: int | None, severity: str, kind: str, message: str) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO alerts (ts, run_id, severity, kind, message) VALUES (?, ?, ?, ?, ?)",
            (time.time(), run_id, severity, kind, message),
        )


def fetch_runs(limit: int = 500) -> list[sqlite3.Row]:
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute(
            "SELECT * FROM runs ORDER BY ts DESC LIMIT ?", (limit,)
        ).fetchall()


def fetch_alerts(limit: int = 200) -> list[sqlite3.Row]:
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute(
            "SELECT * FROM alerts ORDER BY ts DESC LIMIT ?", (limit,)
        ).fetchall()
