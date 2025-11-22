#!/usr/bin/env python3
"""
Create a clean ZIP of the current repo, excluding:
  - Git / VCS directories
  - Common cache dirs
  - Virtualenvs (venv, .venv311)
  - Any directory literally named "old models"

Usage:
  python make_clean_zip.py                # outputs project_clean.zip
  python make_clean_zip.py my_archive.zip # custom zip name
"""

import os
import sys
import zipfile
from pathlib import Path
from typing import Iterable, Set

# Directories to skip by exact name
EXCLUDE_DIRS: Set[str] = {
    ".git",
    ".github",
    ".mypy_cache",
    ".pytest_cache",
    "__pycache__",
    ".idea",
    ".vscode",
    "venv",
    ".venv",
    ".venv311",
    "old models",
}

# Files to skip by exact name (rare but handy)
EXCLUDE_FILES: Set[str] = {
    ".DS_Store",
}

def should_skip_dir(dir_name: str) -> bool:
    """
    Decide whether to skip a directory based on its name.
    """
    # Normalize to plain name (no path)
    name = dir_name

    # Exact matches (strong rule)
    if name in EXCLUDE_DIRS:
        return True

    # Add any additional pattern-style rules here if needed.
    return False


def should_skip_file(file_name: str) -> bool:
    """
    Decide whether to skip a file based on its name.
    """
    name = file_name
    if name in EXCLUDE_FILES:
        return True

    # Add any additional pattern-style rules here if needed.
    return False


def iter_files(root: Path) -> Iterable[Path]:
    """
    Yield all files under root, applying directory and file exclusions.
    """
    for dirpath, dirnames, filenames in os.walk(root):
        # dirpath is a string; turn into Path for convenience
        dir_path = Path(dirpath)

        # In-place prune of dirnames so os.walk does not descend into them
        pruned = []
        for d in dirnames:
            if should_skip_dir(d):
                # Skip this directory (and its subtree)
                continue
            pruned.append(d)
        dirnames[:] = pruned

        # Yield files that are not excluded
        for fn in filenames:
            if should_skip_file(fn):
                continue
            yield dir_path / fn


def make_zip(root: Path, zip_path: Path) -> None:
    """
    Create a ZIP file at zip_path containing the tree under root,
    applying exclusions.
    """
    root = root.resolve()
    zip_path = zip_path.resolve()

    print(f"Zipping from root: {root}")
    print(f"Creating archive: {zip_path}")
    print("Excluding dirs:", ", ".join(sorted(EXCLUDE_DIRS)))
    print("Excluding files:", ", ".join(sorted(EXCLUDE_FILES)) or "(none)")

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file_path in iter_files(root):
            # Store paths relative to the root in the archive
            rel_path = file_path.relative_to(root)
            zf.write(file_path, rel_path)
    print("Done.")


def main(argv: list[str]) -> int:
    cwd = Path.cwd()

    if len(argv) >= 2:
        zip_name = argv[1]
    else:
        zip_name = "project_clean.zip"

    zip_path = cwd / zip_name

    # Safety: avoid zipping the zip if it already exists inside the tree
    if zip_path.exists():
        print(f"Removing existing archive at: {zip_path}")
        zip_path.unlink()

    make_zip(root=cwd, zip_path=zip_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

    