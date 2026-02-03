"""Walk one unit for a given player using the OpenEnv proxy.

This demonstrates an end-to-end flow where the first response (a snapshot written
by the stepper) is used to drive the next request (a `push_command` walk).

Prereqs:
- 0 A.D. running with RL interface enabled
- Stepper running with snapshot export enabled:
    export ZEROAD_STATE_OUT=run/latest_state.json
    export ZEROAD_STATE_EVERY_N=10
    python tools/execute_move.py --run
- OpenEnv proxy running:
    python tools/run_openenv_zero_ad_server.py --port=8001

Usage:
  API_BASE=http://127.0.0.1:8001 python tools/walk_one_player.py --player-id 1 --x 150 --z 200
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


def _pick_entity_id(snapshot: Dict[str, Any], player_id: int) -> Optional[int]:
    state = snapshot.get("state")
    if not isinstance(state, dict):
        return None

    entities = state.get("entities")
    if not isinstance(entities, dict):
        return None

    # Prefer likely units.
    best: list[int] = []
    fallback: list[int] = []
    for sid, ent in entities.items():
        if not isinstance(ent, dict):
            continue
        if ent.get("owner") != player_id:
            continue
        pos = ent.get("position")
        if not isinstance(pos, (list, tuple)) or len(pos) < 2:
            continue

        try:
            eid = int(sid)
        except Exception:
            continue

        tpl = ent.get("template")
        if isinstance(tpl, str) and ("units/" in tpl or tpl.startswith("units")):
            best.append(eid)
        else:
            fallback.append(eid)

    if best:
        return best[0]
    if fallback:
        return fallback[0]
    return None


def _entity_info(
    snapshot: Dict[str, Any], entity_id: int
) -> Tuple[Optional[int], Optional[Any], Optional[str]]:
    state = snapshot.get("state")
    if not isinstance(state, dict):
        return None, None, None
    entities = state.get("entities")
    if not isinstance(entities, dict):
        return None, None, None
    ent = entities.get(str(entity_id))
    if not isinstance(ent, dict):
        return None, None, None
    return ent.get("owner"), ent.get("position"), ent.get("template")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--player-id", type=int, default=1)
    parser.add_argument("--x", type=float, default=150)
    parser.add_argument("--z", type=float, default=200)
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
    snapshot: Optional[Dict[str, Any]] = None
    while time.time() < deadline:
        snapshot = _load_snapshot(snap_path)
        if snapshot and isinstance(snapshot.get("state"), dict):
            break
        time.sleep(0.25)

    if not snapshot:
        raise SystemExit(
            f"No snapshot found at {snap_path} (set ZEROAD_STATE_OUT and run the stepper)"
        )

    eid = _pick_entity_id(snapshot, args.player_id)
    if not eid:
        raise SystemExit(
            f"No movable entity found for player_id={args.player_id} in snapshot {snap_path}"
        )

    owner, pos, tpl = _entity_info(snapshot, eid)
    print(f"Selected entity id={eid} owner={owner} pos={pos} template={tpl}")

    action = {
        "op": "push_command",
        "player_id": args.player_id,
        "cmd": {
            "type": "walk",
            "entities": [eid],
            "x": args.x,
            "z": args.z,
            "queued": False,
            "pushFront": True,
        },
    }

    resp = _http_post_json(f"{api_base}/step", {"action": action})
    print(json.dumps(resp, indent=2))


if __name__ == "__main__":
    main()
