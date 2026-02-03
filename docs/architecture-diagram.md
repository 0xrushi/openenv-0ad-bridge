# Multi-Provider LLM Arena Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        0 A.D. Game Engine                        │
│                     (RL Interface Enabled)                       │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP (port 6000)
                             │
                             ▼
                ┌────────────────────────┐
                │   Stepper Process      │
                │  (execute_move.py)     │
                │                        │
                │  - Calls /step         │
                │  - Writes snapshots    │
                └────────┬───────────────┘
                         │
                         │ Writes every N steps
                         ▼
              ┌─────────────────────┐
              │ run/latest_state.json│
              │  (Game State File)   │
              └─────────┬────────────┘
                        │
                        │ Read by agents
                        │
        ┌───────────────┴────────────────┐
        │                                │
        ▼                                ▼
┌──────────────┐              ┌──────────────────┐
│   Agent 1    │              │     Agent 2      │
│  (Player 1)  │              │   (Player 2)     │
│              │              │                  │
│ Provider:    │              │ Provider:        │
│ ├─ OpenAI    │              │ ├─ Grok          │
│ ├─ Grok      │              │ ├─ OpenAI        │
│ ├─ Gemini    │              │ ├─ Gemini        │
│ └─ Local     │              │ └─ Local         │
└──────┬───────┘              └──────┬───────────┘
       │                             │
       │ POST /step                  │ POST /step
       │ (OpenEnv actions)           │ (OpenEnv actions)
       │                             │
       └────────────┬────────────────┘
                    │
                    ▼
       ┌────────────────────────┐
       │  OpenEnv Proxy Server  │
       │  (openenv_zero_ad)     │
       │                        │
       │  - Validates actions   │
       │  - Calls RL interface  │
       └────────┬───────────────┘
                │ HTTP (port 6000)
                │
                ▼
       ┌────────────────────────┐
       │   0 A.D. RL Interface  │
       │  (push_command, etc.)  │
       └────────────────────────┘
```

## Component Details

### 1. 0 A.D. Game Engine
- **Purpose**: Runs the actual RTS game simulation
- **Config**: Started with `--rl-interface=127.0.0.1:6000`
- **Note**: When RL interface is enabled, simulation only advances via `/step` calls

### 2. Stepper Process
- **File**: `tools/execute_move.py --run`
- **Purpose**:
  - Continuously calls `/step` on RL interface (keeps game running)
  - Writes game state snapshots to disk
- **Environment Variables**:
  - `ZEROAD_RL_URL`: RL interface URL
  - `ZEROAD_STATE_OUT`: Snapshot output path
  - `ZEROAD_STATE_EVERY_N`: Write frequency (every N steps)

### 3. Game State File
- **File**: `run/latest_state.json`
- **Purpose**: Omniscient snapshot of current game state
- **Contains**:
  - All entities (units, buildings, resources)
  - Entity properties (position, template, owner, hitpoints)
  - Current step and game time
- **Updated**: Every N simulation steps by stepper

### 4. LLM Agents
- **File**: `tools/multi_provider_match.py`
- **Purpose**: Read state, make decisions, send actions
- **Providers**:
  - **OpenAI**: Uses OpenAI API (GPT-4o, GPT-4, etc.)
  - **Grok**: Uses xAI API (Grok-beta, Grok-2-latest)
  - **Gemini**: Uses Google Gemini API (Gemini 2.0 Flash, Gemini 1.5 Pro)
  - **Local**: Uses local OpenAI-compatible server (LM Studio, Ollama, vLLM)
- **Decision Loop**:
  1. Read `latest_state.json`
  2. Summarize state (limit entities for token efficiency)
  3. Generate prompt with skills knowledge
  4. Call LLM API
  5. Parse JSON response (action list)
  6. Send actions to OpenEnv proxy
- **Skills Integration**: Agents have knowledge from `skills/` directory

### 5. OpenEnv Proxy Server
- **File**: `openenv_zero_ad/server.py`
- **Port**: 8001 (configurable)
- **Purpose**:
  - OpenEnv-compatible interface (gymnasium-style)
  - Validates actions (entity ownership, valid IDs)
  - Translates to RL interface calls
- **Endpoints**:
  - `POST /reset`: Reset session
  - `POST /step`: Execute action
  - `GET /schema`: Get action schema
  - `GET /health`: Health check

### 6. 0 A.D. RL Interface
- **Port**: 6000 (configurable)
- **Purpose**: Native RL interface built into 0 A.D.
- **Actions**:
  - `push_command`: Inject simulation command
  - `evaluate`: Execute JavaScript code

## Data Flow

### Decision Loop (Every N Seconds)

```
1. Stepper writes state
   └─> run/latest_state.json updated

2. Agent reads state
   └─> Loads latest_state.json
   └─> Summarizes (limits to max_entities)

3. Agent generates prompt
   └─> System prompt + skills knowledge
   └─> User prompt with current state

4. Agent calls LLM API
   └─> OpenAI: https://api.openai.com/v1/chat/completions
   └─> Grok:   https://api.x.ai/v1/chat/completions
   └─> Gemini: https://generativelanguage.googleapis.com/v1beta/openai/chat/completions
   └─> Local:  http://localhost:1234/v1/chat/completions

5. LLM returns JSON
   {
     "actions": [
       {
         "op": "push_command",
         "player_id": 1,
         "cmd": {"type": "walk", "entities": [123], "x": 600, "z": 650}
       }
     ]
   }

6. Agent sends to OpenEnv proxy
   └─> POST http://127.0.0.1:8001/step

7. Proxy validates
   └─> Entity exists?
   └─> Entity owned by player?
   └─> Command structure valid?

8. Proxy calls RL interface
   └─> POST http://127.0.0.1:6000/... (push_command)

9. Game engine processes
   └─> Unit starts moving

10. Repeat after decision_interval_s
```

## Configuration Flow

### TOML Config → Agent Config → API Call

```toml
# configs/multi_provider_match.toml
[players.openai_p1]
player_id = 1
provider = "openai"
model = "gpt-4o"
strategy_hint = "..."
```

Becomes:

```python
AgentConfig(
    player_id=1,
    provider="openai",
    model="gpt-4o",
    base_url="https://api.openai.com/v1",  # from env or default
    api_key=os.environ["OPENAI_API_KEY"],  # from env
    strategy_hint="...",
)
```

Used in:

```python
def _llm_chat(agent: AgentConfig, messages: List[Dict]):
    url = f"{agent.base_url}/chat/completions"
    payload = {
        "model": agent.model,
        "messages": messages,
        "temperature": agent.temperature,
    }
    headers = {"authorization": f"Bearer {agent.api_key}"}
    return post_json(url, payload, headers)
```

## Skills Integration

### Skills Directory → Agent Knowledge

```
skills/
├── openenv-actions.md      ─┐
├── cookbook-gameplay.md     ├─> Loaded at startup
└── debugging-playbook.md   ─┘

                             │
                             ▼
                      _SKILLS_KNOWLEDGE
                             │
                             ▼
                    _agent_prompt() includes in system prompt
                             │
                             ▼
                    Agent knows available actions
```

### Example: Walk Command

From `skills/cookbook-gameplay.md`:

```markdown
### Walk (Basic Movement)
curl -X POST "$API_BASE/step" -d '{
  "action": {
    "op": "push_command",
    "player_id": 1,
    "cmd": {
      "type": "walk",
      "entities": [123],
      "x": 600,
      "z": 600,
      "queued": false
    }
  }
}'
```

Agent learns:
- Command type: `walk`
- Required fields: `entities`, `x`, `z`
- Optional fields: `queued`, `pushFront`

Agent can generate:
```json
{
  "actions": [
    {
      "op": "push_command",
      "player_id": 1,
      "cmd": {
        "type": "walk",
        "entities": [123, 124],
        "x": 650,
        "z": 700,
        "queued": false,
        "pushFront": true
      }
    }
  ]
}
```

## Provider Comparison

| Feature | OpenAI | Grok | Gemini | Local |
|---------|--------|------|--------|-------|
| **Cost** | $$ | $$ | $ | Free |
| **Latency** | 1-3s | 1-3s | 0.5-2s | 0.1-2s |
| **Quality** | High | High | High | Varies |
| **Rate Limits** | Yes | Yes | Yes | No |
| **Privacy** | Cloud | Cloud | Cloud | Local |
| **Setup** | API key | API key | API key | Install model |
| **Models** | GPT-4o, GPT-4 | Grok-beta | Gemini 2.0 Flash, 1.5 Pro | Any Llama, Mistral, etc. |

## Error Handling

### Validation Flow

```
Agent sends action
      │
      ▼
OpenEnv Proxy validates
      │
      ├─> Entity exists?
      │   └─> No: Return {ok: false, error: "invalid_entity_ids"}
      │
      ├─> Entity owned by player?
      │   └─> No: Return {ok: false, error: "wrongOwner"}
      │
      └─> Valid command structure?
          └─> No: Return {ok: false, error: "invalid_command"}

All checks pass
      │
      ▼
Send to RL interface
      │
      ▼
Game engine executes
```

## Performance Considerations

### Token Usage (per decision per agent)

```
System prompt:          ~1000 tokens
Skills knowledge:       ~1500 tokens (truncated)
State summary:          ~500 tokens (max_entities = 50)
Agent strategy:         ~100 tokens
───────────────────────────────────────
Total input:            ~3100 tokens
Expected output:        ~200 tokens
───────────────────────────────────────
Total per decision:     ~3300 tokens
```

With 2 agents, 1 second intervals:
- Decisions per hour: 7,200
- Tokens per hour: ~24M tokens
- OpenAI GPT-4o cost: ~$120/hour

### Optimization Strategies

1. **Increase decision interval**: 1s → 5s (5x reduction)
2. **Reduce max_entities**: 50 → 20 (reduce state summary size)
3. **Use cheaper models**: GPT-4o → GPT-3.5-turbo (10x cheaper)
4. **Use local models**: Free (but requires GPU)

## Multi-Server Local Setup

Run multiple local models in parallel:

```
┌──────────────────┐         ┌──────────────────┐
│   LM Studio      │         │   Ollama         │
│   Port: 1234     │         │   Port: 11434    │
│                  │         │                  │
│   Llama-3-70B    │         │   Mistral-7B     │
└────────┬─────────┘         └────────┬─────────┘
         │                            │
         │                            │
         └───────────┬────────────────┘
                     │
                     ▼
         ┌───────────────────────┐
         │  Multi-Provider Match │
         │                       │
         │  Player 1: local      │
         │  (Llama via 1234)     │
         │                       │
         │  Player 2: local      │
         │  (Mistral via 11434)  │
         └───────────────────────┘
```

Config:
```toml
[players.llama]
provider = "local"
base_url = "http://localhost:1234/v1"

[players.mistral]
provider = "local"
base_url = "http://localhost:11434/v1"
```

## Summary

This architecture enables:
- ✅ Multiple LLM providers competing in same match
- ✅ Providers use skills from `skills/` directory
- ✅ State-based decision making (omniscient view)
- ✅ Real-time action execution
- ✅ Validation and error handling
- ✅ Logging for analysis
- ✅ Cost optimization via local models
