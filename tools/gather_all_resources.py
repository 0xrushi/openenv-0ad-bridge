"""Issue gather commands for multiple resource types (OpenEnv proxy).

This is an integration-style script meant to demonstrate end-to-end API control.
It does NOT step the simulation; run the stepper separately.

Flow:
1) Read the omniscient snapshot written by the stepper (`ZEROAD_STATE_OUT`).
2) Pick one worker unit for `--player-id`.
3) Pick a target entity for each resource type by template heuristics.
4) Send `push_command` gather orders via the OpenEnv proxy.

Prereqs:
- Stepper running with snapshot export:
    export ZEROAD_STATE_OUT=run/latest_state.json
    python tools/execute_move.py --run
- OpenEnv proxy running:
    python tools/run_openenv_zero_ad_server.py --port=8001

Usage:
  API_BASE=http://127.0.0.1:8001 python tools/gather_all_resources.py --player-id 1
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
    """Return (x,z) position for an entity from the stepper snapshot."""

    state = snapshot.get("state")
    entities = state.get("entities") if isinstance(state, dict) else None
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

    # Fallback: any unit for this player.
    for sid, ent in entities.items():
        if not str(sid).isdigit() or not isinstance(ent, dict):
            continue
        if ent.get("owner") != player_id:
            continue
        tpl = ent.get("template")
        if isinstance(tpl, str) and "units/" in tpl:
            return int(sid)

    return None


def _pick_workers(
    snapshot: Dict[str, Any], player_id: int, max_n: int = 4
) -> list[int]:
    """Pick up to max_n worker-like unit ids for player_id."""

    state = snapshot.get("state")
    entities = state.get("entities") if isinstance(state, dict) else None
    if not isinstance(entities, dict):
        return []

    workers: list[int] = []
    for sid, ent in entities.items():
        if len(workers) >= max_n:
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
            workers.append(int(sid))

    # Fallback: any units if no explicit workers found.
    if not workers:
        for sid, ent in entities.items():
            if len(workers) >= max_n:
                break
            if not str(sid).isdigit() or not isinstance(ent, dict):
                continue
            if ent.get("owner") != player_id:
                continue
            tpl = ent.get("template")
            if isinstance(tpl, str) and "units/" in tpl:
                workers.append(int(sid))

    return workers


def _pick_target(
    snapshot: Dict[str, Any], kind: str, near_entity_id: Optional[int] = None
) -> Optional[int]:
    """Pick a resource target by template heuristics.

    If near_entity_id is provided and has a position, chooses the nearest
    matching target by distance.
    """

    state = snapshot.get("state")
    entities = state.get("entities") if isinstance(state, dict) else None
    if not isinstance(entities, dict):
        return None

    kind = kind.lower()

    near_pos: Optional[Tuple[float, float]] = None
    if near_entity_id is not None:
        near_pos = _pos(snapshot, near_entity_id)

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

        match = False
        if kind == "chicken":
            match = "chicken" in t
        elif kind == "wood":
            match = "tree" in t and "gaia" in t
        elif kind == "metal":
            match = ("metal" in t or "ore" in t) and "gaia" in t
        elif kind == "stone":
            match = ("stone" in t or "rock" in t) and "gaia" in t
        else:
            raise ValueError(f"unknown resource kind: {kind}")

        if not match:
            continue

        tid = int(sid)
        if not near_pos:
            return tid

        tpos = _pos(snapshot, tid)
        if not tpos:
            continue
        wx, wz = near_pos
        tx, tz = tpos
        d2 = (tx - wx) * (tx - wx) + (tz - wz) * (tz - wz)
        if best_d2 is None or d2 < best_d2:
            best_d2 = d2
            best = tid

    return best


def _send_gather(
    api_base: str, player_id: int, worker_id: int, target_id: int
) -> Dict[str, Any]:
    return _http_post_json(
        f"{api_base}/step",
        {
            "action": {
                "op": "push_command",
                "player_id": player_id,
                "cmd": {
                    "type": "gather",
                    "entities": [worker_id],
                    "target": target_id,
                    "queued": False,
                },
            }
        },
    )


def _eval(api_base: str, code: str) -> Dict[str, Any]:
    """Run an OpenEnv evaluate action."""

    return _http_post_json(
        f"{api_base}/step",
        {"action": {"op": "evaluate", "code": code}},
        timeout_s=10.0,
    )


def _player_civ(api_base: str, player_id: int) -> Optional[str]:
    """Best-effort: fetch the civ string for player_id."""

    code = (
        "(function(){"
        "var pm=Engine.QueryInterface(SYSTEM_ENTITY, IID_PlayerManager);"
        "if(!pm) return {ok:false, error:'no IID_PlayerManager'};"
        f"var pid={int(player_id)};"
        "var ent=pm.GetPlayerByID(pid);"
        "var p=Engine.QueryInterface(ent, IID_Player);"
        "if(!p) return {ok:false, error:'no IID_Player'};"
        "var civ = (typeof p.GetCiv === 'function') ? p.GetCiv() : null;"
        "return {ok:true, civ:civ};"
        "})()"
    )
    resp = _eval(api_base, code)
    obs = resp.get("observation") if isinstance(resp, dict) else None
    if not isinstance(obs, dict) or obs.get("ok") is False:
        return None
    result = obs.get("result")
    if isinstance(result, dict) and isinstance(result.get("civ"), str):
        return result["civ"]
    return None


def _send_construct_house(
    api_base: str,
    player_id: int,
    builder_id: int,
    x: float,
    z: float,
    template: str,
    angle: float = 0.0,
) -> Dict[str, Any]:
    return _http_post_json(
        f"{api_base}/step",
        {
            "action": {
                "op": "push_command",
                "player_id": player_id,
                "cmd": {
                    "type": "construct",
                    "entities": [builder_id],
                    "template": template,
                    "x": x,
                    "z": z,
                    "angle": angle,
                    "queued": False,
                },
            }
        },
    )


def _send_repair(
    api_base: str,
    player_id: int,
    builder_id: int,
    target_id: int,
    autocontinue: bool = True,
    queued: bool = False,
) -> Dict[str, Any]:
    """Order builders to build a foundation (repair is used for building)."""

    return _http_post_json(
        f"{api_base}/step",
        {
            "action": {
                "op": "push_command",
                "player_id": player_id,
                "cmd": {
                    "type": "repair",
                    "entities": [builder_id],
                    "target": target_id,
                    "autocontinue": autocontinue,
                    "queued": queued,
                },
            }
        },
    )


def _find_new_house_like_entity(
    snapshot: Dict[str, Any],
    player_id: int,
    near_x: float,
    near_z: float,
    max_dist: float = 80.0,
) -> Optional[int]:
    """Best-effort: detect a newly placed house/foundation near (near_x, near_z)."""

    state = snapshot.get("state")
    entities = state.get("entities") if isinstance(state, dict) else None
    if not isinstance(entities, dict):
        return None
    max_d2 = max_dist * max_dist
    for sid, ent in entities.items():
        if not str(sid).isdigit() or not isinstance(ent, dict):
            continue
        if ent.get("owner") != player_id:
            continue
        tpl = ent.get("template")
        if not isinstance(tpl, str):
            continue
        t = tpl.lower()
        if "house" not in t:
            continue
        p = ent.get("position")
        if not (isinstance(p, (list, tuple)) and len(p) >= 2):
            continue
        try:
            ex, ez = float(p[0]), float(p[1])
        except Exception:
            continue
        d2 = (ex - near_x) * (ex - near_x) + (ez - near_z) * (ez - near_z)
        if d2 <= max_d2:
            return int(sid)
    return None


def _find_house_foundation_entity(
    snapshot: Dict[str, Any],
    player_id: int,
    near_x: float,
    near_z: float,
    max_dist: float = 80.0,
) -> Optional[int]:
    """Best-effort: find a house foundation near (near_x, near_z)."""

    state = snapshot.get("state")
    entities = state.get("entities") if isinstance(state, dict) else None
    if not isinstance(entities, dict):
        return None
    max_d2 = max_dist * max_dist
    for sid, ent in entities.items():
        if not str(sid).isdigit() or not isinstance(ent, dict):
            continue
        if ent.get("owner") != player_id:
            continue
        tpl = ent.get("template")
        if not isinstance(tpl, str):
            continue
        t = tpl.lower()
        if "foundation" not in t:
            continue
        if "house" not in t:
            continue
        p = ent.get("position")
        if not (isinstance(p, (list, tuple)) and len(p) >= 2):
            continue
        try:
            ex, ez = float(p[0]), float(p[1])
        except Exception:
            continue
        d2 = (ex - near_x) * (ex - near_x) + (ez - near_z) * (ez - near_z)
        if d2 <= max_d2:
            return int(sid)
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--player-id", type=int, default=1)
    parser.add_argument(
        "--api-base", default=os.environ.get("API_BASE", "http://127.0.0.1:8001")
    )
    parser.add_argument(
        "--snapshot",
        default=os.environ.get("ZEROAD_STATE_OUT", "run/latest_state.json"),
    )
    parser.add_argument("--wait-s", type=float, default=20.0)
    parser.add_argument("--pause-s", type=float, default=2.0)
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

    workers = _pick_workers(snap, args.player_id, max_n=5)
    if not workers:
        raise SystemExit(f"No worker-like unit found for player_id={args.player_id}")

    # If we have 4+ villagers, assign one per resource. Otherwise reuse workers.
    kinds = ["chicken", "wood", "stone", "metal"]
    assignments: Dict[str, int] = {}
    for i, kind in enumerate(kinds):
        assignments[kind] = (
            workers[i] if len(workers) >= 4 else workers[i % len(workers)]
        )

    house_builder: Optional[int] = workers[4] if len(workers) >= 5 else None

    print(f"player_id={args.player_id} workers={workers}")
    print("assignments:")
    for kind in kinds:
        print(f"  {kind}: worker={assignments[kind]}")
    if house_builder is not None:
        print(f"  house: worker={house_builder}")

    for kind in kinds:
        # Refresh snapshot each time (IDs remain stable within a match, but this
        # makes the selection more robust early-game).
        snap2 = _load_snapshot(snap_path) or snap
        worker_id = assignments[kind]
        target = _pick_target(snap2, kind, near_entity_id=worker_id)
        if target is None:
            print(f"{kind}: target not found (skipping)")
            continue

        print(f"{kind}: worker={worker_id} target={target} -> gather")
        resp = _send_gather(api_base, args.player_id, worker_id, target)
        print(json.dumps(resp, indent=2))
        time.sleep(args.pause_s)

    # If we have a 5th villager, try building a house.
    if house_builder is None:
        return

    snap3 = _load_snapshot(snap_path) or snap
    bpos = _pos(snap3, house_builder)
    if not bpos:
        print("house: builder has no position (skipping)")
        return

    civ = os.environ.get("ZEROAD_HOUSE_CIV") or _player_civ(api_base, args.player_id)
    template = os.environ.get("ZEROAD_HOUSE_TEMPLATE")
    if not template:
        # 0 A.D. public mod uses civ subfolders: structures/<civ>/house
        template = f"structures/{civ}/house" if civ else "structures/athen/house"

    bx, bz = bpos
    offsets = [
        (15, 0),
        (0, 15),
        (-15, 0),
        (0, -15),
        (20, 20),
        (-20, 20),
        (20, -20),
        (-20, -20),
        (30, 0),
        (0, 30),
    ]

    placed = False
    for dx, dz in offsets:
        x = bx + dx
        z = bz + dz
        print(f"house: trying template={template} at ({x:.1f}, {z:.1f})")
        resp = _send_construct_house(
            api_base, args.player_id, house_builder, x, z, template
        )
        print(json.dumps(resp, indent=2))
        time.sleep(args.pause_s)

        snap4 = _load_snapshot(snap_path)
        if (
            snap4
            and _find_new_house_like_entity(snap4, args.player_id, x, z) is not None
        ):
            placed = True
            print("house: detected a house-like entity near placement")

            foundation_id = _find_house_foundation_entity(snap4, args.player_id, x, z)
            if foundation_id is not None:
                print(f"house: foundation={foundation_id} -> repair(build)")
                rep = _send_repair(
                    api_base, args.player_id, house_builder, foundation_id
                )
                print(json.dumps(rep, indent=2))
            break

    if not placed:
        print(
            "house: sent construct commands, but did not detect a house in the snapshot. "
            "This may still have succeeded (or placement/template may be invalid). "
            "Try setting ZEROAD_HOUSE_TEMPLATE=structures/<civ>/house."
        )


if __name__ == "__main__":
    main()
