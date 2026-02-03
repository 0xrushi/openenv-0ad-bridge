# 0 A.D. Gameplay Cookbook

Copy/paste recipes for movement, combat, scouting, economy, building, training, research, and more using OpenEnv actions.

## Setup

Set your API base URL:

```bash
export API_BASE=http://127.0.0.1:8001
```

Get fresh entity IDs (required for each match):

```bash
python tools/execute_move.py --list --player=1
python tools/execute_move.py --list --player=2
```

**Important**: Entity IDs are NOT stable between matches. Always get fresh IDs.

## Movement Commands

### Walk (Basic Movement)

```bash
curl -sS -X POST "$API_BASE/step" -H 'content-type: application/json' \
  -d '{"action":{"op":"push_command","player_id":1,"cmd":{"type":"walk","entities":[123],"x":600,"z":600,"queued":false,"pushFront":true}}}' \
  | python -m json.tool
```

Replace: `player_id`, `entities`, `x`, `z`

### Stop

```bash
curl -sS -X POST "$API_BASE/step" -H 'content-type: application/json' \
  -d '{"action":{"op":"push_command","player_id":1,"cmd":{"type":"stop","entities":[123],"queued":false}}}' \
  | python -m json.tool
```

### Patrol

```bash
curl -sS -X POST "$API_BASE/step" -H 'content-type: application/json' \
  -d '{"action":{"op":"push_command","player_id":1,"cmd":{"type":"patrol","entities":[123,124],"x":650,"z":650,"queued":false}}}' \
  | python -m json.tool
```

## Combat Commands

### Attack Specific Target

Replace `target` with enemy entity ID:

```bash
curl -sS -X POST "$API_BASE/step" -H 'content-type: application/json' \
  -d '{"action":{"op":"push_command","player_id":1,"cmd":{"type":"attack","entities":[123,124],"target":9001,"queued":false,"allowCapture":true}}}' \
  | python -m json.tool
```

### Attack-Walk (Move While Attacking)

Useful for pushing into unexplored areas:

```bash
curl -sS -X POST "$API_BASE/step" -H 'content-type: application/json' \
  -d '{"action":{"op":"push_command","player_id":1,"cmd":{"type":"attack-walk","entities":[123,124],"x":700,"z":700,"queued":false,"allowCapture":true,"targetClasses":{"attack":["Unit"]}}}}' \
  | python -m json.tool
```

### Guard / Follow

```bash
curl -sS -X POST "$API_BASE/step" -H 'content-type: application/json' \
  -d '{"action":{"op":"push_command","player_id":1,"cmd":{"type":"guard","entities":[123],"target":124,"queued":false}}}' \
  | python -m json.tool
```

### Set Stance

Common stances: `aggressive`, `defensive`, `passive`

```bash
curl -sS -X POST "$API_BASE/step" -H 'content-type: application/json' \
  -d '{"action":{"op":"push_command","player_id":1,"cmd":{"type":"stance","entities":[123,124],"name":"aggressive","queued":false}}}' \
  | python -m json.tool
```

### Formation

```bash
curl -sS -X POST "$API_BASE/step" -H 'content-type: application/json' \
  -d '{"action":{"op":"push_command","player_id":1,"cmd":{"type":"formation","entities":[123,124,125],"name":"Line Closed","queued":false}}}' \
  | python -m json.tool
```

## Economy Commands

### Gather Resources

Requires target entity ID (tree, mine, berries):

```bash
curl -sS -X POST "$API_BASE/step" -H 'content-type: application/json' \
  -d '{"action":{"op":"push_command","player_id":1,"cmd":{"type":"gather","entities":[200,201],"target":5555,"queued":false}}}' \
  | python -m json.tool
```

To find resource entity IDs:
- Use `run/latest_state.json` and filter by template
- Or use `/evaluate` to search for resource entities

### Return Resources

Requires dropsite entity ID:

```bash
curl -sS -X POST "$API_BASE/step" -H 'content-type: application/json' \
  -d '{"action":{"op":"push_command","player_id":1,"cmd":{"type":"returnresource","entities":[200,201],"target":3000,"queued":false}}}' \
  | python -m json.tool
```

Note: Command name may vary by engine version (`returnresource` vs `returnResource`).

## Building Commands

### Construct Building

Requires:
- Builder entities (workers)
- Building template name
- Placement coordinates (x, z) and angle

```bash
curl -sS -X POST "$API_BASE/step" -H 'content-type: application/json' \
  -d '{"action":{"op":"push_command","player_id":1,"cmd":{"type":"construct","entities":[200,201],"template":"structures/athen_house","x":620,"z":610,"angle":0,"queued":false}}}' \
  | python -m json.tool
```

Template names are civilization-specific. Common examples:
- `structures/athen_house`
- `structures/athen_barracks`
- `structures/athen_civil_centre`

### Repair Building

```bash
curl -sS -X POST "$API_BASE/step" -H 'content-type: application/json' \
  -d '{"action":{"op":"push_command","player_id":1,"cmd":{"type":"repair","entities":[200,201],"target":5001,"autocontinue":true,"queued":false}}}' \
  | python -m json.tool
```

## Training & Research

### Train Units

Requires production building entity ID (barracks, civic center) and unit template:

```bash
curl -sS -X POST "$API_BASE/step" -H 'content-type: application/json' \
  -d '{"action":{"op":"push_command","player_id":1,"cmd":{"type":"train","entities":[4000],"template":"units/athen_infantry_spearman_b","count":3,"metadata":{}}}}' \
  | python -m json.tool
```

### Research Technology

Requires building entity ID that can research and tech template name:

```bash
curl -sS -X POST "$API_BASE/step" -H 'content-type: application/json' \
  -d '{"action":{"op":"push_command","player_id":1,"cmd":{"type":"research","entity":4000,"template":"phase_town"}}}' \
  | python -m json.tool
```

## Garrison & Unload

### Garrison Units

```bash
curl -sS -X POST "$API_BASE/step" -H 'content-type: application/json' \
  -d '{"action":{"op":"push_command","player_id":1,"cmd":{"type":"garrison","entities":[123,124],"target":5000,"queued":false}}}' \
  | python -m json.tool
```

### Unload Selected Units

```bash
curl -sS -X POST "$API_BASE/step" -H 'content-type: application/json' \
  -d '{"action":{"op":"push_command","player_id":1,"cmd":{"type":"unload","garrisonHolder":5000,"entities":[123,124]}}}' \
  | python -m json.tool
```

### Unload All

```bash
curl -sS -X POST "$API_BASE/step" -H 'content-type: application/json' \
  -d '{"action":{"op":"push_command","player_id":1,"cmd":{"type":"unload-all-by-owner","garrisonHolders":[5000]}}}' \
  | python -m json.tool
```

## Healing

### Heal Unit

Support varies by civilization and unit type:

```bash
curl -sS -X POST "$API_BASE/step" -H 'content-type: application/json' \
  -d '{"action":{"op":"push_command","player_id":1,"cmd":{"type":"heal","entities":[6001],"target":123,"queued":false}}}' \
  | python -m json.tool
```

If `heal` is not supported, use `guard` near the target.

## Scouting

Scouting combines movement with state queries:

1. Move fast units to waypoints (use `walk`)
2. Query game state using `/evaluate` or state snapshots

Example omniscient query:

```bash
curl -sS -X POST "$API_BASE/step" -H 'content-type: application/json' \
  -d '{"action":{"op":"evaluate","code":"(function(){return JSON.stringify({ok:true});})()"}}' \
  | python -m json.tool
```

## Group Control

There's no "selection" concept in the API. Groups are client-side:

- Maintain sets of entity IDs (e.g., `army1`, `scouts`, `workers`)
- Each action uses `entities:[...]` explicitly

Typical workflow:
1. Maintain groups from state snapshots
2. Issue orders per group (walk, attack-walk, stance, formation)

## Troubleshooting

### Command Returns `ok: false`

Read `observation.error` in the response. Common errors:
- `invalid_entity_ids`: Entity doesn't exist
- `wrongOwner`: Entity belongs to different player

### Command Succeeds But Nothing Happens

1. Verify stepper is running
2. Check entity IDs are correct for this match
3. Try different coordinates
4. Use `/evaluate` with `Engine.PostCommand` as alternative

### Getting Help

```bash
# Check proxy health
curl -sS "$API_BASE/health"

# View schema
curl -sS "$API_BASE/schema" | python -m json.tool

# List entities
python tools/execute_move.py --list --player=1
```
