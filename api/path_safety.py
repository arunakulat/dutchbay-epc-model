"""Confine caller-supplied file paths to a vetted set of repo roots (CASPER).

The ``/run-pipeline`` and ``/run-tornado`` endpoints accept caller-supplied
scenario and AEP-summary paths. Without confinement a caller could read an
arbitrary file via ``../`` traversal, an absolute path, or a symlink that
resolves outside the project. :func:`confined_path` resolves a candidate and
asserts it lives under one of the allowed roots sourced from
``config/defaults.yaml`` (``defaults.api.allowed_path_roots``), failing loud
otherwise (CESSPIT: the policy lives in config, not a Python literal).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml  # project core dependency

#: Repository root (this file lives at ``<root>/api/path_safety.py``).
REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULTS_PATH = REPO_ROOT / "config" / "defaults.yaml"


class UnsafePathError(ValueError):
    """Raised when a caller-supplied path escapes the allowed roots."""


@lru_cache(maxsize=1)
def allowed_roots() -> tuple[Path, ...]:
    """Return the absolute allowed roots from ``config/defaults.yaml``.

    Reads ``defaults.api.allowed_path_roots`` (a list of repo-relative directory
    names) and resolves each against :data:`REPO_ROOT`. Fails loud if the key is
    missing or malformed — an absent policy must never silently widen access.
    """
    data = yaml.safe_load(_DEFAULTS_PATH.read_text())
    try:
        names = data["defaults"]["api"]["allowed_path_roots"]
    except (KeyError, TypeError) as exc:  # pragma: no cover - config-integrity guard
        raise UnsafePathError(
            "config/defaults.yaml missing defaults.api.allowed_path_roots "
            "(required to confine API file-path inputs)."
        ) from exc
    if not isinstance(names, list) or not names:
        raise UnsafePathError(
            "defaults.api.allowed_path_roots must be a non-empty list."
        )
    return tuple((REPO_ROOT / str(name)).resolve() for name in names)


def confined_path(candidate: str, *, must_exist: bool = False) -> Path:
    """Resolve ``candidate`` and assert it lives under an allowed root.

    Relative paths resolve against the repository root; absolute paths are taken
    as given. The path is fully resolved (``..`` segments and symlinks collapsed)
    *before* the containment check, so traversal cannot escape an allowed root.

    Raises
    ------
    UnsafePathError
        If ``candidate`` is empty, resolves outside every allowed root, or
        (when ``must_exist``) does not exist.
    """
    if not isinstance(candidate, str) or not candidate.strip():
        raise UnsafePathError("path must be a non-empty string.")
    raw = Path(candidate).expanduser()
    resolved = (raw if raw.is_absolute() else REPO_ROOT / raw).resolve()
    roots = allowed_roots()
    if not any(resolved == root or resolved.is_relative_to(root) for root in roots):
        allowed = ", ".join(str(r.relative_to(REPO_ROOT)) for r in roots)
        raise UnsafePathError(
            f"path {candidate!r} resolves outside the allowed roots ({allowed})."
        )
    if must_exist and not resolved.exists():
        raise UnsafePathError(f"path {candidate!r} does not exist.")
    return resolved
