#!/usr/bin/env python3
"""
gh_tools.py – Small helper CLI for Git + GitHub (`gh`) automation
for the DutchBay_EPC_Model repo.

Subcommands
-----------
- status
    Show repo root, branch, and short git status.

- close-issues
    Close one or more GitHub issues via `gh issue close`.

- commit
    Bump VERSION, inject a CHANGELOG entry, commit, and push.
    Includes first-push handling (auto `--set-upstream`).
"""

from __future__ import annotations

import argparse
import datetime as _dt
import subprocess
import sys
from pathlib import Path
from typing import List, Optional


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------


def run(
    cmd: List[str],
    *,
    check: bool = True,
    cwd: Optional[Path] = None,
    capture: bool = False,
) -> subprocess.CompletedProcess:
    """
    Wrapper around subprocess.run that prints the command first.

    If capture=True, returns the CompletedProcess with stdout captured.
    Otherwise, returns the CompletedProcess with normal stdout/stderr.
    """
    display = " ".join(cmd)
    print(f"\n$ {display}")
    kwargs = {
        "cwd": str(cwd) if cwd is not None else None,
        "check": check,
        "text": True,
    }
    if capture:
        kwargs["stdout"] = subprocess.PIPE
        kwargs["stderr"] = subprocess.STDOUT
    proc = subprocess.run(cmd, **kwargs)  # type: ignore[arg-type]
    return proc


def get_repo_root() -> Path:
    """Return the git repo root using `git rev-parse --show-toplevel`."""
    proc = run(["git", "rev-parse", "--show-toplevel"], capture=True)
    if proc.returncode != 0 or not proc.stdout:
        print("ERROR: Could not determine git repo root.", file=sys.stderr)
        sys.exit(proc.returncode or 1)
    root = Path(proc.stdout.strip())
    print(f"Repo root: {root}")
    return root


# ---------------------------------------------------------------------------
# Status command
# ---------------------------------------------------------------------------


def cmd_status(_args: argparse.Namespace) -> None:
    """Show repo root and short git status."""
    root = get_repo_root()
    run(["git", "status", "-sb"], cwd=root, check=False)


# ---------------------------------------------------------------------------
# Close issues command
# ---------------------------------------------------------------------------


def cmd_close_issues(args: argparse.Namespace) -> None:
    """
    Close one or more GitHub issues via `gh issue close`.

    Usage examples:
        python gh_tools.py close-issues 12 34 56
        python gh_tools.py close-issues --comment "Done in v0.2.0" 42
    """
    root = get_repo_root()

    if not args.issues:
        print("No issue numbers provided. Nothing to do.", file=sys.stderr)
        return

    base_cmd = ["gh", "issue", "close"]
    for issue in args.issues:
        cmd = base_cmd + [str(issue)]
        if args.comment:
            cmd += ["--comment", args.comment]
        run(cmd, cwd=root, check=True)


# ---------------------------------------------------------------------------
# CHANGELOG / VERSION helpers
# ---------------------------------------------------------------------------


def update_version_file(root: Path, version: str) -> None:
    """Overwrite the VERSION file at repo root with the given version."""
    version_path = root / "VERSION"
    print(f"Updating {version_path} -> {version}")
    version_path.write_text(version.strip() + "\n", encoding="utf-8")


def inject_changelog_entry(root: Path, version: str, message: str) -> None:
    """
    Inject a minimal vX.Y.Z section into CHANGELOG.md.

    Strategy:
      - If CHANGELOG.md exists: insert a new section near the top.
      - If not: create a simple changelog with a header + entry.
    """
    changelog_path = root / "CHANGELOG.md"
    today = _dt.date.today().isoformat()
    header_line = f"## v{version} - {today}\n"
    body_line = f"- {message.strip() or 'Update recorded by gh_tools.py'}\n"

    new_block = f"\n{header_line}\n{body_line}\n"

    if not changelog_path.exists():
        print(f"{changelog_path} not found. Creating a new one.")
        content = "# Changelog\n" + new_block
        changelog_path.write_text(content, encoding="utf-8")
        return

    original = changelog_path.read_text(encoding="utf-8")

    # If there's an explicit "Unreleased" header, insert after it.
    marker = "## [Unreleased]"
    if marker in original:
        before, after = original.split(marker, 1)
        updated = f"{before}{marker}\n{new_block}{after}"
        print(f"Injecting v{version} section into CHANGELOG after [Unreleased].")
    else:
        # Otherwise, put our new block right after the first header if present.
        lines = original.splitlines(keepends=True)
        if lines and lines[0].startswith("# "):
            updated = "".join(lines[:1]) + new_block + "".join(lines[1:])
        else:
            updated = new_block + original

        print(f"Injecting v{version} section into CHANGELOG near the top.")

    changelog_path.write_text(updated, encoding="utf-8")


# ---------------------------------------------------------------------------
# Commit command
# ---------------------------------------------------------------------------


def cmd_commit(args: argparse.Namespace) -> None:
    """
    Commit helper:

      * Update VERSION
      * Inject a CHANGELOG entry
      * git add -A
      * git commit -m "<message> (vX.Y.Z)"
      * git push (auto-sets upstream on first push)

    Examples:
      python gh_tools.py commit --version 0.2.0 --message "v14 CI baseline"
      python gh_tools.py commit -v 0.2.1 -m "Tighten analytics tests"
    """
    root = get_repo_root()

    # Show current short status first
    run(["git", "status", "-sb"], cwd=root, check=False)

    version = (args.version or "").strip()
    if not version:
        print("ERROR: --version is required for commit.", file=sys.stderr)
        sys.exit(1)

    message = (args.message or "").strip()
    if not message:
        message = "Automated commit"

    if args.dry_run:
        print("\n[DRY RUN] Would update VERSION, CHANGELOG, add, commit, push.")
        print(f"Version: {version}")
        print(f"Message: {message}")
        return

    # 1) Update VERSION
    update_version_file(root, version)

    # 2) Inject CHANGELOG entry
    inject_changelog_entry(root, version, message)

    # 3) Stage everything
    run(["git", "add", "-A"], cwd=root, check=True)

    # 4) Commit
    full_msg = f"{message} (v{version})"
    run(["git", "commit", "-m", full_msg], cwd=root, check=True)

    # 5) Push with auto upstream handling
    try:
        push_cmd = ["git", "push"]
        if args.remote:
            push_cmd.append(args.remote)
            if args.branch:
                push_cmd.append(args.branch)
        run(push_cmd, check=True, cwd=root)
    except subprocess.CalledProcessError:
        # Likely "no upstream branch" – fix automatically.
        print(
            "git push failed – attempting to set upstream for current branch...",
            file=sys.stderr,
        )
        # Get current branch name
        proc = run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            check=True,
            cwd=root,
            capture=True,
        )
        current_branch = (proc.stdout or "").strip()
        if not current_branch or current_branch == "HEAD":
            print(
                "ERROR: Could not determine current branch. "
                "Please push manually with:\n"
                "  git push --set-upstream origin <branch>",
                file=sys.stderr,
            )
            sys.exit(1)

        remote = args.remote or "origin"
        branch = args.branch or current_branch
        print(f"Setting upstream: {remote} {branch}")
        run(
            ["git", "push", "--set-upstream", remote, branch],
            check=True,
            cwd=root,
        )

    print("\n✅ Commit + push complete.")


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Helper tools for Git/GitHub automation (DutchBay EPC v14)."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # status
    p_status = subparsers.add_parser(
        "status", help="Show repo root and short git status."
    )
    p_status.set_defaults(func=cmd_status)

    # close-issues
    p_close = subparsers.add_parser(
        "close-issues", help="Close one or more issues via `gh issue close`."
    )
    p_close.add_argument(
        "issues",
        nargs="*",
        help="Issue numbers to close (e.g. 12 34 56).",
    )
    p_close.add_argument(
        "--comment",
        help="Optional comment to add when closing issues.",
    )
    p_close.set_defaults(func=cmd_close_issues)

    # commit
    p_commit = subparsers.add_parser(
        "commit",
        help=(
            "Update VERSION + CHANGELOG, git add/commit, and push "
            "(with auto upstream)."
        ),
    )
    p_commit.add_argument(
        "-v",
        "--version",
        required=True,
        help="Version string to write into VERSION (e.g. 0.2.0).",
    )
    p_commit.add_argument(
        "-m",
        "--message",
        help="Commit message (without version suffix).",
    )
    p_commit.add_argument(
        "--remote",
        help="Git remote name (default: origin).",
    )
    p_commit.add_argument(
        "--branch",
        help="Branch to push (default: current branch).",
    )
    p_commit.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without modifying anything.",
    )
    p_commit.set_defaults(func=cmd_commit)

    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

    