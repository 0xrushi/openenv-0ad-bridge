"""Multi-provider LLM arena for 0 A.D.

Supports OpenAI, Grok (xAI), Gemini, and local OpenAI-compatible endpoints.
Each provider can control a player and make autonomous decisions.

This script reads game state snapshots and queries LLM providers for actions,
then executes those actions via the OpenEnv proxy.

Usage:
    # Set required API keys
    export OPENAI_API_KEY=sk-...
    export XAI_API_KEY=xai-...
    export GEMINI_API_KEY=...

    # Run the match
    python tools/multi_provider_match.py --config configs/multi_provider_match.toml

    # Dry run (show prompts without calling LLMs)
    python tools/multi_provider_match.py --config configs/multi_provider_match.toml --dry-run

Config:
    See configs/multi_provider_match.toml for examples

Requirements:
    - 0 A.D. running with RL interface
    - Stepper running and writing state snapshots
    - OpenEnv proxy running
"""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Literal

try:
    from pydantic import BaseModel, Field, ConfigDict
    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False
    print("Warning: pydantic not installed. Schema enforcement disabled.")
    print("Install with: pip install pydantic")

import tomllib


# ============================================================================
# HTTP Utilities
# ============================================================================


def _http_post_json(
    url: str, payload: Dict[str, Any], headers: Optional[Dict[str, str]] = None, timeout_s: float = 10.0
) -> Dict[str, Any]:
    """Post JSON payload and return JSON response."""
    data = json.dumps(payload).encode("utf-8")
    req_headers = {"content-type": "application/json"}
    if headers:
        req_headers.update(headers)

    req = urllib.request.Request(url, data=data, headers=req_headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:  # noqa: S310
        raw = resp.read().decode("utf-8")
    return json.loads(raw)


# ============================================================================
# OpenEnv API
# ============================================================================


def openenv_step(openenv_base: str, action: Dict[str, Any]) -> Dict[str, Any]:
    """Execute an action via the OpenEnv proxy."""
    return _http_post_json(f"{openenv_base.rstrip('/')}/step", {"action": action})


def openenv_reset(openenv_base: str) -> Dict[str, Any]:
    """Reset the OpenEnv proxy session."""
    return _http_post_json(f"{openenv_base.rstrip('/')}/reset", {})


# ============================================================================
# State Management
# ============================================================================


def _load_state_snapshot(path: Path) -> Optional[Dict[str, Any]]:
    """Load game state snapshot from file."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except Exception:
        return None


def _summarize_state(
    snapshot: Dict[str, Any], player_ids: List[int], max_entities: int = 50
) -> Dict[str, Any]:
    """Reduce the full game state to a prompt-sized summary.

    Includes:
    - Current step and game time
    - Entities for each player (id, position, template)
    - Limited to max_entities per player
    """
    state = snapshot.get("state") if isinstance(snapshot, dict) else None
    if not isinstance(state, dict):
        return {"error": "no_state"}

    entities = state.get("entities")
    if not isinstance(entities, dict):
        return {"error": "no_entities"}

    players_list = state.get("players")
    players_info = {}
    if isinstance(players_list, list):
        # Map 0 A.D. player index (0=Gaia, 1=Player1, etc.) to info
        for idx, pdata in enumerate(players_list):
             if not isinstance(pdata, dict):
                 continue
             players_info[idx] = {
                 "resources": pdata.get("resourceCounts"),
                 "pop": pdata.get("popCount"),
                 "popLimit": pdata.get("popLimit"),
                 "civ": pdata.get("civ"),
             }

    out: Dict[str, Any] = {
        "step": snapshot.get("step"),
        "time": snapshot.get("time"),
        "players": {},
        "global_players": players_info,  # Add global player stats
    }

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
                    "hitpoints": ent.get("hitpoints"),
                    "maxHitpoints": ent.get("maxHitpoints"),
                }
            )
            if len(lst) >= max_entities:
                break
        out["players"][str(pid)] = {"entities": lst, "entity_count": len(lst)}

    return out


# ============================================================================
# Pydantic Models for Schema Enforcement
# ============================================================================

if PYDANTIC_AVAILABLE:
    class GameCommand(BaseModel):
        """A single game command (walk, attack, gather, etc.)"""
        type: str = Field(..., description="Command type (walk, attack, gather, train, etc.)")
        entities: Optional[List[int]] = Field(None, description="Entity IDs to command")
        entity: Optional[int] = Field(None, description="Single entity ID (for research, etc.)")
        x: Optional[float] = Field(None, description="X coordinate")
        z: Optional[float] = Field(None, description="Z coordinate")
        target: Optional[int] = Field(None, description="Target entity ID")
        queued: Optional[bool] = Field(False, description="Whether to queue the command")
        pushFront: Optional[bool] = Field(None, description="Push to front of queue")
        template: Optional[str] = Field(None, description="Template name for construct/train")
        count: Optional[int] = Field(None, description="Count for train command")
        angle: Optional[float] = Field(None, description="Angle for construct")
        allowCapture: Optional[bool] = Field(None, description="Allow capturing buildings")
        targetClasses: Optional[Dict[str, List[str]]] = Field(None, description="Target classes for attack-walk")
        name: Optional[str] = Field(None, description="Name for stance/formation")
        autocontinue: Optional[bool] = Field(None, description="Auto-continue for repair")
        garrisonHolder: Optional[int] = Field(None, description="Garrison holder entity ID")
        garrisonHolders: Optional[List[int]] = Field(None, description="Garrison holder entity IDs")
        metadata: Optional[Dict[str, Any]] = Field(None, description="Metadata for train command")

        model_config = ConfigDict(extra="allow")  # Allow additional fields for flexibility

    class GameAction(BaseModel):
        """A single OpenEnv action"""
        op: Literal["push_command", "evaluate"] = Field(..., description="Operation type")
        player_id: Optional[int] = Field(None, description="Player ID (for push_command)")
        cmd: Optional[GameCommand] = Field(None, description="Command (for push_command)")
        code: Optional[str] = Field(None, description="JavaScript code (for evaluate)")

    class GameActions(BaseModel):
        """Container for multiple game actions"""
        actions: List[GameAction] = Field(default_factory=list, description="List of actions to execute")

        model_config = ConfigDict(
            json_schema_extra={
                "examples": [
                    {
                        "actions": [
                            {
                                "op": "push_command",
                                "player_id": 1,
                                "cmd": {
                                    "type": "walk",
                                    "entities": [123, 124],
                                    "x": 600,
                                    "z": 650,
                                    "queued": False,
                                    "pushFront": True
                                }
                            }
                        ]
                    }
                ]
            }
        )


# ============================================================================
# JSON Extraction
# ============================================================================


def _json_extract(s: str) -> Optional[Dict[str, Any]]:
    """Extract a JSON object from LLM output.

    Handles:
    - Pure JSON
    - JSON wrapped in markdown code blocks
    - Multiple code blocks (takes first valid one)
    """
    s = s.strip()
    if not s:
        return None

    # Try direct parse
    try:
        obj = json.loads(s)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass

    # Try fenced code blocks
    if "```" in s:
        parts = s.split("```")
        for i in range(1, len(parts), 2):
            block = parts[i]
            # Strip optional language tag (json, python, etc.)
            if "\n" in block:
                lines = block.split("\n", 1)
                if lines[0].strip().lower() in ("json", "python", "py", ""):
                    block = lines[1] if len(lines) > 1 else ""
            block = block.strip()
            try:
                obj = json.loads(block)
                if isinstance(obj, dict):
                    return obj
            except Exception:
                continue

    return None


# ============================================================================
# LLM Provider Configurations
# ============================================================================


@dataclass
class AgentConfig:
    """Configuration for a single agent/player."""
    key: str
    player_id: int
    name: str
    provider: str  # "openai", "grok", "gemini", or "local"
    model: str
    temperature: float
    max_output_tokens: int
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    api_key_env: Optional[str] = None
    strategy_hint: Optional[str] = None


def _get_provider_config(provider: str, config: Dict[str, Any]) -> tuple[str, str]:
    """Get base_url and api_key for a provider.

    Returns:
        (base_url, api_key)
    """
    if provider == "openai":
        base_url = config.get("base_url") or os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
        api_key_env = config.get("api_key_env", "OPENAI_API_KEY")
        api_key = config.get("api_key") or os.environ.get(api_key_env)
        if not api_key:
            raise RuntimeError(f"API key not found: set {api_key_env} environment variable")
        return base_url.rstrip("/"), api_key

    elif provider == "grok":
        base_url = config.get("base_url", "https://api.x.ai/v1")
        api_key_env = config.get("api_key_env", "XAI_API_KEY")
        api_key = config.get("api_key") or os.environ.get(api_key_env)
        if not api_key:
            raise RuntimeError(f"Grok API key not found: set {api_key_env} environment variable")
        return base_url.rstrip("/"), api_key

    elif provider == "gemini":
        # Gemini uses OpenAI-compatible API via Google AI Studio
        base_url = config.get("base_url", "https://generativelanguage.googleapis.com/v1beta/openai")
        api_key_env = config.get("api_key_env", "GEMINI_API_KEY")
        api_key = config.get("api_key") or os.environ.get(api_key_env)
        if not api_key:
            raise RuntimeError(f"Gemini API key not found: set {api_key_env} environment variable")
        return base_url.rstrip("/"), api_key

    elif provider == "local":
        base_url = config.get("base_url", "http://localhost:1234/v1")
        api_key = config.get("api_key", "not-needed")  # Local servers often don't need real keys
        return base_url.rstrip("/"), api_key

    else:
        raise ValueError(f"Unknown provider: {provider}")


# ============================================================================
# LLM API Call
# ============================================================================


def _llm_chat(
    agent: AgentConfig,
    messages: List[Dict[str, str]],
    use_schema: bool = True,
) -> str:
    """Call an LLM provider's chat completion endpoint.

    Supports OpenAI, Grok, Gemini, and local OpenAI-compatible servers.

    Args:
        agent: Agent configuration
        messages: Chat messages
        use_schema: Whether to enforce JSON schema (requires pydantic)
    """
    if not agent.base_url or not agent.api_key:
        raise RuntimeError(f"Agent {agent.name} missing base_url or api_key")

    url = f"{agent.base_url}/chat/completions"

    payload = {
        "model": agent.model,
        "messages": messages,
        "temperature": agent.temperature,
        "max_tokens": agent.max_output_tokens,
    }

    # Add JSON schema enforcement if available
    if use_schema and PYDANTIC_AVAILABLE:
        try:
            # Gemini doesn't support strict json_schema mode well yet
            # Use simpler json_object mode for now
            if agent.provider == "gemini":
                payload["response_format"] = {"type": "json_object"}
            # OpenAI supports strict schema
            elif agent.provider in ("openai", "local"):
                schema = GameActions.model_json_schema()
                payload["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "game_actions",
                        "strict": True,
                        "schema": schema
                    }
                }
            # Grok uses json_object mode
            elif agent.provider == "grok":
                payload["response_format"] = {"type": "json_object"}
            else:
                payload["response_format"] = {"type": "json_object"}

        except Exception as e:
            print(f"  Warning: Could not add schema enforcement: {e}")
            # Fallback to json_object mode
            payload["response_format"] = {"type": "json_object"}
    else:
        # Fallback: request JSON format without strict schema
        payload["response_format"] = {"type": "json_object"}

    headers = {
        "content-type": "application/json",
        "authorization": f"Bearer {agent.api_key}",
    }

    try:
        resp = _http_post_json(url, payload, headers=headers, timeout_s=120)

        # Check finish_reason for debugging
        finish_reason = resp.get("choices", [{}])[0].get("finish_reason")
        if finish_reason == "length":
            print(f"  Warning: Response truncated due to max_tokens limit!")
            print(f"  Current max_tokens: {payload['max_tokens']}")

        # Get usage info if available
        if "usage" in resp:
            usage = resp["usage"]
            completion_tokens = usage.get("completion_tokens", 0)
            if completion_tokens >= payload["max_tokens"] * 0.9:
                print(f"  Warning: Used {completion_tokens}/{payload['max_tokens']} tokens (90%+)")

        return resp["choices"][0]["message"]["content"]
    except Exception as e:
        raise RuntimeError(f"LLM API call failed: {e}")


# ============================================================================
# Agent Prompting
# ============================================================================


def _load_skills_knowledge() -> str:
    """Load skills documentation to include in agent knowledge."""
    skills_dir = Path("skills")
    if not skills_dir.exists():
        return ""

    knowledge_parts = []

    # Load key skill files
    for filename in ["openenv-actions.md", "cookbook-gameplay.md"]:
        filepath = skills_dir / filename
        if filepath.exists():
            content = filepath.read_text(encoding="utf-8")
            knowledge_parts.append(f"## {filename}\n\n{content}")

    return "\n\n".join(knowledge_parts)


_SKILLS_KNOWLEDGE = _load_skills_knowledge()


def _agent_prompt(
    agent: AgentConfig,
    summary: Dict[str, Any],
    max_actions: int
) -> List[Dict[str, str]]:
    """Generate the prompt for an agent to make a decision.

    Includes:
    - System prompt with rules and action schema
    - Skills/actions documentation
    - Current game state observation
    - Strategy hint (if configured)
    """

    system_parts = [
        f"You are an autonomous RTS agent controlling player {agent.player_id} in 0 A.D.",
        "",
        "## Your Task",
        "Analyze the current game state and output 0-{} OpenEnv actions as JSON.".format(max_actions),
        "",
        "## IMPORTANT: JSON Format (STRICTLY ENFORCED)",
        "Your response MUST be valid JSON matching this exact schema:",
        "- Top level: object with 'actions' array",
        "- Each action: object with 'op' field (either 'push_command' or 'evaluate')",
        "- For push_command: include 'player_id' and 'cmd' object",
        "- For evaluate: include 'code' string",
        "",
        "DO NOT include any text before or after the JSON.",
        "DO NOT wrap in markdown code blocks.",
        "Output ONLY the raw JSON object.",
        "",
        "## Rules",
        f"1. You are player_id={agent.player_id}",
        f"2. Maximum {max_actions} actions per decision",
        "3. Use only entity IDs that exist for your player in the observation",
        "4. If no good action is available, return: {\"actions\": []}",
        "",
        "## Action Schema",
        "```json",
        "{",
        '  "actions": [',
        "    {",
        '      "op": "push_command",',
        f'      "player_id": {agent.player_id},',
        '      "cmd": {',
        '        "type": "walk",',
        '        "entities": [123, 124],',
        '        "x": 600,',
        '        "z": 650,',
        '        "queued": false,',
        '        "pushFront": true',
        "      }",
        "    }",
        "  ]",
        "}",
        "```",
        "",
        "## Available Actions",
        "You can use these command types in 'cmd':",
        "",
        "**Movement:**",
        "- walk: {type:'walk', entities:[...], x:NUM, z:NUM, queued:BOOL, pushFront:BOOL}",
        "- stop: {type:'stop', entities:[...], queued:BOOL}",
        "- patrol: {type:'patrol', entities:[...], x:NUM, z:NUM, queued:BOOL}",
        "",
        "**Combat:**",
        "- attack: {type:'attack', entities:[...], target:ENTITY_ID, queued:BOOL}",
        "- attack-walk: {type:'attack-walk', entities:[...], x:NUM, z:NUM, queued:BOOL}",
        "",
        "**Economy:**",
        "- gather: {type:'gather', entities:[...], target:RESOURCE_ID, queued:BOOL}",
        "- returnresource: {type:'returnresource', entities:[...], target:DROPSITE_ID, queued:BOOL}",
        "",
        "**Building:**",
        "- construct: {type:'construct', entities:[...], template:STR, x:NUM, z:NUM, angle:NUM, queued:BOOL}",
        "  REQUIRED: x, z, angle fields for placement!",
        "",
        "**Production:**",
        "- train: {type:'train', entities:[BUILDING_ID], template:STR, count:NUM}",
        "",
        "**Important:** Always include ALL required fields for each command type!",
        "",
    ]

    # Add strategy hint if provided
    if agent.strategy_hint:
        system_parts.extend([
            "## Your Strategy",
            agent.strategy_hint.strip(),
            "",
        ])

    # Add skills knowledge if available (reduced for token efficiency)
    if _SKILLS_KNOWLEDGE and agent.provider != "gemini":
        system_parts.extend([
            "## Reference: Available Commands",
            "(See documentation below for detailed command examples)",
            "",
            _SKILLS_KNOWLEDGE[:2000],  # Limit to avoid token overflow
            "",
        ])
    elif agent.provider == "gemini":
        # Gemini: skip detailed skills to save tokens
        system_parts.append("Refer to the action examples above for command syntax.")
        system_parts.append("")

    system = "\n".join(system_parts)

    user_content = {
        "you_are": {
            "name": agent.name,
            "player_id": agent.player_id,
        },
        "observation": summary,
        "instruction": (
            "Analyze the game state and decide on 0-{} actions. "
            "Check 'global_players' for your current resources and population. "
            "Think step by step: "
            "1. Check if you have enough resources for your desired action (e.g., training units). "
            "2. If resources are low (e.g., < 100 food), prioritize 'gather' actions. "
            "3. Only then, output JSON with an 'actions' array. "
            "If uncertain, output fewer actions or an empty list."
        ).format(max_actions),
    }

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(user_content, indent=2)},
    ]


# ============================================================================
# Logging
# ============================================================================


def _log_decision(log_file: Optional[Path], record: Dict[str, Any]) -> None:
    """Append a decision record to the log file (JSONL format)."""
    if not log_file:
        return

    log_file.parent.mkdir(parents=True, exist_ok=True)
    with log_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


# ============================================================================
# Main Loop
# ============================================================================


def main() -> None:
    parser = argparse.ArgumentParser(description="Multi-provider LLM arena match")
    parser.add_argument("--config", default="configs/multi_provider_match.toml", help="Config file path")
    parser.add_argument("--dry-run", action="store_true", help="Show prompts without calling LLMs")
    args = parser.parse_args()

    cfg_path = Path(args.config)
    if not cfg_path.exists():
        raise SystemExit(f"Config file not found: {cfg_path}")

    cfg = tomllib.loads(cfg_path.read_text(encoding="utf-8"))

    # Match configuration
    match = cfg.get("match") or {}
    openenv_base = match.get("openenv_base", "http://127.0.0.1:8001")
    state_file = Path(match.get("state_file", "run/latest_state.json"))
    decision_interval_s = float(match.get("decision_interval_s", 1.0))
    max_actions = int(match.get("max_actions_per_decision", 3))
    max_entities = int(match.get("max_entities_in_summary", 50))
    log_decisions = match.get("log_decisions", False)
    log_file = Path(match["log_file"]) if log_decisions and "log_file" in match else None

    # Parse player configurations
    players_cfg = cfg.get("players") or {}
    agents: List[AgentConfig] = []

    for key, p in players_cfg.items():
        # Check if player is enabled (default: true)
        if not p.get("enabled", True):
            print(f"Skipping disabled player: {key} (player_id={p.get('player_id')})")
            continue

        provider = p.get("provider", "openai")
        base_url, api_key = _get_provider_config(provider, p)

        agents.append(
            AgentConfig(
                key=key,
                player_id=int(p["player_id"]),
                name=str(p.get("name", key)),
                provider=provider,
                model=str(p["model"]),
                temperature=float(p.get("temperature", 0.2)),
                max_output_tokens=int(p.get("max_output_tokens", 800)),
                base_url=base_url,
                api_key=api_key,
                strategy_hint=p.get("strategy_hint"),
            )
        )

    agents.sort(key=lambda a: a.player_id)

    # Print configuration
    print("=" * 70)
    print("Multi-Provider LLM Arena Match")
    print("=" * 70)
    print(f"OpenEnv base: {openenv_base}")
    print(f"State file: {state_file}")
    print(f"Decision interval: {decision_interval_s}s")
    print(f"Max actions per decision: {max_actions}")
    print()

    if not agents:
        raise SystemExit("No enabled agents found in configuration. Enable at least one player.")

    print(f"Enabled Agents: {len(agents)}")
    for a in agents:
        print(f"  Player {a.player_id}: {a.name}")
        print(f"    Provider: {a.provider}")
        print(f"    Model: {a.model}")
        print(f"    Base URL: {a.base_url}")

    # Check for AI-controlled players
    all_player_ids = set(p.get("player_id") for p in players_cfg.values() if p.get("player_id"))
    agent_player_ids = set(a.player_id for a in agents)
    ai_controlled = sorted(all_player_ids - agent_player_ids)

    if ai_controlled:
        print()
        print(f"AI-Controlled Players: {ai_controlled}")
        print("  (These players are controlled by built-in 0 A.D. AI)")

    print("=" * 70)
    print()

    # Reset proxy session
    print("Resetting OpenEnv proxy...")
    try:
        openenv_reset(openenv_base)
        print("✓ Proxy reset successful")
    except Exception as e:
        raise SystemExit(f"Failed to reset OpenEnv proxy: {e}")

    print()
    print("Waiting for game state updates...")
    print("(Ensure stepper is running and writing to state file)")
    print()

    last_step = None
    decision_count = 0

    try:
        while True:
            # Load latest state snapshot
            snap = _load_state_snapshot(state_file)
            if not snap:
                time.sleep(0.25)
                continue

            # Wait for state to update
            current_step = snap.get("step")
            if current_step == last_step:
                time.sleep(0.25)
                continue

            last_step = current_step
            decision_count += 1

            print(f"\n[Decision {decision_count}] Step {current_step}, Time {snap.get('time', 'unknown')}")

            # Summarize state for agents
            summary = _summarize_state(snap, [a.player_id for a in agents], max_entities=max_entities)

            # Each agent makes a decision
            for agent in agents:
                messages = _agent_prompt(agent, summary, max_actions=max_actions)

                if args.dry_run:
                    print(f"\n[{agent.name}] DRY RUN - System Prompt Preview:")
                    print(messages[0]["content"][:500])
                    print(f"\n[{agent.name}] DRY RUN - User Prompt Preview:")
                    print(messages[1]["content"][:500])
                    continue

                # Call LLM
                try:
                    start_time = time.time()
                    output = _llm_chat(agent, messages)
                    elapsed = time.time() - start_time
                    print(f"  [{agent.name}] Raw Output:\n{output}")
                except Exception as e:
                    print(f"  [{agent.name}] ✗ LLM call failed: {e}")
                    continue

                # Parse and validate JSON response
                obj = None
                validation_error = None

                # Try Pydantic validation first (strictest)
                if PYDANTIC_AVAILABLE:
                    try:
                        # Try direct JSON parse
                        data = json.loads(output.strip())
                        validated = GameActions.model_validate(data)
                        obj = validated.model_dump(exclude_none=True)
                    except json.JSONDecodeError as e:
                        validation_error = f"JSON decode error: {e}"
                        # Fallback to extraction
                        obj = _json_extract(output)
                        if obj:
                            try:
                                validated = GameActions.model_validate(obj)
                                obj = validated.model_dump()
                                validation_error = None  # Success via extraction
                            except Exception as ve:
                                validation_error = f"Pydantic validation error: {ve}"
                    except Exception as e:
                        validation_error = f"Pydantic validation error: {e}"
                        obj = _json_extract(output)
                else:
                    # No Pydantic, use basic extraction
                    obj = _json_extract(output)

                if not obj or "actions" not in obj or not isinstance(obj["actions"], list):
                    print(f"  [{agent.name}] ✗ Invalid output (expected JSON with 'actions' array)")
                    print(f"  Output length: {len(output)} chars")
                    print(f"  First 500 chars: {output[:500]}")
                    if validation_error:
                        print(f"  Validation error: {validation_error}")
                    if obj:
                        print(f"  Parsed object keys: {list(obj.keys())}")
                    else:
                        print(f"  JSON extraction failed - no valid JSON found")
                    if log_file:
                        _log_decision(log_file, {
                            "timestamp": datetime.now().isoformat(),
                            "step": current_step,
                            "agent": agent.name,
                            "error": "invalid_output",
                            "validation_error": validation_error,
                            "output": output[:1000],
                            "output_length": len(output),
                            "extracted_obj": str(obj) if obj else None,
                        })
                    continue

                # Execute actions
                actions_sent = 0
                actions_rejected = 0

                for action in obj["actions"][:max_actions]:
                    if not isinstance(action, dict):
                        continue

                    # Ensure player_id is correct
                    if action.get("op") == "push_command":
                        action["player_id"] = agent.player_id

                        # Validate construct commands have required fields
                        cmd = action.get("cmd", {})
                        if cmd.get("type") == "construct":
                            missing_fields = []
                            if "x" not in cmd or cmd["x"] is None:
                                missing_fields.append("x")
                            if "z" not in cmd or cmd["z"] is None:
                                missing_fields.append("z")
                            if "angle" not in cmd or cmd["angle"] is None:
                                cmd["angle"] = 0  # Default angle if missing

                            if missing_fields:
                                print(f"  [{agent.name}] ✗ construct command missing required fields: {missing_fields}")
                                print(f"    Command: {json.dumps(cmd, indent=2)[:200]}")
                                actions_rejected += 1
                                continue

                        # Remove null fields that shouldn't be there
                        if isinstance(cmd, dict):
                            # targetClasses should only be in attack-walk
                            if cmd.get("type") not in ("attack-walk",) and "targetClasses" in cmd:
                                del cmd["targetClasses"]
                            # metadata should only be in train
                            if cmd.get("type") not in ("train",) and "metadata" in cmd:
                                del cmd["metadata"]

                    try:
                        resp = openenv_step(openenv_base, action)
                        obs = resp.get("observation") if isinstance(resp, dict) else None

                        if isinstance(obs, dict):
                            if obs.get("ok") is False:
                                actions_rejected += 1
                                error_msg = obs.get("error", "unknown")
                                print(f"  [{agent.name}] ✗ Action rejected: {error_msg}")
                            else:
                                actions_sent += 1
                        else:
                            actions_sent += 1

                    except urllib.error.HTTPError as e:
                        # HTTP error with response body
                        print(f"  [{agent.name}] ✗ Action send failed: HTTP {e.code}")
                        try:
                            error_body = e.read().decode("utf-8")
                            print(f"    Server error: {error_body[:300]}")
                        except:
                            pass
                        print(f"    Action: {json.dumps(action, indent=2)[:300]}")
                        continue
                    except Exception as e:
                        print(f"  [{agent.name}] ✗ Action send failed: {e}")
                        print(f"    Action: {json.dumps(action, indent=2)[:300]}")
                        continue

                # Log decision
                status_icon = "✓" if actions_sent > 0 else "○"
                print(f"  [{agent.name}] {status_icon} Sent {actions_sent}/{len(obj['actions'])} actions ({elapsed:.2f}s)")
                if obj['actions']:
                    print(f"  [{agent.name}] Parsed Decisions: {json.dumps(obj['actions'], indent=2)}")

                if log_file:
                    _log_decision(log_file, {
                        "timestamp": datetime.now().isoformat(),
                        "step": current_step,
                        "agent": agent.name,
                        "model": agent.model,
                        "provider": agent.provider,
                        "actions_sent": actions_sent,
                        "actions_rejected": actions_rejected,
                        "elapsed_s": elapsed,
                        "output": output,
                    })

            # Wait before next decision
            time.sleep(decision_interval_s)

    except KeyboardInterrupt:
        print("\n\nMatch interrupted by user")
        print(f"Total decisions: {decision_count}")
        if log_file and log_file.exists():
            print(f"Log file: {log_file}")


if __name__ == "__main__":
    main()
