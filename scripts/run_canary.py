"""Run a canary evaluation: stable vs canary agent versions across the eval
suite, then automatically promote or roll back the active version.

Usage:
    python scripts/run_canary.py               # 1 pass per prompt per version
    python scripts/run_canary.py --iterations 3 # more samples, steadier signal
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rich.console import Console  # noqa: E402

from src.canary.runner import run_canary_evaluation  # noqa: E402
from src.observability.tracing import setup_tracing  # noqa: E402
from src.settings import get_settings  # noqa: E402

console = Console()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=1, help="Repeats per prompt per version")
    args = parser.parse_args()

    settings = get_settings()
    if not settings.anthropic_api_key:
        console.print(
            "[red]ANTHROPIC_API_KEY is not set.[/red] Copy .env.example to .env and add your key."
        )
        raise SystemExit(1)

    url = setup_tracing(settings.phoenix_port)
    console.print(f"Phoenix trace UI: [link={url}]{url}[/link]\n")

    run_canary_evaluation(iterations=args.iterations)


if __name__ == "__main__":
    main()
