"""Integration test: gather chicken, wood, stone, metal (best-effort).

This requires a running match, stepper snapshot export, and the OpenEnv proxy.
It is skipped unless RUN_ZEROAD_INTEGRATION=1.
"""

import json
import os
import time
import unittest
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


def _pick_worker(snapshot: Dict[str, Any], player_id: int) -> Optional[int]:
    state = snapshot.get("state")
    entities = state.get("entities") if isinstance(state, dict) else None
    if not isinstance(entities, dict):
        return None
    for sid, ent in entities.items():
        if not str(sid).isdigit() or not isinstance(ent, dict):
            continue
        if ent.get("owner") != player_id:
            continue
        tpl = ent.get("template")
        if not isinstance(tpl, str) or "units/" not in tpl:
            continue
        t = tpl.lower()
        if "citizen" in t or "female" in t or "worker" in t:
            return int(sid)
    return None


def _pick_workers(
    snapshot: Dict[str, Any], player_id: int, max_n: int = 4
) -> list[int]:
    state = snapshot.get("state")
    entities = state.get("entities") if isinstance(state, dict) else None
    if not isinstance(entities, dict):
        return []

    out: list[int] = []
    for sid, ent in entities.items():
        if len(out) >= max_n:
            break
        if not str(sid).isdigit() or not isinstance(ent, dict):
            continue
        if ent.get("owner") != player_id:
            continue
        tpl = ent.get("template")
        if not isinstance(tpl, str) or "units/" not in tpl:
            continue
        t = tpl.lower()
        if "citizen" in t or "female" in t or "worker" in t:
            out.append(int(sid))

    return out


def _pick_target(snapshot: Dict[str, Any], kind: str, worker_id: int) -> Optional[int]:
    state = snapshot.get("state")
    entities = state.get("entities") if isinstance(state, dict) else None
    if not isinstance(entities, dict):
        return None
    wpos = _pos(snapshot, worker_id)
    if not wpos:
        return None
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

        ok = False
        if kind == "chicken":
            ok = "chicken" in t
        elif kind == "wood":
            ok = "gaia" in t and "tree" in t
        elif kind == "stone":
            ok = "gaia" in t and ("stone" in t or "rock" in t)
        elif kind == "metal":
            ok = "gaia" in t and ("metal" in t or "ore" in t)
        else:
            raise ValueError(kind)

        if not ok:
            continue

        tid = int(sid)
        tpos = _pos(snapshot, tid)
        if not tpos:
            continue
        tx, tz = tpos
        d2 = (tx - wx) * (tx - wx) + (tz - wz) * (tz - wz)
        if best_d2 is None or d2 < best_d2:
            best_d2 = d2
            best = tid

    return best


@unittest.skipUnless(
    os.environ.get("RUN_ZEROAD_INTEGRATION") == "1",
    "Set RUN_ZEROAD_INTEGRATION=1 to run integration tests",
)
class TestIntegrationGatherAll(unittest.TestCase):
    def test_gather_all(self):
        api_base = os.environ.get("API_BASE", "http://127.0.0.1:8001").rstrip("/")
        snapshot_path = Path(
            os.environ.get("ZEROAD_STATE_OUT", "run/latest_state.json")
        ).expanduser()
        player_id = int(os.environ.get("ZEROAD_PID", "1"))

        # Wait for a usable snapshot.
        deadline = time.time() + 20
        snap: Optional[Dict[str, Any]] = None
        while time.time() < deadline:
            snap = _load_snapshot(snapshot_path)
            if snap and isinstance(snap.get("state"), dict):
                st = snap["state"]
                if (
                    isinstance(st, dict)
                    and isinstance(st.get("entities"), dict)
                    and st["entities"]
                ):
                    break
            time.sleep(0.25)
        if not snap:
            self.skipTest(f"No snapshot available at {snapshot_path}")

        workers = _pick_workers(snap, player_id, max_n=5)
        if not workers:
            worker = _pick_worker(snap, player_id)
            if worker is None:
                self.skipTest(f"No worker for player_id={player_id}")
            workers = [worker]

        kinds = ["chicken", "wood", "stone", "metal"]
        assignments: Dict[str, int] = {}
        for i, kind in enumerate(kinds):
            assignments[kind] = (
                workers[i] if len(workers) >= 4 else workers[i % len(workers)]
            )

        # Optional: 5th worker for a house build attempt.
        house_builder = workers[4] if len(workers) >= 5 else None

        for kind in kinds:
            # Refresh snapshot for target selection.
            snap2 = _load_snapshot(snapshot_path) or snap
            worker_id = assignments[kind]
            target = _pick_target(snap2, kind, worker_id)
            if target is None:
                continue

            resp = _http_post_json(
                f"{api_base}/step",
                {
                    "action": {
                        "op": "push_command",
                        "player_id": player_id,
                        "cmd": {
                            "type": "gather",
                            "entities": [worker_id],
                            "target": target,
                            "queued": False,
                        },
                    }
                },
            )
            obs = resp.get("observation")
            if not isinstance(obs, dict):
                self.fail(f"Invalid OpenEnv response: {resp!r}")
            if obs.get("ok") is False:
                self.fail(f"Rejected gather {kind}: {obs.get('error')}")

        # Best-effort construct command. We only assert the proxy doesn't reject the IDs.
        if house_builder is not None:
            resp = _http_post_json(
                f"{api_base}/step",
                {
                    "action": {
                        "op": "push_command",
                        "player_id": player_id,
                        "cmd": {
                            "type": "construct",
                            "entities": [house_builder],
                            "template": "structures/athen/house",
                            "x": 0,
                            "z": 0,
                            "angle": 0,
                            "queued": False,
                        },
                    }
                },
            )
            obs = resp.get("observation")
            if not isinstance(obs, dict):
                self.fail(f"Invalid OpenEnv response: {resp!r}")


if __name__ == "__main__":
    unittest.main()
