"""Run the OpenEnv-format proxy server for 0 A.D. RL interface.

Example:
  export ZEROAD_RL_URL=http://127.0.0.1:6000
  python tools/run_openenv_zero_ad_server.py --host=127.0.0.1 --port=8000

Then in another terminal run your stepper:
  python tools/execute_move.py --run

Server endpoints:
  POST /reset
  POST /step
  GET  /state
  GET  /schema
  GET  /health
  WS   /ws
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import uvicorn


def main() -> None:
    # When executed as `python tools/...`, Python's import path defaults to the
    # `tools/` directory. Add the repo root so `openenv_zero_ad` is importable.
    project_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(project_root))

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()

    from openenv_zero_ad.server import app

    # Passing an app object avoids import-path issues.
    # If you need autoreload, prefer running uvicorn directly:
    #   PYTHONPATH=. uvicorn openenv_zero_ad.server:app --reload
    uvicorn.run(app, host=args.host, port=args.port, reload=False, log_level="info")


if __name__ == "__main__":
    main()
