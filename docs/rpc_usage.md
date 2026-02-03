# Hannibal Realtime API (RL HTTP) Usage Guide

Control a running 0 A.D. match via the built-in RL interface HTTP server.

This is the canonical realtime transport for scripts/agents.

## Quick Start

### 1. Start 0 A.D. with RL interface enabled

The repo launcher supports enabling the RL interface with an env var:

```bash
ZEROAD_RL_INTERFACE=127.0.0.1:6000 python launcher.py
```

### 2. Use the Python RL client

```python
from hannibal_api.rl_interface_client import RLInterfaceClient

rl = RLInterfaceClient("http://127.0.0.1:6000")

# Move units (no simulation step required)
rl.walk_push(player_id=1, entity_ids=[186, 188], x=150, z=200)
```

## Endpoints

- `POST /evaluate`: Evaluate JS in the Simulation2 ScriptInterface and return JSON.
- `POST /step`: Apply one simulation step and optional (player_id, command) inputs.

In code, these are wrapped by `hannibal_api/rl_interface_client.py`.

## Example Commands

### Move Entities (walk)

```python
from hannibal_api.rl_interface_client import RLInterfaceClient

rl = RLInterfaceClient("http://127.0.0.1:6000")

# Canonical move command is `walk`.
rl.walk_push(player_id=1, entity_ids=[186, 188], x=150, z=200)
```

### Evaluate (omniscient query)

```python
from hannibal_api.rl_interface_client import RLInterfaceClient

rl = RLInterfaceClient("http://127.0.0.1:6000")

# Note: the RL interface returns JSON. If your snippet returns a JSON string,
# you may need to json.loads(...) it in Python.
out = rl.evaluate("(function(){ return JSON.stringify({ok:true}); })()")
print(out)
```

## Legacy Notes (Deprecated)

Older documentation in this repo referenced manual UI steps and file-based command/response files.
That is not required for realtime API play and should be considered deprecated in favor of RL HTTP.

## OpenEnv Proxy (Recommended)

If you want an OpenEnv-style API (`/reset`, `/step`, `/state`, `/ws`) that proxies to the RL interface, use:

- `openenv_zero_ad/server.py`
- `tools/run_openenv_zero_ad_server.py`
- `docs/terminal_setup.md`

## Automation

Your automation is the Python script itself: it talks to the running match over HTTP.
