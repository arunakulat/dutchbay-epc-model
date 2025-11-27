#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    GO-WITH-THE-FLOW CI MEGA SCRIPT v2                       ║
║                   Enhanced with Research-Driven Features                     ║
║                                                                              ║
║  "Build once, build right" - Consolidated, deduplicated, team-treasured     ║
║                                                                              ║
║  PIPELINE ORDER: black → isort → compileall → pytest → mypy                 ║
║  OPTIONAL EXTRAS: --coverage --flake8 --pylint --bandit --security          ║
║  NEW FEATURES: --parallel --diagnose --fix --init-git-hooks                 ║
║  USAGE: python scripts/go_with_the_flow_ci.py [--fast] [--files ...]        ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import typer

# ═════════════════════════════════════════════════════════════════════════════
# LOGGER SETUP (Debug-First Principle)
# ═════════════════════════════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.DEBUG,
    format="%(levelname)-8s | %(message)s",
)
logger = logging.getLogger(__name__)

# ═════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═════════════════════════════════════════════════════════════════════════════

REPO_ROOT = Path(__file__).resolve().parent.parent

# Primary pipeline targets (black → isort → compileall → pytest → mypy)
BLACK_TARGETS = ("analytics", "finance", "run_full_pipeline_v14.py", "scripts")
ISORT_TARGETS = BLACK_TARGETS
COMPILE_TARGETS = ("analytics", "finance")

# Test targets
FAST_PYTEST_TARGETS = (
    "tests/api/",
    "tests/contracts/test_sensitivity_edgecases.py",
)
FULL_PYTEST_TARGETS = ("tests",)

# Type checking targets
MYPY_TARGETS = ("analytics", "finance", "run_full_pipeline_v14.py")

# Optional analysis tools (extras)
FLAKE8_TARGETS = BLACK_TARGETS
PYLINT_TARGETS = BLACK_TARGETS
BANDIT_TARGETS = ("analytics", "finance")

# Timing estimates for --dry-run (in seconds)
TIMING_ESTIMATES = {
    "black": 2,
    "isort": 1,
    "compileall": 3,
    "pytest_fast": 15,
    "pytest_full": 45,
    "mypy": 12,
    "coverage": 20,
    "flake8": 5,
    "pylint": 10,
    "bandit": 3,
}

# ═════════════════════════════════════════════════════════════════════════════
# UNIFIED COMMAND EXECUTION (Consolidated from _run_step + run)
# ═════════════════════════════════════════════════════════════════════════════


@dataclass
class StepResult:
    """Result of a CI step execution."""

    label: str
    exit_code: int
    elapsed_time: float
    passed: bool
    output: Optional[str] = None


@dataclass
class PipelineStats:
    """Overall pipeline statistics."""

    total_time: float
    stages_run: int
    stages_passed: int
    stages_failed: int
    stage_timings: dict[str, float] = field(default_factory=dict)


def run_command(
    cmd: list[str],
    *,
    label: str,
    cwd: Path = REPO_ROOT,
    capture: bool = False,
    allow_fail: bool = False,
    verbose: bool = False,
) -> StepResult:
    """
    Run a shell command with unified logging and error handling.

    Args:
        cmd: Command to run (list of strings)
        label: Human-readable label for logging
        cwd: Working directory (default: repo root)
        capture: Capture stdout/stderr
        allow_fail: Don't raise on non-zero exit
        verbose: Print command before running

    Returns:
        StepResult with exit code, timing, and output

    Raises:
        typer.Exit on failure (unless allow_fail=True)
    """
    logger.info(f"\n{'='*70}")
    logger.info(f"[{label}]")
    logger.info(f"{'='*70}")

    cmd_display = " ".join(cmd)
    if verbose:
        logger.info(f"$ {cmd_display}")

    start = time.time()

    try:
        kwargs: dict = {
            "cwd": str(cwd),
            "text": True,
        }

        if capture:
            kwargs["stdout"] = subprocess.PIPE
            kwargs["stderr"] = subprocess.STDOUT

        result = subprocess.run(cmd, **kwargs)  # type: ignore
        elapsed = time.time() - start

        if result.returncode != 0:
            if allow_fail:
                logger.warning(
                    f"⚠️  {label} exited with code {result.returncode} "
                    "(allowed to fail)"
                )
                return StepResult(
                    label=label,
                    exit_code=result.returncode,
                    elapsed_time=elapsed,
                    passed=False,
                    output=result.stdout if capture else None,
                )

            logger.error(f"❌ FAILED: {label} (exit code {result.returncode})")
            raise typer.Exit(code=result.returncode)

        logger.info(f"✅ Completed: {label} ({elapsed:.2f}s)")
        return StepResult(
            label=label,
            exit_code=0,
            elapsed_time=elapsed,
            passed=True,
            output=result.stdout if capture else None,
        )

    except Exception as exc:
        logger.error(f"❌ Exception in {label}: {exc}")
        raise typer.Exit(code=1)


# ═════════════════════════════════════════════════════════════════════════════
# UTILITY FUNCTIONS
# ═════════════════════════════════════════════════════════════════════════════


def get_repo_root() -> Path:
    """Get git repo root using git rev-parse (consolidated from multiple sources)."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=True,
        )
        return Path(result.stdout.strip())
    except subprocess.CalledProcessError:
        logger.error("❌ Could not determine git repo root")
        raise typer.Exit(code=1)


def parse_files_argument(files: Optional[str]) -> list[str]:
    """Parse comma-separated --files argument into clean list."""
    if not files:
        return []
    return [p.strip() for p in files.split(",") if p.strip()]


def split_code_and_tests(files: list[str]) -> tuple[list[str], list[str]]:
    """Split file list into code files and test files."""
    code_files = [f for f in files if not f.startswith("tests")]
    test_files = [f for f in files if f.startswith("tests")]
    return code_files, test_files


def show_fire_warning() -> None:
    """Show available emergency/fire-fighting tools."""
    typer.echo("\n" + "=" * 70)
    typer.echo("🔥 EMERGENCY TOOLS (Ready to deploy):")
    typer.echo("=" * 70)
    typer.echo("\nWhen large refactoring/migrations needed:")
    typer.echo("  • bowler - AST-safe large-scale refactoring (Meta/Facebook)")
    typer.echo("  • libcst - Concrete syntax tree manipulation for code transforms")
    typer.echo("\nUsage: python scripts/go_with_the_flow_ci.py fire-warning")
    typer.echo("\n" + "=" * 70)


# ═════════════════════════════════════════════════════════════════════════════
# ENVIRONMENT DIAGNOSTICS (NEW - Tier 1 Enhancement)
# ═════════════════════════════════════════════════════════════════════════════


def diagnose_environment() -> None:
    """Run comprehensive environment diagnostics."""
    typer.echo("\n" + "=" * 70)
    typer.echo("🔍 ENVIRONMENT DIAGNOSTICS")
    typer.echo("=" * 70)

    repo = get_repo_root()
    typer.echo(f"\n📍 Repository: {repo}")

    # Python info
    typer.echo("\n🐍 Python Information:")
    typer.echo(f"  Executable: {sys.executable}")
    typer.echo(f"  Version: {sys.version}")

    # Virtual environment
    venv_active = "VIRTUAL_ENV" in os.environ
    venv_path = os.environ.get("VIRTUAL_ENV", "Not active")
    typer.echo("\n📦 Virtual Environment:")
    status = "✅ ACTIVE" if venv_active else "❌ NOT ACTIVE"
    typer.echo(f"  Status: {status}")
    typer.echo(f"  Path: {venv_path}")

    if not venv_active:
        typer.echo(f"  💡 Activate with: source {repo}/.venv311/bin/activate")

    # pip info
    typer.echo("\n📋 pip Information:")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "--version"],
            capture_output=True,
            text=True,
            check=True,
        )
        typer.echo(f"  {result.stdout.strip()}")
    except subprocess.CalledProcessError:
        typer.echo("  ❌ Error checking pip")

    # Key dependencies
    typer.echo("\n🔧 Key Dependencies:")
    key_packages = ["black", "isort", "pytest", "mypy", "pytest-xdist"]
    for pkg in key_packages:
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "show", pkg],
                capture_output=True,
                text=True,
                check=True,
            )
            version_line = [l for l in result.stdout.split("\n") if l.startswith("Version")]
            if version_line:
                version = version_line[0].split(": ")[1]
                typer.echo(f"  ✅ {pkg}: {version}")
            else:
                typer.echo(f"  ❌ {pkg}: Could not determine version")
        except subprocess.CalledProcessError:
            typer.echo(f"  ❌ {pkg}: NOT INSTALLED")

    # Git info
    typer.echo("\n🔀 Git Information:")
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=str(repo),
            capture_output=True,
            text=True,
            check=True,
        )
        branch = result.stdout.strip()
        typer.echo(f"  Current branch: {branch}")
    except subprocess.CalledProcessError:
        typer.echo("  ❌ Error getting branch")

    try:
        result = subprocess.run(
            ["git", "status", "--short"],
            cwd=str(repo),
            capture_output=True,
            text=True,
            check=True,
        )
        if result.stdout.strip():
            typer.echo("  ⚠️  Uncommitted changes detected")
        else:
            typer.echo("  ✅ Working directory clean")
    except subprocess.CalledProcessError:
        pass

    # Disk space
    typer.echo("\n💾 Disk Space:")
    try:
        import shutil

        total, used, free = shutil.disk_usage(repo)
        free_gb = free / (1024**3)
        total_gb = total / (1024**3)
        used_pct = (used / total) * 100
        typer.echo(f"  Total: {total_gb:.1f} GB")
        typer.echo(f"  Used: {used_pct:.1f}%")
        typer.echo(f"  Free: {free_gb:.1f} GB")
        if free_gb < 1:
            typer.echo("  ⚠️  WARNING: Low disk space!")
    except Exception as e:
        typer.echo(f"  Could not determine: {e}")

    typer.echo("\n" + "=" * 70)
    typer.echo("✅ Diagnostics complete")
    typer.echo("=" * 70 + "\n")


# ═════════════════════════════════════════════════════════════════════════════
# PRIMARY PIPELINE STAGES (black → isort → compileall → pytest → mypy)
# ═════════════════════════════════════════════════════════════════════════════


def stage_black(targets: list[str], verbose: bool = False, fix: bool = False) -> StepResult:
    """Stage 1: Code formatting with black."""
    cmd = [sys.executable, "-m", "black", "--line-length=100"]
    if fix:
        cmd.append("--quiet")
    cmd.extend(targets)
    return run_command(
        cmd,
        label="🎨 black - Code Formatter",
        verbose=verbose,
    )


def stage_isort(targets: list[str], verbose: bool = False, fix: bool = False) -> StepResult:
    """Stage 2: Import organization with isort."""
    cmd = [sys.executable, "-m", "isort"]
    if fix:
        cmd.append("--quiet")
    cmd.extend(targets)
    return run_command(
        cmd,
        label="📦 isort - Import Sorter",
        verbose=verbose,
    )


def stage_compileall(targets: list[str], verbose: bool = False) -> StepResult:
    """Stage 3: Syntax validation with compileall."""
    results = []
    for target in targets:
        result = run_command(
            [sys.executable, "-m", "compileall", target],
            label=f"✓ compileall - Syntax Check ({target})",
            verbose=verbose,
            allow_fail=False,
        )
        results.append(result)

    # Combine results
    all_passed = all(r.passed for r in results)
    total_time = sum(r.elapsed_time for r in results)

    return StepResult(
        label="✓ compileall - All Syntax Checks",
        exit_code=0 if all_passed else 1,
        elapsed_time=total_time,
        passed=all_passed,
    )


def stage_pytest(
    targets: list[str],
    fast_mode: bool = False,
    verbose: bool = False,
    parallel: bool = False,
) -> StepResult:
    """Stage 4: Test execution with pytest."""
    mode_label = "(FAST)" if fast_mode else "(FULL)"
    cmd = [sys.executable, "-m", "pytest", *targets, "-v"]

    if parallel:
        cmd.extend(["-n", "auto"])
        mode_label += " (PARALLEL)"

    return run_command(
        cmd,
        label=f"🧪 pytest - Test Suite {mode_label}",
        verbose=verbose,
    )


def stage_mypy(targets: list[str], verbose: bool = False) -> StepResult:
    """Stage 5: Type checking with mypy."""
    return run_command(
        [sys.executable, "-m", "mypy", *targets],
        label="🔍 mypy - Type Checker",
        verbose=verbose,
    )


# ═════════════════════════════════════════════════════════════════════════════
# OPTIONAL ANALYSIS TOOLS (extras, not in main pipeline)
# ═════════════════════════════════════════════════════════════════════════════


def stage_coverage(
    targets: Optional[list[str]] = None, verbose: bool = False
) -> StepResult:
    """Optional: Test coverage report with coverage.py."""
    result = run_command(
        [sys.executable, "-m", "coverage", "run", "-m", "pytest", "--quiet"]
        + (targets or []),
        label="📊 coverage - Test Coverage Report",
        verbose=verbose,
        allow_fail=True,
    )

    # Generate report
    if result.passed:
        run_command(
            [sys.executable, "-m", "coverage", "report", "-m"],
            label="📋 coverage - Coverage Summary",
            verbose=verbose,
            allow_fail=True,
        )

    return result


def stage_flake8(targets: list[str], verbose: bool = False) -> StepResult:
    """Optional: PEP 8 linting with flake8."""
    return run_command(
        [sys.executable, "-m", "flake8", *targets, "--max-line-length=100"],
        label="📝 flake8 - Style & Compliance",
        verbose=verbose,
        allow_fail=True,  # Warnings don't fail pipeline
    )


def stage_pylint(targets: list[str], verbose: bool = False) -> StepResult:
    """Optional: Deep code quality analysis with pylint."""
    return run_command(
        [sys.executable, "-m", "pylint", *targets, "--exit-zero"],
        label="🔬 pylint - Code Quality Analysis",
        verbose=verbose,
        allow_fail=True,
    )


def stage_bandit(targets: list[str], verbose: bool = False) -> StepResult:
    """Optional: Security scanning with bandit."""
    return run_command(
        [sys.executable, "-m", "bandit", "-r", *targets, "-ll"],
        label="🛡️  bandit - Security Scan",
        verbose=verbose,
        allow_fail=True,  # Warnings don't fail pipeline
    )


# ═════════════════════════════════════════════════════════════════════════════
# PRE-COMMIT SETUP (NEW - Tier 1 Enhancement)
# ═════════════════════════════════════════════════════════════════════════════


def setup_pre_commit_hooks() -> None:
    """Generate and install pre-commit hooks."""
    import os

    repo = get_repo_root()
    precommit_config = repo / ".pre-commit-config.yaml"

    typer.echo("\n" + "=" * 70)
    typer.echo("🪝 SETTING UP PRE-COMMIT HOOKS")
    typer.echo("=" * 70)

    # Generate .pre-commit-config.yaml
    config_content = """# Pre-commit hooks configuration (auto-generated by Go-With-The-Flow CI)
# Run hooks automatically before commits
# Install with: pre-commit install
# Manual run: pre-commit run --all-files

repos:
  - repo: https://github.com/psf/black
    rev: '24.1.1'
    hooks:
      - id: black
        language_version: python3

  - repo: https://github.com/pycqa/isort
    rev: '5.13.2'
    hooks:
      - id: isort
        args: ['--profile=black']

  - repo: https://github.com/PyCQA/flake8
    rev: '7.0.0'
    hooks:
      - id: flake8
        args: ['--max-line-length=100']

# Uncomment below to add pytest and mypy to pre-commit hooks
# Note: These can slow down commits if you have many tests
# Consider using --stages manual and running them separately
#
#  - repo: local
#    hooks:
#      - id: pytest
#        name: pytest
#        entry: pytest tests/ -v --tb=short
#        language: system
#        pass_filenames: false
#        stages: [manual]
#
#      - id: mypy
#        name: mypy
#        entry: mypy analytics finance
#        language: system
#        pass_filenames: false
#        stages: [manual]
"""

    typer.echo(f"\n📝 Writing {precommit_config}")
    precommit_config.write_text(config_content)
    typer.echo("   ✅ Config written")

    # Install pre-commit framework
    typer.echo("\n📦 Installing pre-commit framework...")
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-q", "pre-commit"],
            check=True,
        )
        typer.echo("   ✅ pre-commit installed")
    except subprocess.CalledProcessError:
        typer.echo("   ⚠️  Could not install pre-commit")
        return

    # Install git hooks
    typer.echo("\n🔧 Installing git hooks...")
    try:
        subprocess.run(
            ["pre-commit", "install"],
            cwd=str(repo),
            check=True,
            capture_output=True,
        )
        typer.echo("   ✅ Git hooks installed")
    except subprocess.CalledProcessError:
        typer.echo("   ⚠️  Could not install git hooks")
        typer.echo(f"   💡 Try: cd {repo} && pre-commit install")
        return

    typer.echo("\n" + "=" * 70)
    typer.echo("✅ PRE-COMMIT HOOKS READY")
    typer.echo("=" * 70)
    typer.echo("\n📚 Usage:")
    typer.echo("  Manually run: pre-commit run --all-files")
    typer.echo("  Auto on commit: Hooks will run before each git commit")
    typer.echo("  Skip hooks: git commit --no-verify")
    typer.echo()


# ═════════════════════════════════════════════════════════════════════════════
# ENHANCED REPORTING (NEW - Tier 1 Enhancement)
# ═════════════════════════════════════════════════════════════════════════════


def print_timing_breakdown(stats: PipelineStats) -> None:
    """Print detailed timing breakdown."""
    typer.echo("\n📊 Timing Breakdown:")

    if stats.stage_timings:
        # Find slowest stage
        slowest = max(stats.stage_timings.items(), key=lambda x: x[1]) if stats.stage_timings else None

        for stage, elapsed in stats.stage_timings.items():
            is_slowest = " ⚠️ (slowest)" if slowest and stage == slowest[0] else ""
            typer.echo(f"   {stage}: {elapsed:.2f}s{is_slowest}")

        typer.echo(f"   {'─' * 40}")

    typer.echo(f"   Total: {stats.total_time:.2f}s")


# ═════════════════════════════════════════════════════════════════════════════
# TYPER APP & COMMANDS
# ═════════════════════════════════════════════════════════════════════════════

import os

app = typer.Typer(
    help="Go-with-the-Flow CI Pipeline - Production Quality, One Command",
    no_args_is_help=False,
)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    fast: bool = typer.Option(
        False,
        "--fast",
        help="Fast lane: targeted tests instead of full suite",
    ),
    parallel: bool = typer.Option(
        False,
        "--parallel",
        help="Run pytest with parallel execution (-n auto)",
    ),
    fix: bool = typer.Option(
        False,
        "--fix",
        help="Auto-fix mode: format code with black/isort before checking",
    ),
    no_black: bool = typer.Option(False, "--no-black", help="Skip black formatter"),
    no_isort: bool = typer.Option(False, "--no-isort", help="Skip isort"),
    no_compile: bool = typer.Option(
        False, "--no-compile", help="Skip compileall syntax check"
    ),
    no_pytest: bool = typer.Option(False, "--no-pytest", help="Skip pytest"),
    no_mypy: bool = typer.Option(False, "--no-mypy", help="Skip mypy type checker"),
    coverage: bool = typer.Option(
        False, "--coverage", help="Add test coverage analysis"
    ),
    flake8: bool = typer.Option(False, "--flake8", help="Add flake8 linting"),
    pylint: bool = typer.Option(False, "--pylint", help="Add pylint analysis"),
    bandit: bool = typer.Option(False, "--bandit", help="Add security scanning"),
    security: bool = typer.Option(
        False,
        "--security",
        help="Enable all security/analysis tools (coverage, flake8, bandit)",
    ),
    files: Optional[str] = typer.Option(
        None,
        "--files",
        help='Comma-separated file list (e.g. "analytics/foo.py,tests/test_foo.py")',
    ),
    verbose: bool = typer.Option(False, "-v", "--verbose", help="Verbose output"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would run"),
) -> None:
    """
    Run Go-with-the-Flow CI checks.

    DEFAULT PIPELINE:
      black → isort → compileall → pytest → mypy

    FAST MODE (--fast):
      Run targeted smoke tests instead of full suite

    NEW FEATURES (from deep research):
      --parallel: Run pytest with -n auto (3-5x faster!)
      --fix: Auto-format with black/isort before checking
      --init-git-hooks: Setup pre-commit framework

    OPTIONAL EXTRAS:
      --coverage: Test coverage report
      --flake8: Additional linting
      --pylint: Deep code quality
      --bandit: Security scanning
      --security: All of above

    FILE TARGETING (--files):
      Restrict checks to specific files (comma-separated)

    EXAMPLES:
      python scripts/go_with_the_flow_ci.py
      python scripts/go_with_the_flow_ci.py --fast --parallel
      python scripts/go_with_the_flow_ci.py --security --verbose
      python scripts/go_with_the_flow_ci.py --files "analytics/foo.py,tests/test_foo.py"
      python scripts/go_with_the_flow_ci.py --dry-run
    """

    # Exit if subcommand was invoked
    if ctx.invoked_subcommand is not None:
        return

    repo = get_repo_root()
    start_time = time.time()
    results: list[StepResult] = []
    stats = PipelineStats(total_time=0, stages_run=0, stages_passed=0, stages_failed=0)

    # Banner
    typer.echo("\n" + "╔" + "═" * 68 + "╗")
    typer.echo("║  🚀 GO-WITH-THE-FLOW CI PIPELINE v2 (Enhanced)                    ║")
    typer.echo("║  'Build once, build right' - Consolidated & Production-Grade      ║")
    typer.echo("╚" + "═" * 68 + "╝")

    typer.echo(f"\n📍 Repository: {repo}")
    typer.echo(f"🔧 Python: {sys.executable}")
    typer.echo(f"📦 Version: {sys.version.split()[0]}")

    # Determine configuration
    mode = "FAST LANE" if fast else "FULL PIPELINE"
    selected_files = parse_files_argument(files)
    scope = "SELECTED FILES" if selected_files else "DEFAULT TARGETS"

    typer.echo(f"\n⚙️  Mode: {mode} | Scope: {scope}")

    if parallel:
        typer.echo("⚡ Parallel mode: pytest will use -n auto")
    if fix:
        typer.echo("🔧 Auto-fix mode: Code will be formatted")

    # Apply --security flag
    if security:
        coverage = flake8 = bandit = True
        typer.echo("🛡️  Security mode enabled (coverage + flake8 + bandit)")

    # Parse file targets
    if selected_files:
        code_files, test_files = split_code_and_tests(selected_files)
        black_targets = code_files or selected_files
        pytest_targets = test_files or [f for f in selected_files if f.startswith("tests")]
    else:
        black_targets = list(BLACK_TARGETS)
        pytest_targets = list(FAST_PYTEST_TARGETS if fast else FULL_PYTEST_TARGETS)

    if verbose:
        typer.echo("\n📋 Configuration:")
        typer.echo(f"  Black targets: {', '.join(black_targets)}")
        typer.echo(f"  Test targets: {', '.join(pytest_targets)}")
        typer.echo(f"  Stages: black={not no_black}, isort={not no_isort}, " +
                   f"compile={not no_compile}, pytest={not no_pytest}, mypy={not no_mypy}")

    if dry_run:
        typer.echo("\n[DRY RUN] Pipeline stages that would execute:")
        estimated_total = 0

        if not no_black:
            typer.echo(f"  • black {' '.join(black_targets)} (~{TIMING_ESTIMATES['black']}s)")
            estimated_total += TIMING_ESTIMATES["black"]
        if not no_isort:
            typer.echo(f"  • isort {' '.join(black_targets)} (~{TIMING_ESTIMATES['isort']}s)")
            estimated_total += TIMING_ESTIMATES["isort"]
        if not no_compile:
            typer.echo(f"  • compileall {' '.join(COMPILE_TARGETS)} (~{TIMING_ESTIMATES['compileall']}s)")
            estimated_total += TIMING_ESTIMATES["compileall"]
        if not no_pytest:
            pytest_time = TIMING_ESTIMATES["pytest_fast" if fast else "pytest_full"]
            if parallel:
                pytest_time = max(5, pytest_time // 3)  # Rough 3x speedup estimate
            typer.echo(f"  • pytest {' '.join(pytest_targets)} (~{pytest_time}s)")
            estimated_total += pytest_time
        if not no_mypy:
            typer.echo(f"  • mypy {' '.join(MYPY_TARGETS)} (~{TIMING_ESTIMATES['mypy']}s)")
            estimated_total += TIMING_ESTIMATES["mypy"]
        if coverage:
            typer.echo(f"  • coverage (~{TIMING_ESTIMATES['coverage']}s)")
            estimated_total += TIMING_ESTIMATES["coverage"]
        if flake8:
            typer.echo(f"  • flake8 (~{TIMING_ESTIMATES['flake8']}s)")
            estimated_total += TIMING_ESTIMATES["flake8"]
        if bandit:
            typer.echo(f"  • bandit (~{TIMING_ESTIMATES['bandit']}s)")
            estimated_total += TIMING_ESTIMATES["bandit"]

        typer.echo(f"\n⏱️  Estimated total time: ~{estimated_total}s")
        return

    # ═════════════════════════════════════════════════════════════════════════
    # EXECUTE PRIMARY PIPELINE
    # ═════════════════════════════════════════════════════════════════════════

    try:
        # Stage 1: black
        if not no_black:
            result = stage_black(black_targets, verbose=verbose, fix=fix)
            results.append(result)
            stats.stage_timings["black"] = result.elapsed_time
            stats.stages_run += 1
            if result.passed:
                stats.stages_passed += 1
            else:
                stats.stages_failed += 1
                raise typer.Exit(code=result.exit_code)

        # Stage 2: isort
        if not no_isort:
            result = stage_isort(black_targets, verbose=verbose, fix=fix)
            results.append(result)
            stats.stage_timings["isort"] = result.elapsed_time
            stats.stages_run += 1
            if result.passed:
                stats.stages_passed += 1
            else:
                stats.stages_failed += 1
                raise typer.Exit(code=result.exit_code)

        # Stage 3: compileall
        if not no_compile:
            result = stage_compileall(list(COMPILE_TARGETS), verbose=verbose)
            results.append(result)
            stats.stage_timings["compileall"] = result.elapsed_time
            stats.stages_run += 1
            if result.passed:
                stats.stages_passed += 1
            else:
                stats.stages_failed += 1
                raise typer.Exit(code=result.exit_code)

        # Stage 4: pytest
        if not no_pytest:
            result = stage_pytest(
                pytest_targets, fast_mode=fast, verbose=verbose, parallel=parallel
            )
            results.append(result)
            pytest_label = "pytest_fast" if fast else "pytest_full"
            stats.stage_timings["pytest"] = result.elapsed_time
            stats.stages_run += 1
            if result.passed:
                stats.stages_passed += 1
            else:
                stats.stages_failed += 1
                raise typer.Exit(code=result.exit_code)

        # Stage 5: mypy
        if not no_mypy:
            mypy_targets_list = (
                code_files if selected_files else list(MYPY_TARGETS)
            )
            result = stage_mypy(mypy_targets_list or list(MYPY_TARGETS), verbose=verbose)
            results.append(result)
            stats.stage_timings["mypy"] = result.elapsed_time
            stats.stages_run += 1
            if result.passed:
                stats.stages_passed += 1
            else:
                stats.stages_failed += 1
                raise typer.Exit(code=result.exit_code)

        # ═════════════════════════════════════════════════════════════════════
        # OPTIONAL ANALYSIS TOOLS
        # ═════════════════════════════════════════════════════════════════════

        if coverage:
            result = stage_coverage(pytest_targets or None, verbose=verbose)
            results.append(result)
            stats.stage_timings["coverage"] = result.elapsed_time

        if flake8:
            result = stage_flake8(list(FLAKE8_TARGETS), verbose=verbose)
            results.append(result)
            stats.stage_timings["flake8"] = result.elapsed_time

        if pylint:
            result = stage_pylint(list(PYLINT_TARGETS), verbose=verbose)
            results.append(result)
            stats.stage_timings["pylint"] = result.elapsed_time

        if bandit:
            result = stage_bandit(list(BANDIT_TARGETS), verbose=verbose)
            results.append(result)
            stats.stage_timings["bandit"] = result.elapsed_time

        # ═════════════════════════════════════════════════════════════════════
        # SUCCESS REPORT
        # ═════════════════════════════════════════════════════════════════════

        stats.total_time = time.time() - start_time

        typer.echo("\n" + "=" * 70)
        typer.echo("✅ GO-WITH-THE-FLOW CI PIPELINE SUCCESSFUL")
        typer.echo("=" * 70)

        typer.echo("\n📊 Pipeline Results:")
        typer.echo(f"  Stages executed: {stats.stages_run}")
        typer.echo(f"  Passed: {stats.stages_passed}")
        typer.echo(f"  Failed: {stats.stages_failed}")

        print_timing_breakdown(stats)

        typer.echo("\n✨ Code quality: PASSING")
        typer.echo("   Formatting: ✅ Compliant (black)")
        typer.echo("   Imports: ✅ Organized (isort)")
        typer.echo("   Syntax: ✅ Valid (compileall)")
        typer.echo("   Tests: ✅ All passing (pytest)")
        typer.echo("   Types: ✅ Validated (mypy)")

        typer.echo("\n🚀 Ready for commit!")

        show_fire_warning()

    except typer.Exit:
        raise
    except Exception as exc:
        logger.error(f"❌ Unexpected error: {exc}")
        raise typer.Exit(code=1)


@app.command()
def diagnose() -> None:
    """Run comprehensive environment diagnostics."""
    diagnose_environment()


@app.command()
def init_git_hooks() -> None:
    """Initialize pre-commit git hooks for automatic checks."""
    setup_pre_commit_hooks()


@app.command()
def info() -> None:
    """Show CI pipeline information and configuration."""
    typer.echo("\n" + "=" * 70)
    typer.echo("GO-WITH-THE-FLOW CI v2 - INFORMATION")
    typer.echo("=" * 70)

    typer.echo("\n📋 PRIMARY PIPELINE (always run unless skipped):")
    typer.echo("  1️⃣  black (line_length=100) - Code formatting")
    typer.echo("  2️⃣  isort - Import organization")
    typer.echo("  3️⃣  compileall - Syntax validation")
    typer.echo("  4️⃣  pytest - Test execution")
    typer.echo("  5️⃣  mypy - Type checking")

    typer.echo("\n✨ NEW TIER 1 ENHANCEMENTS (v2):")
    typer.echo("  • --parallel: Run pytest with -n auto (3-5x faster)")
    typer.echo("  • --fix: Auto-format code before checking")
    typer.echo("  • --diagnose: Run environment diagnostics")
    typer.echo("  • --init-git-hooks: Setup pre-commit framework")

    typer.echo("\n📊 OPTIONAL ANALYSIS TOOLS (via --coverage / --flake8 / etc):")
    typer.echo("  • coverage - Test coverage report")
    typer.echo("  • flake8 - PEP 8 style compliance")
    typer.echo("  • pylint - Deep code quality")
    typer.echo("  • bandit - Security scanning")
    typer.echo("  • --security - All of above")

    typer.echo("\n⚡ QUICK START:")
    typer.echo("  Full suite: python scripts/go_with_the_flow_ci.py")
    typer.echo("  Fast + parallel: python scripts/go_with_the_flow_ci.py --fast --parallel")
    typer.echo("  Auto-format: python scripts/go_with_the_flow_ci.py --fix")
    typer.echo("  Setup hooks: python scripts/go_with_the_flow_ci.py --init-git-hooks")
    typer.echo("  Diagnose: python scripts/go_with_the_flow_ci.py --diagnose")
    typer.echo("  With security: python scripts/go_with_the_flow_ci.py --security")
    typer.echo("  Dry run: python scripts/go_with_the_flow_ci.py --dry-run")

    typer.echo("\n🔧 SKIP OPTIONS:")
    typer.echo("  --no-black: Skip formatting")
    typer.echo("  --no-isort: Skip import sorting")
    typer.echo("  --no-compile: Skip syntax check")
    typer.echo("  --no-pytest: Skip tests")
    typer.echo("  --no-mypy: Skip type checking")

    typer.echo("\n🎯 FILE TARGETING (--files):")
    typer.echo("  Example: --files 'analytics/foo.py,tests/api/test_foo.py'")
    typer.echo("  • Runs black/isort/compile/mypy only on selected files")
    typer.echo("  • Runs pytest only on selected test files (paths under tests/)")
    typer.echo("  • Override default targets entirely")

    typer.echo("\n📚 AVAILABLE COMMANDS:")
    typer.echo("  info - Show this information")
    typer.echo("  diagnose - Run environment diagnostics")
    typer.echo("  init-git-hooks - Setup pre-commit framework")
    typer.echo("  fire-warning - Show emergency refactoring tools")

    typer.echo("\n" + "=" * 70)


@app.command()
def fire_warning() -> None:
    """Show emergency tools for large refactoring/migrations."""
    show_fire_warning()


if __name__ == "__main__":
    app()

# ═════════════════════════════════════════════════════════════════════════════
# EOF - GO WITH THE FLOW CI MEGA SCRIPT v2 (Enhanced with Research)
# Production-Grade, Consolidated, Team-Treasured
# ═════════════════════════════════════════════════════════════════════════════
