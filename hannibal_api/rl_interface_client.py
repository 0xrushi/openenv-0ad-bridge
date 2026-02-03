from __future__ import annotations

import json
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib import request
from urllib.error import URLError

from pydantic import BaseModel, ConfigDict, Field


class WalkCommand(BaseModel):
    """0 A.D. simulation command to move units (walk)."""

    model_config = ConfigDict(extra="forbid")

    type: str = Field(default="walk")
    entities: List[int] = Field(min_length=1)
    x: float
    z: float
    queued: bool = False
    # If true, push the order in front of the current order queue.
    # (Supported by simulation/helpers/Commands.js walk handler.)
    pushFront: bool = True


class RLInterfaceClient:
    """HTTP client for 0 A.D.'s built-in RL interface.

    This requires starting pyrogenesis with:
      --rl-interface=127.0.0.1:6000
    """

    def __init__(self, base_url: str = "http://127.0.0.1:6000"):
        self.base_url = base_url.rstrip("/")

    def _post(self, route: str, body: str, timeout: float = 10.0) -> str:
        data = body.encode("utf-8")
        resp = request.urlopen(url=f"{self.base_url}/{route}", data=data, timeout=timeout)  # noqa: S310
        return resp.read().decode("utf-8", errors="replace")

    def step(self, commands: Iterable[Tuple[int, Dict[str, Any]]]) -> Dict[str, Any]:
        """Apply one simulation step with a list of (player_id, command_dict)."""

        lines: List[str] = []
        for player_id, cmd in commands:
            lines.append(f"{int(player_id)};{json.dumps(cmd, separators=(',', ':'))}")
        raw = self._post("step", "\n".join(lines))
        return json.loads(raw)

    def evaluate(self, code: str) -> Any:
        """Evaluate JS in the Simulation2 ScriptInterface and return JSON."""

        raw = self._post("evaluate", code)
        return json.loads(raw)

    def postcommand(self, player_id: int, cmd: Dict[str, Any]) -> Any:
        """Send a simulation command via Engine.PostCommand using /evaluate.

        This avoids stepping the simulation from the RL interface (so it works
        alongside a running visual match).
        """

        payload = json.dumps(cmd, separators=(",", ":"))
        code = (
            "(function(){"
            f"Engine.PostCommand({int(player_id)}, {payload});"
            "return {ok:true};"
            "})()"
        )
        return self.evaluate(code)

    def walk_postcommand(
        self,
        player_id: int,
        entity_ids: Sequence[int],
        x: float,
        z: float,
        queued: bool = False,
    ) -> Any:
        cmd = WalkCommand(entities=list(entity_ids), x=x, z=z, queued=queued)
        return self.postcommand(player_id, cmd.model_dump(mode="json"))

    def push_command(self, player_id: int, cmd: Dict[str, Any]) -> Any:
        """Push a command via IID_CommandQueue.PushLocalCommand using /evaluate.

        Unlike postcommand / Engine.PostCommand, this uses the CommandQueue
        component which is the canonical way to inject commands without
        advancing the simulation – ideal for visual (non-headless) games.
        """

        payload = json.dumps(cmd, separators=(",", ":"))
        code = (
            "(function(){"
            "var cmpCQ=Engine.QueryInterface(SYSTEM_ENTITY,IID_CommandQueue);"
            f"cmpCQ.PushLocalCommand({int(player_id)},{payload});"
            "return JSON.stringify({ok:true});"
            "})()"
        )
        raw = self._post("evaluate", code)
        return json.loads(raw)

    def walk_push(
        self,
        player_id: int,
        entity_ids: Sequence[int],
        x: float,
        z: float,
        queued: bool = False,
    ) -> Any:
        """Send a walk command via PushLocalCommand (no simulation step)."""
        cmd = WalkCommand(entities=list(entity_ids), x=x, z=z, queued=queued)
        return self.push_command(player_id, cmd.model_dump(mode="json"))

    def move(
        self,
        player_id: int,
        entity_ids: Sequence[int],
        x: float,
        z: float,
        queued: bool = False,
    ) -> Dict[str, Any]:
        cmd = WalkCommand(entities=list(entity_ids), x=x, z=z, queued=queued)
        return self.step([(player_id, cmd.model_dump(mode="json"))])
