import os
import sys
import zipfile
from pathlib import Path
from typing import Iterable, Set


# Directories to skip entirely
SKIP_DIR_NAMES: Set[str] = {
    ".git",
    ".idea",
    ".mypy_cache",
    ".pytest_cache",
    ".venv",
    ".venv311",
    ".vscode",
    "__pycache__",
    "venv",
    "old models",
}

# File extensions to include (lowercase, with leading dot)
ALLOWED_EXTS: Set[str] = {
    ".py",
    ".ini",
    ".md",
    ".toml",
    ".txt",
    ".json",
    ".yaml",
    ".yml",
    ".pdf",
    ".csv",
    ".xls",
    ".xlsx",
    ".xlsm",
}


def should_skip_dir(dir_name: str) -> bool:
    """
    Return True if this directory should be skipped during traversal.

    Rules:
      - skip if name is in SKIP_DIR_NAMES
      - skip if name starts with '.' and is not '.github'
    """
    if dir_name in SKIP_DIR_NAMES:
        return True
    if dir_name.startswith(".") and dir_name != ".github":
        return True
    return False


def should_include_file(root: Path, name: str) -> bool:
    """
    Decide whether to include a file based on extension and location.
    """
    ext = Path(name).suffix.lower()

    # Always require the extension to be in ALLOWED_EXTS
    if ext not in ALLOWED_EXTS:
        return False

    # No extra rules needed here: .github will be traversed,
    # and workflows/*.yml will be picked up by the extension check.
    return True


def iter_files(root: Path) -> Iterable[Path]:
    """
    Yield all files under root that match ALLOWED_EXTS,
    respecting the directory skip rules.
    """
    for current_root, dirs, files in os.walk(root):
        current_root_path = Path(current_root)

        # Filter directories in-place for os.walk
        filtered_dirs = []
        for d in dirs:
            if should_skip_dir(d):
                continue
            filtered_dirs.append(d)
        dirs[:] = filtered_dirs

        # Files
        for f in files:
            if should_include_file(current_root_path, f):
                yield current_root_path / f


def make_zip(root: Path, zip_path: Path) -> None:
    """
    Create a zip archive at zip_path containing allowed files under root.
    """
    print(f"Zipping from root: {root}")
    print(f"Creating archive: {zip_path}")
    print(f"Excluding dirs: {', '.join(sorted(SKIP_DIR_NAMES))}")
    print(f"Including extensions: {', '.join(sorted(ALLOWED_EXTS))}")
    print()

    root = root.resolve()
    zip_path = zip_path.resolve()

    count = 0
    with zipfile.ZipFile(
        zip_path,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        allowZip64=True,
    ) as zf:
        for file_path in iter_files(root):
            rel_path = file_path.relative_to(root)
            zf.write(file_path, rel_path.as_posix())
            count += 1
            if count % 100 == 0:
                print(f"  Added {count} files... last: {rel_path}")

    print(f"\nDone. Total files added: {count}")


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(f"Usage: {argv[0]} <output_zip_name>", file=sys.stderr)
        return 1

    zip_name = argv[1]
    root = Path.cwd()
    zip_path = root / zip_name

    make_zip(root=root, zip_path=zip_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
