"""CASPER contract freeze (revived from quarantine).

History:
    Originally quarantined by scripts/quarantine_bad_irr_mc_tests.py with the
    reason "absolute IRR band assertions without frozen/regression labeling".
    Investigation (Sprint 18D) confirmed the quarantine reason was a false
    positive: the test asserts only the contract version string and the
    presence of canonical CasperResult fields. There are no IRR band
    assertions in this file.

Why revived:
    Sprint 18D fixes the casper_payload \u2194 EquityPerformance bug. A
    contract-freeze test belongs alongside that fix to catch any future
    drift in the CASPER result envelope (contract version string,
    field set on the canonical dataclass).

Adaptations vs the quarantined version:
    - CasperResult.multi_tech_generation_breakdown was removed from the
      canonical dataclass (no longer in contracts_v14). The kwarg and
      __annotations__ assertion are dropped.
    - CasperResult.scenario is now typed ScenarioResult | str (no None
      allowed). The test passes the string sentinel "<frozen-contract-stub>".
    - CasperResult.contract_version is currently defined as a no-args
      method, not an attribute. The test calls it as a method. (Pre-
      existing issue recorded as follow-up; out of scope for this branch.)
    - Two CASPER_CONTRACT_VERSION constants exist: payload emits
      "casper_result_v1" while CasperResult.contract_version() returns
      "v1.0". This freeze test pins each in its own module so the drift
      cannot widen silently. Reconciliation is a pre-existing follow-up
      out of scope for this branch.

Framework Compliance:
    - TEST-01: contract-level regression pin
    - TYPE-01: full type hints
    - ARCH-04: canonical contracts_v14 surface only
    - GWTF R23/R25: lives on a feature branch with PR + CI

Author: Aruna Kulatunga
Sprint: 18D (CASPER contract alignment)
"""

from __future__ import annotations

from analytics.casper.casper_payload import (
    CASPER_CONTRACT_VERSION as PAYLOAD_CASPER_CONTRACT_VERSION,
)
from analytics.contracts_v14 import (
    CASPER_CONTRACT_VERSION as CONTRACTS_CASPER_CONTRACT_VERSION,
)
from analytics.contracts_v14 import CasperResult


def test_payload_casper_contract_version_is_frozen() -> None:
    """analytics.casper.casper_payload.CASPER_CONTRACT_VERSION is the value
    emitted into every CASPER JSON payload (see _casper_to_dict). Pin it.
    """
    assert PAYLOAD_CASPER_CONTRACT_VERSION == "casper_result_v1"


def test_contracts_casper_contract_version_is_frozen() -> None:
    """analytics.contracts_v14.CASPER_CONTRACT_VERSION is the value returned
    by CasperResult.contract_version(). Currently "v1.0" — different from
    the payload constant. Pinned to catch any future drift in either
    location.

    Pre-existing follow-up: these two constants should be reconciled.
    They were independently introduced in different modules and have
    silently disagreed since at least Sprint 14. Out of scope for the
    current branch.
    """
    assert CONTRACTS_CASPER_CONTRACT_VERSION == "v1.0"


def test_casper_result_constructs_with_canonical_fields() -> None:
    """The canonical CasperResult dataclass accepts a minimal scenario
    sentinel plus the documented fields. This pins the constructor surface
    against accidental field additions or removals.
    """
    result = CasperResult(
        scenario="<frozen-contract-stub>",
        baseline_kpis={"project_irr": 0.12},
        sensitivities=None,
        monte_carlo=None,
    )
    assert result.baseline_kpis["project_irr"] == 0.12
    assert result.sensitivities is None
    assert result.monte_carlo is None


def test_casper_result_contract_version_method_matches_contracts_constant() -> None:
    """CasperResult.contract_version is currently a no-args method whose
    return value must equal the contracts_v14-level constant.
    Pinning both forms guards against drift in either direction.
    """
    result = CasperResult(scenario="<frozen-contract-stub>")
    assert result.contract_version() == CONTRACTS_CASPER_CONTRACT_VERSION


def test_casper_result_has_documented_canonical_fields() -> None:
    """The CasperResult dataclass must expose exactly the canonical
    field set. New fields require an explicit contract version bump.
    """
    canonical_fields = {
        "scenario",
        "baseline_kpis",
        "sensitivities",
        "monte_carlo",
        "metadata",
    }
    annotations = set(CasperResult.__annotations__.keys())
    # Use set equality so additions are caught loudly.
    assert annotations == canonical_fields, (
        f"CasperResult field set drifted. "
        f"Added: {annotations - canonical_fields}. "
        f"Removed: {canonical_fields - annotations}."
    )
