"""Refresh SHA-256 entries in a corpus MANIFEST for files that have been regenerated.

A corpus manifest pins the content of every committed source and derived artifact. When a
derived artifact is legitimately regenerated — a re-rendered dossier, an edited register — its
recorded hash goes stale and ``sha256sum -c`` fails. Editing the manifest by hand invites
transcription errors in exactly the record that exists to prevent them.

This rewrites only the named paths, leaves every other line byte-identical, and re-verifies the
whole manifest afterwards. It refuses to touch a path that is not already in the manifest, so it
cannot be used to quietly add an unrecorded file.
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def refresh(manifest: Path, targets: list[str]) -> int:
    lines = manifest.read_text().splitlines()
    known = {}
    for i, line in enumerate(lines):
        if line.startswith("#") or not line.strip():
            continue
        parts = line.split(None, 1)
        if len(parts) == 2:
            known[parts[1].strip()] = i

    root = manifest.parent
    updated = 0
    for rel in targets:
        if rel not in known:
            raise SystemExit(
                f"refusing to add an unrecorded path: {rel}\n"
                "This tool only refreshes hashes already in the manifest."
            )
        f = root / rel
        if not f.exists():
            raise SystemExit(f"missing file: {f}")
        lines[known[rel]] = f"{sha256_of(f)}  {rel}"
        updated += 1

    manifest.write_text("\n".join(lines) + "\n")
    return updated


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("manifest", type=Path)
    ap.add_argument("paths", nargs="+", help="manifest-relative paths to re-hash")
    args = ap.parse_args()

    n = refresh(args.manifest, args.paths)
    print(f"refreshed {n} entr{'y' if n == 1 else 'ies'}")

    result = subprocess.run(
        ["sha256sum", "-c", args.manifest.name],
        cwd=args.manifest.parent,
        capture_output=True,
        text=True,
    )
    bad = [ln for ln in result.stdout.splitlines() if not ln.endswith(": OK")]
    if bad or result.returncode != 0:
        print("MANIFEST STILL FAILING:", *bad, sep="\n  ")
        return 1
    print(f"manifest verifies: {len(result.stdout.splitlines())} entries OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
