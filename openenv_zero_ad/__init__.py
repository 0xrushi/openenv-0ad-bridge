"""OpenEnv-format proxy environment for 0 A.D. RL HTTP interface.

This package exposes a small OpenEnv-compatible HTTP API (reset/step/state/ws)
that proxies to a running 0 A.D. instance started with `--rl-interface=IP:PORT`.

The action space is intentionally low-level:
- `op=push_command`: inject a Simulation2 command dict
- `op=evaluate`: run a JS snippet via the RL interface
"""

from .models import (
    EvaluateAction,
    PushCommandAction,
    ResetRequest,
    ResetResponse,
    SchemaResponse,
    StepRequest,
    StepResponse,
    ZeroADObservation,
    ZeroADState,
)
from .server import app, create_app

__all__ = [
    "EvaluateAction",
    "PushCommandAction",
    "ResetRequest",
    "ResetResponse",
    "SchemaResponse",
    "StepRequest",
    "StepResponse",
    "ZeroADObservation",
    "ZeroADState",
    "create_app",
    "app",
]
