#!/usr/bin/env python3
"""
Build a zip bundle from a JSON manifest.

- Reads a manifest JSON file describing which files/dirs to include.
- Applies optional excludes and rename rules.
- Produces a deterministic-ish zip suitable for sharing or releases.

Usage:
    python scripts/build_zip_from_manifest.py --manifest release_manifest.json
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path
from typing import Dict, Iterable, List
from zipfile import ZIP_DEFLATED, ZipFile

logger = logging.getLogger(__name__)


def load_manifest(path: Path) -> Dict:
    logger.info("Loading manifest from %s", path)
    with path.open("r", encoding="utf-8") as f:
        manifest = json.load(f)

    if "include" not in manifest or not isinstance(manifest["include"], list):
        raise ValueError("Manifest must contain an 'include' list.")

    # Normalize some defaults
    manifest.setdefault("base_dir", ".")
    manifest.setdefault("output_zip", "bundle.zip")
    manifest.setdefault("exclude", [])
    manifest.setdefault("rename_map", {})

    return manifest


def should_exclude(rel_path: Path, exclude_prefixes: Iterable[str]) -> bool:
    rel_str = rel_path.as_posix() + ("/" if rel_path.is_dir() else "")
    for prefix in exclude_prefixes:
        # Normalize both sides to posix-style
        p = prefix.rstrip("/")
        if not p:
            continue
        if rel_str == p or rel_str.startswith(p + "/"):
            return True
    return False


def iter_files(
    base_dir: Path,
    includes: List[str],
    exclude_prefixes: Iterable[str],
) -> Iterable[Path]:
    for pattern in includes:
        target = (base_dir / pattern).resolve()
        if not target.exists():
            logger.warning("Included path does not exist, skipping: %s", pattern)
            continue

        if target.is_file():
            rel = target.relative_to(base_dir)
            if not should_exclude(rel, exclude_prefixes):
                yield target
            continue

        # Walk directory
        for root, dirs, files in os.walk(target):
            root_path = Path(root)
            rel_root = root_path.relative_to(base_dir)

            # Prune excluded dirs in-place
            pruned_dirs = []
            for d in list(dirs):
                subdir_rel = rel_root / d
                if should_exclude(subdir_rel, exclude_prefixes):
                    logger.debug("Pruning excluded dir: %s", subdir_rel)
                else:
                    pruned_dirs.append(d)
            dirs[:] = pruned_dirs

            for fname in files:
                fpath = root_path / fname
                rel_file = fpath.relative_to(base_dir)
                if should_exclude(rel_file, exclude_prefixes):
                    continue
                yield fpath


def build_zip_from_manifest(manifest_path: Path) -> Path:
    manifest = load_manifest(manifest_path)

    base_dir = (manifest_path.parent / manifest["base_dir"]).resolve()
    output_zip = (manifest_path.parent / manifest["output_zip"]).resolve()
    includes: List[str] = manifest["include"]
    exclude: List[str] = manifest["exclude"]
    rename_map: Dict[str, str] = manifest["rename_map"]

    logger.info("Base dir: %s", base_dir)
    logger.info("Output zip: %s", output_zip)

    if not base_dir.exists():
        raise FileNotFoundError(f"Base dir does not exist: {base_dir}")

    files_to_add = sorted(set(iter_files(base_dir, includes, exclude)))

    logger.info("Files to add: %d", len(files_to_add))

    output_zip.parent.mkdir(parents=True, exist_ok=True)

    with ZipFile(output_zip, "w", compression=ZIP_DEFLATED) as zf:
        for fpath in files_to_add:
            rel = fpath.relative_to(base_dir).as_posix()
            arcname = rename_map.get(rel, rel)
            logger.debug("Adding %s as %s", fpath, arcname)
            zf.write(fpath, arcname)

    logger.info("Created zip: %s (entries: %d)", output_zip, len(files_to_add))
    return output_zip


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a zip bundle from a JSON manifest."
    )
    parser.add_argument(
        "--manifest",
        "-m",
        type=str,
        required=True,
        help="Path to the JSON manifest file (e.g. release_manifest.json).",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable debug logging.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s:%(name)s:%(message)s",
    )

    manifest_path = Path(args.manifest).resolve()
    try:
        zip_path = build_zip_from_manifest(manifest_path)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to build zip: %s", exc, exc_info=True)
        raise SystemExit(1) from exc

    print(f"Created: {zip_path}")


if __name__ == "__main__":
    main()
