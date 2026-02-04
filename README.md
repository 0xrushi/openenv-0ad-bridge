# openenv-0ad-bridge

Programmatic control of a running 0 A.D. match via the built-in RL interface HTTP server, with an OpenEnv-format proxy on top.

This can be used as an LLM arena: run multiple agents (e.g. `gpt-4o` vs `gpt-5`) that read a shared omniscient snapshot and issue low-level commands against the same running match.

## Demo

**0.A.D. movement demo (reduced colors to compress gif)**

![0 A.D. Movement Demo](images/0admovedemo_optimized.gif)



**Video demo (basic agent thinking and movements; issues of context length leading to errors)**

[![Video: basic agent thinking and movements](https://img.youtube.com/vi/qCLUHdn229w/maxresdefault.jpg)](https://youtu.be/qCLUHdn229w)

## Origin Story

I first prototyped this concept on an open-source Age of Empires-style engine:

- Repo: https://github.com/SFTtech/openage

But that engine was still in development for ~10 years and I couldn’t proceed.
I later remembered that 0A.D. was also a development since long time and it turned out to be pretty stable, which motivated me to rebuild the idea on top of 0A.D.

I cannot leave my memories of Age of Empires 2 if that engine ever gets to a stable 1.0 release, I hope I’ll be able to add this concept there someday.


**Age of Empires Open Engine POC**

![Age of Empires Open Engine POC](images/monkwolo.gif)

---

Core pieces:
- RL interface client: `hannibal_api/rl_interface_client.py`
- OpenEnv-format proxy server: `openenv_zero_ad/server.py`
- Stepper tool (keeps sim running): `tools/execute_move.py --run`
- LLM-vs-LLM driver (optional): `tools/llm_match.py` + `configs/llm_match.toml`

## Quick Start

### Setup

- Install 0 A.D.
  - Arch Linux: `sudo pacman -S 0ad`
- Install Python deps: `python -m pip install -r requirements.txt`

### Paths / Local Configuration

- 0 A.D. binary path: `launcher.py` uses `--binary` (default: `pyrogenesis` and will try common paths like `/usr/bin/pyrogenesis` and `/usr/games/pyrogenesis`). If your binary lives elsewhere, pass `--binary` when launching.
- ~~Legacy (not required for the OpenEnv bridge): `data.py`, `tools/data.py`, `pack.sh`, `tools/pack.sh` contain hard-coded local paths from the old mod/packaging workflow.~~

See `docs/terminal_setup.md`.

## Docker Setup (Alternative)

Docker Compose provides an all-in-one containerized setup with 0 A.D., noVNC web viewer, OpenEnv proxy, and stepper.

### Prerequisites

- Docker and Docker Compose installed

### Quick Start with Docker

1) Start all services:

```bash
docker compose up -d
```

2) Access the services:

- **noVNC Web Viewer**: http://localhost:6080/vnc.html (view the game in your browser)
- **OpenEnv API**: http://localhost:8001 (proxy endpoint, changed from 8000 to avoid conflicts)
- **0 A.D. RL Interface**: 127.0.0.1:6000 (internal)

3) Test the API:

```bash
curl http://localhost:8001/health
```

### Services

The Docker setup includes:

- **zero-ad**: 0 A.D. game running with RL interface on port 6000, X server on display :99, VNC on 5900, noVNC on 6080
- **openenv-proxy**: OpenEnv API server on port 8001
- **stepper**: Keeps the simulation running continuously
- **client**: Example client (runs once and exits)
- **scratch**: Utility container for debugging

### Configuration

Environment variables in `docker-compose.yml`:

- `ZEROAD_RL_INTERFACE`: 127.0.0.1:6000
- `ZEROAD_MAP`: scenarios/arcadia
- `ZEROAD_PLAYERS`: 2
- `DISPLAY_NUM`: 99 (X display number)
- `VNC_PORT`: 5900
- `NOVNC_PORT`: 6080

### Persistent Data

Game data is persisted in local directories (auto-created):

- `./0ad-user-data`: Player data, replays, saves
- `./0ad-user-config`: Configuration files
- `./0ad`: Shared game directory

### Stopping

```bash
docker compose down
```

## Typical Workflow

1) Launch 0 A.D. with RL interface:

```bash
ZEROAD_RL_INTERFACE=127.0.0.1:6000 python launcher.py
```

Defaults: launches `scenarios/arcadia` (Player 1 civ `athen`). To use another scenario, pass `--map=...` and also set `--civ`/`ZEROAD_CIV` to something other than `athen`.

2) Run the stepper (required for `--rl-interface`):

```bash
export ZEROAD_RL_URL=http://127.0.0.1:6000
export ZEROAD_STEP_SLEEP=0.01
export ZEROAD_STATE_OUT=run/latest_state.json
export ZEROAD_STATE_EVERY_N=10
python tools/execute_move.py --run
```

3) Run the OpenEnv proxy:

```bash
export ZEROAD_RL_URL=http://127.0.0.1:6000
python tools/run_openenv_zero_ad_server.py --host=127.0.0.1 --port=8000
```

4) Smoke test:

```bash
API_BASE=http://127.0.0.1:8000 bash tools/openenv_examples.sh
```

## LLM Arena

- OpenEnv gives a simple `/reset` + `/step` surface for agents to target.
- The stepper publishes `run/latest_state.json` so decision loops don’t call RL `/step` (single authoritative clock).
- `tools/llm_match.py` demonstrates two agents taking turns emitting low-level actions (`push_command` + `evaluate`).

## Notes

- 0 A.D. must be started with `--rl-interface=IP:PORT`.
- When `--rl-interface` is enabled, the simulation only advances via `/step`; run the stepper in a separate terminal.

## tmux Bootstrap

If you have tmux installed, the following command can replace 4 terminal screens:

```bash
python -m pip install libtmux
python tools/start_tmux_env.py
tmux attach -t zero-ad
```


## Acknowledgements

This project borrows heavily from existing open-source work:
- [0 A.D.] (https://gitea.wildfiregames.com/)
- [OpenEnv](https://github.com/meta-pytorch/OpenEnv)
- [Hannibal](https://github.com/agentx-cgn/Hannibal)
