# Claude Skills

This folder contains Claude Code skills - repeatable workflows for common tasks in the 0 A.D. OpenEnv project.

## What Are Claude Skills?

Claude skills are structured guides that help you quickly perform common tasks. Each skill is a self-contained playbook with:
- Clear prerequisites
- Step-by-step instructions
- Troubleshooting tips
- Example commands ready to copy/paste

## Available Skills

### Setup & Infrastructure

- **[zero-ad-openenv-setup.md](./zero-ad-openenv-setup.md)**: Launch 0 A.D. with RL HTTP, run stepper, run OpenEnv proxy, verify setup
  - Use this when: Starting a new session or setting up the environment for the first time

### Core Operations

- **[openenv-actions.md](./openenv-actions.md)**: Send low-level actions (push_command/evaluate), find entity IDs, debug issues
  - Use this when: Learning the OpenEnv API or debugging action problems

- **[cookbook-gameplay.md](./cookbook-gameplay.md)**: Copy/paste recipes for all game actions (movement, combat, economy, building, etc.)
  - Use this when: You need quick command examples for specific game actions

### Advanced Features

- **[llm-arena-match.md](./llm-arena-match.md)**: Run two LLM agents competing against each other
  - Use this when: Testing AI agents or running model comparisons

### Debugging

- **[debugging-playbook.md](./debugging-playbook.md)**: Diagnose common failures in RL interface, stepper, and OpenEnv proxy
  - Use this when: Something isn't working and you need to troubleshoot

## Quick Start Workflow

1. **First time setup**: Follow `zero-ad-openenv-setup.md`
2. **Learn the basics**: Read `openenv-actions.md`
3. **Try game commands**: Use `cookbook-gameplay.md` recipes
4. **Run LLM agents**: Set up with `llm-arena-match.md`
5. **When stuck**: Check `debugging-playbook.md`

## How to Use These Skills

### With Claude Code

If you're using Claude Code (the CLI tool), you can:

1. Reference these skills in your prompts:
   ```
   "Follow the zero-ad-openenv-setup skill to set up the environment"
   ```

2. Ask Claude to execute specific skills:
   ```
   "Run through the debugging playbook to diagnose the issue"
   ```

### Manual Usage

Each skill can be used independently:

1. Open the skill file
2. Follow the instructions step-by-step
3. Copy/paste commands as needed
4. Refer to troubleshooting sections when issues arise

## Skill Structure

Each skill includes:

```markdown
# Skill Name

Brief description

## Prerequisites
What you need before starting

## Steps
Numbered instructions with commands

## Verification
How to confirm it worked

## Troubleshooting
Common issues and solutions

## Examples
Real-world usage examples
```

## Environment Variables Reference

Many skills use these environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `ZEROAD_RL_INTERFACE` | - | Address for RL interface (e.g., `127.0.0.1:6000`) |
| `ZEROAD_RL_URL` | - | URL of running RL interface |
| `ZEROAD_STEP_SLEEP` | 0.01 | Seconds between simulation steps |
| `ZEROAD_STATE_OUT` | - | Path to write state snapshots |
| `ZEROAD_STATE_EVERY_N` | 10 | Write state every N steps |
| `API_BASE` | - | OpenEnv proxy base URL |
| `OPENAI_API_KEY` | - | OpenAI API key for LLM agents |

## Related Documentation

- **Codex Skills**: See `../skills/` for the original Codex-format skills
- **Main README**: See `../README.md` for project overview
- **Tools**: See `../tools/` for script documentation

## Contributing

To add a new skill:

1. Create a new `.md` file following the structure above
2. Add it to this README's skill list
3. Include practical examples and troubleshooting tips
4. Test all commands before committing

## Differences from Codex Skills

The Claude skills are adapted from Codex skills with these changes:

- **More detailed explanations**: Claude skills include more context and reasoning
- **Better troubleshooting**: Extended debugging sections with multiple solutions
- **Example-rich**: More copy/paste examples ready to use
- **Workflow-oriented**: Focused on end-to-end workflows rather than just procedures

Both skill formats are maintained for compatibility with different AI tools and workflows.
