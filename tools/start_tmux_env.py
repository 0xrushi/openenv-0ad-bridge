"""Start a tmux session with 0 A.D. RL + OpenEnv proxy.

This creates a tmux session with 4 panes:
  A) Launch 0 A.D. with RL interface enabled
  B) Stepper (keeps simulation advancing via /step)
  C) OpenEnv-format proxy server (FastAPI)
  D) Scratch pane (curl examples)

Requirements:
  - tmux installed
  - python -m pip install libtmux

Usage:
  python tools/start_tmux_env.py
  python tools/start_tmux_env.py --session=zero-ad --rl-port=6000 --api-port=8000
"""

from __future__ import annotations

import argparse
import socket
from pathlib import Path

import libtmux
from libtmux.constants import PaneDirection


def _sh(cmd: str) -> str:
    """Wrap command for bash -lc."""

    return f"bash -lc {cmd!r}"


def _maybe_source_venv(venv_activate: Path) -> str:
    """Return a shell prefix to activate venv if present."""

    if venv_activate.exists():
        return f"source {str(venv_activate)!r} && "
    return ""


def _split(target, vertical: bool):
    """Compatibility wrapper for libtmux split API.

    Newer libtmux versions removed `split_window()` in favor of `split()`.
    """

    # libtmux>=0.33 uses `split(direction=PaneDirection.*)`.
    if hasattr(target, "split"):
        # Historical compatibility: older libtmux used `vertical=True` to mean a
        # side-by-side split. Map that to RIGHT. Otherwise split BELOW.
        direction = PaneDirection.Right if vertical else PaneDirection.Below
        return target.split(direction=direction)

    # Older libtmux used `split_window(vertical=...)`.
    return target.split_window(vertical=vertical)


def _pick_free_port(host: str, preferred: int, max_tries: int = 50) -> int:
    """Pick a free TCP port starting at preferred.

    We avoid ports that already have a listener, even if it's not our server.
    This is intentionally conservative to prevent uvicorn bind failures.
    """

    port = preferred
    for _ in range(max_tries):
        # If something is already listening, skip.
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.settimeout(0.2)
            if probe.connect_ex((host, port)) == 0:
                port += 1
                continue

        # Try binding to confirm it's available.
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind((host, port))
            except OSError:
                port += 1
                continue
            return port
    raise SystemExit(f"Could not find a free port near {preferred} on {host}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--session", default="zero-ad")
    parser.add_argument("--rl-host", default="127.0.0.1")
    parser.add_argument("--rl-port", type=int, default=6000)
    parser.add_argument("--api-host", default="127.0.0.1")
    parser.add_argument("--api-port", type=int, default=8000)
    parser.add_argument(
        "--map",
        default="scenarios/arcadia",
        help="Autostart map (e.g. scenarios/arcadia, random/anatolian_plateau)",
    )
    parser.add_argument(
        "--civ",
        default=None,
        help="Force a civilization by selecting a civ-specific sandbox scenario (e.g. athen).",
    )
    parser.add_argument(
        "--no-kill", action="store_true", help="Do not kill an existing session"
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    venv_activate = project_root / ".venv" / "bin" / "activate"
    venv_prefix = _maybe_source_venv(venv_activate)

    rl_addr = f"{args.rl_host}:{args.rl_port}"
    rl_url = f"http://{args.rl_host}:{args.rl_port}"
    api_port = _pick_free_port(args.api_host, args.api_port)
    api_url = f"http://{args.api_host}:{api_port}"

    server = libtmux.Server()
    if server.has_session(args.session) and not args.no_kill:
        server.kill_session(args.session)

    session = server.new_session(args.session, attach=False)
    # libtmux removed `attached_window`/`attached_pane`; use active_*.
    window = session.active_window
    window.rename_window("zero-ad")

    pane_a = window.active_pane
    if pane_a is None:
        raise SystemExit("tmux window has no active pane")
    civ_arg = f" --civ={args.civ!r}" if args.civ else ""
    pane_a.send_keys(
        _sh(
            "set -e; "
            f"cd {str(project_root)!r} && "
            + venv_prefix
            + f"export ZEROAD_RL_INTERFACE={rl_addr!r} && "
            + f"python launcher.py --map={args.map!r}"
            + civ_arg
        )
    )

    pane_b = _split(window, vertical=True)
    if pane_b is None:
        raise SystemExit("tmux split returned no pane")
    pane_b.send_keys(
        _sh(
            "set -e; "
            f"cd {str(project_root)!r} && "
            + venv_prefix
            + f"export ZEROAD_RL_URL={rl_url!r} && "
            + "export ZEROAD_STEP_SLEEP=0.01 && "
            + "export ZEROAD_STATE_OUT=run/latest_state.json && "
            + "export ZEROAD_STATE_EVERY_N=10 && "
            + "echo 'Waiting for RL interface...'; "
            + f"until curl -sS -m 1 -X POST {rl_url}/evaluate --data '1+1' >/dev/null 2>&1; do sleep 0.5; done; "
            + "echo 'RL interface is up. Waiting for match init...'; sleep 2; "
            + "echo 'Starting stepper...'; "
            + "python tools/execute_move.py --run"
        )
    )

    pane_c = _split(pane_a, vertical=False)
    if pane_c is None:
        raise SystemExit("tmux split returned no pane")
    pane_c_cmd = (
        "set -e; "
        f"cd {str(project_root)!r} && "
        + venv_prefix
        + f"export ZEROAD_RL_URL={rl_url!r} && "
        + "echo 'Waiting for RL interface...'; "
        + f"until curl -sS -m 1 -X POST {rl_url}/evaluate --data '1+1' >/dev/null 2>&1; do sleep 0.5; done; "
        + "echo 'RL interface is up. Starting OpenEnv proxy...'; "
        + f"python tools/run_openenv_zero_ad_server.py --host={args.api_host} --port={api_port}"
    )
    pane_c.send_keys(_sh(pane_c_cmd))

    pane_d = _split(pane_b, vertical=False)
    if pane_d is None:
        raise SystemExit("tmux split returned no pane")
    # Start an interactive shell in pane D, then configure it explicitly.
    # Setting env vars inside a subshell isn't always reliable across shells,
    # so we send the setup commands directly to the pane.
    pane_d.send_keys("bash")
    pane_d.send_keys(f"cd {str(project_root)!r}")
    if venv_activate.exists():
        pane_d.send_keys(f"source {str(venv_activate)!r}")
    pane_d.send_keys(f"export API_BASE={api_url!r}")
    pane_d.send_keys(
        f"until curl -sS -m 1 {api_url}/health >/dev/null 2>&1; do sleep 0.5; done"
    )
    pane_d.send_keys("bash tools/openenv_examples.sh")

    window.select_layout("tiled")

    print(
        f"Session '{args.session}' started. Attach with: tmux attach -t {args.session}\n"
        f"RL interface: {rl_url}\n"
        f"OpenEnv proxy: {api_url} (requested {args.api_port})"
    )


if __name__ == "__main__":
    main()
