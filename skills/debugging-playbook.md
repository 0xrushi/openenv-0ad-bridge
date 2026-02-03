# Debugging Playbook

Diagnose common failure modes in the RL interface, stepper, and OpenEnv proxy.

## Quick Health Checks

### RL Interface

Test the raw RL HTTP interface:

```bash
curl -sS -m 2 -X POST http://127.0.0.1:6000/evaluate --data '1+1'
```

Expected: JSON response with result

### OpenEnv Proxy

```bash
# Health check
curl -sS http://127.0.0.1:8000/health

# View schema
curl -sS http://127.0.0.1:8000/schema | python -m json.tool
```

### Stepper

```bash
python tools/execute_move.py --diag
```

This checks:
- RL interface connectivity
- Current game state
- Entity counts

## Common Issues

### 1. Proxy Port Already in Use

**Symptom**: Uvicorn error: "address already in use"

**Solutions**:
- Use a different port: `python tools/run_openenv_zero_ad_server.py --port=8001`
- Find and stop the process using the port:
  ```bash
  lsof -i :8000
  kill <PID>
  ```

### 2. Stepper Timeouts

**Symptom**: `TimeoutError` in `tools/execute_move.py`

**Solutions**:
- Increase step delay:
  ```bash
  export ZEROAD_STEP_SLEEP=0.02  # up from 0.01
  ```
- The stepper has built-in retry logic
- Check CPU load - reduce if stepper is struggling

**Why it happens**: The simulation can't keep up with step requests

### 3. Unit Didn't Move

**Symptom**: `push_command` returns `ok: true` but unit doesn't move

**Debug steps**:
1. Verify entity IDs are valid for this match:
   ```bash
   python tools/execute_move.py --list --player=1
   ```

2. Ensure stepper is running:
   ```bash
   # Should show continuous output
   # Check Terminal B
   ```

3. Try different coordinates:
   ```bash
   # Test with known-good coordinates near spawn
   ```

4. Check command response for errors:
   ```bash
   # Look for ok: false or error messages
   ```

### 4. 0 A.D. Crashes or Timer Errors

**Symptom**: Game crashes during startup or shows timer errors

**Root cause**: Stepper starts too early, before simulation initialization completes

**Solutions**:
- The tmux starter already includes a delay
- If using manual terminals, wait 5-10 seconds after launching 0 A.D. before starting stepper
- Check game logs for initialization errors

### 5. Entity IDs Are Wrong/Stale

**Symptom**: Commands fail with `invalid_entity_ids` error

**Cause**: Entity IDs change between matches

**Solution**:
```bash
# ALWAYS get fresh IDs when starting a new match
python tools/execute_move.py --list --player=1
python tools/execute_move.py --list --player=2
```

### 6. Evaluate Action Fails

**Symptom**: `/step` with evaluate returns errors

**Debug**:
```bash
# Test simple evaluation
curl -sS -X POST http://127.0.0.1:8000/step \
  -H 'content-type: application/json' \
  -d '{"action":{"op":"evaluate","code":"1+1"}}' \
  | python -m json.tool
```

**Common causes**:
- Syntax error in JavaScript code
- RL interface not responding
- Simulation not initialized

### 7. State Snapshots Not Updating

**Symptom**: `run/latest_state.json` is stale or missing

**Check**:
```bash
# Verify environment variables
echo $ZEROAD_STATE_OUT
echo $ZEROAD_STATE_EVERY_N

# Check file modification time
ls -lh run/latest_state.json

# Watch for updates
watch -n 1 'ls -lh run/latest_state.json'
```

**Fix**: Ensure stepper is running with correct environment variables

### 8. OpenEnv Proxy Returns 500 Errors

**Debug**:
1. Check proxy logs (Terminal C output)
2. Verify RL interface is responding:
   ```bash
   curl -sS http://127.0.0.1:6000/evaluate -d '1+1'
   ```
3. Check `ZEROAD_RL_URL` environment variable matches actual RL interface address

## Diagnostic Workflow

When something breaks, follow this order:

1. **Test RL interface directly**
   ```bash
   curl -sS http://127.0.0.1:6000/evaluate --data '1+1'
   ```

2. **Test OpenEnv proxy health**
   ```bash
   curl -sS http://127.0.0.1:8000/health
   ```

3. **Run stepper diagnostics**
   ```bash
   python tools/execute_move.py --diag
   ```

4. **List entities**
   ```bash
   python tools/execute_move.py --list --player=1
   ```

5. **Test simple command**
   ```bash
   # Get an entity ID from step 4, then:
   curl -sS -X POST http://127.0.0.1:8000/step \
     -H 'content-type: application/json' \
     -d '{"action":{"op":"push_command","player_id":1,"cmd":{"type":"stop","entities":[<ID>],"queued":false}}}' \
     | python -m json.tool
   ```

## Log Locations

- **0 A.D. logs**: Check terminal A output
- **Stepper logs**: Check terminal B output
- **OpenEnv proxy logs**: Check terminal C output
- **Game state**: `run/latest_state.json`

## Environment Variables Checklist

Verify these are set correctly:

```bash
# For 0 A.D. (Terminal A)
echo $ZEROAD_RL_INTERFACE  # Should be: 127.0.0.1:6000

# For Stepper (Terminal B)
echo $ZEROAD_RL_URL        # Should be: http://127.0.0.1:6000
echo $ZEROAD_STEP_SLEEP    # Should be: 0.01 or 0.02
echo $ZEROAD_STATE_OUT     # Should be: run/latest_state.json
echo $ZEROAD_STATE_EVERY_N # Should be: 10

# For OpenEnv Proxy (Terminal C)
echo $ZEROAD_RL_URL        # Should be: http://127.0.0.1:6000
```

## Performance Tuning

If experiencing slowdowns:

1. **Increase step sleep**: `export ZEROAD_STEP_SLEEP=0.02`
2. **Reduce snapshot frequency**: `export ZEROAD_STATE_EVERY_N=20`
3. **Check CPU usage**: `top` or `htop`
4. **Close other applications** to free resources

## Getting More Help

If issues persist:
1. Check the main README.md for updated troubleshooting
2. Review the skills documentation
3. Check GitHub issues for similar problems
