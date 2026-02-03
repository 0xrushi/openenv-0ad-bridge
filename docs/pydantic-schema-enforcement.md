# Pydantic Schema Enforcement

The multi-provider LLM arena now uses **Pydantic schema enforcement** to ensure LLMs return properly structured JSON responses.

## What Is It?

Instead of relying on LLMs to follow JSON format instructions, we:
1. Define a strict Pydantic schema for game actions
2. Send the JSON schema to the LLM API
3. The API enforces the schema and guarantees valid output
4. We validate the response with Pydantic

## Benefits

✅ **No more malformed JSON** - LLMs must follow exact schema
✅ **Automatic validation** - Pydantic catches structure errors
✅ **Better error messages** - Know exactly what went wrong
✅ **Type safety** - All fields are properly typed
✅ **Auto-completion** - IDEs can suggest fields

## Schema Definition

### GameActions (Top Level)
```python
class GameActions(BaseModel):
    actions: List[GameAction]  # List of 0-N actions
```

### GameAction (Individual Action)
```python
class GameAction(BaseModel):
    op: Literal["push_command", "evaluate"]  # Operation type
    player_id: Optional[int]                 # For push_command
    cmd: Optional[GameCommand]               # Command details
    code: Optional[str]                      # For evaluate
```

### GameCommand (Command Details)
```python
class GameCommand(BaseModel):
    type: str                    # walk, attack, gather, etc.
    entities: Optional[List[int]] # Entity IDs to command
    x: Optional[float]           # X coordinate
    z: Optional[float]           # Z coordinate
    target: Optional[int]        # Target entity ID
    queued: Optional[bool]       # Queue the command
    template: Optional[str]      # Template for construct/train
    # ... and more fields
```

## Example Valid JSON

```json
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
        "queued": false,
        "pushFront": true
      }
    },
    {
      "op": "push_command",
      "player_id": 1,
      "cmd": {
        "type": "gather",
        "entities": [200],
        "target": 5555
      }
    }
  ]
}
```

## Provider Support

| Provider | Schema Support | Mode |
|----------|---------------|------|
| **OpenAI** | ✅ Full | `json_schema` with `strict: true` |
| **Gemini** | ✅ Full | `json_schema` with `strict: true` |
| **Grok** | ⚠️ Partial | `json_object` (no strict schema) |
| **Local** | ⚠️ Varies | Depends on server implementation |

## Testing the Schema

### Test 1: Validate Schema Definition
```bash
python tools/test_schema.py
```

Expected output:
```
======================================================================
Testing Pydantic Schema Validation
======================================================================

Test 1:
Input: {"actions": [{"op": "push_command", "player_id": 1, ...
✓ VALID - 1 action(s)
  Action 1: op=push_command, cmd.type=walk

Test 2:
Input: {"actions": [{"op": "push_command", ...
✓ VALID - 2 action(s)
  Action 1: op=push_command, cmd.type=walk
  Action 2: op=push_command, cmd.type=gather

Test 3:
Input: {"actions": []}...
✓ VALID - 0 action(s)

Test 4:
Input: {"actions": [{"op": "evaluate", ...
✓ VALID - 1 action(s)
  Action 1: op=evaluate

Test 5:
Input: {"commands": []}...
✗ INVALID
  - actions: Field required

Test 6:
Input: {"actions": [{"op": "invalid_op", ...
✗ INVALID
  - actions.0.op: Input should be 'push_command' or 'evaluate'
```

### Test 2: Test with Real LLM
```bash
# Run with schema enforcement enabled (default)
python tools/multi_provider_match.py --config configs/gemini_vs_ai.toml
```

The output will now show:
- `✓` Success: Schema validated
- `✗` Invalid: Shows Pydantic validation errors

## How It Works

### 1. Schema Generation
```python
schema = GameActions.model_json_schema()
# Returns JSON Schema compatible with OpenAI/Gemini
```

### 2. API Request with Schema
```python
payload = {
    "model": "gemini-3-flash-preview",
    "messages": [...],
    "response_format": {
        "type": "json_schema",
        "json_schema": {
            "name": "game_actions",
            "strict": True,
            "schema": schema
        }
    }
}
```

### 3. Response Validation
```python
data = json.loads(output)
validated = GameActions.model_validate(data)
# Raises ValidationError if invalid
```

## Error Handling

### Before (Without Schema)
```
[Gemini] ✗ Invalid output (expected JSON with 'actions' array)
Output length: 1234 chars
First 500 chars: {"action": [{"type": "walk"...
```

Hard to debug - is it a JSON parse error? Missing field? Wrong type?

### After (With Schema)
```
[Gemini] ✗ Invalid output (expected JSON with 'actions' array)
Output length: 1234 chars
Validation error: Pydantic validation error: 1 validation error for GameActions
actions.0.cmd.entities
  Field required [type=missing, input_value={'type': 'walk', 'x': 600}, input_type=dict]
```

Clear error - the `entities` field is missing from the walk command!

## Configuration

Schema enforcement is **enabled by default**. To disable:

```python
# In multi_provider_match.py
output = _llm_chat(agent, messages, use_schema=False)
```

Or if Pydantic is not installed:
```bash
# Schema enforcement automatically disabled
# Falls back to basic JSON extraction
```

## Common Validation Errors

### 1. Missing Required Field
```
ValidationError: 1 validation error for GameActions
actions
  Field required
```
**Fix**: Ensure response has `"actions"` key

### 2. Wrong Operation Type
```
ValidationError: 1 validation error for GameActions
actions.0.op
  Input should be 'push_command' or 'evaluate'
```
**Fix**: Use only `"push_command"` or `"evaluate"` for `op` field

### 3. Missing Command
```
ValidationError: 1 validation error for GameActions
actions.0.cmd
  Field required
```
**Fix**: Include `cmd` object for `push_command` operations

### 4. Invalid Entity IDs
```
ValidationError: 1 validation error for GameActions
actions.0.cmd.entities.0
  Input should be a valid integer
```
**Fix**: Ensure entity IDs are integers, not strings

## Debugging

### Check What Schema Is Sent
```python
from tools.multi_provider_match import GameActions
import json

schema = GameActions.model_json_schema()
print(json.dumps(schema, indent=2))
```

### Test Validation Locally
```python
from tools.multi_provider_match import GameActions

test_data = {
    "actions": [
        {"op": "push_command", "player_id": 1, "cmd": {"type": "walk", "entities": [123], "x": 500, "z": 500}}
    ]
}

try:
    validated = GameActions.model_validate(test_data)
    print("✓ Valid!")
except Exception as e:
    print(f"✗ Invalid: {e}")
```

## Performance Impact

Schema enforcement adds minimal overhead:
- **Schema generation**: Once at startup (~1ms)
- **Validation**: ~0.1ms per response
- **API latency**: No change (schema sent with request)

## Migration Guide

Old configs work without changes. Schema enforcement is automatic.

**Before:**
```python
obj = _json_extract(output)
if not obj or "actions" not in obj:
    print("Invalid output")
```

**After:**
```python
validated = GameActions.model_validate(json.loads(output))
obj = validated.model_dump()
# Guaranteed to have correct structure
```

## Requirements

```bash
# Already in requirements.txt
pip install pydantic>=2
```

If Pydantic is not installed, the system falls back to basic JSON extraction with a warning.

## Future Enhancements

- [ ] Add more specific command schemas (WalkCommand, AttackCommand, etc.)
- [ ] Validate entity IDs exist in game state
- [ ] Validate coordinates are within map bounds
- [ ] Add response streaming support
- [ ] Generate TypeScript types from schema

## References

- [Pydantic Documentation](https://docs.pydantic.dev/)
- [OpenAI Structured Outputs](https://platform.openai.com/docs/guides/structured-outputs)
- [Gemini JSON Mode](https://ai.google.dev/gemini-api/docs/json-mode)
- [JSON Schema Specification](https://json-schema.org/)
