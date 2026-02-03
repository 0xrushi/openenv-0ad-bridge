"""Pick one worker and gather nearest metal mine (OpenEnv proxy).

Prereqs:
- Stepper running with snapshot export:
    export ZEROAD_STATE_OUT=run/latest_state.json
    python tools/execute_move.py --run
- OpenEnv proxy running:
    python tools/run_openenv_zero_ad_server.py --port=8001

Usage:
  API_BASE=http://127.0.0.1:8001 python tools/gather_nearest_metal.py --player-id 1
"""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


def _http_post_json(
    url: str, payload: Dict[str, Any], timeout_s: float = 10.0
) -> Dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"content-type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:  # noqa: S310
        raw = resp.read().decode("utf-8")
    return json.loads(raw)


def _load_snapshot(path: Path) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except Exception:
        return None


def _pos(snapshot: Dict[str, Any], entity_id: int) -> Optional[Tuple[float, float]]:
    state = snapshot.get("state")
    if not isinstance(state, dict):
        return None
    entities = state.get("entities")
    if not isinstance(entities, dict):
        return None
    ent = entities.get(str(entity_id))
    if not isinstance(ent, dict):
        return None
    p = ent.get("position")
    if isinstance(p, (list, tuple)) and len(p) >= 2:
        try:
            return float(p[0]), float(p[1])
        except Exception:
            return None
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--player-id", type=int, default=1)
    parser.add_argument(
        "--snapshot",
        default=os.environ.get("ZEROAD_STATE_OUT", "run/latest_state.json"),
    )
    parser.add_argument(
        "--api-base", default=os.environ.get("API_BASE", "http://127.0.0.1:8001")
    )
    parser.add_argument("--wait-s", type=float, default=20.0)
    args = parser.parse_args()

    api_base = args.api_base.rstrip("/")
    snap_path = Path(args.snapshot).expanduser()

    deadline = time.time() + args.wait_s
    snap: Optional[Dict[str, Any]] = None
    while time.time() < deadline:
        snap = _load_snapshot(snap_path)
        if snap and isinstance(snap.get("state"), dict):
            break
        time.sleep(0.25)

    if not snap:
        raise SystemExit(f"No snapshot found at {snap_path}")

    state = snap.get("state")
    entities = state.get("entities") if isinstance(state, dict) else None
    if not isinstance(entities, dict):
        raise SystemExit("Snapshot has no entities")

    worker_id: Optional[int] = None
    for sid, ent in entities.items():
        if not str(sid).isdigit() or not isinstance(ent, dict):
            continue
        if ent.get("owner") != args.player_id:
            continue
        tpl = ent.get("template")
        if not isinstance(tpl, str) or "units/" not in tpl:
            continue
        t = tpl.lower()
        if "citizen" in t or "female" in t or "worker" in t:
            worker_id = int(sid)
            break
    if worker_id is None:
        raise SystemExit(f"No worker-like unit found for player_id={args.player_id}")

    wpos = _pos(snap, worker_id)
    if not wpos:
        raise SystemExit(f"Worker {worker_id} has no position")
    wx, wz = wpos

    best: Optional[int] = None
    best_d2: Optional[float] = None
    for sid, ent in entities.items():
        if not str(sid).isdigit() or not isinstance(ent, dict):
            continue
        if ent.get("owner") != 0:
            continue
        tpl = ent.get("template")
        if not isinstance(tpl, str):
            continue
        t = tpl.lower()
        if "gaia" not in t:
            continue
        if "metal" not in t and "ore" not in t:
            continue
        tid = int(sid)
        tpos = _pos(snap, tid)
        if not tpos:
            continue
        tx, tz = tpos
        d2 = (tx - wx) * (tx - wx) + (tz - wz) * (tz - wz)
        if best_d2 is None or d2 < best_d2:
            best_d2 = d2
            best = tid

    if best is None:
        raise SystemExit("No metal mine found")

    print(f"worker={worker_id} metal={best} d2={best_d2}")
    resp = _http_post_json(
        f"{api_base}/step",
        {
            "action": {
                "op": "push_command",
                "player_id": args.player_id,
                "cmd": {
                    "type": "gather",
                    "entities": [worker_id],
                    "target": best,
                    "queued": False,
                },
            }
        },
    )
    print(json.dumps(resp, indent=2))


if __name__ == "__main__":
    main()
