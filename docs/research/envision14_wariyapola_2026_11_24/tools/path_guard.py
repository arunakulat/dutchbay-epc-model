"""Reject writing screening/proprietary products into *any* Git worktree.

Validate against the actual package checkout, not the caller-supplied --repo.
All paths are resolved, so symlinked destinations cannot bypass this check.
"""

from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
TRUSTED_CHECKOUT = PACKAGE.parents[2]


def require_external_path(path: Path, *, declared_repo: Path | None = None) -> Path:
    candidate = path.expanduser().resolve()
    protected = [TRUSTED_CHECKOUT.resolve()]
    if declared_repo is not None:
        protected.append(declared_repo.expanduser().resolve())
    for base in protected:
        if candidate == base or candidate.is_relative_to(base):
            raise ValueError(
                "Refusing proprietary/screening output in a project checkout"
            )
    for ancestor in (candidate, *candidate.parents):
        if (ancestor / ".git").exists():
            raise ValueError("Refusing output inside an alternate Git checkout")
    return candidate
