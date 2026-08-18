#!/bin/bash
# =============================================================================
# DutchBay EPC Model - Virtual Environment Setup & Validation Script
# Purpose: Ensures the project .venv exists, is active, and dependencies installed
# Note: `make setup` is the canonical bootstrap; this script is an equivalent
#       standalone helper.
# =============================================================================

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Project root (where this script lives)
PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$PROJECT_ROOT/.venv"
REQUIREMENTS="$PROJECT_ROOT/requirements.txt"

echo "================================================================================"
echo "DutchBay V13 - Virtual Environment Setup"
echo "================================================================================"
echo "Project Root: $PROJECT_ROOT"
echo ""

# =============================================================================
# Step 1: Check Python 3 Installation
# =============================================================================
echo "Step 1: Checking Python installation..."

# Prefer the CI baseline explicitly. A generic `python3` can point at a newer,
# incompatible Homebrew interpreter (or even a broken shim), especially in a fresh
# Codex worktree. Fall back only to interpreters that can execute and meet >=3.12.
PYTHON_CMD=""
for candidate in python3.12 python3 python; do
    if command -v "$candidate" >/dev/null 2>&1 \
        && "$candidate" -c 'import sys; raise SystemExit(sys.version_info < (3, 12))' \
            >/dev/null 2>&1; then
        PYTHON_CMD="$candidate"
        break
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo -e "${RED}✗ A working Python 3.12+ interpreter was not found.${NC}"
    echo ""
    echo "Install the CI baseline using Homebrew:"
    echo "  brew install python@3.12"
    echo ""
    echo "Or download Python 3.12+ from https://www.python.org/downloads/"
    exit 1
fi

PYTHON_VERSION=$(
    "$PYTHON_CMD" -c 'import platform; print(f"Python {platform.python_version()}")'
)
echo -e "${GREEN}✓${NC} Found: $PYTHON_VERSION ($PYTHON_CMD)"

echo ""

# =============================================================================
# Step 2: Check if Virtual Environment Exists
# =============================================================================
echo "Step 2: Checking virtual environment..."

if [ -d "$VENV_DIR" ]; then
    echo -e "${GREEN}✓${NC} Virtual environment exists: $VENV_DIR"
else
    echo -e "${YELLOW}⚠${NC}  Virtual environment not found. Creating..."
    $PYTHON_CMD -m venv "$VENV_DIR"

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓${NC} Virtual environment created successfully"
    else
        echo -e "${RED}✗ Failed to create virtual environment${NC}"
        exit 1
    fi
fi

echo ""

# =============================================================================
# Step 3: Activate Virtual Environment
# =============================================================================
echo "Step 3: Activating virtual environment..."

# Source the activation script
source "$VENV_DIR/bin/activate"

if [ "$VIRTUAL_ENV" = "$VENV_DIR" ]; then
    echo -e "${GREEN}✓${NC} Virtual environment activated"
    echo "   VIRTUAL_ENV: $VIRTUAL_ENV"
else
    echo -e "${RED}✗ Failed to activate virtual environment${NC}"
    exit 1
fi

echo ""

# =============================================================================
# Step 4: Install/Update Dependencies
# =============================================================================
echo "Step 4: Installing dependencies..."

if [ -f "$REQUIREMENTS" ]; then
    echo "Installing from requirements.txt (pinned lock) + the [dev] toolchain..."
    pip install --upgrade pip --quiet
    pip install -r "$REQUIREMENTS" --quiet
    pip install -e ".[dev]" --quiet
    echo -e "${GREEN}✓${NC} Dependencies installed"
else
    echo -e "${YELLOW}⚠${NC}  requirements.txt not found. Installing essential packages..."
    pip install --upgrade pip --quiet
    pip install numpy pandas scipy pyyaml pydantic pytest pytest-cov --quiet
    echo -e "${GREEN}✓${NC} Essential packages installed"
fi

echo ""

# =============================================================================
# Step 5: Verification
# =============================================================================
echo "Step 5: Verifying installation..."

# Check Python in venv
VENV_PYTHON="$VENV_DIR/bin/python"
if [ -x "$VENV_PYTHON" ]; then
    VENV_PY_VER=$("$VENV_PYTHON" --version)
    echo -e "${GREEN}✓${NC} Python in venv: $VENV_PY_VER"
else
    echo -e "${RED}✗ Python not found in venv${NC}"
    exit 1
fi

# Check key packages
echo "Checking key packages..."
"$VENV_PYTHON" -c "import numpy; print(f'  numpy: {numpy.__version__}')" 2>/dev/null && echo -e "${GREEN}✓${NC} numpy installed" || echo -e "${YELLOW}⚠${NC}  numpy not installed"
"$VENV_PYTHON" -c "import pandas; print(f'  pandas: {pandas.__version__}')" 2>/dev/null && echo -e "${GREEN}✓${NC} pandas installed" || echo -e "${YELLOW}⚠${NC}  pandas not installed"
"$VENV_PYTHON" -c "import scipy; print(f'  scipy: {scipy.__version__}')" 2>/dev/null && echo -e "${GREEN}✓${NC} scipy installed" || echo -e "${YELLOW}⚠${NC}  scipy not installed"

echo ""

# =============================================================================
# Summary
# =============================================================================
echo "================================================================================"
echo -e "${GREEN}✓ Setup Complete!${NC}"
echo "================================================================================"
echo ""
echo "Virtual environment is ready at:"
echo "  $VENV_DIR"
echo ""
echo "To activate manually in future sessions:"
echo "  cd $PROJECT_ROOT"
echo "  source .venv/bin/activate"
echo ""
echo "To run Python scripts:"
echo "  .venv/bin/python your_script.py"
echo ""
echo "To deactivate:"
echo "  deactivate"
echo ""
echo "================================================================================"
