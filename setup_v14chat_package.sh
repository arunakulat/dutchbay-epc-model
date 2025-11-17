#!/bin/bash
# Create dutchbay_v14chat package structure
# Date: 2025-11-17 07:03 AM
# Branch: v14chat-upgrade

set -e

echo "================================================================"
echo "CREATING DUTCHBAY_V14CHAT PACKAGE STRUCTURE"
echo "================================================================"
echo ""

# Create v14chat package structure
echo "[1/5] Creating package directories..."
mkdir -p dutchbay_v14chat
mkdir -p dutchbay_v14chat/finance
mkdir -p dutchbay_v14chat/config
mkdir -p dutchbay_v14chat/reporting
mkdir -p dutchbay_v14chat/tests

echo "✓ Directories created"

# Create __init__.py files
echo ""
echo "[2/5] Creating __init__.py files..."
cat > dutchbay_v14chat/__init__.py << 'EOF'
"""
DutchBay V14 Chat - Enhanced Financial Model
Version: 14.0.0-chat
Date: 2025-11-17

New Features:
- Construction period modeling (2 years)
- Grace period support
- Debt tranching
- Tax scenario analysis (3 scenarios)
"""

__version__ = "14.0.0-chat"
__author__ = "DutchBay V14 Team"

EOF

cat > dutchbay_v14chat/finance/__init__.py << 'EOF'
"""Finance module for dutchbay_v14chat"""
EOF

cat > dutchbay_v14chat/config/__init__.py << 'EOF'
"""Configuration module for dutchbay_v14chat"""
EOF

cat > dutchbay_v14chat/reporting/__init__.py << 'EOF'
"""Reporting module for dutchbay_v14chat"""
EOF

cat > dutchbay_v14chat/tests/__init__.py << 'EOF'
"""Tests for dutchbay_v14chat"""
EOF

echo "✓ __init__.py files created"

# Copy key v13 files as reference/base
echo ""
echo "[3/5] Copying v13 base files..."

# Essential utilities (unchanged from v13)
cp dutchbay_v13/finance/irr.py dutchbay_v14chat/finance/irr.py
cp dutchbay_v13/finance/utils.py dutchbay_v14chat/finance/utils.py

# Configuration and data adapters
cp dutchbay_v13/config.py dutchbay_v14chat/config.py
cp dutchbay_v13/adapters.py dutchbay_v14chat/adapters.py
cp dutchbay_v13/db_types.py dutchbay_v14chat/db_types.py

# Core files that will be extended
cp dutchbay_v13/finance/debt.py dutchbay_v14chat/finance/debt_v13.py
cp dutchbay_v13/finance/cashflow.py dutchbay_v14chat/finance/cashflow_v13.py
cp dutchbay_v13/finance/metrics.py dutchbay_v14chat/finance/metrics_v13.py

echo "✓ Base files copied from v13"

# Create v14 subdirectory for new modules
echo ""
echo "[4/5] Creating v14 module directory..."
mkdir -p dutchbay_v14chat/finance/v14
cat > dutchbay_v14chat/finance/v14/__init__.py << 'EOF'
"""
V14 New Features Module

New modules:
- scenario_manager.py: Tax scenario switching
- tax_calculator.py: Depreciation & tax holidays
"""
EOF

echo "✓ V14 module directory ready"

# Create config directory for v14 YAML
echo ""
echo "[5/5] Creating configuration directory..."
mkdir -p config/v14chat

cat > config/v14chat/README.md << 'EOF'
# V14 Chat Configuration

Place full_model_variables_v14.yaml here.

This directory contains:
- full_model_variables_v14.yaml: Main model configuration
- Scenario-specific overrides
- Tax parameter variations
EOF

echo "✓ Configuration directory created"

echo ""
echo "================================================================"
echo "PACKAGE STRUCTURE CREATED SUCCESSFULLY"
echo "================================================================"
echo ""
echo "Created structure:"
echo ""
echo "dutchbay_v14chat/"
echo "├── __init__.py (version 14.0.0-chat)"
echo "├── finance/"
echo "│   ├── __init__.py"
echo "│   ├── v14/ (for new modules)"
echo "│   │   └── __init__.py"
echo "│   ├── irr.py (from v13)"
echo "│   ├── utils.py (from v13)"
echo "│   ├── debt_v13.py (reference copy)"
echo "│   ├── cashflow_v13.py (reference copy)"
echo "│   └── metrics_v13.py (reference copy)"
echo "├── config.py"
echo "├── adapters.py"
echo "├── db_types.py"
echo "├── config/"
echo "└── tests/"
echo ""
echo "config/"
echo "└── v14chat/"
echo "    └── README.md"
echo ""
echo "✓ Ready for v14 modules!"
echo ""
echo "Next steps:"
echo "1. Add scenario_manager.py to dutchbay_v14chat/finance/v14/"
echo "2. Add tax_calculator.py to dutchbay_v14chat/finance/v14/"  
echo "3. Add full_model_variables_v14.yaml to config/v14chat/"
echo "4. Create refactored debt.py, cashflow.py, metrics.py"
echo ""
