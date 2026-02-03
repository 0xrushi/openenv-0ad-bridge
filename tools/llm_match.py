"""Run an LLM-vs-LLM match using the OpenEnv proxy.

This script does not step the simulation. It assumes a separate stepper is
calling the 0 A.D. RL interface `/step` continuously (see `tools/execute_move.py --run`).

It reads an omniscient snapshot from a file written by the stepper and asks
two LLM agents (e.g. gpt-4o vs gpt-5) to output low-level OpenEnv actions:
- op=push_command (inject Simulation2 command dict)
- op=evaluate (run JS snippet)

Config:
  configs/llm_match.toml

Env:
  OPENAI_API_KEY   required for real LLM calls
  OPENAI_BASE_URL  optional (defaults to https://api.openai.com/v1)
"""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import tomllib


def _http_post_json(
    url: str, payload: Dict[str, Any], timeout_s: float = 10.0
) -> Dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"content-type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:  # noqa: S310
        raw = resp.read().decode("utf-8")
    return json.loads(raw)


def openenv_step(openenv_base: str, action: Dict[str, Any]) -> Dict[str, Any]:
    return _http_post_json(f"{openenv_base.rstrip('/')}/step", {"action": action})


def openenv_reset(openenv_base: str) -> Dict[str, Any]:
    return _http_post_json(f"{openenv_base.rstrip('/')}/reset", {})


def _load_state_snapshot(path: Path) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except Exception:
        return None


def _summarize_state(
    snapshot: Dict[str, Any], player_ids: List[int], max_entities: int = 40
) -> Dict[str, Any]:
    """Reduce the stepper snapshot to a prompt-sized summary."""

    state = snapshot.get("state") if isinstance(snapshot, dict) else None
    if not isinstance(state, dict):
        return {"error": "no_state"}

    entities = state.get("entities")
    if not isinstance(entities, dict):
        return {"error": "no_entities"}

    out: Dict[str, Any] = {
        "step": snapshot.get("step"),
        "time": snapshot.get("time"),
        "players": {},
    }

    # entities keys are strings.
    for pid in player_ids:
        lst: List[Dict[str, Any]] = []
        for sid, ent in entities.items():
            if not isinstance(ent, dict):
                continue
            if ent.get("owner") != pid:
                continue
            pos = ent.get("position")
            lst.append(
                {
                    "id": int(sid) if str(sid).isdigit() else sid,
                    "pos": pos,
                    "template": ent.get("template"),
                }
            )
            if len(lst) >= max_entities:
                break
        out["players"][str(pid)] = {"entities": lst}

    return out


def _json_extract(s: str) -> Optional[Dict[str, Any]]:
    """Extract a JSON object from a model output.

    Accepts pure JSON or a JSON block wrapped in markdown.
    """

    s = s.strip()
    if not s:
        return None

    # Try direct parse.
    try:
        obj = json.loads(s)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass

    # Try fenced block.
    if "```" in s:
        parts = s.split("```")
        for i in range(1, len(parts), 2):
            block = parts[i]
            # Strip optional language tag
            block = block.split("\n", 1)[1] if "\n" in block else ""
            block = block.strip()
            try:
                obj = json.loads(block)
                if isinstance(obj, dict):
                    return obj
            except Exception:
                continue
    return None


@dataclass
class AgentConfig:
    key: str
    player_id: int
    name: str
    model: str
    temperature: float
    max_output_tokens: int


def _openai_chat(
    model: str,
    messages: List[Dict[str, str]],
    temperature: float,
    max_output_tokens: int,
) -> str:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")

    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip(
        "/"
    )
    url = f"{base_url}/chat/completions"

    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_output_tokens,
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "content-type": "application/json",
            "authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310
        raw = resp.read().decode("utf-8")
    out = json.loads(raw)
    return out["choices"][0]["message"]["content"]


def _agent_prompt(
    agent: AgentConfig, summary: Dict[str, Any], max_actions: int
) -> List[Dict[str, str]]:
    system = (
        "You are an RTS control agent for 0 A.D.\n"
        "You output low-level OpenEnv actions as JSON.\n\n"
        "Rules:\n"
        "- Output ONLY JSON.\n"
        f"- You are player_id={agent.player_id}.\n"
        f"- Return at most {max_actions} actions per decision.\n"
        "- Prefer op=push_command to issue commands.\n"
        "- Only use entity ids that exist for your player from the observation.\n\n"
        "Action schema:\n"
        "{\n"
        '  "actions": [\n'
        "    {\n"
        '      "op": "push_command",\n'
        '      "player_id": 1,\n'
        '      "cmd": {"type":"walk","entities":[123],"x":500,"z":500,"queued":false,"pushFront":true}\n'
        "    }\n"
        "  ]\n"
        "}\n"
    )
    user = {
        "you_are": {"name": agent.name, "player_id": agent.player_id},
        "observation": summary,
        "objective": "Play to win. If no good action, return an empty actions list.",
    }
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(user)},
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/llm_match.toml")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    cfg_path = Path(args.config)
    cfg = tomllib.loads(cfg_path.read_text(encoding="utf-8"))

    match = cfg.get("match") or {}
    openenv_base = match.get("openenv_base", "http://127.0.0.1:8001")
    state_file = Path(match.get("state_file", "run/latest_state.json"))
    decision_interval_s = float(match.get("decision_interval_s", 1.0))
    max_actions = int(match.get("max_actions_per_decision", 2))

    players = cfg.get("players") or {}
    agents: List[AgentConfig] = []
    for key, p in players.items():
        agents.append(
            AgentConfig(
                key=key,
                player_id=int(p["player_id"]),
                name=str(p.get("name", key)),
                model=str(p["model"]),
                temperature=float(p.get("temperature", 0.2)),
                max_output_tokens=int(p.get("max_output_tokens", 600)),
            )
        )
    agents.sort(key=lambda a: a.player_id)

    print(f"OpenEnv base: {openenv_base}")
    print(f"State file: {state_file}")
    print("Agents:")
    for a in agents:
        print(f"  - p{a.player_id}: {a.name} ({a.model})")

    print("Resetting proxy session...")
    try:
        openenv_reset(openenv_base)
    except Exception as e:
        raise SystemExit(f"Failed to reset OpenEnv proxy: {e}")

    last_step = None
    while True:
        snap = _load_state_snapshot(state_file)
        if not snap:
            time.sleep(0.25)
            continue
        if snap.get("step") == last_step:
            time.sleep(0.25)
            continue
        last_step = snap.get("step")

        summary = _summarize_state(snap, [a.player_id for a in agents])

        for agent in agents:
            messages = _agent_prompt(agent, summary, max_actions=max_actions)
            if args.dry_run:
                print(f"\n[{agent.name}] DRY RUN prompt:")
                print(messages[-1]["content"])
                continue

            try:
                out = _openai_chat(
                    model=agent.model,
                    messages=messages,
                    temperature=agent.temperature,
                    max_output_tokens=agent.max_output_tokens,
                )
            except Exception as e:
                print(f"[{agent.name}] LLM error: {e}")
                continue

            obj = _json_extract(out)
            if not obj or "actions" not in obj or not isinstance(obj["actions"], list):
                print(
                    f"[{agent.name}] invalid output (expected JSON with actions): {out[:200]!r}"
                )
                continue

            sent = 0
            for action in obj["actions"][:max_actions]:
                if not isinstance(action, dict):
                    continue
                # Ensure correct player_id.
                if action.get("op") == "push_command":
                    action["player_id"] = agent.player_id

                try:
                    resp = openenv_step(openenv_base, action)
                except Exception as e:
                    print(f"[{agent.name}] send failed: {e}")
                    continue

                obs = resp.get("observation") if isinstance(resp, dict) else None
                if isinstance(obs, dict) and obs.get("ok") is False:
                    print(f"[{agent.name}] rejected: {obs.get('error')}")
                sent += 1

            if sent:
                print(f"[{agent.name}] sent {sent} action(s) at step {last_step}")

        time.sleep(decision_interval_s)


if __name__ == "__main__":
    main()
