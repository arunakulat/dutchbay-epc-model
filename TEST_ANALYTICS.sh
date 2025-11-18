#!/bin/bash
# Test script for Analytics Master Suite
# Run from project root

set -e  # Exit on error

echo "====================================="
echo "Testing Analytics Master Suite"
echo "====================================="
echo ""

# Ensure virtual environment is activated
if [[ -z "$VIRTUAL_ENV" ]]; then
    echo "Activating virtual environment..."
    source .venv311/bin/activate
fi

echo "Python: $(which python)"
echo "Python version: $(python --version)"
echo ""

# Install/upgrade dependencies
echo "Installing analytics dependencies..."
pip install -q openpyxl matplotlib pyyaml scipy numpy-financial
echo "Dependencies installed."
echo ""

# Create exports directory if needed
mkdir -p exports/charts

# Run analytics on existing scenarios
echo "Running analytics on scenarios in ./scenarios..."
echo ""

python analytics/scenario_analytics.py \
  --dir ./scenarios \
  --output ./exports/DutchBay_Analytics_Test_$(date +%Y%m%d_%H%M%S).xlsx \
  --discount 0.08 \
  --dscr 1.25

echo ""
echo "====================================="
echo "Test complete!"
echo "Check ./exports/ for output files"
echo "====================================="
