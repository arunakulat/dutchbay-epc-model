"""Build a finance-safe QSTS overlay from a verified Issue #923 package.

The adapter closes only the #923-B3 package-to-runtime seam. It does not run QSTS,
claim convergence or site evidence, construct an operator dispatch schedule, or enable
canonical finance. Package identity remains anchored by a caller-supplied SHA-256.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal, TypedDict

from analytics.grid.synthetic_feeder_placeholder import (
    verify_synthetic_feeder_package,
)

_RUNTIME_COMPILE_STATUS = "passed_compile_only_no_convergence_claim"


class SyntheticFinanceWiringOverlay(TypedDict):
    """The fixed noncanonical finance classification for a synthetic QSTS run."""

    enabled: Literal[False]
    mode: Literal["synthetic_counterfactual"]
    canonical_eligible: Literal[False]


class SyntheticQstsOverlay(TypedDict):
    """Strict QSTS submapping derived only from a verified synthetic package."""

    enabled: Literal[True]
    input_kind: Literal["synthetic_placeholder"]
    feeder_model_path: str
    source_manifest_sha256: str
    export_cap_mw: float
    generation_profile_mw: list[float]
    finance_wiring: SyntheticFinanceWiringOverlay


def build_verified_synthetic_qsts_overlay(
    *, manifest_path: str | Path, expected_manifest_sha256: str
) -> SyntheticQstsOverlay:
    """Verify one governed package and return its finance-safe QSTS submapping.

    Args:
        manifest_path: Path to the package's canonical ``manifest.json``.
        expected_manifest_sha256: External trust-anchor digest for that manifest.

    Returns:
        A new QSTS submapping containing the verified feeder path, profile, export cap,
        manifest identity, and fixed noncanonical finance classification.

    Raises:
        FileNotFoundError: If the manifest or a governed package payload is absent.
        ValueError: If verification fails or the package lacks the required detached
            OpenDSS compile status.
    """

    package = verify_synthetic_feeder_package(
        manifest_path=manifest_path,
        expected_manifest_sha256=expected_manifest_sha256,
    )
    if package.opendss_compile_status != _RUNTIME_COMPILE_STATUS:
        raise ValueError(
            "Runtime use of a synthetic_placeholder requires a package whose detached "
            "OpenDSS compile check passed. Test-only compile-disabled packages are not "
            "runtime inputs."
        )

    return {
        "enabled": True,
        "input_kind": "synthetic_placeholder",
        "feeder_model_path": str(package.master_path),
        "source_manifest_sha256": package.manifest_sha256,
        "export_cap_mw": package.export_cap_mw,
        "generation_profile_mw": list(package.generation_profile_mw),
        "finance_wiring": {
            "enabled": False,
            "mode": "synthetic_counterfactual",
            "canonical_eligible": False,
        },
    }


__all__ = [
    "SyntheticFinanceWiringOverlay",
    "SyntheticQstsOverlay",
    "build_verified_synthetic_qsts_overlay",
]
