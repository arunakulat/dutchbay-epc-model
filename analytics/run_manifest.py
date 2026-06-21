"""Auditable run manifest — binds every pipeline output to its inputs and code.

ICAEW audit posture / project-finance reproducibility: a lender or auditor must be
able to verify that a given result came from a specific *resolved* config (after any
overrides), a specific engine version, and a specific commit. This stamps a compact
manifest that makes a run reproducible and tamper-evident.

The engine version is read from the repo ``VERSION`` file (CCCDIR — single source of
truth, never a Python literal), correcting the previously hardcoded ``v14.3.0`` that
had drifted from the real version. The config hash is a stable sorted-key SHA-256 of
the resolved config, mirroring the existing ``analytics.mc.engine._stable_config_hash``
primitive.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

_REPO_ROOT = Path(__file__).resolve().parents[1]
_VERSION_PATH = _REPO_ROOT / "VERSION"

#: Bump when the manifest's own field set changes (so consumers can branch on shape).
MANIFEST_SCHEMA_VERSION = "1.0"


@lru_cache(maxsize=1)
def engine_version() -> str:
    """The engine version, read from the repo ``VERSION`` file (single source of truth)."""
    try:
        return _VERSION_PATH.read_text(encoding="utf-8").strip() or "unknown"
    except OSError:
        return "unknown"


def config_sha256(config: Mapping[str, Any]) -> str:
    """Stable SHA-256 of a resolved config (sorted-key JSON; non-JSON coerced to str)."""
    payload = json.dumps(config, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def git_sha(default: str = "unknown") -> str:
    """Current commit SHA: an env override first (CI/artifacts without .git), then
    ``git rev-parse HEAD``, then ``default``. Never raises."""
    env = os.environ.get("DUTCHBAY_GIT_SHA") or os.environ.get("GIT_COMMIT")
    if env:
        return env.strip()
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=_REPO_ROOT,
        )
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return default


@dataclass(frozen=True)
class RunManifest:
    """Reproducibility stamp for one pipeline run."""

    config_sha256: str
    engine_version: str
    git_sha: str
    generated_at: str  # UTC ISO-8601
    seed: Optional[int]
    validation_mode: Optional[str]
    manifest_schema_version: str = MANIFEST_SCHEMA_VERSION

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


def build_run_manifest(
    config: Mapping[str, Any],
    *,
    seed: Optional[int] = None,
    validation_mode: Optional[str] = None,
    generated_at: Optional[str] = None,
) -> RunManifest:
    """Build a :class:`RunManifest` from a RESOLVED (post-override) config.

    ``generated_at`` may be injected for deterministic tests; otherwise a UTC ISO-8601
    timestamp (seconds precision) is stamped.
    """
    return RunManifest(
        config_sha256=config_sha256(config),
        engine_version=engine_version(),
        git_sha=git_sha(),
        generated_at=generated_at
        or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        seed=seed,
        validation_mode=validation_mode,
    )


__all__ = [
    "MANIFEST_SCHEMA_VERSION",
    "RunManifest",
    "engine_version",
    "config_sha256",
    "git_sha",
    "build_run_manifest",
]
