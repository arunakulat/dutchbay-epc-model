# dutchbay_v13/schema.py
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import os

try:
    import yaml  # type: ignore
except Exception as e:  # pragma: no cover
    raise RuntimeError("PyYAML is required to load schema files") from e


# --------------------------------------------------------------------
# Public surface
#   - EXTRA_SCHEMA_PATHS is mutable: validate.py reads it on import
#   - register_extra_schema(p) lets other modules add paths at runtime
#   - iter_schema_documents() yields parsed schema mappings
# --------------------------------------------------------------------

# Module directory (…/dutchbay_v13/)
_MODDIR = Path(__file__).resolve().parent

# Built-in schemas we ship (relative to module dir).
# Add here only if the file actually exists in-repo.
_BASE_SCHEMA_CANDIDATES: Tuple[str, ...] = (
    "inputs/schema/financing_terms.schema.yaml",
    "inputs/schema/financing_terms.schema.json",
)

# Final list of absolute paths we will try to load.
BASE_SCHEMA_PATHS: List[str] = [
    str((_MODDIR / rel).resolve())
    for rel in _BASE_SCHEMA_CANDIDATES
    if (_MODDIR / rel).exists()
]

# Mutable list that callers may extend at runtime.
# validate.py will read this list; scenario runner / adapters can also push here.
EXTRA_SCHEMA_PATHS: List[str] = []

# Optional: allow comma-separated extra paths via env for local experiments.
_env_extra = os.environ.get("DB13_EXTRA_SCHEMAS", "").strip()
if _env_extra:
    for raw in _env_extra.split(","):
        p = raw.strip()
        if p:
            try:
                pp = str(Path(p).expanduser().resolve())
            except Exception:
                pp = p
            if pp not in EXTRA_SCHEMA_PATHS:
                EXTRA_SCHEMA_PATHS.append(pp)


def register_extra_schema(path: str) -> None:
    """
    Register an extra JSON/YAML schema file path (absolute or relative).
    Idempotent; ignores duplicates and missing files (validate.py
    will check existence when loading).
    """
    if not path:
        return
    try:
        pp = str(Path(path).expanduser().resolve())
    except Exception:
        pp = path
    if pp not in EXTRA_SCHEMA_PATHS:
        EXTRA_SCHEMA_PATHS.append(pp)


def _load_yaml(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"Schema at {path} must be a mapping at top level.")
    return data


def _load_one_schema(path: str) -> Optional[Dict[str, Any]]:
    try:
        p = Path(path)
        if not p.exists():
            return None
        if p.suffix.lower() in (".yaml", ".yml"):
            return _load_yaml(p)
        # Allow JSON content via YAML loader as well (YAML is superset)
        return _load_yaml(p)
    except Exception:
        # Do not raise here; validate.py will continue with others
        return None


def iter_schema_documents() -> Iterable[Dict[str, Any]]:
    """
    Yield parsed schema mappings from BASE_SCHEMA_PATHS + EXTRA_SCHEMA_PATHS.
    Missing or invalid files are skipped safely.
    """
    seen: set[str] = set()
    for path in BASE_SCHEMA_PATHS + EXTRA_SCHEMA_PATHS:
        if not path or path in seen:
            continue
        seen.add(path)
        doc = _load_one_schema(path)
        if doc:
            yield doc


__all__ = [
    "BASE_SCHEMA_PATHS",
    "EXTRA_SCHEMA_PATHS",
    "register_extra_schema",
    "iter_schema_documents",
]

