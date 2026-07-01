"""Lint tests enforcing the entrypoint CLI policy.

POLICY (the deliberate, principled split — read this before "making everything Hydra"):

    Hydra (@hydra.main) is MANDATORY for the canonical *pipeline* entrypoints — the ones
    that orchestrate the whole model off a composable config tree (run_full_pipeline_v14,
    run_scenario_analytics_v14, the sensitivity / Monte-Carlo CLIs). There, Hydra earns its
    keep: config composition (scenario + overrides), multirun sweeps, and structured config
    are exactly what these CLIs need. That set is ``CANONICAL_CLIS`` below.

    argparse is PERMITTED — by design, not as a gap — for the thin ``scripts/`` utilities
    that wrap a SINGLE library call ("read one --config YAML, call one function, print
    CSV/JSON": e.g. run_global_sensitivity, run_multi_tech_tornado, run_tornado_from_cli,
    run_epc_margin, run_fx_calibration). For those, Hydra is pure ceremony AND imposes
    intrusive runtime side-effects (``@hydra.main`` changes the working directory and writes
    ``outputs/`` + ``.hydra/`` dirs by default) that are actively wrong for a tool whose job
    is to emit a CSV. A blanket "ban argparse everywhere / convert all entrypoints to Hydra"
    was evaluated and REJECTED: it is high-blast-radius (≈10 scripts) ceremony against the
    Unix small-composable-tools grain, with zero compositional benefit for a thin wrapper.

    So "Hydra-only" here means Hydra-only *for the canonical pipeline CLIs* — NOT repo-wide.
    The CI gate scopes itself to ``CANONICAL_CLIS`` precisely because of this split.

These tests ensure:
1. Canonical pipeline CLIs use @hydra.main (GWTF R3)
2. No argparse in canonical pipeline CLIs (thin scripts/ utilities may use argparse)
3. Workflows use Hydra syntax (key=value)
4. No duplicate entrypoints (*_FIXED.py)
5. All canonical CLIs print JSON (GWTF CLI-03)

Run:
    pytest tests/lint/test_entrypoints_hydra_only.py -v

GWTF:
    - R3: Hydra-only policy enforcement
    - CLI-01: Hydra architecture validation
    - CLI-03: JSON output requirement
    - R25: Clean structure (no duplicates)

CESSPIT:
    - Policy-driven: Automated GWTF enforcement
    - Integration Testing: CI gate for compliance
    - Clean: Prevents technical debt accumulation

DSGCCCG:
    Dolphins Swim Gracefully Capturing Clean Current Groups
    Step 4 - Guard rails to prevent regression

Author: Dutch Bay Wind Farm Team
Date: December 2025
Version: 1.0.0
"""

from pathlib import Path

import pytest

# ═════════════════════════════════════════════════════════════════════════════
# Test Configuration
# ═════════════════════════════════════════════════════════════════════════════

# Canonical PIPELINE CLIs (MUST be Hydra — config composition earns its keep here).
# This is an intentional whitelist, not an arbitrary one: a CLI belongs here only if it
# orchestrates the model off a composable config tree. Thin scripts/ utilities that wrap a
# single library call are deliberately NOT listed and may use argparse (see module docstring).
CANONICAL_CLIS = [
    "run_full_pipeline_v14.py",
    "run_scenario_analytics_v14.py",
    "analytics/cli/cli_sensitivity_hydra.py",
    "analytics/cli/cli_monte_carlo_hydra.py",
]

# Legacy CLIs (MUST have DEPRECATED warning, allowed argparse until Sprint 18)
LEGACY_CLIS = [
    "analytics/cli/cli_sensitivity.py",
    "analytics/monte_carlo_v14.py",
]


# ═════════════════════════════════════════════════════════════════════════════
# Test 1: Canonical CLIs Use Hydra
# ═════════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("cli_path", CANONICAL_CLIS)
def test_canonical_cli_uses_hydra(cli_path):
    """Canonical CLIs must use @hydra.main decorator (GWTF R3).

    Args:
        cli_path: Path to CLI script (repo-relative)

    Asserts:
        - File exists
        - Contains @hydra.main decorator
        - Does NOT import argparse

    Rationale:
        GWTF R3 mandates Hydra-only for consistency and config management.
        Argparse creates incompatible CLI patterns.
    """
    path = Path(cli_path)
    assert path.exists(), (
        f"Canonical CLI not found: {cli_path}\n" f"Expected in: {path.resolve()}"
    )

    content = path.read_text()

    # Must have Hydra decorator
    assert "@hydra.main" in content, (
        f"{cli_path} must use @hydra.main decorator\n"
        f"GWTF R3: All canonical CLIs must be Hydra-based\n"
        f"Fix: Add @hydra.main(version_base='1.3', config_path='...', config_name='...')"
    )

    # Must NOT import argparse
    assert "import argparse" not in content, (
        f"{cli_path} must not use argparse (use Hydra overrides)\n"
        f"GWTF R3: No argparse in canonical CLIs\n"
        f"Fix: Remove 'import argparse' and use Hydra config overrides"
    )

    assert "from argparse" not in content, (
        f"{cli_path} must not use argparse (use Hydra overrides)\n"
        f"GWTF R3: No argparse in canonical CLIs\n"
        f"Fix: Remove 'from argparse import ...' and use Hydra config"
    )


# ═════════════════════════════════════════════════════════════════════════════
# Test 2: Legacy CLIs Marked Deprecated
# ═════════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("cli_path", LEGACY_CLIS)
def test_legacy_cli_marked_deprecated(cli_path):
    """Legacy CLIs must have DEPRECATED or LEGACY warning in docstring.

    Args:
        cli_path: Path to legacy CLI script

    Asserts:
        - If file exists, must contain DEPRECATED or LEGACY

    Rationale:
        Prevents confusion about which CLI is canonical.
        Warns users to migrate to Hydra wrappers.
    """
    path = Path(cli_path)
    if not path.exists():
        pytest.skip(f"Legacy CLI not found (may be removed): {cli_path}")

    content = path.read_text()

    # Must have deprecation warning
    has_deprecated = "DEPRECATED" in content or "LEGACY" in content
    assert has_deprecated, (
        f"{cli_path} must be marked DEPRECATED or LEGACY\n"
        f"This CLI uses argparse (not Hydra-compliant)\n"
        f"Fix: Add to module docstring:\n"
        f'  """DEPRECATED: Use analytics/cli_*_hydra.py instead..."""'
    )


# ═════════════════════════════════════════════════════════════════════════════
# Test 3: Workflows Use Hydra Style
# ═════════════════════════════════════════════════════════════════════════════


def test_workflows_use_hydra_style():
    """CI workflows must use Hydra overrides (key=value), not argparse flags.

    Asserts:
        - No --config in .github/workflows/*.yml
        - No --output-dir or --output_dir
        - No --output

    Rationale:
        Hydra CLIs don't accept argparse-style flags.
        CI must use key=value syntax for consistency.
    """
    workflows_dir = Path(".github/workflows")
    if not workflows_dir.exists():
        pytest.skip("No workflows directory")

    banned_patterns = [
        ("--config ", "Use config=... instead"),
        ("--output-dir ", "Use export_dir=... or output_dir=... instead"),
        ("--output_dir ", "Use export_dir=... or output_dir=... instead"),
        ("--output ", "Use output=... instead"),
    ]

    violations = []
    for workflow in workflows_dir.glob("*.yml"):
        content = workflow.read_text()

        for pattern, suggestion in banned_patterns:
            if pattern in content:
                # Find line number
                lines = content.split("\n")
                line_nums = [i + 1 for i, line in enumerate(lines) if pattern in line]
                violations.append((workflow.name, pattern, suggestion, line_nums))

    assert len(violations) == 0, (
        "Workflows contain argparse-style flags (not Hydra-compatible):\n"
        + "\n".join(
            [
                f"  {name} line {nums}: {pattern.strip()!r} - {sug}"
                for name, pattern, sug, nums in violations
            ]
        )
        + "\n\nGWTF R3: Use Hydra overrides (key=value) in all workflows"
    )


# ═════════════════════════════════════════════════════════════════════════════
# Test 4: No Duplicate Entrypoints
# ═════════════════════════════════════════════════════════════════════════════


def test_no_duplicate_entrypoints():
    """Ensure no duplicate entrypoints (FIXED copies, unexpected runners).

    Asserts:
        - No *_FIXED.py files
        - Only canonical run_*.py in repo root

    Rationale:
        Duplicates create confusion about canonical versions.
        CESSPIT Clean principle: one canonical version only.
    """
    # Check for FIXED copies
    fixed_files = list(Path(".").glob("*_FIXED.py"))
    fixed_files += list(Path("analytics").glob("*_FIXED.py"))

    assert len(fixed_files) == 0, (
        f"Found FIXED copies (should be deleted): {fixed_files}\n"
        f"CESSPIT Clean: Merge fixes to canonical versions and delete FIXED copies\n"
        f"Fix: git rm {' '.join(str(f) for f in fixed_files)}"
    )

    # Check repo root for unexpected runners
    allowed_runners = {"run_full_pipeline_v14.py", "run_scenario_analytics_v14.py"}
    root_runners = [
        f for f in Path(".").glob("run_*.py") if f.name not in allowed_runners
    ]

    assert len(root_runners) == 0, (
        f"Found unexpected runner scripts in repo root: {root_runners}\n"
        f"GWTF R25: Only canonical CLIs in repo root\n"
        f"Fix: Move to scripts/ or delete if obsolete"
    )


# ═════════════════════════════════════════════════════════════════════════════
# Test 5: Canonical CLIs Print JSON
# ═════════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("cli_path", CANONICAL_CLIS)
def test_canonical_clis_print_json(cli_path):
    """Canonical CLIs must print structured JSON (GWTF CLI-03).

    Args:
        cli_path: Path to CLI script

    Asserts:
        - Imports json module
        - Uses json.dumps() for output

    Rationale:
        CLI-03 mandates JSON-first outputs for CI/tooling integration.
        Structured output enables programmatic consumption.
    """
    path = Path(cli_path)
    if not path.exists():
        pytest.skip(f"CLI not found: {cli_path}")

    content = path.read_text()

    # Must import json
    assert "import json" in content, (
        f"{cli_path} must import json for structured output\n"
        f"GWTF CLI-03: All CLIs must print JSON\n"
        f"Fix: Add 'import json' and use json.dumps() for output"
    )

    # Must use json.dumps
    assert "json.dumps" in content, (
        f"{cli_path} must use json.dumps for CLI-03 compliance\n"
        f"GWTF CLI-03: Output must be structured JSON\n"
        f"Fix: Use print(json.dumps(result, indent=2))"
    )


# ═════════════════════════════════════════════════════════════════════════════
# Test Documentation
# ═════════════════════════════════════════════════════════════════════════════


def test_documentation():
    """Document the canonical CLI list for reference.

    This test always passes but prints useful information.
    """
    print("\n" + "=" * 80)
    print("CANONICAL CLIS (Hydra-only):")
    for cli in CANONICAL_CLIS:
        status = "✅" if Path(cli).exists() else "❌"
        print(f"  {status} {cli}")

    print("\nLEGACY CLIS (Deprecated):")
    for cli in LEGACY_CLIS:
        status = "⚠️" if Path(cli).exists() else "✅ (removed)"
        print(f"  {status} {cli}")

    print("\nGWTF POLICY:")
    print("  - R3: All canonical CLIs must use @hydra.main")
    print("  - CLI-01: Hydra architecture required")
    print("  - CLI-03: JSON-first outputs")
    print("  - R25: Clean structure (no duplicates)")
    print("=" * 80)

    assert True, "Documentation printed"
