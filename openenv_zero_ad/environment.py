from __future__ import annotations

import json
import os
import threading
import time
import uuid
from typing import Any, Dict, Optional

from pydantic import TypeAdapter

from hannibal_api.rl_interface_client import RLInterfaceClient

from .models import (
    EvaluateAction,
    PushCommandAction,
    ZeroADAction,
    ZeroADObservation,
    ZeroADState,
)


_ACTION_ADAPTER = TypeAdapter(ZeroADAction)


def _normalize_eval_result(value: Any) -> Any:
    """Best-effort normalization for RL /evaluate return values.

    The 0 A.D. RL interface JSON-encodes the evaluation result. Some helper
    snippets in this repo return JSON-stringified objects, which then decode
    to a Python `str`. If the returned value is a JSON string, parse it.
    """

    if isinstance(value, str):
        s = value.strip()
        if not s:
            return value
        if (s.startswith("{") and s.endswith("}")) or (
            s.startswith("[") and s.endswith("]")
        ):
            try:
                return json.loads(s)
            except Exception:
                return value
    return value


def _extract_int_list(value: Any) -> list[int]:
    """Extract a list of ints from a JSON-ish container.

    Accepts lists/tuples containing ints or digit-strings.
    Skips bools (since bool is a subclass of int).
    """
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        out: list[int] = []
        for v in value:
            if isinstance(v, bool):
                continue
            if isinstance(v, int):
                out.append(v)
            elif isinstance(v, str) and v.isdigit():
                out.append(int(v))
        return out
    return []


class ZeroADSession:
    """Stateful proxy session for one running 0 A.D. instance."""

    def __init__(self, rl_url: Optional[str] = None):
        self.rl_url = (
            rl_url or os.environ.get("ZEROAD_RL_URL") or "http://127.0.0.1:6000"
        ).rstrip("/")
        self.rl = RLInterfaceClient(self.rl_url)

        self._lock = threading.Lock()
        self._state = ZeroADState(rl_url=self.rl_url)

    @property
    def state(self) -> ZeroADState:
        return self._state

    def _get_sim_time(self) -> Optional[float]:
        code = (
            "(function(){"
            "var cmpTimer=Engine.QueryInterface(SYSTEM_ENTITY,IID_Timer);"
            "if(!cmpTimer) return {error:'no IID_Timer'};"
            "var t=typeof cmpTimer.GetTime==='function'?cmpTimer.GetTime():-1;"
            "return {time:t};"
            "})()"
        )
        out = _normalize_eval_result(self.rl.evaluate(code))
        if isinstance(out, dict) and isinstance(out.get("time"), (int, float)):
            return float(out["time"])
        return None

    def _validate_sim_command(
        self, player_id: int, cmd: Dict[str, Any]
    ) -> Optional[str]:
        """Return a validation error string, or None if ok.

        This is a best-effort guardrail to return a clear error before sending
        invalid entity IDs into the simulation.
        """

        # Entity IDs expected to be owned by player_id.
        owned_ids: list[int] = []
        owned_ids.extend(_extract_int_list(cmd.get("entities")))

        # IDs that must exist (owner may be different).
        must_exist_ids: list[int] = []
        for key in ("target",):
            v = cmd.get(key)
            if isinstance(v, bool):
                continue
            if isinstance(v, int):
                must_exist_ids.append(v)
            elif isinstance(v, str) and v.isdigit():
                must_exist_ids.append(int(v))

        for key in ("entity", "garrisonHolder"):
            v = cmd.get(key)
            if isinstance(v, bool):
                continue
            if isinstance(v, int):
                owned_ids.append(v)
            elif isinstance(v, str) and v.isdigit():
                owned_ids.append(int(v))

        owned_ids.extend(_extract_int_list(cmd.get("garrisonHolders")))

        # Deduplicate and drop non-positive IDs.
        owned_ids = sorted({i for i in owned_ids if isinstance(i, int) and i > 0})
        must_exist_ids = sorted(
            {i for i in must_exist_ids if isinstance(i, int) and i > 0}
        )

        # Basic type-specific checks.
        if cmd.get("type") == "walk":
            if not owned_ids:
                return "walk requires non-empty 'entities'"
            if not isinstance(cmd.get("x"), (int, float)) or not isinstance(
                cmd.get("z"), (int, float)
            ):
                return "walk requires numeric 'x' and 'z'"

        if not owned_ids and not must_exist_ids:
            return None

        payload_owned = json.dumps(owned_ids, separators=(",", ":"))
        payload_exist = json.dumps(must_exist_ids, separators=(",", ":"))

        code = (
            "(function(){"
            f"var playerId={int(player_id)};"
            f"var ownedIds={payload_owned};"
            f"var existIds={payload_exist};"
            "var missing=[];"
            "var wrongOwner=[];"
            "function exists(id){"
            "  return !!(Engine.QueryInterface(id,IID_Ownership) || Engine.QueryInterface(id,IID_Identity) || Engine.QueryInterface(id,IID_Position));"
            "}"
            "for (var i=0;i<ownedIds.length;i++){"
            "  var id=ownedIds[i];"
            "  var cmpOwn=Engine.QueryInterface(id,IID_Ownership);"
            "  if (!cmpOwn){ missing.push(id); continue; }"
            "  var owner = typeof cmpOwn.GetOwner === 'function' ? cmpOwn.GetOwner() : cmpOwn.owner;"
            "  if (owner !== playerId) wrongOwner.push({id:id, owner:owner});"
            "}"
            "for (var j=0;j<existIds.length;j++){"
            "  var tid=existIds[j];"
            "  if (!exists(tid)) missing.push(tid);"
            "}"
            "if (missing.length || wrongOwner.length){"
            "  return {ok:false, missing:missing, wrongOwner:wrongOwner};"
            "}"
            "return {ok:true};"
            "})()"
        )

        try:
            out = _normalize_eval_result(self.rl.evaluate(code))
        except Exception as e:
            return f"validation_failed: {e}"

        if isinstance(out, dict) and out.get("ok") is False:
            parts: list[str] = []
            missing = out.get("missing")
            wrong = out.get("wrongOwner")
            if isinstance(missing, list) and missing:
                parts.append(f"missing={missing}")
            if isinstance(wrong, list) and wrong:
                parts.append(f"wrongOwner={wrong}")
            return "invalid_entity_ids: " + ", ".join(parts)

        return None

    def reset(
        self,
        seed: Optional[int] = None,
        episode_id: Optional[str] = None,
        **_kwargs: Any,
    ) -> Dict[str, Any]:
        """Reset local session state (does not reset the 0 A.D. match)."""

        with self._lock:
            self._state.episode_id = episode_id or str(uuid.uuid4())
            self._state.step_count = 0

            # Ping RL interface.
            try:
                ping = self.rl.evaluate("1+1")
                ping = _normalize_eval_result(ping)
            except Exception as e:
                obs = ZeroADObservation(
                    ok=False,
                    error=f"rl_interface_unreachable: {e}",
                    episode_id=self._state.episode_id,
                    step_count=self._state.step_count,
                )
                return obs.model_dump(mode="json")

            # Best-effort stepper detection (requires sim time to advance).
            t1 = self._get_sim_time()
            time.sleep(0.05)
            t2 = self._get_sim_time()
            stepper_detected: Optional[bool]
            if t1 is None or t2 is None:
                stepper_detected = None
            else:
                stepper_detected = t2 > t1

            self._state.last_sim_time = t2 if t2 is not None else t1
            self._state.stepper_detected = stepper_detected

            obs = ZeroADObservation(
                ok=True,
                result={"ping": ping, "seed": seed},
                episode_id=self._state.episode_id,
                step_count=self._state.step_count,
                stepper_detected=stepper_detected,
                sim_time=self._state.last_sim_time,
            )
            return obs.model_dump(mode="json")

    def step(
        self,
        action_dict: Dict[str, Any],
        timeout_s: Optional[float] = None,
        **_kwargs: Any,
    ) -> Dict[str, Any]:
        """Execute one OpenEnv step (proxying to RL /evaluate)."""

        with self._lock:
            action = _ACTION_ADAPTER.validate_python(action_dict)
            result: Any
            try:
                if isinstance(action, PushCommandAction):
                    err = self._validate_sim_command(action.player_id, action.cmd)
                    if err:
                        obs = ZeroADObservation(
                            ok=False,
                            error=err,
                            episode_id=self._state.episode_id,
                            step_count=self._state.step_count,
                            stepper_detected=self._state.stepper_detected,
                            sim_time=self._state.last_sim_time,
                        )
                        return obs.model_dump(mode="json")
                    result = self.rl.push_command(action.player_id, action.cmd)
                elif isinstance(action, EvaluateAction):
                    # RLInterfaceClient.evaluate uses a fixed 10s timeout internally.
                    # Keep timeout_s for API compatibility; ignore for now.
                    _ = timeout_s
                    result = self.rl.evaluate(action.code)
                else:
                    raise ValueError(f"unsupported action type: {type(action)}")
            except Exception as e:
                obs = ZeroADObservation(
                    ok=False,
                    error=str(e),
                    episode_id=self._state.episode_id,
                    step_count=self._state.step_count,
                    stepper_detected=self._state.stepper_detected,
                    sim_time=self._state.last_sim_time,
                )
                return obs.model_dump(mode="json")

            result = _normalize_eval_result(result)

            self._state.step_count += 1
            t = self._get_sim_time()
            if t is not None:
                self._state.last_sim_time = t

            obs = ZeroADObservation(
                ok=True,
                result=result,
                episode_id=self._state.episode_id,
                step_count=self._state.step_count,
                stepper_detected=self._state.stepper_detected,
                sim_time=self._state.last_sim_time,
            )
            return obs.model_dump(mode="json")
