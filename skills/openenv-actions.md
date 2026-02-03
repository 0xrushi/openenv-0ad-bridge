# OpenEnv Actions

How to send low-level actions (push_command/evaluate), find valid entity IDs, and debug issues.

## Action Types

The OpenEnv proxy supports two main action types:

### 1. Evaluate

Execute JavaScript in the simulation engine:

```bash
curl -sS -X POST "$API_BASE/step" \
  -H 'content-type: application/json' \
  -d '{"action":{"op":"evaluate","code":"1+1"}}' \
  | python -m json.tool
```

Use this for:
- Querying game state
- Running custom logic
- Debugging

### 2. Push Command

Inject a Simulation2 command (movement, attack, build, etc.):

```bash
curl -sS -X POST "$API_BASE/step" \
  -H 'content-type: application/json' \
  -d '{"action":{"op":"push_command","player_id":1,"cmd":{"type":"walk","entities":[123],"x":600,"z":600,"queued":false,"pushFront":true}}}' \
  | python -m json.tool
```

## Getting Valid Entity IDs

Entity IDs are NOT stable between matches. You must get fresh IDs for each game.

### Using the Helper Script

```bash
# List all entities for player 1
python tools/execute_move.py --list --player=1

# List all entities for player 2
python tools/execute_move.py --list --player=2
```

This will show entity IDs, templates, positions, and other info.

### Using State Snapshots

If the stepper is writing snapshots (`ZEROAD_STATE_OUT=run/latest_state.json`):

```bash
# View the latest state
cat run/latest_state.json | python -m json.tool

# Filter for specific entity types
cat run/latest_state.json | python -m json.tool | grep -A5 "template"
```

## Quick Tests

### Test OpenEnv Proxy Health

```bash
curl -sS http://127.0.0.1:8000/health | python -m json.tool
```

Expected response:
```json
{
  "status": "ok"
}
```

### Test Evaluate Action

```bash
curl -sS -X POST http://127.0.0.1:8000/step \
  -H 'content-type: application/json' \
  -d '{"action":{"op":"evaluate","code":"1+1"}}' \
  | python -m json.tool
```

### Get OpenEnv Schema

```bash
curl -sS http://127.0.0.1:8000/schema | python -m json.tool
```

## Troubleshooting

### Unit Didn't Move

If `push_command` returns success but nothing happens:

1. **Wrong entity ID (doesn't exist)**
   - Proxy returns: `ok: false` with `invalid_entity_ids`
   - Fix: Get fresh entity IDs with `--list`

2. **Wrong owner (not your player)**
   - Proxy returns: `ok: false` with `wrongOwner`
   - Fix: Verify you're using the correct `player_id`

3. **Stepper not running**
   - Command is injected but never processed
   - Fix: Ensure stepper is running in Terminal B

4. **Invalid/unreachable coordinates**
   - Fix: Try different `(x, z)` coordinates
   - Check map bounds and obstacles

### Command Validation

The proxy validates:
- Entity IDs exist
- Entity ownership (player_id matches)
- Required command fields

If validation fails, the response includes:
```json
{
  "ok": false,
  "error": "invalid_entity_ids: [123, 456]"
}
```

### Stepper Diagnostics

```bash
python tools/execute_move.py --diag
```

This checks:
- RL interface connectivity
- Current game state
- Entity counts

## Best Practices

1. **Always get fresh entity IDs** at the start of each match
2. **Check command responses** for `ok: false` and error messages
3. **Verify stepper is running** before sending commands
4. **Use small coordinate increments** when testing movement
5. **Start with simple commands** (walk, stop) before complex ones
