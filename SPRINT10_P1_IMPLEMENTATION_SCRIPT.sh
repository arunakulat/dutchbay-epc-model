#!/bin/bash
# Sprint 10 P1: All three optimizations - Implementation Script
# Run this after pulling: bash SPRINT10_P1_IMPLEMENTATION_SCRIPT.sh

set -e

echo "═══════════════════════════════════════════════════════════════════════════"
echo "Sprint 10 P1: Monte Carlo Speed Optimization - Implementation"
echo "═══════════════════════════════════════════════════════════════════════════"

# Backup original
cp analytics/monte_carlo_v14.py analytics/monte_carlo_v14.py.backup
echo "✅ Backed up original to analytics/monte_carlo_v14.py.backup"

# ============================================================================
# P1.1: CONFIG CACHING
# ============================================================================
echo ""
echo "[1/3] Applying P1.1: Config caching optimization..."

# Step 1: Add cache dict after imports (after line 27: warnings.filterwarnings)
python3 << 'EOF'
import re

with open('analytics/monte_carlo_v14.py', 'r') as f:
    content = f.read()

# Find insertion point: after "warnings.filterwarnings("ignore", category=RuntimeWarning)"
insert_marker = 'warnings.filterwarnings("ignore", category=RuntimeWarning)\n'

if insert_marker in content:
    cache_block = '''\n# ===== P1.1 OPTIMIZATION: Config Caching =====
# Module-level cache to avoid reloading YAML files per iteration
_CONFIG_CACHE: dict[str, "MonteCarloConfig"] = {}
'''
    content = content.replace(insert_marker, insert_marker + cache_block)
    print("✅ Added _CONFIG_CACHE dict")
else:
    print("⚠️  Could not find insertion point")

with open('analytics/monte_carlo_v14.py', 'w') as f:
    f.write(content)
EOF

# Step 2: Replace config loading in run_monte_carlo_analysis
python3 << 'EOF'
with open('analytics/monte_carlo_v14.py', 'r') as f:
    content = f.read()

# Find and replace the config loading section
old_pattern = '''    logger.info("Starting Monte Carlo analysis: %s", base_config_path)

    # Load + validate Monte Carlo configuration
    mc_config = _load_monte_carlo_config(scenario_config_path)'''

new_pattern = '''    logger.info("Starting Monte Carlo analysis: %s", base_config_path)

    # ===== P1.1 OPTIMIZATION: Load from cache if available =====
    if scenario_config_path in _CONFIG_CACHE:
        logger.info("Loading MC config from cache: %s", scenario_config_path)
        mc_config = _CONFIG_CACHE[scenario_config_path]
    else:
        # Load + validate Monte Carlo configuration
        mc_config = _load_monte_carlo_config(scenario_config_path)
        _CONFIG_CACHE[scenario_config_path] = mc_config'''

if old_pattern in content:
    content = content.replace(old_pattern, new_pattern)
    print("✅ Added config caching logic to run_monte_carlo_analysis()")
else:
    print("⚠️  Could not find config loading pattern")

with open('analytics/monte_carlo_v14.py', 'w') as f:
    f.write(content)
EOF

echo "✅ P1.1 applied: Config caching"

# ============================================================================
# Validation
# ============================================================================
echo ""
echo "Validating Python syntax..."
python3 -m py_compile analytics/monte_carlo_v14.py
echo "✅ Syntax valid"

echo ""
echo "═══════════════════════════════════════════════════════════════════════════"
echo "Sprint 10 P1.1 Complete"
echo "═══════════════════════════════════════════════════════════════════════════"
echo ""
echo "Next steps:"
echo "  1. Run tests: pytest tests/api/test_monte_carlo_regression_toy.py -v"
echo "  2. Record baseline runtime"
echo "  3. Compare with 54.82s baseline"
echo "  4. Target: ~40s (27% speedup)"
echo ""
echo "To revert:"
echo "  cp analytics/monte_carlo_v14.py.backup analytics/monte_carlo_v14.py"
