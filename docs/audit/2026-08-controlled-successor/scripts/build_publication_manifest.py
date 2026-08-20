#!/usr/bin/env python3
"""Build the non-self-referential SHA-256 manifest for the published audit pack."""

from __future__ import annotations

import hashlib
from pathlib import Path

PACK_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = PACK_ROOT / "PUBLICATION_MANIFEST.sha256"
EXCLUDED_NAMES = {MANIFEST.name}


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    """Write a stable manifest for every repository-published pack file."""
    files = sorted(
        path
        for path in PACK_ROOT.rglob("*")
        if path.is_file()
        and path.name not in EXCLUDED_NAMES
        and "__pycache__" not in path.parts
    )
    body = "".join(
        f"{_digest(path)}  {path.relative_to(PACK_ROOT).as_posix()}\n" for path in files
    )
    MANIFEST.write_text(body, encoding="utf-8")
    print(f"wrote {MANIFEST} with {len(files)} entries")


if __name__ == "__main__":
    main()
