# Multi-Provider LLM Arena

Run LLM battles in 0 A.D. using multiple providers: OpenAI, Grok (xAI), and local OpenAI-compatible endpoints.

## Overview

This template allows you to pit different LLM models against each other in a real-time strategy match. Each agent:
- Reads the current game state from snapshots
- Uses provider-specific APIs (OpenAI, Grok, or local)
- Makes autonomous decisions using skills from `skills/` directory
- Sends OpenEnv actions to control units

**Supported Providers:**
- **OpenAI**: GPT-4o, GPT-4, GPT-3.5, etc.
- **Grok (xAI)**: Grok-beta, Grok-2-latest
- **Local**: Any OpenAI-compatible server (LM Studio, Ollama, vLLM, etc.)

## Quick Start

### 1. Prerequisites

Start the required services:

```bash
# Terminal A: 0 A.D. with RL interface
ZEROAD_RL_INTERFACE=127.0.0.1:6000 python launcher.py --map="scenarios/arcadia"

# Terminal B: Stepper (keeps simulation running)
export ZEROAD_RL_URL=http://127.0.0.1:6000
export ZEROAD_STEP_SLEEP=0.01
export ZEROAD_STATE_OUT=run/latest_state.json
export ZEROAD_STATE_EVERY_N=10
python tools/execute_move.py --run

# Terminal C: OpenEnv proxy
export ZEROAD_RL_URL=http://127.0.0.1:6000
python tools/run_openenv_zero_ad_server.py --host=127.0.0.1 --port=8001
```

### 2. Set API Keys

```bash
# For OpenAI
export OPENAI_API_KEY=sk-...

# For Grok (xAI)
export XAI_API_KEY=xai-...

# For local endpoints (usually not needed)
# No API key required
```

### 3. Configure Match

Edit `configs/multi_provider_match.toml`:

```toml
[match]
openenv_base = "http://127.0.0.1:8001"
state_file = "run/latest_state.json"
decision_interval_s = 1.0
max_actions_per_decision = 3

[players.openai_p1]
player_id = 1
name = "GPT-4o"
provider = "openai"
model = "gpt-4o"
temperature = 0.2
max_output_tokens = 800

[players.grok_p2]
player_id = 2
name = "Grok-Beta"
provider = "grok"
model = "grok-beta"
temperature = 0.3
max_output_tokens = 800
```

### 4. Run Match

```bash
# Terminal D: LLM arena
python tools/multi_provider_match.py --config configs/multi_provider_match.toml
```

## Configuration Guide

### Match Settings

```toml
[match]
openenv_base = "http://127.0.0.1:8001"       # OpenEnv proxy URL
state_file = "run/latest_state.json"          # Game state snapshot path
decision_interval_s = 1.0                     # Seconds between decisions
max_actions_per_decision = 3                  # Max actions per agent per turn
max_entities_in_summary = 50                  # Max entities to include in state
log_decisions = true                           # Enable decision logging
log_file = "run/match_log.jsonl"              # Log file path (JSONL format)
```

### Provider: OpenAI

```toml
[players.openai_p1]
player_id = 1
name = "GPT-4o"
provider = "openai"
model = "gpt-4o"                              # or "gpt-4", "gpt-3.5-turbo"
temperature = 0.2
max_output_tokens = 800

# Optional: Custom base URL (default: https://api.openai.com/v1)
# base_url = "https://api.openai.com/v1"

# Optional: Custom API key env var (default: OPENAI_API_KEY)
# api_key_env = "OPENAI_API_KEY"

# Optional: Strategy hint for this agent
strategy_hint = """
Focus on:
1. Early economy: Train 10+ workers
2. Military production: Build barracks by minute 5
3. Aggressive expansion: Scout and attack
"""
```

**Environment Variables:**
- `OPENAI_API_KEY`: Required
- `OPENAI_BASE_URL`: Optional (defaults to `https://api.openai.com/v1`)

### Provider: Grok (xAI)

```toml
[players.grok_p2]
player_id = 2
name = "Grok-Beta"
provider = "grok"
model = "grok-beta"                           # or "grok-2-latest"
temperature = 0.3
max_output_tokens = 800

# Optional: Custom API key env var (default: XAI_API_KEY)
# api_key_env = "XAI_API_KEY"

strategy_hint = """
Defensive strategy:
1. Build walls and towers early
2. Tech rushing: Research phases quickly
3. Late-game dominance
"""
```

**Environment Variables:**
- `XAI_API_KEY`: Required
- Base URL is automatically set to `https://api.x.ai/v1`

### Provider: Local OpenAI-Compatible

```toml
[players.local_p1]
player_id = 1
name = "Local-Llama3"
provider = "local"
model = "llama-3-70b-instruct"                # Model name on your server
temperature = 0.4
max_output_tokens = 1000

base_url = "http://localhost:1234/v1"         # Your local server URL
api_key = "not-needed"                         # Some servers need a dummy key

strategy_hint = """
Adaptive strategy:
1. Analyze opponent opening
2. Counter their composition
3. Exploit resources efficiently
"""
```

**Supported Local Servers:**
- **LM Studio**: Runs Llama, Mistral, etc. locally
- **Ollama**: Local model serving
- **vLLM**: High-performance inference server
- **text-generation-webui**: Gradio-based UI with OpenAI API
- **LocalAI**: OpenAI-compatible API for local models

**Setup Example (LM Studio):**
1. Download LM Studio: https://lmstudio.ai/
2. Load a model (e.g., `llama-3-70b-instruct`)
3. Start local server (default: `http://localhost:1234`)
4. Use `http://localhost:1234/v1` as `base_url`

## Skills Integration

Agents automatically receive knowledge from the `skills/` directory:

- **`skills/openenv-actions.md`**: Core action types (evaluate, push_command)
- **`skills/cookbook-gameplay.md`**: Command examples (walk, attack, gather, build, train)
- **`skills/debugging-playbook.md`**: Troubleshooting tips

The skills are embedded in the agent's system prompt, so they know:
- How to format commands
- Available action types
- Common patterns and best practices

### Action Schema

Agents output JSON with this format:

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
        "type": "train",
        "entities": [4000],
        "template": "units/athen_infantry_spearman_b",
        "count": 3,
        "metadata": {}
      }
    }
  ]
}
```

### Available Commands

From `skills/cookbook-gameplay.md`:

**Movement:**
- `walk`: Move units to coordinates
- `stop`: Stop current action
- `patrol`: Patrol between points

**Combat:**
- `attack`: Attack specific target
- `attack-walk`: Move while attacking
- `guard`: Guard/follow another unit
- `stance`: Set combat stance (aggressive, defensive, passive)
- `formation`: Set unit formation

**Economy:**
- `gather`: Gather resources
- `returnresource`: Return resources to dropsite

**Building:**
- `construct`: Build structure
- `repair`: Repair building

**Production:**
- `train`: Train units
- `research`: Research technology

**Garrison:**
- `garrison`: Enter building/ship
- `unload`: Exit selected units
- `unload-all-by-owner`: Exit all units

## Usage Examples

### Example 1: OpenAI vs Grok

```toml
[players.openai]
player_id = 1
provider = "openai"
model = "gpt-4o"

[players.grok]
player_id = 2
provider = "grok"
model = "grok-beta"
```

```bash
export OPENAI_API_KEY=sk-...
export XAI_API_KEY=xai-...
python tools/multi_provider_match.py --config configs/openai_vs_grok.toml
```

### Example 2: Local vs Local (Different Models)

```toml
[players.llama]
player_id = 1
provider = "local"
model = "llama-3-70b-instruct"
base_url = "http://localhost:1234/v1"
api_key = "dummy"

[players.mistral]
player_id = 2
provider = "local"
model = "mistral-7b-instruct"
base_url = "http://localhost:8080/v1"
api_key = "dummy"
```

### Example 3: OpenAI vs Local

```toml
[players.gpt4]
player_id = 1
provider = "openai"
model = "gpt-4o"

[players.local_llama]
player_id = 2
provider = "local"
model = "llama-3-70b-instruct"
base_url = "http://localhost:1234/v1"
```

## Debugging

### Dry Run Mode

Test prompts without calling LLMs:

```bash
python tools/multi_provider_match.py --config configs/multi_provider_match.toml --dry-run
```

This shows:
- System prompts sent to agents
- User prompts with game state
- No actual API calls made

### Check Logs

If `log_decisions = true`:

```bash
# View all decisions
cat run/match_log.jsonl | python -m json.tool

# Filter by agent
cat run/match_log.jsonl | grep "GPT-4o"

# Count actions
cat run/match_log.jsonl | jq '.actions_sent' | awk '{sum+=$1} END {print sum}'
```

### Common Issues

#### "API key not found"

**Solution:**
```bash
# Check env vars
echo $OPENAI_API_KEY
echo $XAI_API_KEY

# Set them
export OPENAI_API_KEY=sk-...
export XAI_API_KEY=xai-...
```

#### "Failed to reset OpenEnv proxy"

**Solution:**
1. Verify OpenEnv proxy is running (Terminal C)
2. Check URL matches config (`openenv_base`)
3. Test with curl:
   ```bash
   curl -sS http://127.0.0.1:8001/health
   ```

#### "invalid_entity_ids" errors

**Cause:** Agent is using non-existent entity IDs

**Solution:**
1. Ensure stepper is writing fresh state snapshots
2. Check state file is updating:
   ```bash
   watch -n 1 'ls -lh run/latest_state.json'
   ```
3. Increase `max_entities_in_summary` to give agents more context

#### Agents do nothing

**Causes:**
- State file not updating (stepper not running)
- Agents returning empty actions
- All actions rejected by proxy

**Debug:**
```bash
# 1. Check stepper output (Terminal B)
# Should show continuous step calls

# 2. Check state file
cat run/latest_state.json | python -m json.tool | head -50

# 3. Use dry-run to see prompts
python tools/multi_provider_match.py --dry-run

# 4. Check logs
tail -f run/match_log.jsonl
```

## Advanced Usage

### Custom Strategy Prompts

Add detailed strategy hints per agent:

```toml
[players.aggressive]
player_id = 1
strategy_hint = """
AGGRESSIVE RUSH STRATEGY:
1. Train only 5 workers (min economy)
2. Build barracks at 2 minutes
3. Constant military production (spearmen + archers)
4. Attack at 4 minutes with first wave
5. Never stop producing military units
6. Focus attacks on enemy workers and buildings
"""

[players.defensive]
player_id = 2
strategy_hint = """
DEFENSIVE BOOM STRATEGY:
1. Train 15+ workers (strong economy)
2. Build walls and towers around base
3. Research all economic technologies
4. Advance to phase 3 quickly
5. Build siege weapons for late game
6. Counter-attack only when stronger
"""
```

### Tournament System

Run multiple matches and track wins:

```bash
# Match 1
python tools/multi_provider_match.py --config configs/match1.toml > logs/match1.log

# Match 2
python tools/multi_provider_match.py --config configs/match2.toml > logs/match2.log

# Match 3 (reversed sides)
python tools/multi_provider_match.py --config configs/match3.toml > logs/match3.log
```

### Hybrid Control

Mix LLM decisions with scripted logic:

```python
# Custom wrapper around multi_provider_match.py
# - LLM decides high-level strategy
# - Scripts handle micro-management (worker gathering, unit production)
# - Combine both action sets
```

## Performance Considerations

### Token Usage

- Each decision prompt includes game state + skills documentation
- Approximate tokens per decision: 2000-4000
- With `decision_interval_s = 1.0` and 2 agents: ~7200 decisions/hour
- OpenAI cost: ~$0.50-2.00/hour (depending on model)

**Optimization:**
- Increase `decision_interval_s` to 2-5 seconds
- Reduce `max_entities_in_summary` (fewer entities in state)
- Use cheaper models (gpt-3.5-turbo, local models)

### Latency

- OpenAI/Grok: 1-3 seconds per API call
- Local models: 0.1-2 seconds (depends on hardware)

**For real-time matches:**
- Use local models for lowest latency
- Run multiple local servers in parallel
- Consider smaller, faster models (7B-13B parameters)

### Local Model Recommendations

**Fast (7B-13B params):**
- Mistral-7B-Instruct
- Llama-3-8B-Instruct
- Phi-3-Medium

**Balanced (30B-70B params):**
- Llama-3-70B-Instruct
- Mixtral-8x7B

**Best Quality (requires powerful GPU):**
- Llama-3.1-405B (quantized)
- Qwen-72B

## Next Steps

1. **Experiment with providers**: Test different model combinations
2. **Tune strategies**: Refine `strategy_hint` prompts
3. **Build tournaments**: Run multiple matches and rank models
4. **Add analytics**: Track win rates, action efficiency, etc.
5. **Optimize prompts**: A/B test different system prompts
6. **Fine-tune models**: Use match logs to fine-tune local models

## References

- OpenEnv Integration Guide: https://art.openpipe.ai/integrations/openenv-integration
- OpenAI API: https://platform.openai.com/docs/api-reference
- Grok API: https://docs.x.ai/
- LM Studio: https://lmstudio.ai/
- Ollama: https://ollama.ai/
- vLLM: https://docs.vllm.ai/
