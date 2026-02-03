from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

from fastapi import Body, FastAPI, WebSocket, WebSocketDisconnect
from pydantic import TypeAdapter

from .environment import ZeroADSession
from .models import (
    ResetRequest,
    ResetResponse,
    SchemaResponse,
    StepRequest,
    StepResponse,
    ZeroADAction,
    ZeroADObservation,
    ZeroADState,
)


_ACTION_SCHEMA = TypeAdapter(ZeroADAction).json_schema()


def create_app(
    session: Optional[ZeroADSession] = None, rl_url: Optional[str] = None
) -> FastAPI:
    """Create a FastAPI app implementing the OpenEnv HTTP shape."""

    if session is None:
        resolved = rl_url or os.environ.get("ZEROAD_RL_URL")
        session = ZeroADSession(resolved)

    app = FastAPI(
        title="0 A.D. OpenEnv Proxy",
        version="0.1.0",
        description="OpenEnv-format HTTP API proxying to 0 A.D. RL interface.",
    )

    @app.post("/reset", response_model=ResetResponse)
    async def reset(
        request: ResetRequest = Body(default_factory=ResetRequest),
    ) -> ResetResponse:
        obs = session.reset(**request.model_dump(exclude_unset=True))
        return ResetResponse(observation=obs, reward=None, done=False)

    @app.post("/step", response_model=StepResponse)
    async def step(request: StepRequest) -> StepResponse:
        obs = session.step(request.action, timeout_s=request.timeout_s)
        return StepResponse(observation=obs, reward=None, done=False)

    @app.get("/state", response_model=ZeroADState)
    async def state() -> ZeroADState:
        return session.state

    @app.get("/health")
    async def health() -> Dict[str, Any]:
        return {"status": "healthy"}

    @app.get("/schema", response_model=SchemaResponse)
    async def schema() -> SchemaResponse:
        return SchemaResponse(
            action=_ACTION_SCHEMA,
            observation=ZeroADObservation.model_json_schema(),
            state=ZeroADState.model_json_schema(),
        )

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        await websocket.accept()
        try:
            while True:
                raw = await websocket.receive_text()
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError as e:
                    await websocket.send_text(
                        json.dumps(
                            {
                                "type": "error",
                                "data": {
                                    "message": f"Invalid JSON: {e}",
                                    "code": "INVALID_JSON",
                                },
                            }
                        )
                    )
                    continue

                msg_type = msg.get("type")
                try:
                    if msg_type == "reset":
                        data = msg.get("data") or {}
                        req = ResetRequest.model_validate(data)
                        obs = session.reset(**req.model_dump(exclude_unset=True))
                        await websocket.send_text(
                            json.dumps(
                                {
                                    "type": "observation",
                                    "data": {
                                        "observation": obs,
                                        "reward": None,
                                        "done": False,
                                    },
                                }
                            )
                        )
                    elif msg_type == "step":
                        data = msg.get("data") or {}
                        obs = session.step(data)
                        await websocket.send_text(
                            json.dumps(
                                {
                                    "type": "observation",
                                    "data": {
                                        "observation": obs,
                                        "reward": None,
                                        "done": False,
                                    },
                                }
                            )
                        )
                    elif msg_type == "state":
                        await websocket.send_text(
                            json.dumps(
                                {
                                    "type": "state",
                                    "data": session.state.model_dump(mode="json"),
                                }
                            )
                        )
                    elif msg_type == "close":
                        break
                    else:
                        await websocket.send_text(
                            json.dumps(
                                {
                                    "type": "error",
                                    "data": {
                                        "message": f"Unknown message type: {msg_type}",
                                        "code": "UNKNOWN_TYPE",
                                    },
                                }
                            )
                        )
                except Exception as e:
                    await websocket.send_text(
                        json.dumps(
                            {
                                "type": "error",
                                "data": {"message": str(e), "code": "EXECUTION_ERROR"},
                            }
                        )
                    )
        except WebSocketDisconnect:
            return
        finally:
            try:
                await websocket.close()
            except RuntimeError:
                pass

    return app


app = create_app()
