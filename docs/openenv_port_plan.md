# OpenEnv Interface Plan (0 A.D. RL HTTP)

Goal: expose 0 A.D. RL interface (`/evaluate`, command injection) via an OpenEnv-compatible environment server (`/reset`, `/step`, `/state`, `/ws`) using low-level actions only: `push_command` + `evaluate`.

Assumptions:
- 0 A.D. is launched with RL interface enabled (e.g. `ZEROAD_RL_INTERFACE=127.0.0.1:6000 python launcher.py`)
- A separate stepper keeps simulation advancing (for now: `python tools/execute_move.py --run`)
- Omniscient reads are allowed
- The OpenEnv environment will NOT call RL `/step` (to avoid double-stepping)

---

## Todo

- [x] Define the OpenEnv environment package layout (`openenv_zero_ad/`)
- [x] Add an `openenv.yaml` manifest (for AutoEnv/AutoAction discovery later) (`openenv_zero_ad/openenv.yaml`)

- [x] Define OpenEnv models (Pydantic v2) (`openenv_zero_ad/models.py`)
- [x] Create `ZeroADAction` (discriminated union)
- [x] Add `op="push_command"` with `player_id: int`, `cmd: dict`
- [x] Add `op="evaluate"` with `code: str`

- [x] Create `ZeroADObservation`
- [x] Add `result: any | None` (raw value returned by RL)
- [x] Add `error: str | None`
- [x] Keep `reward=None` and `done=False` for now

- [x] Create `ZeroADState`
- [x] Track `episode_id`, `step_count`
- [x] Track `rl_url`
- [x] Track `last_sim_time` (best-effort)
- [x] Track `stepper_detected` (best-effort)

- [x] Implement the OpenEnv Environment server (proxy to RL HTTP) (`openenv_zero_ad/environment.py`)
- [x] Implement session state (episode_id/step_count) + RL proxy
- [x] Implement `reset(seed=None, episode_id=None, **kwargs)` (ping + stepper detection)
- [x] Implement `step(action, timeout_s=None, **kwargs)` for `push_command` + `evaluate`
- [x] Never call RL `/step` here

- [x] Build an OpenEnv-compatible HTTP/WebSocket app (`openenv_zero_ad/server.py`)
- [x] Configure RL URL via env var (e.g. `ZEROAD_RL_URL=http://127.0.0.1:6000`)

- [ ] Provide client-side usage (start with GenericEnvClient)

- [x] Add minimal examples (server runner) (`tools/run_openenv_zero_ad_server.py`)

- [x] Unit tests (no live 0 A.D.) (`tests/test_openenv_zero_ad_server.py`)
- [ ] Optional integration test (guarded by env var, requires RL server + stepper)

- [ ] Operational notes (document clearly)
- [ ] Only one stepper process calls RL `/step`
- [ ] OpenEnv env server never steps sim in this mode
- [ ] Omniscient reads may leak full map/entity info

- [ ] Later: lifecycle + done conditions
- [ ] Add `done=True` when victory/defeat detected
- [ ] Add a reward signal if you decide on training objectives

---

## Acceptance Criteria

- [ ] Can run the OpenEnv server locally and connect with `openenv.core.GenericEnvClient`
- [ ] `reset()` returns a valid OpenEnv response (observation dict, `reward=None`, `done=False`)
- [ ] `step(push_command)` injects a Simulation2 command (e.g. walk) without calling RL `/step`
- [ ] `step(evaluate)` returns evaluated JSON
- [ ] Works while a separate stepper keeps the simulation running
