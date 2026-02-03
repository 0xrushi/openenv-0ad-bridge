"""Test Pydantic schema validation for game actions."""

import json
from pydantic import BaseModel, Field, ValidationError
from typing import List, Optional, Dict, Any, Literal


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

    class Config:
        extra = "allow"


class GameAction(BaseModel):
    """A single OpenEnv action"""
    op: Literal["push_command", "evaluate"] = Field(..., description="Operation type")
    player_id: Optional[int] = Field(None, description="Player ID (for push_command)")
    cmd: Optional[GameCommand] = Field(None, description="Command (for push_command)")
    code: Optional[str] = Field(None, description="JavaScript code (for evaluate)")


class GameActions(BaseModel):
    """Container for multiple game actions"""
    actions: List[GameAction] = Field(default_factory=list, description="List of actions to execute")


# Test cases
test_cases = [
    # Valid: Walk command
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
    },
    # Valid: Multiple actions
    {
        "actions": [
            {
                "op": "push_command",
                "player_id": 1,
                "cmd": {"type": "walk", "entities": [123], "x": 500, "z": 500}
            },
            {
                "op": "push_command",
                "player_id": 1,
                "cmd": {"type": "gather", "entities": [200], "target": 5555}
            }
        ]
    },
    # Valid: Empty actions
    {"actions": []},
    # Valid: Evaluate action
    {
        "actions": [
            {
                "op": "evaluate",
                "code": "JSON.stringify({ok: true})"
            }
        ]
    },
    # Invalid: Missing 'actions' key
    {"commands": []},
    # Invalid: Wrong op type
    {
        "actions": [
            {"op": "invalid_op", "player_id": 1}
        ]
    },
]

print("=" * 70)
print("Testing Pydantic Schema Validation")
print("=" * 70)
print()

for i, test in enumerate(test_cases, 1):
    print(f"Test {i}:")
    print(f"Input: {json.dumps(test, indent=2)[:200]}...")
    try:
        validated = GameActions.model_validate(test)
        print(f"✓ VALID - {len(validated.actions)} action(s)")
        if validated.actions:
            for j, action in enumerate(validated.actions, 1):
                print(f"  Action {j}: op={action.op}", end="")
                if action.op == "push_command" and action.cmd:
                    print(f", cmd.type={action.cmd.type}", end="")
                print()
    except ValidationError as e:
        print(f"✗ INVALID")
        for error in e.errors():
            print(f"  - {error['loc']}: {error['msg']}")
    print()

print("=" * 70)
print("JSON Schema Output")
print("=" * 70)
schema = GameActions.model_json_schema()
print(json.dumps(schema, indent=2)[:500] + "...")
print()
print(f"Full schema length: {len(json.dumps(schema))} bytes")
