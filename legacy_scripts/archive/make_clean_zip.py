#!/usr/bin/env python3
"""
make_clean_zip.py

Create a clean, annotated archive of the DutchBay EPC Model repo.

What it does
------------
Given an output base name, this script will:

  • Walk the repository tree from a chosen root (default: current directory).
  • Exclude virtualenvs, caches, VCS metadata, IDE config, and other junk.
  • Include only whitelisted file extensions, capped by a max file size.
  • Create:
      <output_name>.zip   – compressed archive
      <output_name>.json  – manifest describing the files
      <output_name>.txt   – human-readable concatenated snapshot

Usage
-----
From repo root:

    python scripts/make_clean_zip.py DutchBay_EPC_20251203_1630

Optional flags (order flexible):

    --root PATH         Override root directory to zip (default: CWD)
    --no-manifest       Skip JSON manifest
    --no-snapshot       Skip concatenated snapshot
"""

from __future__ import annotations

import json
import os
import sys
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Set, Tuple

# ---------------------------------------------------------------------------
# Configuration – directory & file filters
# ---------------------------------------------------------------------------

SKIP_DIR_NAMES: Set[str] = {
    ".git",
    ".github",
    ".idea",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    ".venv311",
    ".vscode",
    "__pycache__",
    "venv",
    "env",
    ".env",
    "node_modules",
    "old models",
    "dist",
    "htmlcov",
}

ALLOWED_EXTS: Set[str] = {
    ".py",
    ".ini",
    ".md",
    ".toml",
    ".txt",
    ".json",
    ".yaml",
    ".yml",
    ".csv",
    ".xlsx",
}

# Default maximum size for any single file to be included in the archive
MAX_FILE_SIZE = 2_000_000  # 2 MB

FilePair = Tuple[Path, Path]  # (abs_path, rel_path)


# ---------------------------------------------------------------------------
# Helpers: filtering & iteration
# ---------------------------------------------------------------------------


def _human_bytes(num_bytes: int) -> str:
    """Return a human-friendly representation of a byte size."""
    units: Sequence[str] = ("B", "KB", "MB", "GB", "TB")
    value = float(num_bytes)
    for unit in units:
        if value < 1024.0 or unit == units[-1]:
            return f"{value:,.1f} {unit}"
        value /= 1024.0
    return f"{num_bytes} B"


def should_skip_dir(dir_name: str) -> bool:
    """Return True if the directory should be skipped entirely."""
    if dir_name in SKIP_DIR_NAMES:
        return True
    if dir_name.startswith("."):
        return True
    lowered = dir_name.lower()
    if "venv" in lowered:
        return True
    if dir_name.endswith("_cache") or dir_name.endswith(".cache"):
        return True
    return False


def should_include_file(root: Path, name: str) -> bool:
    """Return True if the file should be included based on extension & size."""
    file_path = root / name

    # Exclude dotfiles directly
    if name.startswith("."):
        return False

    ext = file_path.suffix.lower()
    if ext not in ALLOWED_EXTS:
        return False

    try:
        size = file_path.stat().st_size
    except (OSError, FileNotFoundError):
        return False

    if size > MAX_FILE_SIZE:
        return False

    return True


def iter_files(root: Path) -> Iterable[Path]:
    """
    Yield absolute paths for all files to include beneath 'root'.

    This uses os.walk with in-place filtering of the 'dirs' list to avoid
    descending into skipped directories.
    """
    for current_root, dirs, files in os.walk(root):
        current_root_path = Path(current_root)

        # Filter directories in-place so os.walk won't descend into them
        dirs[:] = [d for d in dirs if not should_skip_dir(d)]

        for name in files:
            if should_include_file(current_root_path, name):
                yield current_root_path / name


# ---------------------------------------------------------------------------
# Manifest + snapshot generation
# ---------------------------------------------------------------------------


def create_manifest(
    root: Path, file_list: List[FilePair], zip_path: Path
) -> Dict[str, Any]:
    """Build a JSON-serializable manifest describing the archive contents."""
    manifest: Dict[str, Any] = {
        "metadata": {
            "created_at": datetime.now().isoformat(),
            "root_directory": str(root),
            "zip_file": zip_path.name,
            "total_files": len(file_list),
            "zip_size_bytes": zip_path.stat().st_size if zip_path.exists() else 0,
        },
        "filters": {
            "excluded_directories": sorted(SKIP_DIR_NAMES),
            "included_extensions": sorted(ALLOWED_EXTS),
            "max_file_size_bytes": MAX_FILE_SIZE,
        },
        "files": [],
    }

    total_size = 0
    for abs_path, rel_path in file_list:
        stat = abs_path.stat()
        total_size += stat.st_size

        manifest["files"].append(
            {
                "path": rel_path.as_posix(),
                "size_bytes": stat.st_size,
                "size_human": _human_bytes(stat.st_size),
                "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "extension": abs_path.suffix.lower(),
            }
        )

    manifest["metadata"]["total_uncompressed_bytes"] = total_size
    manifest["metadata"]["total_uncompressed_human"] = _human_bytes(total_size)

    zip_size = manifest["metadata"]["zip_size_bytes"]
    if zip_size > 0 and total_size > 0:
        ratio = (1 - zip_size / total_size) * 100
        manifest["metadata"]["compression_ratio_percent"] = round(ratio, 2)
    else:
        manifest["metadata"]["compression_ratio_percent"] = 0.0

    return manifest


def save_manifest(manifest: Dict[str, Any], manifest_path: Path) -> None:
    """Write manifest JSON to disk."""
    manifest_path = manifest_path.resolve()
    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    print(f"Manifest saved: {manifest_path}")


def create_concatenated_snapshot(
    root: Path,
    file_list: List[FilePair],
    output_path: Path,
) -> None:
    """
    Create a concatenated, human-readable snapshot of all included files.

    Text-like files are embedded with BEGIN/END fences; data-heavy files such
    as CSV/XLSX are recorded by size only.
    """
    output_path = output_path.resolve()
    print(f"Creating concatenated snapshot: {output_path}")

    header_lines = [
        "# DutchBay EPC Model - Code Snapshot",
        f"Generated: {datetime.now().isoformat()}",
        f"Total Files: {len(file_list)}",
        f"Root: {root}",
        "",
        "------------------------------------------------",
        "",
    ]

    with output_path.open("w", encoding="utf-8") as out:
        out.write("\n".join(header_lines) + "\n")

        for abs_path, rel_path in file_list:
            ext = abs_path.suffix.lower()
            out.write(f"FILE: {rel_path.as_posix()}\n\n")

            if ext in {".xlsx", ".csv"}:
                size = abs_path.stat().st_size
                out.write(f"[Data file: {size} bytes ({_human_bytes(size)})]\n\n")
            else:
                try:
                    with abs_path.open("r", encoding="utf-8") as f:
                        content = f.read()

                    fence = ext.lstrip(".") or "txt"
                    if fence not in {
                        "py",
                        "yaml",
                        "yml",
                        "json",
                        "toml",
                        "ini",
                        "md",
                        "txt",
                    }:
                        fence = "txt"

                    out.write(f"---BEGIN:{fence}---\n")
                    out.write(content)
                    if not content.endswith("\n"):
                        out.write("\n")
                    out.write(f"---END:{fence}---\n\n")
                except Exception as e:  # noqa: BLE001
                    out.write(f"[Error reading file: {e}]\n\n")

            out.write("------------------------------------------------\n\n")

    snapshot_size = output_path.stat().st_size
    print(
        "Snapshot created: {} ({} bytes)".format(
            _human_bytes(snapshot_size), snapshot_size
        )
    )


# ---------------------------------------------------------------------------
# Core zip creation
# ---------------------------------------------------------------------------


def make_zip(
    root: Path,
    zip_path: Path,
    create_json_manifest: bool = True,
    create_snapshot: bool = True,
) -> None:
    """Create the zip archive and optional manifest/snapshot."""
    root = root.resolve()
    zip_path = zip_path.resolve()

    print(f"Zipping from root: {root}")
    print(f"Creating archive: {zip_path}")
    print("Excluding hidden dirs/files, venvs, caches, outputs, legacy")
    print("Including extensions:", ", ".join(sorted(ALLOWED_EXTS)))
    print(f"Max file size: {MAX_FILE_SIZE:,} bytes ({_human_bytes(MAX_FILE_SIZE)})")
    print()

    file_list: List[FilePair] = []
    count = 0

    with zipfile.ZipFile(
        zip_path,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
        allowZip64=True,
    ) as zf:
        for file_path in iter_files(root):
            rel_path = file_path.relative_to(root)
            zf.write(file_path, rel_path.as_posix())
            file_list.append((file_path, rel_path))
            count += 1
            if count % 50 == 0:
                print(f"  Added {count} files... last: {rel_path}")

    print(f"\nDone. Total files added: {count}")

    # Best-effort removal of macOS extended attributes (xattr) to reduce noise
    if sys.platform == "darwin":
        try:
            os.system(f'xattr -c "{zip_path}" 2>/dev/null')
        except Exception:  # noqa: BLE001
            # Non-fatal; ignore if xattr is unavailable
            pass

    if create_json_manifest:
        manifest = create_manifest(root, file_list, zip_path)
        manifest_path = zip_path.with_suffix(".json")
        save_manifest(manifest, manifest_path)
        total_uncompressed = manifest["metadata"]["total_uncompressed_bytes"]
        zip_size = manifest["metadata"]["zip_size_bytes"]
        ratio = manifest["metadata"].get("compression_ratio_percent", 0.0)
        print(
            "Compression: {} → {} ({:.1f}% reduction)".format(
                _human_bytes(total_uncompressed),
                _human_bytes(zip_size),
                ratio,
            )
        )

    if create_snapshot:
        snapshot_path = zip_path.with_suffix(".txt")
        create_concatenated_snapshot(root, file_list, snapshot_path)


# ---------------------------------------------------------------------------
# Minimal, Go-with-the-Flow CLI (no argparse)
# ---------------------------------------------------------------------------


def print_usage(prog: str) -> None:
    print(
        "Usage:",
        prog,
        "<output_name> [--no-manifest] [--no-snapshot] [--root PATH]",
        file=sys.stderr,
    )
    print("Creates:", file=sys.stderr)
    print("  <output_name>.zip   - compressed archive", file=sys.stderr)
    print("  <output_name>.json  - file manifest", file=sys.stderr)
    print("  <output_name>.txt   - concatenated snapshot", file=sys.stderr)


def parse_args(argv: Sequence[str]) -> Dict[str, Any]:
    """
    Very small manual parser to avoid argparse.

    Rules:
      • First non-flag argument → output_name
      • --no-manifest          → disable manifest
      • --no-snapshot          → disable snapshot
      • --root PATH            → set root directory
    """
    cfg: Dict[str, Any] = {
        "output_name": None,
        "root": None,
        "create_manifest": True,
        "create_snapshot": True,
    }

    i = 1
    n = len(argv)
    while i < n:
        token = argv[i]

        if token == "--no-manifest":
            cfg["create_manifest"] = False
            i += 1
            continue

        if token == "--no-snapshot":
            cfg["create_snapshot"] = False
            i += 1
            continue

        if token == "--root":
            if i + 1 >= n:
                print("Error: --root flag requires a PATH argument", file=sys.stderr)
                cfg["error"] = True
                return cfg
            cfg["root"] = argv[i + 1]
            i += 2
            continue

        if token.startswith("--"):
            # Unknown flag – warn but continue
            print(f"Warning: ignoring unknown flag {token!r}", file=sys.stderr)
            i += 1
            continue

        # First positional argument → output_name
        if cfg["output_name"] is None:
            cfg["output_name"] = token
        else:
            # Extra positional args are ignored but warned about
            print(
                f"Warning: ignoring extra positional argument {token!r}",
                file=sys.stderr,
            )
        i += 1

    return cfg


def main(argv: Sequence[str]) -> int:
    if len(argv) < 2:
        print_usage(argv[0])
        return 1

    cfg = parse_args(argv)
    if cfg.get("error"):
        print_usage(argv[0])
        return 1

    output_name = cfg.get("output_name")
    if not output_name:
        print("Error: missing <output_name> argument.", file=sys.stderr)
        print_usage(argv[0])
        return 1

    root_arg = cfg.get("root")
    if root_arg:
        root = Path(root_arg).expanduser().resolve()
    else:
        root = Path.cwd().resolve()

    zip_path = (Path.cwd() / output_name).with_suffix(".zip")

    make_zip(
        root=root,
        zip_path=zip_path,
        create_json_manifest=cfg.get("create_manifest", True),
        create_snapshot=cfg.get("create_snapshot", True),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
# EOF
