#!/usr/bin/env python3
"""
Phase 1: Scripts Folder Cleanup - Backup File Deletion (Fixed)

This script removes backup files from the scripts/ directory following
Go with the Flow v3.0 rules:
- R12: Legacy code isolation
- R19: No spaces in filenames
- DOC-02: Model change log for significant changes
- GOV-01: AI-assisted development contract

Author: DutchBay EPC Model Team
Sprint: v3.0-cleanup
Status: Active
"""

import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class BackupFileCleaner:
    """
    Safely removes backup files from scripts/ directory.

    Follows Go with the Flow v3.0 principles:
    - Validates Git tracking before deletion
    - Provides dry-run mode
    - Logs all actions for audit trail
    - Verifies file patterns before removal
    - Deduplicates file list to prevent double-deletion attempts
    """

    # Backup file patterns to detect
    BACKUP_PATTERNS = [
        "*.bak",
        "*.backup",
        "*_old.py",
        "*_old.sh",
    ]

    # Critical files that should NEVER be deleted (safety list)
    PROTECTED_FILES = [
        "go_with_the_flow_ci.py",
        "fx_correlation_module.py",
        "analyze_directory.py",
    ]

    def __init__(self, scripts_dir: Path, dry_run: bool = True):
        """
        Initialize the cleaner.

        Args:
            scripts_dir: Path to scripts directory
            dry_run: If True, only report what would be deleted
        """
        self.scripts_dir = scripts_dir
        self.dry_run = dry_run
        self.files_to_delete: List[Path] = []
        self.git_tracked: Dict[str, bool] = {}

    def validate_environment(self) -> bool:
        """
        Validate that we're in a Git repository and scripts/ exists.

        Returns:
            True if environment is valid, False otherwise
        """
        if not self.scripts_dir.exists():
            logger.error(f"Scripts directory does not exist: {self.scripts_dir}")
            return False

        if not self.scripts_dir.is_dir():
            logger.error(f"Scripts path is not a directory: {self.scripts_dir}")
            return False

        # Check if we're in a Git repository
        try:
            subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                check=True,
                capture_output=True,
                cwd=self.scripts_dir.parent,
            )
            logger.info("✓ Git repository detected")
            return True
        except subprocess.CalledProcessError:
            logger.error("Not in a Git repository. Aborting for safety.")
            return False

    def find_backup_files(self) -> List[Path]:
        """
        Find all backup files matching defined patterns.
        Uses a set to deduplicate results.

        Returns:
            List of unique backup file paths
        """
        backup_files_set: Set[Path] = set()

        for pattern in self.BACKUP_PATTERNS:
            matches = self.scripts_dir.rglob(pattern)
            for match in matches:
                if match.is_file():
                    # Safety check: ensure not a protected file
                    if match.name not in self.PROTECTED_FILES:
                        backup_files_set.add(match)
                    else:
                        logger.warning(
                            f"⚠️  Protected file matched pattern but will NOT be deleted: {match.name}"
                        )

        # Convert set to sorted list
        return sorted(list(backup_files_set))

    def check_git_tracking(self, file_path: Path) -> Tuple[bool, str]:
        """
        Check if a file is tracked in Git and get its history.

        Args:
            file_path: Path to file to check

        Returns:
            Tuple of (is_tracked, last_commit_info)
        """
        try:
            # Check if file is tracked
            result = subprocess.run(
                ["git", "ls-files", "--error-unmatch", str(file_path)],
                capture_output=True,
                cwd=self.scripts_dir.parent,
                text=True,
            )
            is_tracked = result.returncode == 0

            if is_tracked:
                # Get last commit info
                commit_info = subprocess.run(
                    [
                        "git",
                        "log",
                        "-1",
                        "--format=%h - %s (%cr)",
                        "--",
                        str(file_path),
                    ],
                    capture_output=True,
                    cwd=self.scripts_dir.parent,
                    text=True,
                )
                last_commit = commit_info.stdout.strip() or "No commit history"
            else:
                last_commit = "Not tracked in Git"

            return is_tracked, last_commit

        except subprocess.CalledProcessError as e:
            logger.error(f"Git error checking {file_path}: {e}")
            return False, "Error checking Git status"

    def analyze_files(self) -> None:
        """
        Analyze all backup files and prepare deletion report.
        """
        logger.info(f"\n{'='*80}")
        logger.info("PHASE 1: BACKUP FILE DELETION ANALYSIS")
        logger.info(f"{'='*80}\n")

        self.files_to_delete = self.find_backup_files()

        if not self.files_to_delete:
            logger.info("✓ No backup files found. Scripts directory is clean.")
            return

        logger.info(f"Found {len(self.files_to_delete)} unique backup files:\n")

        total_size = 0
        for idx, file_path in enumerate(self.files_to_delete, 1):
            rel_path = file_path.relative_to(self.scripts_dir.parent)
            file_size = file_path.stat().st_size
            total_size += file_size

            is_tracked, commit_info = self.check_git_tracking(file_path)
            self.git_tracked[str(file_path)] = is_tracked

            logger.info(f"{idx}. {rel_path}")
            logger.info(f"   Size: {file_size:,} bytes")
            logger.info(f"   Git: {'✓ Tracked' if is_tracked else '✗ Untracked'}")
            if is_tracked:
                logger.info(f"   Last commit: {commit_info}")
            logger.info("")

        logger.info(f"{'='*80}")
        logger.info(f"Total files to delete: {len(self.files_to_delete)}")
        logger.info(
            f"Total space to reclaim: {total_size:,} bytes ({total_size / 1024:.2f} KB)"
        )
        logger.info(f"{'='*80}\n")

    def execute_deletion(self) -> Tuple[int, int]:
        """
        Execute deletion of backup files.

        Returns:
            Tuple of (success_count, failure_count)
        """
        if not self.files_to_delete:
            return 0, 0

        if self.dry_run:
            logger.info("🔍 DRY RUN MODE - No files will be deleted")
            logger.info("Run with --execute flag to perform actual deletion\n")
            return len(self.files_to_delete), 0

        logger.info("🗑️  EXECUTING DELETION...\n")

        success_count = 0
        failure_count = 0

        for file_path in self.files_to_delete:
            rel_path = file_path.relative_to(self.scripts_dir.parent)
            try:
                if file_path.exists():
                    file_path.unlink()
                    logger.info(f"✓ Deleted: {rel_path}")
                    success_count += 1
                else:
                    logger.warning(f"⚠️  Already deleted (skipped): {rel_path}")
            except Exception as e:
                logger.error(f"✗ Failed to delete {rel_path}: {e}")
                failure_count += 1

        logger.info(f"\n{'='*80}")
        logger.info(
            f"Deletion complete: {success_count} succeeded, {failure_count} failed"
        )
        logger.info(f"{'='*80}\n")

        return success_count, failure_count

    def generate_commit_message(self) -> str:
        """
        Generate a commit message following R18 (Git Workflow).

        Returns:
            Formatted commit message
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

        message = f"""chore: remove backup files from scripts/ (Phase 1 cleanup)

Remove {len(self.files_to_delete)} backup files following Go with the Flow v3.0:
- R12: Legacy code isolation
- R19: No spaces in filenames (file hygiene)
- DOC-02: Model change log requirements

Files removed:
"""
        for file_path in self.files_to_delete:
            rel_path = file_path.relative_to(self.scripts_dir.parent)
            message += f"  - {rel_path}\n"

        message += f"""
All deleted files are preserved in Git history.
Run 'git log --follow <file>' to view historical versions.

Phase: v3.0-cleanup
Status: Complete
Timestamp: {timestamp}
"""
        return message

    def save_audit_log(self) -> None:
        """
        Save deletion audit log for compliance (GOV-01).
        """
        audit_file = (
            self.scripts_dir.parent
            / "outputs"
            / f"cleanup_phase1_audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        )
        audit_file.parent.mkdir(exist_ok=True)

        with open(audit_file, "w") as f:
            f.write("PHASE 1: BACKUP FILE DELETION AUDIT LOG\n")
            f.write("=" * 80 + "\n")
            f.write(f"Timestamp: {datetime.now().isoformat()}\n")
            f.write(f"Dry Run: {self.dry_run}\n")
            f.write(f"Total Files: {len(self.files_to_delete)}\n")
            f.write("=" * 80 + "\n\n")

            for file_path in self.files_to_delete:
                rel_path = file_path.relative_to(self.scripts_dir.parent)
                is_tracked = self.git_tracked.get(str(file_path), False)
                f.write(f"File: {rel_path}\n")
                f.write(f"  Git Tracked: {is_tracked}\n")
                f.write(f"  Size: {file_path.stat().st_size} bytes\n")
                f.write("\n")

        logger.info(f"📄 Audit log saved: {audit_file}")


def main() -> int:
    """
    Main entry point for Phase 1 cleanup script.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="Phase 1: Remove backup files from scripts/ directory",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run (default) - see what would be deleted
  python cleanup_phase1_fixed.py

  # Execute deletion
  python cleanup_phase1_fixed.py --execute

  # Custom scripts directory
  python cleanup_phase1_fixed.py --scripts-dir /path/to/scripts --execute

Go with the Flow v3.0 Compliance:
  - R12: Legacy code isolation
  - R19: File naming conventions
  - DOC-02: Change logging
  - GOV-01: AI-assisted development standards
""",
    )

    parser.add_argument(
        "--scripts-dir",
        type=Path,
        default=Path("scripts"),
        help="Path to scripts directory (default: scripts/)",
    )

    parser.add_argument(
        "--execute", action="store_true", help="Execute deletion (default is dry-run)"
    )

    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Initialize cleaner
    cleaner = BackupFileCleaner(scripts_dir=args.scripts_dir, dry_run=not args.execute)

    # Validate environment
    if not cleaner.validate_environment():
        logger.error("Environment validation failed. Aborting.")
        return 1

    # Analyze files
    cleaner.analyze_files()

    if not cleaner.files_to_delete:
        logger.info("✓ Phase 1 complete: No cleanup needed")
        return 0

    # Save audit log
    cleaner.save_audit_log()

    # Execute deletion
    success_count, failure_count = cleaner.execute_deletion()

    if not args.execute:
        logger.info("\n" + "=" * 80)
        logger.info("NEXT STEPS:")
        logger.info("=" * 80)
        logger.info("1. Review the files listed above")
        logger.info("2. Run with --execute flag to perform deletion:")
        logger.info("   python cleanup_phase1_fixed.py --execute")
        logger.info("3. Commit changes:")
        logger.info("   git add -A")
        logger.info("   git commit -F commit_message.txt")
        logger.info("=" * 80 + "\n")

        # Save commit message
        commit_msg_file = cleaner.scripts_dir.parent / "commit_message.txt"
        with open(commit_msg_file, "w") as f:
            f.write(cleaner.generate_commit_message())
        logger.info(f"📝 Commit message saved: {commit_msg_file}")

    else:
        if failure_count > 0:
            logger.warning(f"⚠️  {failure_count} files failed to delete")
            return 1
        else:
            logger.info("✅ Phase 1 complete: All backup files deleted successfully")
            logger.info("\nCommit changes:")
            logger.info("  git add -A")
            logger.info(
                "  git commit -m 'chore: remove backup files from scripts/ (Phase 1)'"
            )
            logger.info("\nNext: Run Phase 2 (Legacy Migration)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
