#!/usr/bin/env python3
"""
Small helper CLI around `git` + `gh`.

Existing behaviour:
  - Close GitHub issues via `gh issue close`.

New behaviour:
  - Versioned commit routine:
      * show git status
      * inject VERSION + CHANGELOG entry
      * git add/commit/push
      * show `gh status`

Usage examples
--------------

Close an issue:

    python gh_tools.py close-issue --number 123 --repo yourorg/DutchBay_EPC_Model

Commit with versioning + docs injection:

    python gh_tools.py commit --version 0.2.0 --message "v14 CI baseline"

(Assumes `git` and `gh` are already configured in this repo.)
"""

import argparse
import subprocess
import sys
from pathlib import Path
from datetime import date
from typing import List, Optional


# ---------------------------------------------------------------------------
# Core subprocess helpers
# ---------------------------------------------------------------------------

def run(
    cmd: List[str],
    check: bool = True,
    capture: bool = False,
    cwd: Optional[Path] = None,
) -> subprocess.CompletedProcess:
    """Run a shell command with sane defaults."""
    kwargs = {
        "check": check,
        "text": True,
    }
    if capture:
        kwargs["stdout"] = subprocess.PIPE
        kwargs["stderr"] = subprocess.PIPE
    if cwd is not None:
        kwargs["cwd"] = str(cwd)

    print(f"\n$ {' '.join(cmd)}")
    proc = subprocess.run(cmd, **kwargs)
    if capture:
        if proc.stdout:
            print(proc.stdout.strip())
        if proc.stderr:
            print(proc.stderr.strip(), file=sys.stderr)
    return proc


def get_repo_root() -> Path:
    """Return the git repo root as a Path."""
    proc = run(["git", "rev-parse", "--show-toplevel"], capture=True)
    root = proc.stdout.strip() if proc.stdout else ""
    if not root:
        print("ERROR: Not inside a git repository.", file=sys.stderr)
        sys.exit(1)
    return Path(root)


# ---------------------------------------------------------------------------
# Existing functionality: close GitHub issues
# ---------------------------------------------------------------------------

def cmd_close_issue(args: argparse.Namespace) -> None:
    """
    Close a GitHub issue by number using `gh issue close`.

    Requires:
      - `gh` CLI installed and authenticated
      - repo is accessible to the token used
    """
    cmd = ["gh", "issue", "close", str(args.number)]
    if args.repo:
        cmd.extend(["--repo", args.repo])
    if args.comment:
        cmd.extend(["--comment", args.comment])

    run(cmd, check=True)


# ---------------------------------------------------------------------------
# New functionality: versioned commit routine
# ---------------------------------------------------------------------------

def update_version_file(root: Path, version: str) -> None:
    """
    Write the version string into a VERSION file at repo root.

    If the file exists, it is overwritten.
    """
    version_file = root / "VERSION"
    print(f"Updating {version_file} -> {version}")
    version_file.write_text(f"{version}\n", encoding="utf-8")


def ensure_changelog_section(root: Path, version: str, message: str) -> None:
    """
    Ensure CHANGELOG.md has a section for the given version.

    Simple rules:
      - If file doesn't exist, create a minimal one.
      - If a header '## v{version}' already exists, do nothing.
      - Otherwise, append a new section at the top (after title if present).
    """
    changelog = root / "CHANGELOG.md"
    today = date.today().isoformat()
    header = f"## v{version} – {today}"
    bullet = f"- {message or 'Automated commit via gh_tools'}"

    if not changelog.exists():
        print(f"{changelog} not found; creating a new one.")
        content = [
            "# Changelog",
            "",
            header,
            bullet,
            "",
        ]
        changelog.write_text("\n".join(content) + "\n", encoding="utf-8")
        return

    text = changelog.read_text(encoding="utf-8")
    if header in text:
        print(f"CHANGELOG already has section for v{version}, leaving as-is.")
        return

    lines = text.splitlines()

    # Find insertion point: after first line that starts with '#'
    insert_idx = 0
    if lines and lines[0].startswith("#"):
        # skip title + following blank line if present
        insert_idx = 1
        if len(lines) > 1 and not lines[1].strip():
            insert_idx = 2

    new_section = [
        header,
        bullet,
        "",
    ]

    updated_lines = lines[:insert_idx] + new_section + lines[insert_idx:]
    print(f"Injecting v{version} section into CHANGELOG.md")
    changelog.write_text("\n".join(updated_lines) + "\n", encoding="utf-8")


def cmd_commit(args: argparse.Namespace) -> None:
    """
    Versioned commit routine:

      * show `git status -sb`
      * update VERSION
      * inject CHANGELOG entry
      * git add -A
      * git commit -m "…"
      * git push
      * gh status
    """
    root = get_repo_root()
    print(f"Repo root: {root}")

    # 1) Show status
    run(["git", "status", "-sb"], check=False, capture=False, cwd=root)

    version = args.version.strip()
    if not version:
        print("ERROR: --version is required.", file=sys.stderr)
        sys.exit(1)

    # 2) Documentation injections
    if not args.no_docs:
        update_version_file(root, version)
        ensure_changelog_section(root, version, args.message or "")

    # 3) Stage all changes (you can narrow this if needed later)
    run(["git", "add", "-A"], check=True, cwd=root)

    # 4) Compose commit message
    base_msg = args.message or "Automated commit"
    commit_msg = f"{base_msg} (v{version})"

    # 5) Commit
    try:
        run(["git", "commit", "-m", commit_msg], check=True, cwd=root)
    except subprocess.CalledProcessError as exc:
        print(
            "git commit failed (possibly no changes to commit). "
            "Aborting before push.",
            file=sys.stderr,
        )
        sys.exit(exc.returncode)

    # 6) Push (use current branch + upstream)
    push_cmd = ["git", "push"]
    if args.remote:
        push_cmd.append(args.remote)
        if args.branch:
            push_cmd.append(args.branch)
    run(push_cmd, check=True, cwd=root)

    # 7) Show `gh status` for sanity (don't fail build if this breaks)
    try:
        run(["gh", "status"], check=False, cwd=root)
    except FileNotFoundError:
        print("WARNING: `gh` not found; skipping `gh status`.", file=sys.stderr)


# ---------------------------------------------------------------------------
# CLI wiring
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Helper CLI for GitHub + git workflows around DutchBay EPC."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # close-issue
    p_close = sub.add_parser("close-issue", help="Close a GitHub issue via `gh issue close`.")
    p_close.add_argument("--number", type=int, required=True, help="Issue number.")
    p_close.add_argument(
        "--repo",
        type=str,
        default=None,
        help="GitHub repo (e.g. owner/repo). If omitted, uses current repo.",
    )
    p_close.add_argument(
        "--comment",
        type=str,
        default=None,
        help="Optional closing comment to add to the issue.",
    )
    p_close.set_defaults(func=cmd_close_issue)

    # commit
    p_commit = sub.add_parser(
        "commit",
        help="Versioned commit routine: inject VERSION + CHANGELOG, commit and push.",
    )
    p_commit.add_argument(
        "--version",
        required=True,
        help="Version string to record (e.g. 0.2.0).",
    )
    p_commit.add_argument(
        "--message",
        "-m",
        default=None,
        help="Base commit message (version will be appended).",
    )
    p_commit.add_argument(
        "--remote",
        default=None,
        help="Optional git remote (default: use current branch's upstream).",
    )
    p_commit.add_argument(
        "--branch",
        default=None,
        help="Optional branch name when used with --remote.",
    )
    p_commit.add_argument(
        "--no-docs",
        action="store_true",
        help="Skip VERSION + CHANGELOG updates (just commit whatever is staged).",
    )
    p_commit.set_defaults(func=cmd_commit)

    return parser


def main(argv: Optional[list] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()

    