import json
import os
import sys
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Set

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

MAX_FILE_SIZE = 2_000_000  # 2MB


def should_skip_dir(dir_name: str) -> bool:
    if dir_name in SKIP_DIR_NAMES:
        return True
    if dir_name.startswith("."):
        return True
    if "venv" in dir_name.lower():
        return True
    if dir_name.endswith("_cache") or dir_name.endswith(".cache"):
        return True
    return False


def should_include_file(root: Path, name: str) -> bool:
    file_path = root / name
    if name.startswith("."):
        return False
    ext = Path(name).suffix.lower()
    if ext not in ALLOWED_EXTS:
        return False
    try:
        if file_path.stat().st_size > MAX_FILE_SIZE:
            return False
    except (OSError, FileNotFoundError):
        return False
    return True


def iter_files(root: Path) -> Iterable[Path]:
    for current_root, dirs, files in os.walk(root):
        current_root_path = Path(current_root)
        dirs[:] = [d for d in dirs if not should_skip_dir(d)]
        for f in files:
            if should_include_file(current_root_path, f):
                yield current_root_path / f


def create_manifest(root: Path, file_list: list, zip_path: Path) -> Dict[str, Any]:
    manifest = {
        "metadata": {
            "created_at": datetime.now().isoformat(),
            "root_directory": str(root),
            "zip_file": str(zip_path.name),
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
        manifest["files"].append(
            {
                "path": rel_path.as_posix(),
                "size_bytes": stat.st_size,
                "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "extension": abs_path.suffix.lower(),
            }
        )
        total_size += stat.st_size
    manifest["metadata"]["total_uncompressed_bytes"] = total_size
    if manifest["metadata"]["zip_size_bytes"] > 0 and total_size > 0:
        ratio = (1 - manifest["metadata"]["zip_size_bytes"] / total_size) * 100
        manifest["metadata"]["compression_ratio_percent"] = round(ratio, 2)
    return manifest


def save_manifest(manifest: Dict[str, Any], manifest_path: Path) -> None:
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    print("Manifest saved:", manifest_path)


def create_concatenated_snapshot(
    root: Path, file_list: list, output_path: Path
) -> None:
    print("Creating concatenated snapshot:", output_path)
    with open(output_path, "w", encoding="utf-8") as out:
        out.write("# DutchBay EPC Model - Code Snapshot\n")
        out.write("Generated: {}\n".format(datetime.now().isoformat()))
        out.write("Total Files: {}\n".format(len(file_list)))
        out.write("Root: {}\n\n".format(root))
        out.write("------------------------------------------------\n\n")

        for abs_path, rel_path in file_list:
            ext = abs_path.suffix.lower()
            out.write("FILE: {}\n\n".format(rel_path.as_posix()))
            if ext in {".xlsx", ".csv"}:
                size = abs_path.stat().st_size
                out.write("[Data file: {} bytes]\n\n".format(size))
            else:
                try:
                    with open(abs_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    fence = ext.replace(".", "")
                    if fence not in {"py", "yaml", "yml", "json", "toml", "ini", "md"}:
                        fence = "txt"
                    out.write("---BEGIN:{}---\n".format(fence))
                    out.write(content)
                    if not content.endswith("\n"):
                        out.write("\n")
                    out.write("---END:{}---\n\n".format(fence))
                except Exception as e:
                    out.write("[Error reading file: {}]\n\n".format(e))
            out.write("------------------------------------------------\n\n")
    snapshot_size = output_path.stat().st_size
    print(
        "Snapshot created: {} bytes ({:.2f} MB)".format(
            snapshot_size, snapshot_size / 1024 / 1024
        )
    )


def make_zip(
    root: Path,
    zip_path: Path,
    create_json_manifest: bool = True,
    create_snapshot: bool = True,
) -> None:
    print("Zipping from root:", root)
    print("Creating archive:", zip_path)
    print("Excluding all hidden dirs/files, venvs, caches, outputs, legacy")
    print("Including extensions:", ", ".join(sorted(ALLOWED_EXTS)))
    print(
        "Max file size: {:,} bytes ({:.1f} MB)".format(
            MAX_FILE_SIZE, MAX_FILE_SIZE / 1024 / 1024
        )
    )
    print()

    root = root.resolve()
    zip_path = zip_path.resolve()
    file_list: list = []
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
                print("  Added {} files... last: {}".format(count, rel_path))
    print("\nDone. Total files added:", count)
    print("Removing extended attributes...")
    os.system('xattr -c "{}" 2>/dev/null'.format(zip_path))

    if create_json_manifest:
        manifest = create_manifest(root, file_list, zip_path)
        save_manifest(manifest, zip_path.with_suffix(".json"))
        print(
            "Compression: {} to {} bytes ({:.1f}% reduction)".format(
                manifest["metadata"]["total_uncompressed_bytes"],
                manifest["metadata"]["zip_size_bytes"],
                manifest["metadata"].get("compression_ratio_percent", 0),
            )
        )
    if create_snapshot:
        create_concatenated_snapshot(root, file_list, zip_path.with_suffix(".txt"))


def main(argv: list) -> int:
    if len(argv) < 2:
        print(
            "Usage:",
            argv[0],
            "<output_name> [--no-manifest] [--no-snapshot]",
            file=sys.stderr,
        )
        print("Creates:", file=sys.stderr)
        print("  <output_name>.zip - compressed archive", file=sys.stderr)
        print("  <output_name>.json - file manifest", file=sys.stderr)
        print("  <output_name>.txt - concatenated snapshot", file=sys.stderr)
        return 1
    zip_name = argv[1]
    create_manifest = "--no-manifest" not in argv
    create_snapshot = "--no-snapshot" not in argv
    root = Path.cwd()
    zip_path = root / zip_name
    make_zip(
        root=root,
        zip_path=zip_path,
        create_json_manifest=create_manifest,
        create_snapshot=create_snapshot,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
# EOF
