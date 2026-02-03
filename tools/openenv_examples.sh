#!/usr/bin/env bash

set -u

API_BASE="${1:-${API_BASE:-}}"

if [[ -z "$API_BASE" ]]; then
  echo "Usage: API_BASE=http://127.0.0.1:8000 $0"
  echo "   or: $0 http://127.0.0.1:8000"
  exit 2
fi

echo "API_BASE=$API_BASE"
echo

echo "Waiting for OpenEnv proxy ($API_BASE)..."
for _ in $(seq 1 60); do
  if curl -sS -m 1 "$API_BASE/health" >/dev/null 2>&1; then
    echo "Proxy is up."
    echo
    break
  fi
  sleep 0.5
done

echo "== Health =="
curl -sS "$API_BASE/health" | python -m json.tool || true
echo

echo "== Schema =="
curl -sS "$API_BASE/schema" | python -m json.tool || true
echo

echo "== Reset =="
curl -sS -X POST "$API_BASE/reset" -H 'content-type: application/json' -d '{}' | python -m json.tool || true
echo

echo "== Evaluate (1+1) =="
curl -sS -X POST "$API_BASE/step" -H 'content-type: application/json' -d '{"action":{"op":"evaluate","code":"1+1"}}' | python -m json.tool || true
echo

cat <<'EOF'
More examples:

  # Push a Simulation2 command (walk)
  curl -sS -X POST "$API_BASE/step" -H 'content-type: application/json' \
    -d '{"action":{"op":"push_command","player_id":1,"cmd":{"type":"walk","entities":[186],"x":150,"z":200,"queued":false,"pushFront":true}}}' \
    | python -m json.tool

EOF
