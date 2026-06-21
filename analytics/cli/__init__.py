"""CLI Entrypoints Package.

This package contains Hydra-based command-line interface (CLI) wrappers for
analytics workflows. All CLI tools follow GWTF R3 (Hydra-only) and output
structured JSON (CLI-03).

Modules:
    cli_monte_carlo_hydra: Hydra CLI wrapper for Monte Carlo analysis.
                          Canonical entrypoint for MC simulations.
                          
    cli_sensitivity_hydra: Hydra CLI wrapper for sensitivity analysis.
                          Canonical entrypoint for parameter sensitivity.
                          
    cli_sensitivity: ⚠️ DEPRECATED argparse-based sensitivity CLI.
                    Use cli_sensitivity_hydra instead.
                    Removal planned: Sprint 18 (Q1 2026).

Usage:
    # Monte Carlo (Hydra)
    python analytics/cli/cli_monte_carlo_hydra.py \\
        config=scenarios/example.yaml \\
        n_trials=10000 \\
        seed=42
    
    # Sensitivity (Hydra)
    python analytics/cli/cli_sensitivity_hydra.py \\
        config=scenarios/example.yaml \\
        output_dir=_out/sensitivity
    
    # Legacy sensitivity (DEPRECATED - argparse)
    python analytics/cli/cli_sensitivity.py scenarios/example.yaml

Imports:
    from analytics.cli.cli_monte_carlo_hydra import main
    from analytics.cli.cli_sensitivity_hydra import main

Framework Compliance:
    - GWTF R3: All Hydra-based (except deprecated cli_sensitivity.py)
    - GWTF CLI-03: JSON-first outputs
    - GWTF R24: Google-style docstrings
    - CASPER: Deterministic, traceable, reproducible

Migration:
    - Priority 2 (CLI Modules)
    - 3 files moved from analytics/ root
    - 3 backward compatibility shims created
    - Clean separation from core analytics logic

Author: Dutch Bay Wind Farm Team
Date: December 2025
Version: 1.0.0
"""

from __future__ import annotations

# Public API exports (main functions from CLI modules)
# Note: We don't export main functions here to avoid name conflicts.
# Users should import directly from the specific CLI module they need.

__all__ = [
    "cli_monte_carlo_hydra",
    "cli_sensitivity_hydra",
    "cli_sensitivity",  # Deprecated but maintained for compatibility
]
