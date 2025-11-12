#!/bin/bash
# =============================================================================
# DutchBay V13 Virtual Environment Setup & Validation Script
# Location: /Users/aruna/Desktop/DutchBay_EPC_Extracted/DutchBay_EPC_Model/
# Purpose: Ensures Python venv exists, is active, and dependencies installed
# =============================================================================

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Project root (where this script lives)
PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$PROJECT_ROOT/venv"
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

if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
    PYTHON_VERSION=$(python3 --version)
    echo -e "${GREEN}✓${NC} Found: $PYTHON_VERSION"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
    PYTHON_VERSION=$(python --version)
    echo -e "${GREEN}✓${NC} Found: $PYTHON_VERSION"
else
    echo -e "${RED}✗ Python not found!${NC}"
    echo ""
    echo "Install Python 3.9+ using Homebrew:"
    echo "  brew install python3"
    echo ""
    echo "Or download from: https://www.python.org/downloads/"
    exit 1
fi

# Verify Python version (need 3.9+)
PYTHON_VER=$($PYTHON_CMD -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
MIN_VERSION="3.9"

if [ "$(printf '%s\n' "$MIN_VERSION" "$PYTHON_VER" | sort -V | head -n1)" != "$MIN_VERSION" ]; then
    echo -e "${RED}✗ Python $PYTHON_VER is too old (need 3.9+)${NC}"
    echo "Upgrade Python: brew upgrade python3"
    exit 1
fi

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
    echo "Installing from requirements.txt..."
    pip install --upgrade pip --quiet
    pip install -r "$REQUIREMENTS" --quiet
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
echo "  source venv/bin/activate"
echo ""
echo "To run Python scripts:"
echo "  venv/bin/python your_script.py"
echo ""
echo "To deactivate:"
echo "  deactivate"
echo ""
echo "================================================================================"
