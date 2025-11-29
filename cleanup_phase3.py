#!/usr/bin/env python3
"""
Phase 3: Organize Active Scripts & Reclassify Unknown Scripts

Organizes active v14 scripts into subdirectories and reclassifies unknown/ scripts.
Following Go with the Flow v3.0 rules R14, R12, GOV-01.
"""

import logging
import subprocess
import sys
from pathlib import Path
from typing import Tuple

logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class ScriptOrganizer:
    """Organizes active v14 scripts into logical subdirectories."""

    # Active script categorization
    CI_SCRIPTS = [
        "ci_structure_check.py",
        "check_all_py_files.py",
        "check_staged_py_files.py",
        "check_legacy_imports.py",
        "validate.py",
        "parameter_validation.py",
        "model_guard.py",
    ]

    BUILD_SCRIPTS = [
        "make_clean_zip.py",
        "make_essential_zip.py",
        "build_zip_from_manifest.py",
        "generate_manifest.py",
    ]

    GITHUB_SCRIPTS = [
        "gh_tools.py",
        "auto_close_issues.py",
    ]

    ANALYSIS_SCRIPTS = [
        "fx_correlation_module.py",
        "wacc_engine_yaml.py",
        "analyze_directory.py",
        "gen_scenario_yaml.py",
    ]

    TEST_SCRIPTS = [
        "test_fx_dual_regime_standalone_fixed.py",
        "test_llcr_plcr_real_debt.py",
        "test_irr_quick.py",
        "test_returns_module.py",
        "test_markdown_report.py",
        "test_fx_complete_data.py",
    ]

    # Keep at root level
    ROOT_SCRIPTS = [
        "go_with_the_flow_ci.py",
        "cleanup_phase1.py",
        "cleanup_phase1_fixed.py",
        "cleanup_phase2.py",
        "cleanup_phase3.py",
    ]

    def __init__(self, scripts_dir: Path, dry_run: bool = True):
        self.scripts_dir = scripts_dir
        self.dry_run = dry_run

    def organize(self) -> Tuple[int, int]:
        """Organize active scripts into subdirectories."""
        logger.info("=" * 80)
        logger.info("PHASE 3A: ORGANIZING ACTIVE SCRIPTS")
        logger.info("=" * 80)

        categories = {
            "ci": self.CI_SCRIPTS,
            "build": self.BUILD_SCRIPTS,
            "github": self.GITHUB_SCRIPTS,
            "analysis": self.ANALYSIS_SCRIPTS,
            "tests": self.TEST_SCRIPTS,
        }

        success = 0
        failed = 0

        for subdir, scripts in categories.items():
            target_dir = self.scripts_dir / subdir

            if not self.dry_run:
                target_dir.mkdir(exist_ok=True)
                logger.info(f"✓ Created: scripts/{subdir}/")
            else:
                logger.info(f"Would create: scripts/{subdir}/")

            for script in scripts:
                source = self.scripts_dir / script
                if source.exists():
                    target = target_dir / script
                    if self._move_file(source, target):
                        success += 1
                    else:
                        failed += 1

        return success, failed

    def _move_file(self, source: Path, target: Path) -> bool:
        """Move a file using git mv."""
        try:
            if not self.dry_run:
                subprocess.run(
                    ["git", "mv", str(source), str(target)],
                    check=True,
                    capture_output=True,
                )
                logger.info(f"  ✓ {source.name} → {target.parent.name}/")
            else:
                logger.info(f"  Would move: {source.name} → {target.parent.name}/")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"  ✗ Failed: {source.name}: {e.stderr.decode()}")
            return False


class UnknownReclassifier:
    """Reclassifies scripts from unknown/ based on purpose."""

    # Reclassification rules
    ACTIVE_CI = [
        "ci_phase_c_full.sh",
        "ci_quick.sh",
        "dev_quickcheck.sh",
        "check_outputs.sh",
    ]

    ACTIVE_TEST_RUNNERS = [
        "regression_smoke.sh",
        "run_all_suites.sh",
        "run_api_cov_smoke.sh",
        "run_core_hardened.sh",
        "run_heavy_modules_suite.sh",
        "run_next_modules_suite.sh",
        "run_next_tests.sh",
        "run_reporting_cli_smoke.sh",
        "run_reporting_hardened.sh",
        "run_cli_scenarios_fast.sh",
        "run_heavy_with_shims.sh",
        "run_import_surface_sweep.sh",
    ]

    ACTIVE_BUILD = [
        "make_upload_zip.sh",
        "roll_zip_and_bootstrap.sh",
    ]

    ACTIVE_GITHUB = [
        "setup_github_auth_https.sh",
        "create_v14_analytics_issues.sh",
    ]

    MIGRATIONS = [
        "alias_outdir_flag.sh",
        "housekeep.sh",
        "post_import_sanity.sh",
        "push_and_tag.sh",
        "push_and_tag_fixed.sh",
        "quick_fix_and_test.sh",
        "repo_housekeeping_move.sh",
        "rewrite_scenario_runner_minimal.sh",
        "rewrite_scenario_runner_relaxed.sh",
        "run_phase_c_and_push.sh",
        "venv_up.sh",
    ]

    DEBUG = [
        "debt_module_diagnostic.py",
        "v14_debt_test.py",
    ]

    REPORTING = [
        "generate_reports.py",
    ]

    def __init__(self, unknown_dir: Path, dry_run: bool = True):
        self.unknown_dir = unknown_dir
        self.dry_run = dry_run

    def reclassify(self) -> Tuple[int, int]:
        """Reclassify unknown scripts to appropriate locations."""
        logger.info("")
        logger.info("=" * 80)
        logger.info("PHASE 3B: RECLASSIFYING UNKNOWN SCRIPTS")
        logger.info("=" * 80)

        moves = {
            "scripts/ci": self.ACTIVE_CI,
            "scripts/test_runners": self.ACTIVE_TEST_RUNNERS,
            "scripts/build": self.ACTIVE_BUILD,
            "scripts/github": self.ACTIVE_GITHUB,
            "scripts/reporting": self.REPORTING,
            "legacy/scripts/migrations": self.MIGRATIONS,
            "legacy/scripts/debug_archive": self.DEBUG,
        }

        success = 0
        failed = 0

        for target_dir_str, scripts in moves.items():
            if not scripts:
                continue

            target_dir = Path(target_dir_str)
            logger.info("")
            logger.info(f"Moving {len(scripts)} scripts to {target_dir_str}/")

            if not self.dry_run:
                target_dir.mkdir(parents=True, exist_ok=True)

            for script in scripts:
                source = self.unknown_dir / script
                if source.exists():
                    target = target_dir / script
                    if self._move_file(source, target):
                        success += 1
                    else:
                        failed += 1
                else:
                    logger.warning(f"  ⚠️  Not found: {script}")

        return success, failed

    def _move_file(self, source: Path, target: Path) -> bool:
        """Move a file using git mv."""
        try:
            if not self.dry_run:
                subprocess.run(
                    ["git", "mv", str(source), str(target)],
                    check=True,
                    capture_output=True,
                )
                logger.info(f"  ✓ {source.name}")
            else:
                logger.info(f"  Would move: {source.name}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"  ✗ Failed: {source.name}: {e.stderr.decode()}")
            return False


def generate_summary(scripts_dir: Path) -> None:
    """Generate final organization summary."""
    logger.info("")
    logger.info("=" * 80)
    logger.info("FINAL ORGANIZATION SUMMARY")
    logger.info("=" * 80)
    logger.info("")

    # Count files in each directory
    dirs = {
        "scripts/": len(list(scripts_dir.glob("*.py")))
        + len(list(scripts_dir.glob("*.sh"))),
        "scripts/ci/": (
            len(list((scripts_dir / "ci").glob("*")))
            if (scripts_dir / "ci").exists()
            else 0
        ),
        "scripts/build/": (
            len(list((scripts_dir / "build").glob("*")))
            if (scripts_dir / "build").exists()
            else 0
        ),
        "scripts/github/": (
            len(list((scripts_dir / "github").glob("*")))
            if (scripts_dir / "github").exists()
            else 0
        ),
        "scripts/analysis/": (
            len(list((scripts_dir / "analysis").glob("*")))
            if (scripts_dir / "analysis").exists()
            else 0
        ),
        "scripts/tests/": (
            len(list((scripts_dir / "tests").glob("*")))
            if (scripts_dir / "tests").exists()
            else 0
        ),
        "scripts/test_runners/": (
            len(list((scripts_dir / "test_runners").glob("*")))
            if (scripts_dir / "test_runners").exists()
            else 0
        ),
        "scripts/reporting/": (
            len(list((scripts_dir / "reporting").glob("*")))
            if (scripts_dir / "reporting").exists()
            else 0
        ),
    }

    logger.info("Active scripts structure:")
    for dir_name, count in dirs.items():
        if count > 0:
            logger.info(f"  {dir_name}: {count} files")

    unknown_remaining = Path("legacy/scripts/unknown")
    if unknown_remaining.exists():
        remaining = len(list(unknown_remaining.glob("*")))
        logger.info("")
        logger.info(f"legacy/scripts/unknown/: {remaining} files remaining")
        if remaining > 0:
            logger.info("  (These need manual review)")


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Phase 3: Organize active scripts")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--verbose", action="store_true")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    scripts_dir = Path("scripts")
    unknown_dir = Path("legacy/scripts/unknown")

    # Phase 3A: Organize active scripts
    organizer = ScriptOrganizer(scripts_dir, dry_run=not args.execute)
    org_success, org_failed = organizer.organize()

    # Phase 3B: Reclassify unknown scripts
    reclassifier = UnknownReclassifier(unknown_dir, dry_run=not args.execute)
    recl_success, recl_failed = reclassifier.reclassify()

    # Summary
    generate_summary(scripts_dir)

    total_success = org_success + recl_success
    total_failed = org_failed + recl_failed

    logger.info("")
    logger.info("=" * 80)
    logger.info(f"Phase 3 complete: {total_success} moved, {total_failed} failed")
    logger.info("=" * 80)

    if not args.execute:
        logger.info("")
        logger.info("DRY RUN - Run with --execute to perform moves")
    else:
        if total_failed == 0:
            logger.info("")
            logger.info("Next steps:")
            logger.info("  git add -A")
            logger.info(
                "  git commit -m 'chore: organize scripts into subdirectories (Phase 3)'"
            )

    return 0 if total_failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
