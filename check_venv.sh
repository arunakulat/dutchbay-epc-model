#!/bin/bash
# =============================================================================
# Quick Virtual Environment Check Script
# Checks if venv is active; if not, activates it or runs setup
# =============================================================================

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$PROJECT_ROOT/venv"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Check if venv is already active
if [ -n "$VIRTUAL_ENV" ] && [ "$VIRTUAL_ENV" = "$VENV_DIR" ]; then
    echo -e "${GREEN}✓${NC} Virtual environment already active"
    echo "   $VIRTUAL_ENV"
    exit 0
fi

# Check if venv exists
if [ ! -d "$VENV_DIR" ]; then
    echo -e "${YELLOW}⚠${NC}  Virtual environment not found. Running setup..."
    bash "$PROJECT_ROOT/setup_venv.sh"
    exit $?
fi

# Activate venv
echo "Activating virtual environment..."
source "$VENV_DIR/bin/activate"

if [ "$VIRTUAL_ENV" = "$VENV_DIR" ]; then
    echo -e "${GREEN}✓${NC} Virtual environment activated"
    echo "   $VIRTUAL_ENV"
else
    echo -e "${RED}✗${NC} Failed to activate. Run setup_venv.sh"
    exit 1
fi
