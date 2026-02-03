#!/usr/bin/env python3
"""Execute a move command in a running 0 A.D. match via the RL interface.

Usage:
  python tools/execute_move.py --run                  # keep simulation running
  python tools/execute_move.py --reveal               # reveal entire map
  python tools/execute_move.py --list                 # list player 1 entities
  python tools/execute_move.py --list --player=2      # list player 2 entities
  python tools/execute_move.py 186 480 360            # move + step 50 turns
  python tools/execute_move.py 186 480 360 --steps=200
  python tools/execute_move.py --diag                 # diagnostics

IMPORTANT: When --rl-interface is enabled, 0 A.D. only advances the
simulation through /step calls.  The game will appear frozen until
something calls /step.  Use --run in a separate terminal to keep the
simulation ticking so you can play normally and see AI activity.

Requirements:
  ZEROAD_RL_INTERFACE=127.0.0.1:6000 python launcher.py
"""

import sys
import time
from pathlib import Path
import os
import json
from urllib.error import URLError

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
from hannibal_api.parsing import parse_entity_ids
from hannibal_api.rl_interface_client import RLInterfaceClient


def reveal_map(client):
    """Reveal the entire map (disable fog of war and shroud) for all players."""
    print("Revealing map for all players...")
    try:
        result = client.evaluate(
            "(function(){"
            "var cmpRangeManager = Engine.QueryInterface(SYSTEM_ENTITY, IID_RangeManager);"
            "if (!cmpRangeManager) return JSON.stringify({error:'no IID_RangeManager'});"
            "cmpRangeManager.SetLosRevealAll(-1, true);"
            "return JSON.stringify({ok:true, msg:'map revealed for all players'});"
            "})()"
        )
        print(f"  Result: {result}")
    except Exception as e:
        print(f"  Failed: {e}")


def list_entities(client, player_filter):
    """List entities for a given player by doing one /step and reading state."""
    print(f"Fetching entities (player={player_filter})...")
    try:
        state = client.step([])
        entities = state.get("entities", {}) if isinstance(state, dict) else {}
        units = []
        structures = []
        for eid, ent in entities.items():
            owner = ent.get("owner", -1)
            if player_filter != -1 and owner != player_filter:
                continue
            tpl = ent.get("template", "?")
            pos = ent.get("position", None)
            pos_str = f"({pos[0]:.0f}, {pos[1]:.0f})" if pos else "(no pos)"
            entry = f"  {eid:>5}  owner={owner}  {pos_str:>16}  {tpl}"
            if "units/" in tpl:
                units.append(entry)
            else:
                structures.append(entry)

        if structures:
            print(f"\nStructures ({len(structures)}):")
            for s in structures:
                print(s)
        if units:
            print(f"\nUnits ({len(units)}):")
            for u in units:
                print(u)
        if not units and not structures:
            print("  No entities found for that player.")
        print(f"\nTotal: {len(units)} units, {len(structures)} structures")
    except Exception as e:
        print(f"  Failed: {e}")


def diagnose(client):
    """Check whether the simulation is reachable and advancing."""
    print("--- Diagnostics ---")

    try:
        raw = client.evaluate("1+1")
        print(f"  /evaluate basic test: 1+1 = {raw}")
    except Exception as e:
        print(f"  /evaluate FAILED: {e}")
        return

    try:
        time_info = client.evaluate(
            "(function(){"
            "var cmpTimer = Engine.QueryInterface(SYSTEM_ENTITY, IID_Timer);"
            "if (!cmpTimer) return JSON.stringify({error:'no IID_Timer'});"
            "var t = typeof cmpTimer.GetTime === 'function' ? cmpTimer.GetTime() : -1;"
            "return JSON.stringify({time: t});"
            "})()"
        )
        print(f"  Simulation time: {time_info}")
    except Exception as e:
        print(f"  Time query failed: {e}")

    print("  Calling /step with empty commands...")
    try:
        state = client.step([])
        entities = state.get("entities", {}) if isinstance(state, dict) else {}
        print(f"  /step returned: {len(entities)} entities")
        count = 0
        for eid, ent in entities.items():
            if count >= 5:
                print(f"  ... and {len(entities) - 5} more")
                break
            pos = ent.get("position", "?")
            owner = ent.get("owner", "?")
            tpl = ent.get("template", "?")
            print(f"  Entity {eid}: owner={owner} pos={pos} template={tpl}")
            count += 1
    except Exception as e:
        print(f"  /step FAILED: {e}")

    try:
        time_info2 = client.evaluate(
            "(function(){"
            "var cmpTimer = Engine.QueryInterface(SYSTEM_ENTITY, IID_Timer);"
            "if (!cmpTimer) return JSON.stringify({error:'no IID_Timer'});"
            "var t = typeof cmpTimer.GetTime === 'function' ? cmpTimer.GetTime() : -1;"
            "return JSON.stringify({time: t});"
            "})()"
        )
        print(f"  Simulation time after /step: {time_info2}")
    except Exception as e:
        print(f"  Time query 2 failed: {e}")

    print("--- End Diagnostics ---")


def run_simulation(client):
    """Keep the simulation advancing by calling /step in a loop.

    This is required because --rl-interface pauses the normal game loop.
    Run this in a terminal to make the game playable (click-to-move works,
    AI runs, etc.).  Ctrl+C to stop.
    """
    print("Simulation runner: calling /step continuously. Ctrl+C to stop.")
    print("  The game should now be playable -- click to move units, AI will run.")
    step_count = 0
    sleep_s = float(os.environ.get("ZEROAD_STEP_SLEEP", "0.005"))

    state_out = os.environ.get("ZEROAD_STATE_OUT")
    state_every_n = int(os.environ.get("ZEROAD_STATE_EVERY_N", "10"))
    state_out_path = Path(state_out).expanduser() if state_out else None
    if state_out_path:
        state_out_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        while True:
            try:
                state = client.step([])
                step_count += 1
                if step_count % 100 == 0:
                    print(f"  ... {step_count} steps")

                if (
                    state_out_path
                    and state_every_n > 0
                    and step_count % state_every_n == 0
                    and isinstance(state, dict)
                ):
                    # Snapshot export so external agents can observe without
                    # calling /step themselves.
                    tmp = state_out_path.with_suffix(state_out_path.suffix + ".tmp")
                    payload = {"step": step_count, "time": time.time(), "state": state}
                    tmp.write_text(json.dumps(payload), encoding="utf-8")
                    tmp.replace(state_out_path)
            except Exception as e:
                # If the game is still starting up or the RL server stalls,
                # don't exit the runner; keep retrying.
                print(f"  step error: {e}")
                time.sleep(0.5)
                continue

            # Sleep controls simulation speed. Default is ~5ms.
            time.sleep(sleep_s)
    except KeyboardInterrupt:
        print(f"\nStopped after {step_count} steps.")


def parse_flag(args, prefix):
    """Extract --flag=VALUE from args list."""
    for arg in args:
        if arg.startswith(prefix):
            return arg.split("=", 1)[1]
    return None


def main():
    url = os.environ.get("ZEROAD_RL_URL") or "http://127.0.0.1:6000"
    client = RLInterfaceClient(url)

    if len(sys.argv) >= 2 and sys.argv[1] == "--diag":
        try:
            diagnose(client)
        except URLError as e:
            print(f"Error: RL interface not reachable at {url}: {e}")
            raise SystemExit(2)
        return

    if len(sys.argv) >= 2 and sys.argv[1] == "--run":
        try:
            run_simulation(client)
        except URLError as e:
            print(f"Error: RL interface not reachable at {url}: {e}")
            raise SystemExit(2)
        return

    if len(sys.argv) >= 2 and sys.argv[1] == "--reveal":
        try:
            reveal_map(client)
        except URLError as e:
            print(f"Error: RL interface not reachable at {url}: {e}")
            raise SystemExit(2)
        return

    if len(sys.argv) >= 2 and sys.argv[1] == "--list":
        player = int(parse_flag(sys.argv[2:], "--player=") or "1")
        try:
            list_entities(client, player)
        except URLError as e:
            print(f"Error: RL interface not reachable at {url}: {e}")
            raise SystemExit(2)
        return

    if len(sys.argv) < 4:
        print("Usage:")
        print(
            "  python tools/execute_move.py --run                  # keep game ticking"
        )
        print(
            "  python tools/execute_move.py --reveal               # reveal whole map"
        )
        print(
            "  python tools/execute_move.py --list                 # list player 1 units"
        )
        print(
            "  python tools/execute_move.py --list --player=2      # list player 2 units"
        )
        print("  python tools/execute_move.py <ids> <x> <z>          # move entities")
        print("  python tools/execute_move.py <ids> <x> <z> --steps=200")
        print("  python tools/execute_move.py --diag                 # diagnostics")
        print()
        print("Examples:")
        print("  python tools/execute_move.py 186 480 360")
        print("  python tools/execute_move.py 186,187 480 360 --steps=200")
        print()
        print("NOTE: --rl-interface pauses the game loop. Use --run in a")
        print("separate terminal to keep the simulation advancing.")
        sys.exit(1)

    entity_ids = parse_entity_ids(sys.argv[1])
    x = float(sys.argv[2])
    z = float(sys.argv[3])

    # Parse --steps=N (default 50)
    follow_up_steps = 50
    steps_flag = parse_flag(sys.argv[4:], "--steps=")
    if steps_flag:
        follow_up_steps = int(steps_flag)

    pid = int(os.environ.get("ZEROAD_PID") or "1")

    try:
        # Send the walk command with the first /step
        print(f"Sending walk via /step (pid={pid}): {entity_ids} -> ({x}, {z})")
        state = client.move(pid, entity_ids, x, z, queued=False)

        if isinstance(state, dict) and "entities" in state:
            for eid in entity_ids:
                ent = state["entities"].get(str(eid))
                if ent:
                    print(
                        f"  Entity {eid}: pos={ent.get('position', '?')} owner={ent.get('owner', '?')}"
                    )
                else:
                    print(f"  Entity {eid}: NOT FOUND in state (wrong ID?)")

        # Keep stepping so the unit actually walks to the destination
        if follow_up_steps > 0:
            print(f"  Stepping {follow_up_steps} more turns to let the unit move...")
            for i in range(follow_up_steps):
                state = client.step([])
                time.sleep(0.005)

            # Show final position
            if isinstance(state, dict) and "entities" in state:
                for eid in entity_ids:
                    ent = state["entities"].get(str(eid))
                    if ent:
                        print(f"  Entity {eid} final pos: {ent.get('position', '?')}")

    except URLError as e:
        print(f"Error: RL interface not reachable at {url}: {e}")
        print(
            "Start 0 A.D. with: ZEROAD_RL_INTERFACE=127.0.0.1:6000 python launcher.py"
        )
        raise SystemExit(2)

    print("Done.")


if __name__ == "__main__":
    main()
