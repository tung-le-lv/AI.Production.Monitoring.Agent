"""Interactive REPL for the monitored agent.

Usage:
    python scripts/chat.py             # talk to whichever version is active
    python scripts/chat.py --version canary
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rich.console import Console  # noqa: E402

from src.agent.runner import run_agent  # noqa: E402
from src.observability.tracing import setup_tracing  # noqa: E402
from src.settings import get_active_version_name, get_settings  # noqa: E402

console = Console()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", choices=["stable", "canary"], default=None)
    args = parser.parse_args()

    settings = get_settings()
    if not settings.anthropic_api_key:
        console.print(
            "[red]ANTHROPIC_API_KEY is not set.[/red] Copy .env.example to .env and add your key."
        )
        raise SystemExit(1)

    url = setup_tracing(settings.phoenix_port)
    version = args.version or get_active_version_name()
    console.print(f"[bold]Production Monitoring Agent[/bold] — talking to version: [cyan]{version}[/cyan]")
    console.print(f"Phoenix trace UI: [link={url}]{url}[/link]")
    console.print("Type a message and press enter. Ctrl+C to quit.\n")

    while True:
        try:
            prompt = console.input("[bold green]you>[/bold green] ")
        except (EOFError, KeyboardInterrupt):
            break
        if not prompt.strip():
            continue

        result = run_agent(prompt, version_name=version, run_type="interactive")
        if result["success"]:
            console.print(f"[bold blue]agent>[/bold blue] {result['answer']}")
        else:
            console.print(f"[red]agent error>[/red] {result['error']}")

        console.print(
            f"[dim]latency={result['latency_ms']:.0f}ms  "
            f"tokens_in={result['input_tokens']} tokens_out={result['output_tokens']}  "
            f"cost=${result['cost_usd']:.4f}  iterations={result['iteration_count']}  "
            f"tool_calls={result['tool_call_count']}[/dim]\n"
        )


if __name__ == "__main__":
    main()
