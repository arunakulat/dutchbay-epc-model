#!/bin/bash
# =============================================================================
# DutchBay EPC Model - Developer Environment Setup
#
# Purpose: Ensures a consistent Python virtual environment is created,
#          activated, and all necessary dependencies are installed.
# =============================================================================

set -e # Exit immediately if a command exits with a non-zero status.

# --- Configuration ---
PYTHON_MIN_VERSION="3.11"
VENV_DIR=".venv" # Using .venv is a modern standard
REQUIREMENTS_FILE="requirements.txt"
REQUIREMENTS_DEV_FILE="requirements_dev.txt"

# --- Color Codes for Better UX ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# --- Helper Functions ---
print_header() {
    echo -e "${BLUE}================================================================================${NC}"
    echo -e "${BLUE}🔎 $1${NC}"
    echo -e "${BLUE}================================================================================${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# --- Main Script ---
cd "$(dirname "$0")" # Run from script's directory
PROJECT_ROOT=$(pwd)

print_header "Starting Developer Environment Setup for DutchBay EPC Model"

# 1. Verify Python Version
echo "Checking Python version..."
if ! command -v python3 &> /dev/null; then
    print_error "Python 3 is not installed. Please install Python ${PYTHON_MIN_VERSION} or higher."
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
if [[ "$(printf '%s\n' "$PYTHON_MIN_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$PYTHON_MIN_VERSION" ]]; then
    print_error "Python version ${PYTHON_VERSION} is too old. Please use Python ${PYTHON_MIN_VERSION} or higher."
    exit 1
fi
print_success "Python ${PYTHON_VERSION} found."
echo ""

# 2. Create Virtual Environment
print_header "Setting up virtual environment in '${VENV_DIR}'"
if [ -d "$VENV_DIR" ]; then
    print_success "Virtual environment already exists."
else
    python3 -m venv "$VENV_DIR"
    print_success "Virtual environment created."
fi
echo ""

# 3. Install Dependencies
print_header "Installing dependencies"
source "${VENV_DIR}/bin/activate"
echo "Upgrading pip..."
pip install --upgrade pip > /dev/null 2>&1
print_success "pip is up to date."

echo "Installing production dependencies from ${REQUIREMENTS_FILE}..."
pip install -r "${REQUIREMENTS_FILE}" > /dev/null 2>&1
print_success "Production dependencies installed."

if [ -f "$REQUIREMENTS_DEV_FILE" ]; then
    echo "Installing development dependencies from ${REQUIREMENTS_DEV_FILE}..."
    pip install -r "${REQUIREMENTS_DEV_FILE}" > /dev/null 2>&1
    print_success "Development dependencies installed."
else
    print_warning "${REQUIREMENTS_DEV_FILE} not found. Skipping."
fi
echo ""

# 4. Final Summary
print_header "🎉 Setup Complete! 🎉"
echo "Your developer environment is ready."
echo ""
echo "To activate it in your shell, run the following command:"
echo -e "  ${YELLOW}source ${VENV_DIR}/bin/activate${NC}"
echo ""
echo "Once activated, you can run tests and other project commands."
echo "================================================================================"
