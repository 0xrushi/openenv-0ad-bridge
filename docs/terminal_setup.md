# Terminal Setup (0 A.D. RL HTTP + OpenEnv Proxy)

This setup runs a playable 0 A.D. match with RL interface enabled, keeps the simulation advancing, and exposes an OpenEnv-format HTTP API for scripts.

## Terminal A: Launch 0 A.D. With RL Interface

```bash
ZEROAD_RL_INTERFACE=127.0.0.1:6000 python launcher.py --map="scenarios/arcadia"
```

## Terminal B: Stepper (Keep Simulation Running)

```bash
export ZEROAD_STEP_SLEEP=0.01
export ZEROAD_STATE_OUT=run/latest_state.json
export ZEROAD_STATE_EVERY_N=10
python tools/execute_move.py --run
```

## Terminal C: OpenEnv-Format Proxy Server

```bash
export ZEROAD_RL_URL=http://127.0.0.1:6000
python tools/run_openenv_zero_ad_server.py --host=127.0.0.1 --port=8000
```

If port 8000 is already in use, pick another port (e.g. 8001).

If you want auto-reload:

```bash
PYTHONPATH=. uvicorn openenv_zero_ad.server:app --host=127.0.0.1 --port=8000 --reload
```

## Terminal D: Send Actions (Examples)

Reset (OpenEnv shape):

```bash
curl -sS -X POST http://127.0.0.1:8000/reset \
  -H 'content-type: application/json' \
  -d '{}' | python -m json.tool
```

Evaluate:

```bash
curl -sS -X POST http://127.0.0.1:8000/step \
  -H 'content-type: application/json' \
  -d '{"action":{"op":"evaluate","code":"1+1"}}' | python -m json.tool
```

Push a Simulation2 command (walk/move):

```bash
curl -sS -X POST http://127.0.0.1:8000/step \
  -H 'content-type: application/json' \
  -d '{"action":{"op":"push_command","player_id":1,"cmd":{"type":"walk","entities":[186,188],"x":150,"z":200,"queued":false,"pushFront":true}}}' \
  | python -m json.tool
```

Useful endpoints:
- `GET http://127.0.0.1:8000/health`
- `GET http://127.0.0.1:8000/schema`
- `GET http://127.0.0.1:8000/state`

## Scripted curl examples

You can run a helper script (works even when the tmux script picks port 8001):

```bash
API_BASE=http://127.0.0.1:8001 bash tools/openenv_examples.sh
```

## Optional: LLM vs LLM match driver

This reads omniscient snapshots written by the stepper (`ZEROAD_STATE_OUT`) and sends actions to the OpenEnv proxy.

```bash
export OPENAI_API_KEY=...  # required
python tools/llm_match.py --config configs/llm_match.toml
```

## Optional: Start Everything in tmux

Install libtmux:

```bash
python -m pip install libtmux
```

The tmux script will auto-activate `.venv` in each pane if it exists.

Run:

```bash
python tools/start_tmux_env.py
tmux attach -t zero-ad
```

The tmux script auto-picks a free OpenEnv proxy port (8000, 8001, ...) and prints it when it starts.
