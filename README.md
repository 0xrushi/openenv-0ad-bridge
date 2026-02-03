# 0 A.D. RL HTTP + OpenEnv Proxy

This repo provides a programmatic interface to control a running 0 A.D. match.

Core pieces:
- RL interface client: `hannibal_api/rl_interface_client.py`
- OpenEnv-format proxy server: `openenv_zero_ad/server.py`
- Stepper tool (keeps sim running): `tools/execute_move.py --run`

## Quick Start

See `docs/terminal_setup.md`.

## Notes

- 0 A.D. must be started with `--rl-interface=IP:PORT`.
- When `--rl-interface` is enabled, the simulation only advances via `/step`.
  Run the stepper in a separate terminal.
