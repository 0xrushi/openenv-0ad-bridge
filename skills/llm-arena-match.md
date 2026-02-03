# LLM Arena Match

Run two LLM agents (e.g., gpt-4o vs o1) that make autonomous decisions and control players in 0 A.D.

## Overview

The LLM arena allows you to pit two AI models against each other in a real-time strategy match. Each agent:
- Reads the current game state
- Makes decisions based on its strategy
- Sends OpenEnv actions (movement, combat, economy, etc.)
- Adapts to opponent actions

## Prerequisites

1. **OpenEnv proxy running** (Terminal C)
2. **Stepper running and writing snapshots** (Terminal B)
3. **OpenAI API key** (or other LLM provider)

## Setup

### 1. Set API Key

```bash
export OPENAI_API_KEY=sk-...
```

### 2. Configure Match

Edit `configs/llm_match.toml`:

```toml
[match]
openenv_base = "http://127.0.0.1:8001"  # Match your OpenEnv proxy URL
state_file = "run/latest_state.json"    # Match stepper's ZEROAD_STATE_OUT

[players.p1]
player_id = 1
model = "gpt-4o"
# Add custom prompt/strategy here

[players.p2]
player_id = 2
model = "gpt-4o"
# Add custom prompt/strategy here
```

### 3. Verify Stepper is Writing Snapshots

```bash
# Check file exists and is updating
ls -lh run/latest_state.json
watch -n 1 'ls -lh run/latest_state.json'
```

The file modification time should update regularly (every ~1 second based on `ZEROAD_STATE_EVERY_N`).

## Running a Match

### Start the Arena

```bash
python tools/llm_match.py --config configs/llm_match.toml
```

The script will:
1. Read game state from snapshot file
2. Send state to both LLM agents
3. Get decisions from each agent
4. Execute actions via OpenEnv API
5. Repeat in a decision loop

### Watch the Match

You can observe:
- **Game window**: See units moving and fighting
- **Terminal output**: View agent decisions and actions
- **State file**: Monitor game state changes

## Debugging

### Issue: "invalid_entity_ids" Spam

**Symptom**: Agent repeatedly tries to use non-existent entity IDs

**Causes**:
- Agent is using stale/hardcoded entity IDs
- State snapshot is not updating
- Agent prompt doesn't include current entity information

**Solutions**:
1. Ensure state file is updating:
   ```bash
   ls -lh run/latest_state.json
   ```

2. Verify agent prompt includes entity IDs from current state

3. Add entity ID validation in agent code

### Issue: Nothing Happens

**Debug checklist**:

1. **Stepper running?**
   ```bash
   # Check Terminal B for continuous output
   ```

2. **State file exists?**
   ```bash
   cat run/latest_state.json | python -m json.tool
   ```

3. **OpenEnv proxy healthy?**
   ```bash
   curl -sS http://127.0.0.1:8001/health
   ```

4. **API key valid?**
   ```bash
   echo $OPENAI_API_KEY
   ```

### Issue: Agent Makes Bad Decisions

**Symptom**: Agent does nothing, or makes obviously poor choices

**Improvements**:
1. **Enhance agent prompt**: Add more strategy guidance
2. **Provide more context**: Include resource counts, unit types, map info
3. **Add examples**: Show sample good decisions in prompt
4. **Use better model**: Try GPT-4 or Claude instead of GPT-3.5

### Issue: Actions Rejected

**Symptom**: OpenEnv returns `ok: false`

**Debug**:
```bash
# Check proxy logs (Terminal C)
# Look for validation errors
```

**Common causes**:
- Invalid entity IDs (most common)
- Wrong player_id
- Malformed command structure
- Missing required fields

## Agent Configuration

### Example Agent Prompt Strategy

```toml
[players.p1]
player_id = 1
model = "gpt-4o"
system_prompt = """
You are playing 0 A.D. as player 1.
Focus on:
1. Economy: Keep villagers gathering resources
2. Military: Build barracks early, train infantry
3. Expansion: Build houses to increase pop cap
4. Combat: Use attack-walk to push into enemy territory

Current state will be provided each turn.
Respond with valid OpenEnv actions.
"""
```

### Model Selection

Different models have different strengths:

- **GPT-4**: Strong strategic reasoning, good at long-term planning
- **GPT-3.5**: Faster, cheaper, adequate for simple strategies
- **Claude**: Good at following complex instructions
- **O1**: Excellent at complex reasoning and adaptation

## Match Monitoring

### View Agent Actions

The script outputs each agent's decisions:

```
Player 1 (gpt-4o): Moving scouts to (700, 650)
Player 1 (gpt-4o): Training 3 spearmen at barracks 4023
Player 2 (gpt-4o): Gathering wood with workers [201, 202, 203]
...
```

### State Inspection

You can pause and inspect state:

```bash
# View current game state
cat run/latest_state.json | python -m json.tool

# Filter for specific info
cat run/latest_state.json | python -m json.tool | grep -A 10 "player_id"
```

## Advanced Usage

### Custom Decision Loop

You can modify `tools/llm_match.py` to:
- Add custom decision-making logic
- Implement specialized strategies
- Add learning/adaptation between matches
- Log detailed analytics

### Multi-Match Tournaments

Run multiple matches with different configurations:

```bash
# Match 1: GPT-4 vs GPT-3.5
python tools/llm_match.py --config configs/match1.toml

# Match 2: Different strategies
python tools/llm_match.py --config configs/match2.toml
```

### Hybrid Control

Combine LLM and scripted logic:
- LLM for high-level strategy
- Scripts for micro-management
- Rule-based systems for economy

## Performance Tips

1. **Optimize state updates**: Reduce `ZEROAD_STATE_EVERY_N` if agents don't need frequent updates
2. **Batch actions**: Send multiple commands per agent turn
3. **Cache LLM responses**: Reuse decisions for similar states
4. **Use faster models**: For simple strategies, GPT-3.5 is often sufficient

## Example Match Flow

1. **T=0**: Both agents receive initial state
2. **T=1**: Agent 1 trains workers, Agent 2 scouts
3. **T=2**: Agent 1 builds house, Agent 2 gathers resources
4. **T=3**: Both agents train military units
5. **T=10**: Agents engage in combat
6. **T=20**: Winner emerges

## Logging and Analysis

Enable detailed logging:

```python
# In llm_match.py
import logging
logging.basicConfig(level=logging.DEBUG)
```

This captures:
- All agent decisions
- OpenEnv requests/responses
- Errors and rejections
- Timing information

## Next Steps

- Experiment with different model combinations
- Create specialized agent strategies
- Build a tournament system
- Add win/loss tracking
- Implement ELO ratings for models
