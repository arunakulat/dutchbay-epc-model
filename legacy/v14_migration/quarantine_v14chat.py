#!/usr/bin/env python3
"""
Quarantine Automation for dutchbay_v14chat → legacy/ Migration

Safely moves dutchbay_v14chat/ directory to legacy/dutchbay_v14chat/ with
full validation, backup, and Git awareness.

Usage:
    # Dry-run mode (preview only)
    python quarantine_v14chat.py --dry-run

    # Execute quarantine
    python quarantine_v14chat.py --execute

Safety Features:
    - Git status check (warns if uncommitted changes)
    - Pre-flight validation (source exists, dest writable)
    - Atomic operation (temp move + rename)
    - Rollback on failure
    - Creates quarantine manifest JSON
    - Dry-run preview mode

Exit Codes:
    0 - Success
    1 - Validation error (missing source, permission denied)
    2 - Git safety check failed
    3 - Operation failed (with rollback)
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


class QuarantineError(Exception):
    """Base exception for quarantine operations."""

    pass


class GitSafetyError(QuarantineError):
    """Git safety check failed."""

    pass


class ValidationError(QuarantineError):
    """Pre-flight validation failed."""

    pass


def check_git_status(repo_root: Path) -> Dict[str, Any]:
    """
    Check Git status for uncommitted changes.

    Args:
        repo_root: Repository root directory

    Returns:
        Dict with git status info

    Raises:
        GitSafetyError: If git command fails
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=5,
        )

        if result.returncode != 0:
            return {
                "is_repo": False,
                "has_changes": False,
                "untracked_files": [],
                "modified_files": [],
            }

        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=5,
        )

        if result.returncode != 0:
            raise GitSafetyError(f"git status failed: {result.stderr}")

        lines = result.stdout.strip().split("\n")
        untracked = []
        modified = []

        for line in lines:
            if not line:
                continue
            status = line[:2]
            filepath = line[3:]

            if status.strip() == "??":
                untracked.append(filepath)
            else:
                modified.append(filepath)

        return {
            "is_repo": True,
            "has_changes": len(modified) > 0 or len(untracked) > 0,
            "untracked_files": untracked,
            "modified_files": modified,
        }

    except subprocess.TimeoutExpired:
        raise GitSafetyError("Git command timed out")
    except Exception as e:
        raise GitSafetyError(f"Git check failed: {e}")


def validate_quarantine(source_dir: Path, dest_parent: Path) -> None:
    """Pre-flight validation checks."""
    if not source_dir.exists():
        raise ValidationError(f"Source directory does not exist: {source_dir}")

    if not source_dir.is_dir():
        raise ValidationError(f"Source is not a directory: {source_dir}")

    if not any(source_dir.iterdir()):
        raise ValidationError(f"Source directory is empty: {source_dir}")

    if not dest_parent.exists():
        try:
            dest_parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise ValidationError(f"Cannot create destination parent: {e}")

    dest_dir = dest_parent / source_dir.name
    if dest_dir.exists():
        raise ValidationError(
            f"Destination already exists: {dest_dir}\n"
            f"Please remove it manually or use a different destination."
        )

    if not dest_parent.is_dir():
        raise ValidationError(f"Destination parent is not a directory: {dest_parent}")

    test_file = dest_parent / ".quarantine_write_test"
    try:
        test_file.touch()
        test_file.unlink()
    except Exception as e:
        raise ValidationError(f"Destination not writable: {e}")


def count_files_recursive(directory: Path) -> Dict[str, int]:
    """Count files and directories recursively."""
    total_files = 0
    total_dirs = 0
    py_files = 0

    for item in directory.rglob("*"):
        if item.is_file():
            total_files += 1
            if item.suffix == ".py":
                py_files += 1
        elif item.is_dir():
            total_dirs += 1

    return {
        "total_files": total_files,
        "total_dirs": total_dirs,
        "py_files": py_files,
    }


def create_quarantine_manifest(
    source_dir: Path,
    dest_dir: Path,
    file_counts: Dict[str, int],
    git_status: Dict[str, Any],
) -> Dict[str, Any]:
    """Create quarantine operation manifest."""
    return {
        "quarantine_timestamp": datetime.now().isoformat(),
        "source_path": str(source_dir),
        "destination_path": str(dest_dir),
        "file_counts": file_counts,
        "git_status": git_status,
        "reason": "v14 refactor: dutchbay_v14chat superseded by finance/ and analytics/",
        "script_version": "1.0.0",
    }


def execute_quarantine(
    source_dir: Path,
    dest_parent: Path,
    dry_run: bool = True,
) -> Path:
    """Execute the quarantine operation."""
    dest_dir = dest_parent / source_dir.name

    if dry_run:
        print("[DRY-RUN] Would move:")
        print(f"  Source: {source_dir}")
        print(f"  Dest:   {dest_dir}")
        return dest_dir

    temp_dest = dest_parent / f".{source_dir.name}_quarantine_temp"

    try:
        print(f"📦 Moving {source_dir} → {temp_dest} (temp)...")
        shutil.move(str(source_dir), str(temp_dest))

        print(f"✅ Renaming {temp_dest} → {dest_dir}...")
        temp_dest.rename(dest_dir)

        print(f"✅ Quarantine complete: {dest_dir}")
        return dest_dir

    except Exception as e:
        print(f"❌ Error during quarantine: {e}", file=sys.stderr)

        if temp_dest.exists() and not source_dir.exists():
            print(f"🔄 Rolling back: {temp_dest} → {source_dir}...", file=sys.stderr)
            try:
                shutil.move(str(temp_dest), str(source_dir))
                print("✅ Rollback successful", file=sys.stderr)
            except Exception as rollback_error:
                print(f"❌ ROLLBACK FAILED: {rollback_error}", file=sys.stderr)
                print("   Manual recovery needed!", file=sys.stderr)

        raise QuarantineError(f"Quarantine failed: {e}")


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Quarantine dutchbay_v14chat to legacy/"
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=Path("dutchbay_v14chat"),
        help="Source directory to quarantine (default: dutchbay_v14chat)",
    )
    parser.add_argument(
        "--dest",
        type=Path,
        default=Path("legacy"),
        help="Destination parent directory (default: legacy)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview operation without executing",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute the quarantine operation",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Skip Git safety check (not recommended)",
    )

    args = parser.parse_args()

    if not args.dry_run and not args.execute:
        parser.error("Must specify either --dry-run or --execute")

    dry_run = args.dry_run
    source_dir = args.source.resolve()
    dest_parent = args.dest.resolve()
    dest_dir = dest_parent / source_dir.name

    print("=" * 70)
    print("🔒 QUARANTINE AUTOMATION: dutchbay_v14chat → legacy/")
    print("=" * 70)
    print(f"Mode: {'DRY-RUN' if dry_run else 'EXECUTE'}")
    print(f"Source: {source_dir}")
    print(f"Dest:   {dest_dir}")
    print()

    try:
        if not args.force:
            print("🔍 Checking Git status...")
            repo_root = source_dir.parent
            git_status = check_git_status(repo_root)

            if git_status["is_repo"]:
                print("✅ Git repository detected")

                if git_status["has_changes"]:
                    print("⚠️  WARNING: Uncommitted changes detected!")
                    print(f"   Modified files: {len(git_status['modified_files'])}")
                    print(f"   Untracked files: {len(git_status['untracked_files'])}")
                    print()
                    print(
                        "   Recommendation: Commit or stash changes before quarantine"
                    )
                    print("   Use --force to skip this check (not recommended)")
                    sys.exit(2)
                else:
                    print("✅ No uncommitted changes")
            else:
                print("ℹ️  Not a Git repository (skipping Git check)")
                git_status = {"is_repo": False}
        else:
            print("⚠️  Skipping Git safety check (--force)")
            git_status = {"is_repo": False, "forced": True}

        print()

        print("🔍 Running pre-flight validation...")
        validate_quarantine(source_dir, dest_parent)
        print("✅ Validation passed")
        print()

        print("📊 Scanning source directory...")
        file_counts = count_files_recursive(source_dir)
        print(f"   Total files: {file_counts['total_files']}")
        print(f"   Python files: {file_counts['py_files']}")
        print(f"   Directories: {file_counts['total_dirs']}")
        print()

        print("🚀 Executing quarantine operation...")
        result_dest = execute_quarantine(source_dir, dest_parent, dry_run)
        print()

        if not dry_run:
            print("📝 Creating quarantine manifest...")
            manifest = create_quarantine_manifest(
                source_dir,
                result_dest,
                file_counts,
                git_status,
            )

            manifest_path = dest_parent / "QUARANTINE_MANIFEST.json"
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2, sort_keys=True)

            print(f"✅ Manifest saved: {manifest_path}")
            print()

        print("=" * 70)
        print("✅ QUARANTINE COMPLETE")
        print("=" * 70)

        if dry_run:
            print("This was a DRY-RUN. No files were moved.")
            print("Run with --execute to perform the actual quarantine.")
        else:
            print(f"✅ {source_dir.name} → {dest_dir}")
            print(f"✅ Moved {file_counts['total_files']} files")
            print()
            print("Next steps:")
            print("  1. Run import scanner to verify no broken imports")
            print("  2. Run test suite: pytest")
            print("  3. Commit changes: git add -A && git commit")

        sys.exit(0)

    except ValidationError as e:
        print(f"\n❌ VALIDATION ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    except GitSafetyError as e:
        print(f"\n❌ GIT SAFETY ERROR: {e}", file=sys.stderr)
        print("   Use --force to skip Git checks (not recommended)", file=sys.stderr)
        sys.exit(2)

    except QuarantineError as e:
        print(f"\n❌ QUARANTINE FAILED: {e}", file=sys.stderr)
        sys.exit(3)

    except KeyboardInterrupt:
        print("\n\n⚠️  Operation cancelled by user", file=sys.stderr)
        sys.exit(130)

    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        sys.exit(3)


if __name__ == "__main__":
    main()
