#!/bin/bash
# V14 Git Branch Setup - Diagnostic & Setup Script
# Run this to check current state and setup v14 branch
# Date: 2025-11-17

PROJECT_DIR="/Users/aruna/Desktop/DutchBay_EPC_Extracted/DutchBay_EPC_Model"

echo "================================================================"
echo "DUTCH BAY V14 BRANCH SETUP - SYSTEM CHECK"
echo "================================================================"
echo ""

# Change to project directory
cd "$PROJECT_DIR" || {
    echo "❌ ERROR: Cannot access $PROJECT_DIR"
    exit 1
}

echo "✓ Project directory: $PROJECT_DIR"
echo ""

# ============================================================================
# CHECK 1: Git Status
# ============================================================================
echo "─────────────────────────────────────────────────────────────────"
echo "CHECK 1: Git Repository Status"
echo "─────────────────────────────────────────────────────────────────"

if [ -d .git ]; then
    echo "✓ Git repository exists"
    
    # Current branch
    CURRENT_BRANCH=$(git branch --show-current 2>/dev/null)
    if [ $? -eq 0 ]; then
        echo "  Current branch: $CURRENT_BRANCH"
    else
        echo "  ⚠ Cannot determine current branch"
    fi
    
    # Check for uncommitted changes
    if git diff --quiet && git diff --staged --quiet; then
        echo "  ✓ No uncommitted changes"
    else
        echo "  ⚠ WARNING: Uncommitted changes detected"
        echo ""
        echo "  Modified files:"
        git status --short
    fi
    
    # List all branches
    echo ""
    echo "  Existing branches:"
    git branch -a
    
else
    echo "❌ No Git repository found"
    echo "   Run: git init"
fi

echo ""

# ============================================================================
# CHECK 2: Virtual Environment
# ============================================================================
echo "─────────────────────────────────────────────────────────────────"
echo "CHECK 2: Python Virtual Environment"
echo "─────────────────────────────────────────────────────────────────"

if [ -d .venv311 ]; then
    echo "✓ Virtual environment folder exists: .venv311"
    
    # Check if it has Python
    if [ -f .venv311/bin/python ]; then
        echo "  ✓ Python executable found"
        
        # Check Python version
        VENV_PYTHON=$(.venv311/bin/python --version 2>&1)
        echo "  Version: $VENV_PYTHON"
        
        # Check if activated
        if [ -n "$VIRTUAL_ENV" ]; then
            echo "  ✓ Virtual environment is ACTIVATED"
            echo "    Active venv: $VIRTUAL_ENV"
        else
            echo "  ⚠ Virtual environment NOT activated"
            echo "    To activate: source .venv311/bin/activate"
        fi
    else
        echo "  ❌ Python executable not found in .venv311"
        echo "     Venv may be corrupted"
    fi
else
    echo "❌ Virtual environment not found: .venv311"
    echo "   Create with: python3.11 -m venv .venv311"
fi

echo ""

# ============================================================================
# CHECK 3: Python Dependencies
# ============================================================================
echo "─────────────────────────────────────────────────────────────────"
echo "CHECK 3: Python Dependencies"
echo "─────────────────────────────────────────────────────────────────"

if [ -f requirements.txt ]; then
    echo "✓ requirements.txt found"
    
    if [ -f .venv311/bin/pip ]; then
        echo ""
        echo "  Checking installed packages..."
        
        # Check key packages
        PACKAGES=("numpy" "pandas" "scipy" "pyyaml" "pytest")
        
        for pkg in "${PACKAGES[@]}"; do
            if .venv311/bin/pip list 2>/dev/null | grep -i "^$pkg " > /dev/null; then
                VERSION=$(.venv311/bin/pip show "$pkg" 2>/dev/null | grep Version | awk '{print $2}')
                echo "  ✓ $pkg: $VERSION"
            else
                echo "  ❌ $pkg: NOT INSTALLED"
            fi
        done
    fi
else
    echo "⚠ requirements.txt not found"
fi

echo ""

# ============================================================================
# CHECK 4: Core Python Modules
# ============================================================================
echo "─────────────────────────────────────────────────────────────────"
echo "CHECK 4: Core Python Modules"
echo "─────────────────────────────────────────────────────────────────"

CORE_MODULES=("debt.py" "cashflow.py" "metrics.py" "irr.py" "config.py")

echo "Checking src/ directory..."
if [ -d src ]; then
    for module in "${CORE_MODULES[@]}"; do
        if [ -f "src/$module" ]; then
            SIZE=$(wc -l < "src/$module" 2>/dev/null)
            echo "  ✓ $module ($SIZE lines)"
        else
            echo "  ❌ $module NOT FOUND"
        fi
    done
else
    echo "  ⚠ src/ directory not found"
    echo "    Checking root directory..."
    for module in "${CORE_MODULES[@]}"; do
        if [ -f "$module" ]; then
            SIZE=$(wc -l < "$module" 2>/dev/null)
            echo "  ✓ $module ($SIZE lines)"
        else
            echo "  ⚠ $module NOT FOUND"
        fi
    done
fi

echo ""

# ============================================================================
# CHECK 5: Configuration Files
# ============================================================================
echo "─────────────────────────────────────────────────────────────────"
echo "CHECK 5: Configuration Files"
echo "─────────────────────────────────────────────────────────────────"

CONFIG_FILES=("config/full_model_variables.yaml" "config/full_model_variables_v243.yaml" "full_model_variables.yaml")

for config in "${CONFIG_FILES[@]}"; do
    if [ -f "$config" ]; then
        echo "  ✓ Found: $config"
    fi
done

if ! ls config/*.yaml 2>/dev/null && ! ls *.yaml 2>/dev/null; then
    echo "  ❌ No YAML configuration files found"
fi

echo ""

# ============================================================================
# SUMMARY & RECOMMENDATIONS
# ============================================================================
echo "================================================================"
echo "SUMMARY & RECOMMENDATIONS"
echo "================================================================"
echo ""

# Count issues
ISSUES=0

if [ ! -d .git ]; then
    echo "❌ Git not initialized"
    ISSUES=$((ISSUES + 1))
fi

if [ ! -d .venv311 ] || [ ! -f .venv311/bin/python ]; then
    echo "❌ Virtual environment missing or broken"
    ISSUES=$((ISSUES + 1))
fi

if [ -z "$VIRTUAL_ENV" ]; then
    echo "⚠ Virtual environment not activated"
    ISSUES=$((ISSUES + 1))
fi

if [ $ISSUES -eq 0 ]; then
    echo "✓ All basic checks passed!"
    echo ""
    echo "Ready to create v14 branch."
else
    echo "Found $ISSUES issue(s) that need attention."
fi

echo ""
echo "================================================================"
echo "NEXT STEPS"
echo "================================================================"
echo ""
echo "Execute these commands to fix any issues:"
echo ""

if [ ! -d .git ]; then
    echo "# Initialize Git:"
    echo "git init"
    echo "git add ."
    echo "git commit -m 'Initial commit - v13 baseline'"
    echo ""
fi

if [ ! -d .venv311 ] || [ ! -f .venv311/bin/python ]; then
    echo "# Create virtual environment:"
    echo "python3.11 -m venv .venv311"
    echo ""
fi

if [ -z "$VIRTUAL_ENV" ]; then
    echo "# Activate virtual environment:"
    echo "source .venv311/bin/activate"
    echo ""
fi

echo "# Install/upgrade dependencies:"
echo "pip install --upgrade pip"
echo "pip install numpy pandas scipy pyyaml pytest pytest-cov black flake8 mypy"
echo ""

echo "# Create v14 branch:"
echo "git checkout -b v14-upgrade"
echo ""

echo "================================================================"
echo "Run this script: bash v14_setup_diagnostic.sh"
echo "================================================================"
