from __future__ import annotations

from typing import Any, Dict, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field
from typing_extensions import Annotated


class PushCommandAction(BaseModel):
    """Inject a Simulation2 command via CommandQueue.PushLocalCommand."""

    model_config = ConfigDict(extra="forbid")

    op: Literal["push_command"] = "push_command"
    player_id: int = Field(ge=0)
    cmd: Dict[str, Any]


class EvaluateAction(BaseModel):
    """Evaluate JS in Simulation2 ScriptInterface."""

    model_config = ConfigDict(extra="forbid")

    op: Literal["evaluate"] = "evaluate"
    code: str = Field(min_length=1)


ZeroADAction = Annotated[
    Union[PushCommandAction, EvaluateAction],
    Field(discriminator="op"),
]


class ZeroADObservation(BaseModel):
    """Observation payload returned by the OpenEnv-format proxy server."""

    model_config = ConfigDict(extra="forbid")

    ok: bool = True
    result: Any = None
    error: Optional[str] = None
    episode_id: Optional[str] = None
    step_count: int = 0
    stepper_detected: Optional[bool] = None
    sim_time: Optional[float] = None


class ZeroADState(BaseModel):
    """Server-side state for the OpenEnv-format proxy."""

    model_config = ConfigDict(extra="allow")

    episode_id: Optional[str] = None
    step_count: int = 0
    rl_url: str
    last_sim_time: Optional[float] = None
    stepper_detected: Optional[bool] = None


class ResetRequest(BaseModel):
    """OpenEnv-compatible reset request."""

    model_config = ConfigDict(extra="allow")

    seed: Optional[int] = Field(default=None, ge=0)
    episode_id: Optional[str] = Field(default=None, max_length=255)


class ResetResponse(BaseModel):
    """OpenEnv-compatible reset response."""

    model_config = ConfigDict(extra="forbid")

    observation: Dict[str, Any]
    reward: Optional[float] = None
    done: bool = False


class StepRequest(BaseModel):
    """OpenEnv-compatible step request."""

    model_config = ConfigDict(extra="allow")

    action: Dict[str, Any]
    timeout_s: Optional[float] = Field(default=None, gt=0)
    request_id: Optional[str] = Field(default=None, max_length=255)


class StepResponse(BaseModel):
    """OpenEnv-compatible step response."""

    model_config = ConfigDict(extra="forbid")

    observation: Dict[str, Any]
    reward: Optional[float] = None
    done: bool = False


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str


class SchemaResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Dict[str, Any]
    observation: Dict[str, Any]
    state: Dict[str, Any]
