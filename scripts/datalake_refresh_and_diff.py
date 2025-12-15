#!/usr/bin/env python3
"""Canonical codebase snapshot + datalake refresh + diffs.

This script mimics the manual steps used to create/update ./datalake:

1) Clean root artifacts:
   - Delete any repo-root files matching DutchBay_EPC_*.{json,txt,zip}
     (timestamp ignored by deleting all matches).

2) Recreate snapshot artifacts in repo root:
   - Run: python scripts/make_clean_zip.py DutchBay_EPC_<YYYYMMDD_HHMM>
     This generates <base>.zip, <base>.json (manifest), <base>.txt (all_scripts)

3) Ingest into repo-local datalake:
   - Run scripts/codebase_datalake_ingress.py (bootstraps latest_snapshot.txt
     from newest DutchBay_EPC_*.json and builds derived indexes).

4) Produce snapshot-to-snapshot diffs into ./datalake/codebase/derived:
   - diff_files.csv: added/removed/modified files (based on manifest size_bytes
     and modified_at)
   - diff_imports.csv: added/removed dependency edges (from index_imports.csv)
   - diff_summary.csv: rollup counts

All outputs are written as CSV.

Recommended invocation (per Go-with-the-Flow TOOL-OS-01):
  ./.venv311/bin/python scripts/datalake_refresh_and_diff.py
"""

from __future__ import annotations

import csv
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

RE_ARTIFACT_JSON = re.compile(r"^DutchBay_EPC_.*\\.json$", re.IGNORECASE)
RE_ARTIFACT_TXT = re.compile(r"^DutchBay_EPC_.*\\.txt$", re.IGNORECASE)
RE_ARTIFACT_ZIP = re.compile(r"^DutchBay_EPC_.*\\.zip$", re.IGNORECASE)


@dataclass(frozen=True)
class FileRec:
    path: str
    extension: str
    size_bytes: int
    modified_at: str


@dataclass(frozen=True)
class ImportEdge:
    importer_path: str
    import_type: str
    imported_module: str
    imported_name: str
    import_level: str
    resolved_module: str
    resolved_path: str
    is_internal: str


def repo_root() -> Path:
    # scripts/<this>.py -> repo root is parent of scripts
    return Path(__file__).resolve().parents[1]


def venv_python(root: Path) -> str:
    venv_py = root / ".venv311" / "bin" / "python"
    if venv_py.exists():
        return str(venv_py)
    # fall back to current interpreter
    return sys.executable


def write_csv(path: Path, rows: Sequence[dict], fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(fieldnames))
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fieldnames})


def delete_old_artifacts(root: Path) -> List[str]:
    deleted: List[str] = []
    for p in root.iterdir():
        if not p.is_file():
            continue
        name = p.name
        if (
            RE_ARTIFACT_JSON.match(name)
            or RE_ARTIFACT_TXT.match(name)
            or RE_ARTIFACT_ZIP.match(name)
        ):
            try:
                p.unlink()
                deleted.append(name)
            except OSError:
                # best effort
                pass
    return sorted(deleted)


def run(cmd: List[str], cwd: Path) -> None:
    proc = subprocess.run(cmd, cwd=str(cwd))
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)


def newest_snapshot_id(snapshots_dir: Path) -> Optional[str]:
    if not snapshots_dir.exists():
        return None
    dirs = [d for d in snapshots_dir.iterdir() if d.is_dir()]
    if not dirs:
        return None
    # newest by mtime
    dirs.sort(key=lambda d: d.stat().st_mtime, reverse=True)
    return dirs[0].name


def previous_snapshot_id(snapshots_dir: Path, current_id: str) -> Optional[str]:
    dirs = [d for d in snapshots_dir.iterdir() if d.is_dir() and d.name != current_id]
    if not dirs:
        return None
    dirs.sort(key=lambda d: d.stat().st_mtime, reverse=True)
    return dirs[0].name


def load_manifest_files(snapshot_dir: Path) -> Dict[str, FileRec]:
    manifest_path = snapshot_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    out: Dict[str, FileRec] = {}
    for f in manifest.get("files", []):
        path = (f.get("path") or "").replace("\\\\", "/")
        if not path:
            continue
        out[path] = FileRec(
            path=path,
            extension=str(f.get("extension") or ""),
            size_bytes=int(f.get("size_bytes") or 0),
            modified_at=str(f.get("modified_at") or ""),
        )
    return out


def load_import_edges(snapshot_dir: Path) -> Set[Tuple[str, ...]]:
    """Load normalized import-edge keys from snapshot's index_imports.csv."""
    p = snapshot_dir / "index_imports.csv"
    if not p.exists():
        return set()

    edges: Set[Tuple[str, ...]] = set()
    with p.open("r", encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            edges.add(
                (
                    row.get("importer_path", ""),
                    row.get("import_type", ""),
                    row.get("imported_module", ""),
                    row.get("imported_name", ""),
                    row.get("import_level", ""),
                    row.get("resolved_module", ""),
                    row.get("resolved_path", ""),
                    row.get("is_internal", ""),
                )
            )
    return edges


def compute_file_diffs(
    prev: Dict[str, FileRec], curr: Dict[str, FileRec]
) -> List[dict]:
    prev_paths = set(prev.keys())
    curr_paths = set(curr.keys())

    added = curr_paths - prev_paths
    removed = prev_paths - curr_paths
    common = prev_paths & curr_paths

    diffs: List[dict] = []

    for p in sorted(added):
        c = curr[p]
        diffs.append(
            {
                "change_type": "added",
                "path": p,
                "extension": c.extension,
                "size_prev": "",
                "size_curr": c.size_bytes,
                "modified_at_prev": "",
                "modified_at_curr": c.modified_at,
            }
        )

    for p in sorted(removed):
        a = prev[p]
        diffs.append(
            {
                "change_type": "removed",
                "path": p,
                "extension": a.extension,
                "size_prev": a.size_bytes,
                "size_curr": "",
                "modified_at_prev": a.modified_at,
                "modified_at_curr": "",
            }
        )

    for p in sorted(common):
        a = prev[p]
        b = curr[p]
        if a.size_bytes != b.size_bytes or a.modified_at != b.modified_at:
            diffs.append(
                {
                    "change_type": "modified",
                    "path": p,
                    "extension": b.extension or a.extension,
                    "size_prev": a.size_bytes,
                    "size_curr": b.size_bytes,
                    "modified_at_prev": a.modified_at,
                    "modified_at_curr": b.modified_at,
                }
            )

    return diffs


def compute_import_diffs(
    prev_edges: Set[Tuple[str, ...]], curr_edges: Set[Tuple[str, ...]]
) -> List[dict]:
    added = curr_edges - prev_edges
    removed = prev_edges - curr_edges

    diffs: List[dict] = []
    for e in sorted(added):
        diffs.append(
            {
                "change_type": "added",
                "importer_path": e[0],
                "import_type": e[1],
                "imported_module": e[2],
                "imported_name": e[3],
                "import_level": e[4],
                "resolved_module": e[5],
                "resolved_path": e[6],
                "is_internal": e[7],
            }
        )

    for e in sorted(removed):
        diffs.append(
            {
                "change_type": "removed",
                "importer_path": e[0],
                "import_type": e[1],
                "imported_module": e[2],
                "imported_name": e[3],
                "import_level": e[4],
                "resolved_module": e[5],
                "resolved_path": e[6],
                "is_internal": e[7],
            }
        )

    return diffs


def main() -> int:
    root = repo_root()
    py = venv_python(root)

    # Step 0: ensure datalake skeleton exists
    dl = root / "datalake" / "codebase"
    (dl / "snapshots").mkdir(parents=True, exist_ok=True)
    (dl / "derived").mkdir(parents=True, exist_ok=True)
    (dl / "blobs").mkdir(parents=True, exist_ok=True)

    # Step 1: delete old artifacts
    deleted = delete_old_artifacts(root)

    # Step 2: create new manifest/txt/zip
    base = "DutchBay_EPC_" + datetime.now().strftime("%Y%m%d_%H%M")
    run([py, "scripts/make_clean_zip.py", base], cwd=root)

    # Step 3: ingest datalake (bootstrap latest snapshot pointer)
    run([py, "scripts/codebase_datalake_ingress.py"], cwd=root)

    # Step 4: diffs
    snapshots_dir = dl / "snapshots"
    current_id = newest_snapshot_id(snapshots_dir)
    if not current_id:
        raise SystemExit("No snapshots were created; ingestion failed.")

    prev_id = previous_snapshot_id(snapshots_dir, current_id)

    derived_dir = dl / "derived"
    snap_curr = snapshots_dir / current_id

    # Always write something, even if no prev snapshot exists
    file_diffs: List[dict] = []
    import_diffs: List[dict] = []

    if prev_id:
        snap_prev = snapshots_dir / prev_id

        prev_files = load_manifest_files(snap_prev)
        curr_files = load_manifest_files(snap_curr)
        file_diffs = compute_file_diffs(prev_files, curr_files)

        prev_edges = load_import_edges(snap_prev)
        curr_edges = load_import_edges(snap_curr)
        import_diffs = compute_import_diffs(prev_edges, curr_edges)

    summary = [
        {
            "run_at": datetime.now().isoformat(timespec="seconds"),
            "current_snapshot_id": current_id,
            "previous_snapshot_id": prev_id or "",
            "deleted_root_artifacts": len(deleted),
            "diff_files_added": sum(
                1 for r in file_diffs if r.get("change_type") == "added"
            ),
            "diff_files_removed": sum(
                1 for r in file_diffs if r.get("change_type") == "removed"
            ),
            "diff_files_modified": sum(
                1 for r in file_diffs if r.get("change_type") == "modified"
            ),
            "diff_import_edges_added": sum(
                1 for r in import_diffs if r.get("change_type") == "added"
            ),
            "diff_import_edges_removed": sum(
                1 for r in import_diffs if r.get("change_type") == "removed"
            ),
        }
    ]

    diff_files_path = derived_dir / "diff_files.csv"
    diff_imports_path = derived_dir / "diff_imports.csv"
    diff_summary_path = derived_dir / "diff_summary.csv"

    write_csv(
        diff_files_path,
        file_diffs,
        [
            "change_type",
            "path",
            "extension",
            "size_prev",
            "size_curr",
            "modified_at_prev",
            "modified_at_curr",
        ],
    )

    write_csv(
        diff_imports_path,
        import_diffs,
        [
            "change_type",
            "importer_path",
            "import_type",
            "imported_module",
            "imported_name",
            "import_level",
            "resolved_module",
            "resolved_path",
            "is_internal",
        ],
    )

    write_csv(
        diff_summary_path,
        summary,
        [
            "run_at",
            "current_snapshot_id",
            "previous_snapshot_id",
            "deleted_root_artifacts",
            "diff_files_added",
            "diff_files_removed",
            "diff_files_modified",
            "diff_import_edges_added",
            "diff_import_edges_removed",
        ],
    )

    # Immutable copies into current snapshot folder too
    for p in (diff_files_path, diff_imports_path, diff_summary_path):
        (snap_curr / p.name).write_bytes(p.read_bytes())

    # console hints
    print("OK")
    print(f"deleted_root_artifacts={len(deleted)}")
    print(f"current_snapshot_id={current_id}")
    print(f"previous_snapshot_id={prev_id or ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
