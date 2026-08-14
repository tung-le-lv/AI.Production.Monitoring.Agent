"""Streamlit dashboard: latency/cost trends, alerts, and canary vs stable
comparison for the production monitoring agent.

Run with: streamlit run src/dashboard/app.py
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pandas as pd  # noqa: E402
import plotly.express as px  # noqa: E402
import streamlit as st  # noqa: E402

from src.observability.metrics_store import fetch_alerts, fetch_runs  # noqa: E402
from src.settings import CANARY_REPORTS_PATH, load_agent_versions  # noqa: E402

# Fixed categorical color per entity identity, never cycled/reassigned.
VERSION_COLORS = {"stable": "#4C78A8", "canary": "#F58518"}
SEVERITY_ICON = {"critical": "🔴", "warning": "🟡"}

st.set_page_config(page_title="Production Monitoring Agent", layout="wide")


@st.cache_data(ttl=5)
def load_runs_df() -> pd.DataFrame:
    rows = fetch_runs(limit=2000)
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame([dict(r) for r in rows])
    df["dt"] = pd.to_datetime(df["ts"], unit="s")
    return df


@st.cache_data(ttl=5)
def load_alerts_df() -> pd.DataFrame:
    rows = fetch_alerts(limit=300)
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame([dict(r) for r in rows])
    df["dt"] = pd.to_datetime(df["ts"], unit="s")
    return df


def load_canary_reports() -> list[dict]:
    if not CANARY_REPORTS_PATH.exists():
        return []
    reports = []
    with open(CANARY_REPORTS_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                reports.append(json.loads(line))
    return reports


st.title("🩺 Production Monitoring Agent")

active_version = load_agent_versions()["active"]
st.caption(
    f"Live traffic is currently served by **{active_version}** "
    f"(model: `{load_agent_versions()['versions'][active_version]['model']}`)"
)

if st.button("Refresh"):
    st.cache_data.clear()

runs_df = load_runs_df()
alerts_df = load_alerts_df()

if runs_df.empty:
    st.info("No runs recorded yet. Run `python scripts/chat.py` or `python scripts/run_canary.py` first.")
    st.stop()

# ---------------------------------------------------------------------------
# KPI row
# ---------------------------------------------------------------------------
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total runs", len(runs_df))
col2.metric("Success rate", f"{runs_df['success'].mean():.0%}")
col3.metric("Avg latency", f"{runs_df['latency_ms'].mean():.0f} ms")
col4.metric("Total cost", f"${runs_df['cost_usd'].sum():.4f}")

# ---------------------------------------------------------------------------
# Latency & cost over time
# ---------------------------------------------------------------------------
st.subheader("Latency over time")
fig_latency = px.line(
    runs_df.sort_values("dt"),
    x="dt",
    y="latency_ms",
    color="agent_version",
    color_discrete_map=VERSION_COLORS,
    markers=True,
    labels={"dt": "Time", "latency_ms": "Latency (ms)", "agent_version": "Version"},
)
fig_latency.update_layout(hovermode="x unified")
st.plotly_chart(fig_latency, use_container_width=True)

st.subheader("Cost per run over time")
fig_cost = px.bar(
    runs_df.sort_values("dt"),
    x="dt",
    y="cost_usd",
    color="agent_version",
    color_discrete_map=VERSION_COLORS,
    labels={"dt": "Time", "cost_usd": "Cost (USD)", "agent_version": "Version"},
)
st.plotly_chart(fig_cost, use_container_width=True)

# ---------------------------------------------------------------------------
# Stable vs canary comparison (one metric = one axis per chart)
# ---------------------------------------------------------------------------
st.subheader("Stable vs canary")
by_version = runs_df.groupby("agent_version").agg(
    success_rate=("success", "mean"),
    loop_rate=("loop_detected", "mean"),
    avg_latency_ms=("latency_ms", "mean"),
    avg_cost_usd=("cost_usd", "mean"),
    n_runs=("id", "count"),
).reset_index()

cmp_col1, cmp_col2, cmp_col3 = st.columns(3)
with cmp_col1:
    fig = px.bar(
        by_version, x="agent_version", y="success_rate", color="agent_version",
        color_discrete_map=VERSION_COLORS, labels={"success_rate": "Success rate", "agent_version": "Version"},
    )
    fig.update_yaxes(range=[0, 1], tickformat=".0%")
    fig.update_layout(showlegend=False, title="Success rate")
    st.plotly_chart(fig, use_container_width=True)
with cmp_col2:
    fig = px.bar(
        by_version, x="agent_version", y="avg_latency_ms", color="agent_version",
        color_discrete_map=VERSION_COLORS, labels={"avg_latency_ms": "Avg latency (ms)", "agent_version": "Version"},
    )
    fig.update_layout(showlegend=False, title="Avg latency")
    st.plotly_chart(fig, use_container_width=True)
with cmp_col3:
    fig = px.bar(
        by_version, x="agent_version", y="avg_cost_usd", color="agent_version",
        color_discrete_map=VERSION_COLORS, labels={"avg_cost_usd": "Avg cost (USD)", "agent_version": "Version"},
    )
    fig.update_layout(showlegend=False, title="Avg cost / run")
    st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------
st.subheader("Alerts")
if alerts_df.empty:
    st.success("No alerts fired yet.")
else:
    display = alerts_df.copy()
    display["severity"] = display["severity"].map(lambda s: f"{SEVERITY_ICON.get(s, '')} {s}")
    display["when"] = display["dt"].dt.strftime("%Y-%m-%d %H:%M:%S")
    st.dataframe(
        display[["when", "severity", "kind", "message"]],
        use_container_width=True,
        hide_index=True,
    )

# ---------------------------------------------------------------------------
# Canary history
# ---------------------------------------------------------------------------
st.subheader("Canary evaluation history")
reports = load_canary_reports()
if not reports:
    st.info("No canary evaluations run yet. Run `python scripts/run_canary.py`.")
else:
    latest = reports[-1]
    decision_icon = {"promote": "✅", "rollback": "⏪", "hold": "⏸️"}[latest["decision"]]
    st.write(
        f"**Latest decision ({datetime.fromtimestamp(latest['timestamp']):%Y-%m-%d %H:%M:%S})**: "
        f"{decision_icon} {latest['decision'].upper()} — {latest['reason']}"
    )
    hist_rows = []
    for r in reports:
        hist_rows.append({
            "when": datetime.fromtimestamp(r["timestamp"]).strftime("%Y-%m-%d %H:%M:%S"),
            "decision": r["decision"],
            "stable success": f"{r['stable']['success_rate']:.0%}",
            "canary success": f"{r['canary']['success_rate']:.0%}",
            "stable latency": f"{r['stable']['avg_latency_ms']:.0f}ms",
            "canary latency": f"{r['canary']['avg_latency_ms']:.0f}ms",
            "active after": r["active_after"],
        })
    st.dataframe(pd.DataFrame(hist_rows), use_container_width=True, hide_index=True)
