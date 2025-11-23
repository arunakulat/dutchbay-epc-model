import os
import sys
import zipfile
import json
from pathlib import Path
from typing import Iterable, Set, Dict, Any
from datetime import datetime

# Directories to skip entirely
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
    ".csv",
    ".xlsx",
}

# Maximum individual file size (2MB)
MAX_FILE_SIZE = 2_000_000


def should_skip_dir(dir_name: str) -> bool:
    """
    Return True if this directory should be skipped during traversal.
    """
    if dir_name in SKIP_DIR_NAMES:
        return True
    
    # Skip ALL hidden directories
    if dir_name.startswith("."):
        return True
    
    # Skip any directory with 'venv' in the name
    if "venv" in dir_name.lower():
        return True
    
    # Skip common cache/temp patterns
    if dir_name.endswith("_cache") or dir_name.endswith(".cache"):
        return True
    
    return False


def should_include_file(root: Path, name: str) -> bool:
    """
    Decide whether to include a file based on extension, location, and size.
    """
    file_path = root / name
    
    # Skip hidden files
    if name.startswith("."):
        return False
    
    # Check extension
    ext = Path(name).suffix.lower()
    if ext not in ALLOWED_EXTS:
        return False
    
    # Check file size
    try:
        if file_path.stat().st_size > MAX_FILE_SIZE:
            return False
    except (OSError, FileNotFoundError):
        return False
    
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


def create_manifest(
    root: Path, 
    file_list: list[tuple[Path, Path]], 
    zip_path: Path
) -> Dict[str, Any]:
    """
    Create a manifest dictionary with metadata about the archived files.
    """
    manifest = {
        "metadata": {
            "created_at": datetime.now().isoformat(),
            "root_directory": str(root),
            "zip_file": str(zip_path.name),
            "total_files": len(file_list),
            "zip_size_bytes": zip_path.stat().st_size if zip_path.exists() else 0,
        },
        "filters": {
            "excluded_directories": sorted(list(SKIP_DIR_NAMES)),
            "included_extensions": sorted(list(ALLOWED_EXTS)),
            "max_file_size_bytes": MAX_FILE_SIZE,
        },
        "files": []
    }
    
    # Add file details
    total_size = 0
    for abs_path, rel_path in file_list:
        stat = abs_path.stat()
        file_info = {
            "path": rel_path.as_posix(),
            "size_bytes": stat.st_size,
            "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "extension": abs_path.suffix.lower(),
        }
        manifest["files"].append(file_info)
        total_size += stat.st_size
    
    manifest["metadata"]["total_uncompressed_bytes"] = total_size
    
    # Calculate compression ratio
    if manifest["metadata"]["zip_size_bytes"] > 0:
        ratio = (1 - manifest["metadata"]["zip_size_bytes"] / total_size) * 100
        manifest["metadata"]["compression_ratio_percent"] = round(ratio, 2)
    
    return manifest


def save_manifest(manifest: Dict[str, Any], manifest_path: Path) -> None:
    """
    Save the manifest to a JSON file with pretty formatting.
    """
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    print(f"✓ Manifest saved: {manifest_path}")


def make_zip(root: Path, zip_path: Path, create_json_manifest: bool = True) -> None:
    """
    Create a zip archive at zip_path containing allowed files under root.
    Optionally create a JSON manifest alongside the zip.
    """
    print(f"Zipping from root: {root}")
    print(f"Creating archive: {zip_path}")
    print(f"Excluding all hidden dirs/files (.*), venvs, caches, outputs, legacy")
    print(f"Including extensions: {', '.join(sorted(ALLOWED_EXTS))}")
    print(f"Max file size: {MAX_FILE_SIZE:,} bytes ({MAX_FILE_SIZE/1024/1024:.1f} MB)")
    print()

    root = root.resolve()
    zip_path = zip_path.resolve()
    
    file_list: list[tuple[Path, Path]] = []
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

    print(f"\n✓ Done. Total files added: {count}")
    
    # Remove macOS extended attributes immediately
    print(f"  Removing extended attributes...")
    os.system(f'xattr -c "{zip_path}" 2>/dev/null')
    
    # Create JSON manifest if requested
    if create_json_manifest:
        manifest = create_manifest(root, file_list, zip_path)
        manifest_path = zip_path.with_suffix(".json")
        save_manifest(manifest, manifest_path)
        print(f"  Compression: {manifest['metadata']['total_uncompressed_bytes']:,} → "
              f"{manifest['metadata']['zip_size_bytes']:,} bytes "
              f"({manifest['metadata'].get('compression_ratio_percent', 0):.1f}% reduction)")


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(f"Usage: {argv[0]} <zip_name> [--no-manifest]", file=sys.stderr)
        return 1

    zip_name = argv[1]
    create_manifest = "--no-manifest" not in argv
    
    root = Path.cwd()
    zip_path = root / zip_name

    make_zip(root=root, zip_path=zip_path, create_json_manifest=create_manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
