#!/usr/bin/env python3
"""
One-shot helper to quarantine v13 code into legacy/ and
explicitly exclude it from pytest + mypy.

What it does:
  - Move dutchbay_v13/ -> legacy/dutchbay_v13/
  - Move tests_legacy_v13/ -> legacy/tests_legacy_v13/
  - Move tests that import `dutchbay_v13` -> legacy/tests_v13/
  - Update pytest.ini to ignore legacy/
  - Update mypy.ini to ignore legacy.*
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path


def move_dir(src: Path, dst: Path) -> None:
    if not src.exists():
        print(f"[skip] {src} does not exist")
        return
    if dst.exists():
        print(f"[warn] Destination already exists, not moving: {dst}")
        return
    print(f"[move] {src} -> {dst}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))


def move_v13_tests_by_import(repo_root: Path, legacy_root: Path) -> None:
    tests_root = repo_root / "tests"
    if not tests_root.is_dir():
        print("[skip] tests/ directory not found")
        return

    target_dir = legacy_root / "tests_v13"
    moved_any = False

    for path in tests_root.rglob("test_*.py"):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception as exc:  # pragma: no cover
            print(f"[warn] Could not read {path}: {exc}")
            continue

        if "dutchbay_v13" in text:
            target_dir.mkdir(parents=True, exist_ok=True)
            dest = target_dir / path.name
            print(f"[move] {path} -> {dest}")
            shutil.move(str(path), str(dest))
            moved_any = True

    if not moved_any:
        print("[info] No tests referencing dutchbay_v13 found under tests/")


def patch_pytest_ini(repo_root: Path) -> None:
    ini_path = repo_root / "pytest.ini"
    if not ini_path.exists():
        print("[skip] pytest.ini not found")
        return

    text = ini_path.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines(keepends=True)

    saw_addopts = False
    modified = False

    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("addopts"):
            saw_addopts = True
            if "--ignore=legacy" not in line:
                # Append ignore flag
                line = line.rstrip("\n")
                if not line.endswith(" "):
                    line += " "
                line += "--ignore=legacy\n"
                modified = True
        new_lines.append(line)

    if not saw_addopts:
        new_lines.append(
            "\n# Ensure legacy tree is ignored by pytest\naddopts = --ignore=legacy\n"
        )
        modified = True

    if modified:
        print(f"[patch] Updated {ini_path} to ignore legacy/")
        ini_path.write_text("".join(new_lines), encoding="utf-8")
    else:
        print(f"[info] pytest.ini already ignoring legacy/, no change")


def patch_mypy_ini(repo_root: Path) -> None:
    ini_path = repo_root / "mypy.ini"
    if not ini_path.exists():
        print("[skip] mypy.ini not found")
        return

    text = ini_path.read_text(encoding="utf-8", errors="ignore")

    if "[mypy-legacy.*]" in text:
        print("[info] mypy.ini already has [mypy-legacy.*] section, no change")
        return

    append_block = (
        "\n\n"
        "# Ignore type checking under legacy/ (v13 quarantined code)\n"
        "[mypy-legacy.*]\n"
        "ignore_errors = True\n"
    )

    ini_path.write_text(text + append_block, encoding="utf-8")
    print(f"[patch] Appended [mypy-legacy.*] ignore section to {ini_path}")


def main(argv: list[str]) -> int:
    repo_root = Path(__file__).resolve().parent
    legacy_root = repo_root / "legacy"

    print(f"Repo root: {repo_root}")
    legacy_root.mkdir(exist_ok=True)

    # 1) Move dutchbay_v13/ into legacy/
    move_dir(repo_root / "dutchbay_v13", legacy_root / "dutchbay_v13")

    # 2) Move tests_legacy_v13/ into legacy/
    move_dir(repo_root / "tests_legacy_v13", legacy_root / "tests_legacy_v13")

    # 3) Move any tests that import dutchbay_v13 into legacy/tests_v13
    move_v13_tests_by_import(repo_root, legacy_root)

    # 4) Patch pytest.ini to ignore legacy/
    patch_pytest_ini(repo_root)

    # 5) Patch mypy.ini to ignore legacy.*
    patch_mypy_ini(repo_root)

    print("\nDone. Suggested next steps:")
    print("  - git status  # review moved files and ini patches")
    print("  - pytest      # confirm v14 test suite still passes")
    print("  - mypy        # optional, to ensure nothing unexpected changed")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

    