#!/usr/bin/env python3
"""Repo-local canonical codebase datalake indexer.

Goal
- Keep a canonical, repeatable, repo-local view of the current codebase snapshot.
- Produce structured CSV indexes of files + Python imports/exports/calls.
- Compute a *relevance* closure starting from analytics/** and finance/**.

How it selects the active snapshot
1) Preferred: ./datalake/codebase/latest_snapshot.txt
2) Bootstrap fallback (when pointer is missing):
   - Find newest DutchBay_EPC_*.json in repo root
   - Create a snapshot folder under ./datalake/codebase/snapshots/<snapshot_id>/
   - Copy that JSON to manifest.json (and sibling .txt to all_scripts.txt if present)
   - Write latest_snapshot.txt

Inputs
- ./datalake/codebase/snapshots/<snapshot_id>/manifest.json (required)
- ./datalake/codebase/snapshots/<snapshot_id>/all_scripts.txt (optional)

Outputs (rewritten each run)
- ./datalake/codebase/derived/index_files.csv
- ./datalake/codebase/derived/index_imports.csv
- ./datalake/codebase/derived/index_exports.csv
- ./datalake/codebase/derived/index_calls.csv
- ./datalake/codebase/derived/index_relevant_scripts.csv
- ./datalake/codebase/derived/ingress_runlog.csv

Also writes immutable copies of all derived outputs into the snapshot folder.

Notes
- Import resolution is best-effort (supports absolute and relative imports).
- This tool never deletes snapshots; it only purges ./derived/* on each run.
"""

from __future__ import annotations

import ast
import csv
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set, Tuple


@dataclass(frozen=True)
class ImportEdge:
    snapshot_id: str
    snapshot_created_at: str
    importer_path: str
    import_type: str  # 'import' | 'from'
    imported_module: str
    imported_name: str
    import_level: int
    resolved_module: str
    resolved_path: str
    is_internal: bool


ISO_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})\.(\d+)$")


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def store_blob(blobs_dir: Path, content: bytes, suffix: str) -> str:
    h = sha256_bytes(content)
    out = blobs_dir / f"{h}.{suffix}"
    if not out.exists():
        out.write_bytes(content)
    return h


def snapshot_id_from_created_at(created_at: str) -> str:
    m = ISO_RE.match(created_at or "")
    if m:
        # 2025-12-14T10:42:38.495150 -> 20251214_104238_495150
        return f"{m.group(1)}{m.group(2)}{m.group(3)}_{m.group(4)}{m.group(5)}{m.group(6)}_{m.group(7)}"
    safe = re.sub(r"[^0-9A-Za-z_\-]+", "_", created_at or "")
    return safe[:64] or "unknown"


def importer_package(importer_path: str) -> str:
    parts = importer_path.split("/")
    if len(parts) <= 1:
        return ""
    if parts[-1] == "__init__.py":
        return ".".join(parts[:-1])
    return ".".join(parts[:-1])


def resolve_import(
    importer_path: str,
    module_to_path: Dict[str, str],
    package_to_init: Dict[str, str],
    mod: str,
    level: int,
    name: Optional[str],
) -> Tuple[str, str]:
    """Best-effort resolver from import spec to a repo-relative .py path."""
    pkg = importer_package(importer_path)
    base = mod or ""

    # Handle relative imports (from ..x import y)
    if level and pkg:
        pkg_parts = pkg.split(".")
        rel_base = ".".join(pkg_parts[:-level]) if level <= len(pkg_parts) else ""
        base = f"{rel_base}.{base}".strip(".")

    candidates: List[str] = []
    if name:
        if base:
            candidates.append(f"{base}.{name}")
        candidates.append(name)
    if base:
        candidates.append(base)

    for c in sorted({c for c in candidates if c}, key=lambda x: -len(x)):
        if c in module_to_path:
            return c, module_to_path[c]
        if c in package_to_init:
            return c, package_to_init[c]

    return (candidates[0] if candidates else ""), ""


def callee_str(n: ast.AST) -> str:
    if isinstance(n, ast.Name):
        return n.id
    if isinstance(n, ast.Attribute):
        parts: List[str] = []
        cur: ast.AST = n
        while isinstance(cur, ast.Attribute):
            parts.append(cur.attr)
            cur = cur.value
        if isinstance(cur, ast.Name):
            parts.append(cur.id)
        return ".".join(reversed(parts))
    return ""


def parse_file(
    py_path: Path,
) -> Tuple[List[Tuple[str, str, str, int]], List[str], List[str]]:
    src = py_path.read_text(encoding="utf-8", errors="replace")
    tree = ast.parse(src)

    exports: List[str] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            exports.append(node.name)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    exports.append(t.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            exports.append(node.target.id)

    imports: List[Tuple[str, str, str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                imports.append(("import", a.name, "", 0))
        elif isinstance(node, ast.ImportFrom):
            for a in node.names:
                imports.append(("from", node.module or "", a.name, node.level or 0))

    calls: List[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            s = callee_str(node.func)
            if s:
                calls.append(s)

    return sorted(set(imports)), sorted(set(exports)), sorted(set(calls))


def write_csv(path: Path, rows: Sequence[dict], fieldnames: Sequence[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(fieldnames))
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fieldnames})


def bootstrap_snapshot_from_repo_root(dl: Path) -> str:
    """Create latest snapshot pointer from newest DutchBay_EPC_*.json in repo root."""
    repo_root = Path(".").resolve()
    snapshots = dl / "snapshots"
    snapshots.mkdir(parents=True, exist_ok=True)

    candidates = sorted(
        repo_root.glob("DutchBay_EPC_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise SystemExit(
            "No DutchBay_EPC_*.json found in repo root; cannot bootstrap latest_snapshot.txt"
        )

    manifest_src = candidates[0]
    manifest = json.loads(manifest_src.read_text(encoding="utf-8"))
    created_at = manifest.get("metadata", {}).get("created_at", "unknown")
    snapshot_id = snapshot_id_from_created_at(created_at)

    snap = snapshots / snapshot_id
    snap.mkdir(parents=True, exist_ok=True)
    (snap / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    txt_src = manifest_src.with_suffix(".txt")
    if txt_src.exists():
        (snap / "all_scripts.txt").write_bytes(txt_src.read_bytes())

    (dl / "latest_snapshot.txt").write_text(snapshot_id, encoding="utf-8")
    return snapshot_id


def main() -> int:
    repo_root = Path(".").resolve()
    dl = repo_root / "datalake" / "codebase"
    snapshots = dl / "snapshots"
    blobs = dl / "blobs"
    derived = dl / "derived"

    for p in (snapshots, blobs, derived):
        p.mkdir(parents=True, exist_ok=True)

    latest_ptr = dl / "latest_snapshot.txt"
    if not latest_ptr.exists():
        snapshot_id = bootstrap_snapshot_from_repo_root(dl)
    else:
        snapshot_id = latest_ptr.read_text(encoding="utf-8").strip()

    snap = snapshots / snapshot_id
    manifest_path = snap / "manifest.json"
    if not manifest_path.exists():
        raise SystemExit(f"Missing manifest.json at {manifest_path}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    created_at = manifest.get("metadata", {}).get("created_at", "")

    # Dedupe core artifacts
    manifest_hash = store_blob(blobs, manifest_path.read_bytes(), "json")

    all_scripts_hash = ""
    all_scripts_path = snap / "all_scripts.txt"
    if all_scripts_path.exists():
        all_scripts_hash = store_blob(blobs, all_scripts_path.read_bytes(), "txt")

    files = manifest.get("files", [])
    py_paths = [
        (f.get("path") or "").replace("\\", "/")
        for f in files
        if f.get("extension") == ".py"
    ]

    # Build module mappings
    module_to_path: Dict[str, str] = {}
    package_to_init: Dict[str, str] = {}
    for p in py_paths:
        if not p.endswith(".py"):
            continue
        mod = p[:-3].replace("/", ".")
        if mod.endswith(".__init__"):
            pkg = mod[:-9]
            package_to_init[pkg] = p
            module_to_path[pkg] = p
        else:
            module_to_path[mod] = p

    # Seed = analytics/** + finance/** that exist on disk
    seed = [
        p for p in py_paths if p.startswith("analytics/") or p.startswith("finance/")
    ]
    seed = [p for p in seed if (repo_root / p).exists()]

    relevant: Set[str] = set(seed)
    queue: List[str] = list(seed)

    imports_edges: List[ImportEdge] = []
    exports_rows: List[dict] = []
    calls_rows: List[dict] = []

    parsed_cache: Dict[
        str, Tuple[List[Tuple[str, str, str, int]], List[str], List[str]]
    ] = {}

    while queue:
        importer = queue.pop(0)
        fpath = repo_root / importer

        try:
            if importer not in parsed_cache:
                parsed_cache[importer] = parse_file(fpath)
            imps, exps, calls = parsed_cache[importer]
        except Exception:
            continue

        for e in exps:
            exports_rows.append(
                {
                    "snapshot_id": snapshot_id,
                    "snapshot_created_at": created_at,
                    "path": importer,
                    "exported_name": e,
                }
            )

        for c in calls:
            calls_rows.append(
                {
                    "snapshot_id": snapshot_id,
                    "snapshot_created_at": created_at,
                    "path": importer,
                    "called_symbol": c,
                }
            )

        for imp_type, mod, name, lvl in imps:
            resolved_mod, resolved_path = resolve_import(
                importer_path=importer,
                module_to_path=module_to_path,
                package_to_init=package_to_init,
                mod=mod,
                level=lvl,
                name=name or None,
            )
            is_internal = bool(resolved_path) and (repo_root / resolved_path).exists()

            imports_edges.append(
                ImportEdge(
                    snapshot_id=snapshot_id,
                    snapshot_created_at=created_at,
                    importer_path=importer,
                    import_type=imp_type,
                    imported_module=mod,
                    imported_name=name,
                    import_level=lvl,
                    resolved_module=resolved_mod,
                    resolved_path=resolved_path,
                    is_internal=is_internal,
                )
            )

            if is_internal and resolved_path not in relevant:
                relevant.add(resolved_path)
                queue.append(resolved_path)

    # Rebuild derived from scratch (purge old artifacts)
    for old in derived.glob("*"):
        if old.is_file():
            old.unlink()

    # index_files
    files_rows: List[dict] = []
    for f in files:
        p = (f.get("path") or "").replace("\\", "/")
        ext = f.get("extension", "")
        module_name = ""
        if ext == ".py" and p.endswith(".py"):
            module_name = p[:-3].replace("/", ".")
            if module_name.endswith(".__init__"):
                module_name = module_name[:-9]
        package_root = p.split("/")[0] if "/" in p else ""

        files_rows.append(
            {
                "snapshot_id": snapshot_id,
                "snapshot_created_at": created_at,
                "path": p,
                "extension": ext,
                "size_bytes": f.get("size_bytes"),
                "modified_at": f.get("modified_at"),
                "package_root": package_root,
                "module_name": module_name,
                "is_python": ext == ".py",
                "is_relevant": p in relevant,
            }
        )

    imports_rows = [
        {
            "snapshot_id": e.snapshot_id,
            "snapshot_created_at": e.snapshot_created_at,
            "importer_path": e.importer_path,
            "import_type": e.import_type,
            "imported_module": e.imported_module,
            "imported_name": e.imported_name,
            "import_level": e.import_level,
            "resolved_module": e.resolved_module,
            "resolved_path": e.resolved_path,
            "is_internal": e.is_internal,
        }
        for e in imports_edges
    ]

    # index_relevant_scripts summary
    internal_import_counts: Dict[str, int] = {}
    external_import_counts: Dict[str, int] = {}
    for e in imports_edges:
        if e.is_internal:
            internal_import_counts[e.importer_path] = (
                internal_import_counts.get(e.importer_path, 0) + 1
            )
        else:
            external_import_counts[e.importer_path] = (
                external_import_counts.get(e.importer_path, 0) + 1
            )

    export_counts: Dict[str, int] = {}
    for r in exports_rows:
        export_counts[r["path"]] = export_counts.get(r["path"], 0) + 1

    call_counts: Dict[str, int] = {}
    for r in calls_rows:
        call_counts[r["path"]] = call_counts.get(r["path"], 0) + 1

    relevant_rows: List[dict] = []
    for p in sorted(relevant):
        relevant_rows.append(
            {
                "snapshot_id": snapshot_id,
                "snapshot_created_at": created_at,
                "path": p,
                "package_root": p.split("/")[0] if "/" in p else "",
                "module_name": p[:-3].replace("/", ".") if p.endswith(".py") else "",
                "internal_imports": internal_import_counts.get(p, 0),
                "external_imports": external_import_counts.get(p, 0),
                "exports": export_counts.get(p, 0),
                "unique_calls": call_counts.get(p, 0),
            }
        )

    out_files = derived / "index_files.csv"
    out_imports = derived / "index_imports.csv"
    out_exports = derived / "index_exports.csv"
    out_calls = derived / "index_calls.csv"
    out_relevant = derived / "index_relevant_scripts.csv"
    out_runlog = derived / "ingress_runlog.csv"

    write_csv(
        out_files,
        files_rows,
        [
            "snapshot_id",
            "snapshot_created_at",
            "path",
            "extension",
            "size_bytes",
            "modified_at",
            "package_root",
            "module_name",
            "is_python",
            "is_relevant",
        ],
    )

    write_csv(
        out_imports,
        imports_rows,
        [
            "snapshot_id",
            "snapshot_created_at",
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
        out_exports,
        exports_rows,
        ["snapshot_id", "snapshot_created_at", "path", "exported_name"],
    )
    write_csv(
        out_calls,
        calls_rows,
        ["snapshot_id", "snapshot_created_at", "path", "called_symbol"],
    )
    write_csv(
        out_relevant,
        relevant_rows,
        [
            "snapshot_id",
            "snapshot_created_at",
            "path",
            "package_root",
            "module_name",
            "internal_imports",
            "external_imports",
            "exports",
            "unique_calls",
        ],
    )

    # Dedupe derived into blobs + write runlog
    index_files_hash = store_blob(blobs, out_files.read_bytes(), "csv")
    index_imports_hash = store_blob(blobs, out_imports.read_bytes(), "csv")
    index_exports_hash = store_blob(blobs, out_exports.read_bytes(), "csv")
    index_calls_hash = store_blob(blobs, out_calls.read_bytes(), "csv")
    index_relevant_hash = store_blob(blobs, out_relevant.read_bytes(), "csv")

    write_csv(
        out_runlog,
        [
            {
                "snapshot_id": snapshot_id,
                "snapshot_created_at": created_at,
                "run_at": datetime.now().isoformat(timespec="seconds"),
                "manifest_blob_sha256": manifest_hash,
                "all_scripts_blob_sha256": all_scripts_hash,
                "index_files_blob_sha256": index_files_hash,
                "index_imports_blob_sha256": index_imports_hash,
                "index_exports_blob_sha256": index_exports_hash,
                "index_calls_blob_sha256": index_calls_hash,
                "index_relevant_scripts_blob_sha256": index_relevant_hash,
                "total_files_manifest": len(files),
                "python_files_manifest": len(py_paths),
                "seed_python_files": len(seed),
                "relevant_python_files": len(relevant),
                "imports_edges": len(imports_rows),
                "exports_rows": len(exports_rows),
                "calls_rows": len(calls_rows),
            }
        ],
        [
            "snapshot_id",
            "snapshot_created_at",
            "run_at",
            "manifest_blob_sha256",
            "all_scripts_blob_sha256",
            "index_files_blob_sha256",
            "index_imports_blob_sha256",
            "index_exports_blob_sha256",
            "index_calls_blob_sha256",
            "index_relevant_scripts_blob_sha256",
            "total_files_manifest",
            "python_files_manifest",
            "seed_python_files",
            "relevant_python_files",
            "imports_edges",
            "exports_rows",
            "calls_rows",
        ],
    )

    # Snapshot copies (immutable)
    for p in (out_files, out_imports, out_exports, out_calls, out_relevant, out_runlog):
        (snap / p.name).write_bytes(p.read_bytes())

    print("OK")
    print(f"snapshot_id={snapshot_id}")
    print(f"seed_python_files={len(seed)}")
    print(f"relevant_python_files={len(relevant)}")
    print(f"imports_edges={len(imports_rows)}")
    print(f"exports_rows={len(exports_rows)}")
    print(f"calls_rows={len(calls_rows)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
