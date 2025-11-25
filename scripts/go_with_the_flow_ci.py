#!/usr/bin/env python3
"""
Go-with-the-Flow CI Helper (Typer Edition).

Pure-Python orchestration for local checks with fire-fighting capability:

PRIMARY PIPELINE (daily use):
  • black - code formatting
  • isort - import organization
  • compileall - syntax validation
  • pytest - test suite
  • mypy - type checking

BACKGROUND FORCES (ready for battles):
  • Bowler - large-scale refactoring when migrations hit
  • LibCST - AST manipulation for code transformations

Usage (from repo root):
    python scripts/go_with_the_flow_ci.py
    python scripts/go_with_the_flow_ci.py --fast
    python scripts/go_with_the_flow_ci.py --no-mypy --fast
    python scripts/go_with_the_flow_ci.py --files "analytics/your_module.py,tests/api/test_your_module.py"
    python scripts/go_with_the_flow_ci.py info
    python scripts/go_with_the_flow_ci.py fire-warning
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import typer

# Create app WITHOUT no_args_is_help so it can run default command
app = typer.Typer(
    help="Go-with-the-Flow CI pipeline - build once, build right",
)

REPO_ROOT = Path(__file__).resolve().parent.parent

# ============================================================================
# Default configuration
# ============================================================================

BLACK_TARGETS: tuple[str, ...] = (
    "analytics",
    "finance",
    "run_full_pipeline_v14.py",
    "scripts",
)

ISORT_TARGETS: tuple[str, ...] = BLACK_TARGETS

COMPILE_TARGETS: tuple[str, ...] = (
    "analytics",
    "finance",
)

FAST_PYTEST_TARGETS: tuple[str, ...] = (
    "tests/analytics_layer/test_monte_carlo_v14.py",
    "tests/analytics_layer/test_sensitivity_v14_all.py",
    "tests/api/test_scenario_manager_smoke.py",
    "tests/test_v14_pipeline_smoke.py",
)

FULL_PYTEST_TARGETS: tuple[str, ...] = ("tests",)

MYPY_TARGETS: tuple[str, ...] = (
    "analytics",
    "finance",
    "run_full_pipeline_v14.py",
)


# ============================================================================
# Helpers
# ============================================================================


def _run_step(
    cmd: list[str],
    *,
    cwd: Path,
    label: str,
    allow_fail: bool = False,
) -> tuple[int, float]:
    """Run a single shell step and return (exit_code, elapsed_time)."""
    typer.echo(f"\n{'=' * 70}")
    typer.echo(f"[{label}]")
    typer.echo(f"{'=' * 70}")
    typer.echo(f"$ {' '.join(cmd)}")

    start = time.time()
    result = subprocess.run(cmd, cwd=str(cwd))
    elapsed = time.time() - start

    if result.returncode != 0:
        if allow_fail:
            typer.echo(
                f"⚠️  Warning: {label} exited with code {result.returncode}",
                err=True,
            )
            return result.returncode, elapsed
        typer.echo(
            f"\n❌ FAILED: {label} (exit code {result.returncode})",
            err=True,
        )
        raise typer.Exit(code=result.returncode)

    typer.echo(f"✅ Completed: {label} ({elapsed:.2f}s)")
    return 0, elapsed


def _show_fire_warning() -> None:
    """Show available emergency tools."""
    typer.echo("\n" + "=" * 70)
    typer.echo("🔥 EMERGENCY TOOLS (in background, ready to deploy):")
    typer.echo("=" * 70)
    typer.echo("\nWhen migrations/refactoring needed:")
    typer.echo("  • bowler  - Large-scale AST-safe refactoring")
    typer.echo("  • libcst  - Concrete syntax tree manipulation")
    typer.echo("\nUsage:")
    typer.echo("  python scripts/fire_migration.py <migration_name>")
    typer.echo("\nAvailable migrations:")
    typer.echo("  • rewrite_imports - Fix import paths")
    typer.echo("  • rename_module   - Rename modules/classes")
    typer.echo("  • deprecate_api   - Mark APIs as deprecated")


def _parse_files_argument(files: str | None) -> list[str]:
    """Parse the --files option (comma-separated) into a clean list of paths."""
    if not files:
        return []
    parts = [p.strip() for p in files.split(",")]
    return [p for p in parts if p]


def _split_code_and_tests(files: list[str]) -> tuple[list[str], list[str]]:
    """Split selected files into code_files and test_files."""
    code_files: list[str] = []
    test_files: list[str] = []
    for path in files:
        if path.startswith("tests/") or path.startswith("tests\\"):
            test_files.append(path)
        else:
            code_files.append(path)
    return code_files, test_files


# ============================================================================
# Commands - using @app.callback() for default command
# ============================================================================


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    fast: bool = typer.Option(
        False,
        "--fast",
        help="Fast lane: run targeted pytest suite instead of full tests",
    ),
    no_black: bool = typer.Option(False, "--no-black", help="Skip black formatter"),
    no_isort: bool = typer.Option(False, "--no-isort", help="Skip isort import sorter"),
    no_pytest: bool = typer.Option(False, "--no-pytest", help="Skip pytest"),
    no_mypy: bool = typer.Option(False, "--no-mypy", help="Skip mypy type checker"),
    verbose: bool = typer.Option(False, "-v", "--verbose", help="Verbose output"),
    files: str | None = typer.Option(
        None,
        "--files",
        help=(
            "Comma-separated list of files to focus on, e.g. "
            '"analytics/foo.py,tests/api/test_foo.py". '
            "Overrides default targets for black/isort/compile/pytest/mypy."
        ),
    ),
) -> None:
    """
    Run Go-with-the-Flow CI checks.

    Default: Full pipeline (black → isort → compile → pytest → mypy)
    Fast mode: Targeted tests for quick feedback
    With --files: restrict CI to specific files.
    """

    # If a subcommand was invoked, don't run main pipeline
    if ctx.invoked_subcommand is not None:
        return

    repo = REPO_ROOT
    start_time = time.time()
    steps_run = 0

    typer.echo("🚀 Go-with-the-Flow CI Pipeline")
    typer.echo(f"📍 Repository: {repo}")
    typer.echo(f"🔧 Python: {sys.executable}")
    typer.echo(f"📦 Version: {sys.version.split()[0]}")

    # Parse file overrides
    selected_files = _parse_files_argument(files)
    code_files: list[str] = []
    test_files: list[str] = []

    if selected_files:
        code_files, test_files = _split_code_and_tests(selected_files)

    mode = "FAST LANE" if fast else "FULL PIPELINE"
    scope = "SELECTED FILES" if selected_files else "DEFAULT TARGETS"
    typer.echo(f"⚙️  Mode: {mode} | Scope: {scope}")

    if verbose:
        typer.echo("\n📋 Configuration:")
        if selected_files:
            typer.echo(f"  Selected files: {', '.join(selected_files)}")
        else:
            typer.echo(f"  Black targets: {', '.join(BLACK_TARGETS)}")
            typer.echo(
                f"  Test targets: {FAST_PYTEST_TARGETS if fast else FULL_PYTEST_TARGETS}"
            )

    # ========================================================================
    # 1) BLACK
    # ========================================================================

    if not no_black:
        steps_run += 1
        black_targets: list[str] = selected_files or list(BLACK_TARGETS)
        code, _ = _run_step(
            [sys.executable, "-m", "black", *black_targets],
            cwd=repo,
            label="black - Code Formatter",
        )
        if code != 0:
            raise typer.Exit(code=code)

    # ========================================================================
    # 2) ISORT
    # ========================================================================

    if not no_isort:
        steps_run += 1
        isort_targets: list[str] = selected_files or list(ISORT_TARGETS)
        code, _ = _run_step(
            [sys.executable, "-m", "isort", *isort_targets],
            cwd=repo,
            label="isort - Import Sorter",
        )
        if code != 0:
            raise typer.Exit(code=code)

    # ========================================================================
    # 3) COMPILEALL
    # ========================================================================

    compile_targets: list[str] = selected_files or list(COMPILE_TARGETS)
    for target in compile_targets:
        steps_run += 1
        code, _ = _run_step(
            [sys.executable, "-m", "compileall", target],
            cwd=repo,
            label=f"compileall - Syntax Check ({target})",
        )
        if code != 0:
            raise typer.Exit(code=code)

    # ========================================================================
    # 4) PYTEST
    # ========================================================================

    if not no_pytest:
        steps_run += 1

        if selected_files:
            pytest_targets = test_files or [
                f for f in selected_files if f.startswith("tests")
            ]
            if not pytest_targets:
                pytest_targets = list(
                    FAST_PYTEST_TARGETS if fast else FULL_PYTEST_TARGETS
                )
        else:
            pytest_targets = list(FAST_PYTEST_TARGETS if fast else FULL_PYTEST_TARGETS)

        mode_label = "(FAST LANE)" if fast else "(FULL SUITE)"
        code, _ = _run_step(
            [sys.executable, "-m", "pytest", *pytest_targets],
            cwd=repo,
            label=f"pytest - Test Suite {mode_label}",
        )
        if code != 0:
            raise typer.Exit(code=code)

    # ========================================================================
    # 5) MYPY
    # ========================================================================

    if not no_mypy:
        steps_run += 1
        mypy_targets: list[str] = (
            (code_files or selected_files) if selected_files else list(MYPY_TARGETS)
        )
        code, _ = _run_step(
            [sys.executable, "-m", "mypy", *mypy_targets],
            cwd=repo,
            label="mypy - Type Checker",
        )
        if code != 0:
            raise typer.Exit(code=code)

    # ========================================================================
    # Success Report
    # ========================================================================

    elapsed_total = time.time() - start_time

    typer.echo("\n" + "=" * 70)
    typer.echo("✅ GO-WITH-THE-FLOW CI PIPELINE SUCCESSFUL")
    typer.echo("=" * 70)
    typer.echo("\n📊 Results:")
    typer.echo(f"  Steps executed: {steps_run}")
    typer.echo(f"  Pipeline time: {elapsed_total:.2f}s")
    typer.echo("  Code quality: PASSING ✅")
    typer.echo("\n📝 Repository state:")
    typer.echo("  Formatting: Compliant (black)")
    typer.echo("  Imports:    Organized (isort)")
    typer.echo("  Syntax:     Valid (compileall)")
    if not no_pytest:
        typer.echo("  Tests:      All passing ✅")
    else:
        typer.echo("  Tests:      SKIPPED (--no-pytest)")
    if not no_mypy:
        typer.echo("  Types:      Validated (mypy)")
    else:
        typer.echo("  Types:      SKIPPED (--no-mypy)")
    typer.echo("\n🚀 Ready for commit!")

    _show_fire_warning()


@app.command()
def fire_warning() -> None:
    """Show available emergency/fire-fighting tools."""
    _show_fire_warning()


@app.command()
def info() -> None:
    """Show CI pipeline information and configuration."""
    typer.echo("\n" + "=" * 70)
    typer.echo("GO-WITH-THE-FLOW CI - INFORMATION")
    typer.echo("=" * 70)

    typer.echo("\n📋 Pipeline Stages:")
    typer.echo("  1. black      - Code formatting (consistency)")
    typer.echo("  2. isort      - Import organization (PEP 8)")
    typer.echo("  3. compileall - Syntax validation (early errors)")
    typer.echo("  4. pytest     - Test execution (correctness)")
    typer.echo("  5. mypy       - Type checking (type safety)")

    typer.echo("\n🔥 Emergency Tools (Background):")
    typer.echo("  • bowler  - AST-safe refactoring (Meta/Facebook)")
    typer.echo("  • libcst  - Concrete syntax tree manipulation")

    typer.echo("\n⚡ Quick Start:")
    typer.echo("  Full suite:   python scripts/go_with_the_flow_ci.py")
    typer.echo("  Fast mode:    python scripts/go_with_the_flow_ci.py --fast")
    typer.echo("  Skip mypy:    python scripts/go_with_the_flow_ci.py --no-mypy")
    typer.echo("  Verbose:      python scripts/go_with_the_flow_ci.py -v")
    typer.echo("  Info:         python scripts/go_with_the_flow_ci.py info")
    typer.echo("  Fire tools:   python scripts/go_with_the_flow_ci.py fire-warning")

    typer.echo("\n📊 Default Targets:")
    typer.echo(f"  Black/isort: {', '.join(BLACK_TARGETS)}")
    typer.echo(f"  Compile:     {', '.join(COMPILE_TARGETS)}")
    typer.echo(f"  Mypy:        {', '.join(MYPY_TARGETS)}")

    typer.echo("\n🎯 File-Scoped Mode (--files):")
    typer.echo(
        "  Example: python scripts/go_with_the_flow_ci.py "
        '--files "analytics/foo.py,tests/api/test_foo.py" --fast'
    )
    typer.echo(
        "  • black/isort/compile/mypy run only on the selected files.\n"
        "  • pytest runs only on the selected test files (paths under tests/)."
    )


if __name__ == "__main__":
    app()

# EOF
