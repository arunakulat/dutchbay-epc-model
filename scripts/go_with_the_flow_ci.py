#!/usr/bin/env python3
"""
Go-with-the-Flow CI Helper - Typer Edition v2

Pure-Python orchestration for local checks with fire-fighting capability + artifact generation.

PRIMARY PIPELINE (daily use):
  - black - code formatting
  - isort - import organization
  - compileall - syntax validation
  - pytest - test suite
  - mypy - type checking
  - JSON export (automatic)

BACKGROUND FORCES (ready for battles):
  - Bowler - large-scale refactoring
  - LibCST - AST manipulation for code transformations
  - generate-artifacts - concatenate scripts into single file

USAGE:
  python scripts/go_with_the_flow_ci.py                    # Full pipeline + JSON export
  python scripts/go_with_the_flow_ci.py --fast             # Fast lane + JSON export
  python scripts/go_with_the_flow_ci.py --no-mypy --fast   # Skip mypy, use fast mode
  python scripts/go_with_the_flow_ci.py generate-artifacts # Create concatenated scripts artifact
  python scripts/go_with_the_flow_ci.py info               # Show configuration
  python scripts/go_with_the_flow_ci.py fire-warning       # Show emergency tools
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import typer

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION & PATHS
# ══════════════════════════════════════════════════════════════════════════════

REPO_ROOT = Path(__file__).resolve().parent.parent

BLACK_TARGETS = (
    "analytics",
    "finance",
    "run_full_pipeline_v14.py",
    "scripts",
)

ISORT_TARGETS = tuple(BLACK_TARGETS)

COMPILE_TARGETS = (
    "analytics",
    "finance",
)

FAST_PYTEST_TARGETS = (
    "tests/analytics_layer/test_monte_carlo_v14.py",
    "tests/analytics_layer/test_sensitivity_v14_all.py",
    "tests/api/test_scenario_manager_smoke.py",
    "tests/test_v14_pipeline_smoke.py",
)

FULL_PYTEST_TARGETS = ("tests",)

MYPY_TARGETS = (
    "analytics",
    "finance",
    "run_full_pipeline_v14.py",
)

# Modules to include in concatenated artifact
ARTIFACT_MODULES = (
    "analytics/contracts_v14.py",
    "analytics/sensitivity_v14.py",
    "analytics/scenario_analytics.py",
    "analytics/evaluate_scenario.py",
    "analytics/scenario_loader.py",
    "analytics/schema_guard.py",
    "analytics/core/metrics.py",
    "finance/cashflow_v14.py",
    "finance/debt_v14.py",
    "finance/wacc_v14.py",
    "finance/equity_v14.py",
    "finance/irr.py",
)


# ══════════════════════════════════════════════════════════════════════════════
# CI RESULTS TRACKER (For JSON Export)
# ══════════════════════════════════════════════════════════════════════════════


class CIResults:
    """Track CI execution for JSON export."""

    def __init__(self):
        self.start_time = datetime.now()
        self.steps: list[dict[str, Any]] = []
        self.overall_status = "UNKNOWN"
        self.repo_root = REPO_ROOT

    def add_step(
        self,
        step_name: str,
        status: str,
        elapsed: float,
        exit_code: int,
        details: Optional[dict] = None,
    ) -> None:
        """Record a CI step result."""
        self.steps.append(
            {
                "step_name": step_name,
                "status": status,
                "elapsed_seconds": round(elapsed, 2),
                "exit_code": exit_code,
                **(details or {}),
            }
        )

    def export_json(self, success: bool = True) -> Path:
        """Export CI results as JSON. Overwrites previous results."""
        total_elapsed = (datetime.now() - self.start_time).total_seconds()
        self.overall_status = "PASSED" if success else "FAILED"

        results = {
            "timestamp": self.start_time.isoformat(),
            "run_id": f"ci_{self.start_time.strftime('%Y%m%d_%H%M%S')}",
            "pipeline_version": "go_with_the_flow_v2",
            "host_info": {
                "platform": sys.platform,
                "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
                "repo_root": str(self.repo_root),
            },
            "execution": {
                "total_elapsed_seconds": round(total_elapsed, 2),
                "steps_executed": len(self.steps),
                "overall_status": self.overall_status,
                "steps": self.steps,
            },
            "code_quality": {
                "formatting": (
                    "COMPLIANT"
                    if any(
                        s["step_name"] == "black" and s["status"] == "PASSED"
                        for s in self.steps
                    )
                    else "UNKNOWN"
                ),
                "imports": (
                    "ORGANIZED"
                    if any(
                        s["step_name"] == "isort" and s["status"] == "PASSED"
                        for s in self.steps
                    )
                    else "UNKNOWN"
                ),
                "syntax": (
                    "VALID"
                    if any(
                        s["step_name"] == "compileall" and s["status"] == "PASSED"
                        for s in self.steps
                    )
                    else "UNKNOWN"
                ),
                "tests": (
                    "PASSING"
                    if any(
                        s["step_name"] == "pytest" and s["status"] == "PASSED"
                        for s in self.steps
                    )
                    else "UNKNOWN"
                ),
                "type_safety": (
                    "CLEAN"
                    if any(
                        s["step_name"] == "mypy" and s["status"] == "PASSED"
                        for s in self.steps
                    )
                    else "UNKNOWN"
                ),
            },
            "recommendations": self._get_recommendations(),
        }

        # Ensure outputs dir exists
        outputs_dir = self.repo_root / "outputs"
        outputs_dir.mkdir(exist_ok=True)

        # Delete old JSON file
        old_json = outputs_dir / "ci_results.json"
        if old_json.exists():
            old_json.unlink()

        # Write new JSON file
        json_file = outputs_dir / "ci_results.json"
        json_file.write_text(json.dumps(results, indent=2))

        return json_file

    def _get_recommendations(self) -> list[str]:
        """Generate recommendations based on results."""
        recs = []

        if self.overall_status == "PASSED":
            recs.append("✅ All quality gates passed")
            recs.append("Ready for commit and push")
            recs.append(
                "💡 Consider running: python scripts/go_with_the_flow_ci.py generate-artifacts"
            )
        else:
            recs.append("❌ Some checks failed - review output above")
            recs.append("Fix issues and run again")

        return recs


# Global results tracker
_ci_results = CIResults()


# ══════════════════════════════════════════════════════════════════════════════
# CORE FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════


def run_step(
    cmd: list[str],
    label: str,
    cwd: Path = REPO_ROOT,
    allow_fail: bool = False,
) -> tuple[int, float]:
    """Run a single shell step and return (exit_code, elapsed_time)."""
    typer.echo("\n" + "=" * 70)
    typer.echo(label)
    typer.echo("=" * 70)
    typer.echo(f"$ {' '.join(cmd)}")

    start = time.time()
    result = subprocess.run(cmd, cwd=str(cwd))
    elapsed = time.time() - start

    if result.returncode != 0:
        if allow_fail:
            typer.echo(
                f"⚠️  Warning: {label} exited with code {result.returncode}", err=True
            )
            return result.returncode, elapsed
        else:
            typer.echo(f"❌ FAILED: {label} (exit code {result.returncode})", err=True)
            raise typer.Exit(result.returncode)

    typer.echo(f"✅ Completed {label} in {elapsed:.2f}s")
    return 0, elapsed


def show_fire_warning() -> None:
    """Show available emergency tools."""
    typer.echo("=" * 70)
    typer.echo("EMERGENCY TOOLS (background, ready to deploy)")
    typer.echo("=" * 70)
    typer.echo("🔥 Migrations/refactoring needed?")
    typer.echo("  • bowler - Large-scale AST-safe refactoring")
    typer.echo("  • libcst - Concrete syntax tree manipulation")
    typer.echo()
    typer.echo("Example:")
    typer.echo("  python scripts/fire_migration.py migrationname")
    typer.echo()


def parse_files_argument(files: Optional[str]) -> list[str]:
    """Parse the --files option (comma-separated) into a clean list of paths."""
    if not files:
        return []

    parts = [p.strip() for p in files.split(",")]
    return [p for p in parts if p]


def split_code_and_tests(files: list[str]) -> tuple[list[str], list[str]]:
    """Split selected files into code files and test files."""
    code_files = []
    test_files = []

    for path in files:
        if path.startswith("tests/") or path.startswith("tests\\"):
            test_files.append(path)
        else:
            code_files.append(path)

    return code_files, test_files


# ══════════════════════════════════════════════════════════════════════════════
# TYPER APP
# ══════════════════════════════════════════════════════════════════════════════

app = typer.Typer(
    help="Go-with-the-Flow CI pipeline - build once, build right.",
    no_args_is_help=False,  # Allow default command to run
)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    fast: bool = typer.Option(
        False,
        "--fast",
        help="Fast lane: run targeted pytest suite instead of full tests.",
    ),
    no_black: bool = typer.Option(
        False,
        "--no-black",
        help="Skip black formatter.",
    ),
    no_isort: bool = typer.Option(
        False,
        "--no-isort",
        help="Skip isort import sorter.",
    ),
    no_pytest: bool = typer.Option(
        False,
        "--no-pytest",
        help="Skip pytest.",
    ),
    no_mypy: bool = typer.Option(
        False,
        "--no-mypy",
        help="Skip mypy type checker.",
    ),
    verbose: bool = typer.Option(
        False,
        "-v",
        "--verbose",
        help="Verbose output.",
    ),
    files: Optional[str] = typer.Option(
        None,
        "--files",
        help="Comma-separated list of files to focus on, e.g. analytics/foo.py,tests/api/test_foo.py",
    ),
) -> None:
    """
    Run Go-with-the-Flow CI checks.

    Default: Full pipeline (black → isort → compile → pytest → mypy)
    Fast mode: Targeted tests for quick feedback
    With --files: Restrict CI to specific files
    """

    if ctx.invoked_subcommand is not None:
        return

    repo = REPO_ROOT
    start_time = time.time()
    steps_run = 0

    typer.echo("\n" + "=" * 70)
    typer.echo("GO-WITH-THE-FLOW CI PIPELINE v2")
    typer.echo("=" * 70)
    typer.echo(f"Repository: {repo}")
    typer.echo(f"Python: {sys.executable}")
    typer.echo(f"Version: {sys.version.split()[0]}")

    # Determine mode
    mode = "FAST LANE" if fast else "FULL PIPELINE"
    selected_files = parse_files_argument(files)
    code_files, test_files = split_code_and_tests(selected_files)
    scope = "SELECTED FILES" if selected_files else "DEFAULT TARGETS"

    typer.echo(f"Mode: {mode} | Scope: {scope}")

    if verbose and selected_files:
        typer.echo(f"Selected files: {', '.join(selected_files)}")

    # ─────────────────────────────────────────────────────────────────────────
    # BLACK
    # ─────────────────────────────────────────────────────────────────────────
    if not no_black:
        steps_run += 1
        black_targets = list(selected_files) or list(BLACK_TARGETS)
        code, elapsed = run_step(
            [sys.executable, "-m", "black", *black_targets],
            cwd=repo,
            label="black - Code Formatter",
        )
        _ci_results.add_step(
            "black", "PASSED" if code == 0 else "FAILED", elapsed, code
        )
        if code != 0:
            raise typer.Exit(code)

    # ─────────────────────────────────────────────────────────────────────────
    # ISORT
    # ─────────────────────────────────────────────────────────────────────────
    if not no_isort:
        steps_run += 1
        isort_targets = list(selected_files) or list(ISORT_TARGETS)
        code, elapsed = run_step(
            [sys.executable, "-m", "isort", *isort_targets],
            cwd=repo,
            label="isort - Import Sorter",
        )
        _ci_results.add_step(
            "isort", "PASSED" if code == 0 else "FAILED", elapsed, code
        )
        if code != 0:
            raise typer.Exit(code)

    # ─────────────────────────────────────────────────────────────────────────
    # COMPILEALL
    # ─────────────────────────────────────────────────────────────────────────
    compile_targets = list(selected_files) or list(COMPILE_TARGETS)
    for target in compile_targets:
        steps_run += 1
        code, elapsed = run_step(
            [sys.executable, "-m", "compileall", target],
            cwd=repo,
            label=f"compileall - Syntax Check ({target})",
        )
        _ci_results.add_step(
            f"compileall[{target}]",
            "PASSED" if code == 0 else "FAILED",
            elapsed,
            code,
        )
        if code != 0:
            raise typer.Exit(code)

    # ─────────────────────────────────────────────────────────────────────────
    # PYTEST
    # ─────────────────────────────────────────────────────────────────────────
    if not no_pytest:
        steps_run += 1

        if selected_files:
            pytest_targets = test_files or [
                f for f in selected_files if f.startswith("tests/")
            ]
            if not pytest_targets:
                pytest_targets = list(
                    FAST_PYTEST_TARGETS if fast else FULL_PYTEST_TARGETS
                )
        else:
            pytest_targets = list(FAST_PYTEST_TARGETS if fast else FULL_PYTEST_TARGETS)

        mode_label = "FAST LANE" if fast else "FULL SUITE"
        code, elapsed = run_step(
            [sys.executable, "-m", "pytest", *pytest_targets],
            cwd=repo,
            label=f"pytest - Test Suite ({mode_label})",
        )
        _ci_results.add_step(
            "pytest", "PASSED" if code == 0 else "FAILED", elapsed, code
        )
        if code != 0:
            raise typer.Exit(code)

    # ─────────────────────────────────────────────────────────────────────────
    # MYPY
    # ─────────────────────────────────────────────────────────────────────────
    if not no_mypy:
        steps_run += 1
        mypy_targets = list(code_files) or list(MYPY_TARGETS)
        code, elapsed = run_step(
            [sys.executable, "-m", "mypy", *mypy_targets],
            cwd=repo,
            label="mypy - Type Checker",
        )
        _ci_results.add_step("mypy", "PASSED" if code == 0 else "FAILED", elapsed, code)
        if code != 0:
            raise typer.Exit(code)

    # ─────────────────────────────────────────────────────────────────────────
    # SUCCESS & JSON EXPORT
    # ─────────────────────────────────────────────────────────────────────────
    elapsed_total = time.time() - start_time

    typer.echo("\n" + "=" * 70)
    typer.echo("GO-WITH-THE-FLOW CI PIPELINE SUCCESSFUL ✅")
    typer.echo("=" * 70)
    typer.echo(f"Steps executed: {steps_run}")
    typer.echo(f"Pipeline time: {elapsed_total:.2f}s")
    typer.echo("Code quality: PASSING")
    typer.echo("Repository state:")
    typer.echo("  • Formatting: Compliant (black)")
    typer.echo("  • Imports: Organized (isort)")
    typer.echo("  • Syntax: Valid (compileall)")

    if not no_pytest:
        typer.echo("  • Tests: All passing")
    else:
        typer.echo("  • Tests: SKIPPED (--no-pytest)")

    if not no_mypy:
        typer.echo("  • Types: Validated (mypy)")
    else:
        typer.echo("  • Types: SKIPPED (--no-mypy)")

    typer.echo()
    typer.echo("✨ Ready for commit!")

    # Export JSON results
    json_file = _ci_results.export_json(success=True)
    typer.echo(f"📊 Results exported to: {json_file}")

    show_fire_warning()


@app.command
def generate_artifacts() -> None:
    """Generate concatenated scripts artifact for distribution."""
    typer.echo("=" * 70)
    typer.echo("Generating Concatenated Scripts Artifact")
    typer.echo("=" * 70)

    outputs_dir = REPO_ROOT / "outputs"
    outputs_dir.mkdir(exist_ok=True)

    concatenated = (
        '"""Generated artifact from go_with_the_flow_ci.py - DO NOT EDIT MANUALLY\n\n'
    )
    concatenated += f"Generated: {datetime.now().isoformat()}\n"
    concatenated += f"Modules: {len(ARTIFACT_MODULES)}\n"
    concatenated += '"""\n\n'

    seen_imports = set()
    module_contents = []

    typer.echo(f"Concatenating {len(ARTIFACT_MODULES)} modules...")

    for module_path in ARTIFACT_MODULES:
        full_path = REPO_ROOT / module_path

        if not full_path.exists():
            typer.echo(f"⚠️  Skipping (not found): {module_path}", err=True)
            continue

        try:
            content = full_path.read_text(encoding="utf-8")
            module_contents.append((module_path, content))
            typer.echo(f"  ✓ {module_path}")
        except Exception as e:
            typer.echo(f"  ✗ Failed to read {module_path}: {e}", err=True)

    # Deduplicate and collect imports
    all_imports = []
    all_code = []

    for module_path, content in module_contents:
        lines = content.split("\n")
        imports = []
        code = []
        in_imports = True

        for line in lines:
            if line.startswith(("import ", "from ")):
                if line not in seen_imports:
                    imports.append(line)
                    seen_imports.add(line)
            else:
                if line.strip() and not line.startswith("#"):
                    in_imports = False

                if not in_imports:
                    code.append(line)

        all_imports.extend(imports)
        all_code.append(
            "\n# ══════════════════════════════════════════════════════════════════════════════\n"
        )
        all_code.append(f"# {module_path}\n")
        all_code.append(
            "# ══════════════════════════════════════════════════════════════════════════════\n"
        )
        all_code.extend(code)

    # Combine
    if all_imports:
        concatenated += "\n".join(all_imports)
        concatenated += "\n\n"

    concatenated += "\n".join(all_code)

    # Add footer
    concatenated += f"""

# ══════════════════════════════════════════════════════════════════════════════
# ARTIFACT METADATA
# ══════════════════════════════════════════════════════════════════════════════
# Generated: {datetime.now().isoformat()}
# Modules included: {len(module_contents)}
# Total size: {len(concatenated):,} bytes
# Purpose: Code review, audit, distribution
# Note: This is a documentation artifact - NOT for runtime use
# ══════════════════════════════════════════════════════════════════════════════

EOF
"""

    # Write artifact
    artifact_file = outputs_dir / "concatenated_scripts_v14.py"
    artifact_file.write_text(concatenated, encoding="utf-8")

    size_kb = len(concatenated) / 1024
    typer.echo()
    typer.echo(f"✅ Generated: {artifact_file}")
    typer.echo(f"   Size: {size_kb:.1f} KB ({len(module_contents)} modules)")
    typer.echo("   Use for: Review, audit, distribution to stakeholders")


@app.command
def info() -> None:
    """Show CI pipeline information and configuration."""
    typer.echo("=" * 70)
    typer.echo("GO-WITH-THE-FLOW CI - INFORMATION")
    typer.echo("=" * 70)
    typer.echo("\nPipeline Stages:")
    typer.echo("  1. black - Code formatting consistency")
    typer.echo("  2. isort - Import organization (PEP 8)")
    typer.echo("  3. compileall - Syntax validation (early errors)")
    typer.echo("  4. pytest - Test execution (correctness)")
    typer.echo("  5. mypy - Type checking (type safety)")
    typer.echo("  → JSON export - Automatic after successful run")

    typer.echo("\nEmergency Tools (Background):")
    typer.echo("  • bowler - AST-safe refactoring (Meta/Facebook)")
    typer.echo("  • libcst - Concrete syntax tree manipulation")

    typer.echo("\nQuick Start:")
    typer.echo("  Full suite:")
    typer.echo("    $ python scripts/go_with_the_flow_ci.py")

    typer.echo("\n  Fast mode:")
    typer.echo("    $ python scripts/go_with_the_flow_ci.py --fast")

    typer.echo("\n  Skip mypy:")
    typer.echo("    $ python scripts/go_with_the_flow_ci.py --no-mypy")

    typer.echo("\n  Verbose:")
    typer.echo("    $ python scripts/go_with_the_flow_ci.py -v")

    typer.echo("\n  Specific files:")
    typer.echo(
        "    $ python scripts/go_with_the_flow_ci.py --files analytics/foo.py,tests/api/test_foo.py --fast"
    )

    typer.echo("\n  Generate artifacts:")
    typer.echo("    $ python scripts/go_with_the_flow_ci.py generate-artifacts")

    typer.echo("\nDefault Targets:")
    typer.echo(f"  Black/isort: {', '.join(BLACK_TARGETS)}")
    typer.echo(f"  Compile: {', '.join(COMPILE_TARGETS)}")
    typer.echo(f"  Mypy: {', '.join(MYPY_TARGETS)}")

    typer.echo("\nFile-Scoped Mode (--files):")
    typer.echo("  Example:")
    typer.echo(
        "    $ python scripts/go_with_the_flow_ci.py --files analytics/foo.py,tests/api/test_foo.py --fast"
    )
    typer.echo("  • black/isort/compile/mypy run only on the selected files")
    typer.echo("  • pytest runs only on the selected test files (paths under tests/)")


@app.command
def fire_warning() -> None:
    """Show available emergency fire-fighting tools."""
    show_fire_warning()


# ══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    app()

EOF
