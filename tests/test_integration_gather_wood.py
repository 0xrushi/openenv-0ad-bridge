"""Integration test: pick a worker and order it to gather wood.

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


def _http_get_json(url: str, timeout_s: float = 3.0) -> Dict[str, Any]:
    with urllib.request.urlopen(url, timeout=timeout_s) as resp:  # noqa: S310
        raw = resp.read().decode("utf-8")
    return json.loads(raw)


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


def _eval(openenv_base: str, code: str) -> Dict[str, Any]:
    """Run an OpenEnv evaluate action and return observation.result.

    Returns a dict containing either:
    - {ok:false, error:"..."}
    - {ok:true, result:<any>}
    """

    resp = _http_post_json(
        f"{openenv_base.rstrip('/')}/step",
        {"action": {"op": "evaluate", "code": code}},
        timeout_s=10.0,
    )
    obs = resp.get("observation")
    if not isinstance(obs, dict):
        return {"ok": False, "error": f"invalid_response: {resp!r}"}
    if obs.get("ok") is False:
        return {"ok": False, "error": obs.get("error")}
    return {"ok": True, "result": obs.get("result")}


def _has_resource_gatherer(openenv_base: str, entity_id: int) -> bool:
    code = (
        "(function(){"
        f"var id={int(entity_id)};"
        "var g=Engine.QueryInterface(id,IID_ResourceGatherer);"
        "return {ok:true, has: !!g};"
        "})()"
    )
    out = _eval(openenv_base, code)
    if not isinstance(out, dict) or out.get("ok") is False:
        return False
    res = out.get("result")
    return isinstance(res, dict) and res.get("has") is True


def _has_resource_supply(openenv_base: str, entity_id: int) -> bool:
    code = (
        "(function(){"
        f"var id={int(entity_id)};"
        "var s=Engine.QueryInterface(id,IID_ResourceSupply);"
        "return {ok:true, has: !!s};"
        "})()"
    )
    out = _eval(openenv_base, code)
    if not isinstance(out, dict) or out.get("ok") is False:
        return False
    res = out.get("result")
    return isinstance(res, dict) and res.get("has") is True


def _get_unit_orders(openenv_base: str, entity_id: int) -> Optional[list[dict]]:
    """Fetch UnitAI order queue for an entity (best-effort)."""

    code = (
        "(function(){"
        f"var id={int(entity_id)};"
        "var ai=Engine.QueryInterface(id,IID_UnitAI);"
        "if(!ai) return {ok:false, error:'no IID_UnitAI'};"
        "var orders=null;"
        "if(typeof ai.GetOrders==='function') orders=ai.GetOrders();"
        "else if(typeof ai.GetOrderQueue==='function') orders=ai.GetOrderQueue();"
        "return {ok:true, orders: orders};"
        "})()"
    )

    out = _eval(openenv_base, code)
    if not isinstance(out, dict) or out.get("ok") is False:
        return None
    res = out.get("result")
    if not isinstance(res, dict):
        return None
    orders = res.get("orders")
    if not isinstance(orders, list):
        return None
    return [o for o in orders if isinstance(o, dict)]


def _has_gather_order_targeting(
    openenv_base: str, entity_id: int, target_id: int
) -> bool:
    """Check whether UnitAI has a gather-like order targeting target_id."""

    orders = _get_unit_orders(openenv_base, entity_id)
    if not orders:
        return False
    for o in orders:
        t = o.get("type")
        if not (isinstance(t, str) and "gather" in t.lower()):
            continue
        # Order schema differs by engine/version; target is often stored as a number.
        # Target can show up in different shapes depending on engine.
        candidates = []
        candidates.append(o.get("target"))
        data = o.get("data")
        if isinstance(data, dict):
            candidates.append(data.get("target"))
            candidates.append(data.get("targetEnt"))
            candidates.append(data.get("targetEntity"))

        for c in candidates:
            if isinstance(c, bool):
                continue
            if isinstance(c, int) and c == target_id:
                return True
            if isinstance(c, str) and c.isdigit() and int(c) == target_id:
                return True
    return False


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


def _resource_gatherer_target(openenv_base: str, entity_id: int) -> Optional[int]:
    """Best-effort: return ResourceGatherer target entity id if accessible."""

    code = (
        "(function(){"
        f"var id={int(entity_id)};"
        "var g=Engine.QueryInterface(id,IID_ResourceGatherer);"
        "if(!g) return {ok:false, error:'no IID_ResourceGatherer'};"
        "var t=null;"
        "if(typeof g.GetTargetEntity==='function') t=g.GetTargetEntity();"
        "else if(typeof g.GetTarget==='function') t=g.GetTarget();"
        "return {ok:true, target:t};"
        "})()"
    )
    out = _eval(openenv_base, code)
    if not isinstance(out, dict) or out.get("ok") is False:
        return None
    res = out.get("result")
    if not isinstance(res, dict):
        return None
    t = res.get("target")
    if isinstance(t, bool):
        return None
    if isinstance(t, int):
        return t
    if isinstance(t, str) and t.isdigit():
        return int(t)
    return None


def _pick_builder_and_tree(
    snapshot: Dict[str, Any],
) -> Tuple[Optional[int], Optional[int], Optional[int]]:
    """Pick a plausible worker (builder) and a tree target from the stepper snapshot.

    Returns (player_id, builder_eid, tree_eid).
    """

    state = snapshot.get("state")
    if not isinstance(state, dict):
        return None, None, None
    entities = state.get("entities")
    if not isinstance(entities, dict):
        return None, None, None

    # Prefer player 1 if present.
    player_id: Optional[int] = None
    for _sid, ent in entities.items():
        if not isinstance(ent, dict):
            continue
        if ent.get("owner") == 1:
            player_id = 1
            break

    if player_id is None:
        for _sid, ent in entities.items():
            if not isinstance(ent, dict):
                continue
            owner = ent.get("owner")
            if isinstance(owner, int) and owner > 0:
                player_id = owner
                break

    if player_id is None:
        return None, None, None

    builders: list[int] = []
    trees: list[int] = []

    for sid, ent in entities.items():
        if not isinstance(ent, dict) or not str(sid).isdigit():
            continue
        eid = int(sid)
        owner = ent.get("owner")
        tpl = ent.get("template")

        if owner == player_id and isinstance(tpl, str) and "units/" in tpl:
            builders.append(eid)
        if owner == 0 and isinstance(tpl, str) and ("tree" in tpl and "gaia" in tpl):
            trees.append(eid)

    if not builders or not trees:
        return (
            player_id,
            (builders[0] if builders else None),
            (trees[0] if trees else None),
        )

    # Choose the nearest tree to the first builder position.
    builder = builders[0]
    bpos = _pos(snapshot, builder)
    if not bpos:
        return player_id, builder, trees[0]

    bx, bz = bpos
    best_tree = trees[0]
    best_d2: Optional[float] = None
    for tid in trees:
        tpos = _pos(snapshot, tid)
        if not tpos:
            continue
        tx, tz = tpos
        d2 = (tx - bx) * (tx - bx) + (tz - bz) * (tz - bz)
        if best_d2 is None or d2 < best_d2:
            best_d2 = d2
            best_tree = tid

    return player_id, builder, best_tree


@unittest.skipUnless(
    os.environ.get("RUN_ZEROAD_INTEGRATION") == "1",
    "Set RUN_ZEROAD_INTEGRATION=1 to run integration tests",
)
class TestIntegrationGatherWood(unittest.TestCase):
    def test_gather_wood_with_one_builder(self):
        api_base = os.environ.get("API_BASE", "http://127.0.0.1:8001").rstrip("/")
        snapshot_path = Path(
            os.environ.get("ZEROAD_STATE_OUT", "run/latest_state.json")
        ).expanduser()

        # Ensure proxy is reachable.
        health = _http_get_json(f"{api_base}/health")
        self.assertEqual(health.get("status"), "healthy")

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

        player_id, builder_eid, tree_eid = _pick_builder_and_tree(snap)
        if not (player_id and builder_eid and tree_eid):
            self.skipTest("Could not find candidate builder/tree ids in snapshot")

        # Ensure the chosen unit can gather and the target has supply.
        if not _has_resource_gatherer(api_base, builder_eid):
            self.skipTest(f"Entity {builder_eid} has no IID_ResourceGatherer")
        if not _has_resource_supply(api_base, tree_eid):
            self.skipTest(f"Entity {tree_eid} has no IID_ResourceSupply")

        # Send a gather command.
        resp = _http_post_json(
            f"{api_base}/step",
            {
                "action": {
                    "op": "push_command",
                    "player_id": player_id,
                    "cmd": {
                        "type": "gather",
                        "entities": [builder_eid],
                        "target": tree_eid,
                        "queued": False,
                    },
                }
            },
        )

        obs = resp.get("observation")
        if not isinstance(obs, dict):
            self.fail(f"Invalid OpenEnv response: {resp!r}")
        if obs.get("ok") is False:
            self.fail(f"OpenEnv rejected gather command: {obs.get('error')}")

        # Verify that UnitAI has a gather order targeting our tree.
        deadline2 = time.time() + 6
        while time.time() < deadline2:
            if _has_gather_order_targeting(api_base, builder_eid, tree_eid):
                break
            time.sleep(0.25)
        else:
            orders_dbg = _get_unit_orders(api_base, builder_eid)
            self.fail(
                "Gather accepted but UnitAI shows no gather order targeting the selected tree. "
                f"builder={builder_eid} tree={tree_eid} orders={orders_dbg}"
            )

        # Optional: check ResourceGatherer target if the component exposes it.
        tgt = _resource_gatherer_target(api_base, builder_eid)
        if tgt is not None and tgt != tree_eid:
            self.fail(
                f"Gather order was set but ResourceGatherer target != tree (target={tgt} tree={tree_eid})"
            )


if __name__ == "__main__":
    unittest.main()
