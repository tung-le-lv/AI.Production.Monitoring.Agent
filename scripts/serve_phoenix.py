"""Start a persistent local Arize Phoenix server (trace storage + UI).

Run this once in its own terminal before (or alongside) `chat.py` /
`run_canary.py`. Trace data persists under data/phoenix/ across restarts.

Usage:
    python scripts/serve_phoenix.py
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.settings import DATA_DIR, get_settings  # noqa: E402

settings = get_settings()
working_dir = DATA_DIR / "phoenix"
working_dir.mkdir(parents=True, exist_ok=True)

env = os.environ.copy()
env["PHOENIX_WORKING_DIR"] = str(working_dir)
env["PHOENIX_PORT"] = str(settings.phoenix_port)
env.setdefault("PYTHONUTF8", "1")  # avoid cp1252 crashes on Windows consoles

print(f"Starting Arize Phoenix at http://localhost:{settings.phoenix_port}")
print(f"Trace data persisted at: {working_dir}")
print("Leave this running; Ctrl+C to stop.\n")

subprocess.run([sys.executable, "-m", "phoenix.server.main", "serve"], env=env, check=False)
