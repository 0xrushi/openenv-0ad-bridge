# ZeroAD OpenEnv Setup

Launch 0 A.D. with RL HTTP interface, run stepper, run OpenEnv proxy, and verify the setup.

## Prerequisites

- 0 A.D. installed (`/usr/bin/0ad` works)
- Python dependencies installed: `pip install -r requirements.txt`

## Quick Start (tmux)

For the fastest setup, use the tmux launcher:

```bash
python -m pip install libtmux
python tools/start_tmux_env.py
tmux attach -t zero-ad
```

The tmux script will:
- Launch 0 A.D. with RL interface
- Start the stepper (keeps simulation running)
- Start the OpenEnv proxy
- Print the chosen OpenEnv proxy port

## Manual Setup (3 Terminals)

### Terminal A: Launch 0 A.D. with RL Interface

```bash
ZEROAD_RL_INTERFACE=127.0.0.1:6000 python launcher.py --map="scenarios/arcadia"
```

This starts 0 A.D. with an HTTP RL interface listening on port 6000.

### Terminal B: Start the Stepper

The stepper keeps the simulation advancing and writes state snapshots:

```bash
export ZEROAD_RL_URL=http://127.0.0.1:6000
export ZEROAD_STEP_SLEEP=0.01
export ZEROAD_STATE_OUT=run/latest_state.json
export ZEROAD_STATE_EVERY_N=10
python tools/execute_move.py --run
```

### Terminal C: Start OpenEnv Proxy

```bash
export ZEROAD_RL_URL=http://127.0.0.1:6000
python tools/run_openenv_zero_ad_server.py --host=127.0.0.1 --port=8000
```

If port 8000 is in use, use `--port=8001` or higher.

## Verification

Test the setup with the examples script:

```bash
API_BASE=http://127.0.0.1:8000 bash tools/openenv_examples.sh
```

List entities for player 1:

```bash
python tools/execute_move.py --list --player=1
```

Test health endpoint:

```bash
curl -sS http://127.0.0.1:8000/health | python -m json.tool
```

## Success Criteria

- `tools/openenv_examples.sh` returns valid JSON for Health/Schema/Reset/Evaluate
- You can list entities: `python tools/execute_move.py --list --player=1`
- OpenEnv proxy responds to `/health` endpoint

## Common Issues

### Port Already in Use

If OpenEnv proxy can't bind to port 8000:
- Use a different port: `--port=8001` or higher
- Or stop the process holding the port

### Stepper Timeouts

If you see `TimeoutError` in the stepper:
- Increase `ZEROAD_STEP_SLEEP` (e.g., from 0.01 to 0.02)
- The stepper has automatic retry logic built in

### 0 A.D. Won't Start

- Check that 0 A.D. is installed: `which 0ad`
- Verify the map exists: `scenarios/arcadia`
- Check terminal output for errors

## Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `ZEROAD_RL_INTERFACE` | - | Address for RL interface (e.g., `127.0.0.1:6000`) |
| `ZEROAD_RL_URL` | - | URL of running RL interface (e.g., `http://127.0.0.1:6000`) |
| `ZEROAD_STEP_SLEEP` | 0.01 | Seconds between simulation steps |
| `ZEROAD_STATE_OUT` | - | Path to write state snapshots |
| `ZEROAD_STATE_EVERY_N` | 10 | Write state every N steps |
