#!/bin/bash
# Quick launcher for example LLM arena matches

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Multi-Provider LLM Arena ===${NC}"
echo ""

# Check required API keys
check_api_keys() {
    local needed_keys=()

    if [[ "$1" == *"openai"* ]]; then
        if [ -z "$OPENAI_API_KEY" ]; then
            needed_keys+=("OPENAI_API_KEY")
        fi
    fi

    if [[ "$1" == *"grok"* ]]; then
        if [ -z "$XAI_API_KEY" ]; then
            needed_keys+=("XAI_API_KEY")
        fi
    fi

    if [[ "$1" == *"gemini"* ]]; then
        if [ -z "$GEMINI_API_KEY" ]; then
            needed_keys+=("GEMINI_API_KEY")
        fi
    fi

    if [ ${#needed_keys[@]} -gt 0 ]; then
        echo -e "${RED}Missing API keys:${NC}"
        for key in "${needed_keys[@]}"; do
            echo "  - $key"
        done
        echo ""
        echo "Set them with:"
        for key in "${needed_keys[@]}"; do
            echo "  export $key=your-key-here"
        done
        exit 1
    fi
}

# Show available examples
show_examples() {
    echo "Available example matches:"
    echo ""
    echo "  1) openai_vs_ai       - OpenAI GPT-4o vs Built-in 0 A.D. AI (recommended)"
    echo "  2) gemini_vs_ai       - Google Gemini vs Built-in 0 A.D. AI"
    echo "  3) openai_vs_local    - OpenAI GPT-4o vs Local Llama-3"
    echo "  4) grok_vs_openai     - Grok-Beta vs OpenAI GPT-4o"
    echo "  5) gemini_vs_openai   - Google Gemini vs OpenAI GPT-4o"
    echo "  6) local_vs_local     - Llama-3-70B vs Mistral-7B (both local)"
    echo "  7) custom             - Use your own config file"
    echo ""
}

# Main menu
if [ $# -eq 0 ]; then
    show_examples
    read -p "Select example (1-7): " choice
else
    choice=$1
fi

case $choice in
    1|openai_vs_ai)
        config="configs/openai_vs_ai.toml"
        check_api_keys "openai"
        ;;
    2|gemini_vs_ai)
        config="configs/gemini_vs_ai.toml"
        check_api_keys "gemini"
        ;;
    3|openai_vs_local)
        config="configs/examples/openai_vs_local.toml"
        check_api_keys "openai"
        ;;
    4|grok_vs_openai)
        config="configs/examples/grok_vs_openai.toml"
        check_api_keys "openai grok"
        ;;
    5|gemini_vs_openai)
        config="configs/examples/gemini_vs_openai.toml"
        check_api_keys "openai gemini"
        ;;
    6|local_vs_local)
        config="configs/examples/local_vs_local.toml"
        echo -e "${YELLOW}Note: Ensure both local servers are running:${NC}"
        echo "  - http://localhost:1234 (Llama-3-70B)"
        echo "  - http://localhost:8080 (Mistral-7B)"
        echo ""
        ;;
    7|custom)
        read -p "Enter config file path: " config
        ;;
    *)
        echo -e "${RED}Invalid choice${NC}"
        exit 1
        ;;
esac

# Verify config exists
if [ ! -f "$PROJECT_DIR/$config" ]; then
    echo -e "${RED}Config file not found: $config${NC}"
    exit 1
fi

# Pre-flight checks
echo -e "${YELLOW}Pre-flight checks:${NC}"
echo ""

# Check if state file directory exists
STATE_DIR="$PROJECT_DIR/run"
if [ ! -d "$STATE_DIR" ]; then
    echo -e "${YELLOW}Creating run directory...${NC}"
    mkdir -p "$STATE_DIR"
fi

# Check if OpenEnv proxy is reachable
OPENENV_BASE=$(grep -E "^openenv_base" "$PROJECT_DIR/$config" | cut -d'"' -f2)
if [ -n "$OPENENV_BASE" ]; then
    echo -n "Checking OpenEnv proxy at $OPENENV_BASE ... "
    if curl -sf "$OPENENV_BASE/health" > /dev/null 2>&1; then
        echo -e "${GREEN}OK${NC}"
    else
        echo -e "${RED}FAILED${NC}"
        echo ""
        echo "OpenEnv proxy not responding. Ensure it's running:"
        echo "  export ZEROAD_RL_URL=http://127.0.0.1:6000"
        echo "  python tools/run_openenv_zero_ad_server.py --host=127.0.0.1 --port=8001"
        echo ""
        read -p "Continue anyway? (y/N): " continue
        if [[ ! "$continue" =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
fi

# Check if state file exists
STATE_FILE=$(grep -E "^state_file" "$PROJECT_DIR/$config" | cut -d'"' -f2)
if [ -n "$STATE_FILE" ]; then
    echo -n "Checking state file at $STATE_FILE ... "
    if [ -f "$PROJECT_DIR/$STATE_FILE" ]; then
        echo -e "${GREEN}OK${NC}"
        # Check if it's being updated
        MTIME=$(stat -c %Y "$PROJECT_DIR/$STATE_FILE" 2>/dev/null || stat -f %m "$PROJECT_DIR/$STATE_FILE" 2>/dev/null)
        NOW=$(date +%s)
        AGE=$((NOW - MTIME))
        if [ $AGE -gt 10 ]; then
            echo -e "${YELLOW}  Warning: State file is $AGE seconds old. Ensure stepper is running.${NC}"
        fi
    else
        echo -e "${YELLOW}NOT FOUND${NC}"
        echo ""
        echo "State file doesn't exist yet. Ensure stepper is running:"
        echo "  export ZEROAD_RL_URL=http://127.0.0.1:6000"
        echo "  export ZEROAD_STATE_OUT=run/latest_state.json"
        echo "  python tools/execute_move.py --run"
        echo ""
        read -p "Continue anyway? (y/N): " continue
        if [[ ! "$continue" =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
fi

echo ""
echo -e "${GREEN}Starting match with config: $config${NC}"
echo ""
echo "Press Ctrl+C to stop"
echo ""

# Run the match
cd "$PROJECT_DIR"
python tools/multi_provider_match.py --config "$config"
