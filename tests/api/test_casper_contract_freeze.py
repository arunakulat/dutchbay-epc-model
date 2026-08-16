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
    - CasperResult.generation and .multi_tech_generation_breakdown were dropped
      from the canonical dataclass in the Palette refactor (979520b) while
      casper_payload kept building/reading them; **re-instated Sprint 19 (#60
      unpark)** so the builder/serializer and the contract agree again. The
      customer-visible payload keys ("generation", "technology_breakdown") were
      always part of casper_result_v1 (emitted by _casper_to_dict), so no
      payload version bump — only the documented field set grows by two.
    - CasperResult.scenario is now typed ScenarioResult | str (no None
      allowed). The test passes the string sentinel "<frozen-contract-stub>".
    - CasperResult.contract_version was previously defined as a no-args
      method on this branch's first pass. **Resolved in Sprint 18D, D.X+6**:
      converted to a class-level frozen attribute via
      ``field(default=CASPER_CONTRACT_VERSION, init=False)``. The test
      now asserts attribute-access form.
    - Two CASPER_CONTRACT_VERSION constants previously existed and
      disagreed: payload emitted "casper_result_v1" while contracts_v14
      held "v1.0". **Unified in Sprint 18D, D.X+5** to "casper_result_v1"
      (the customer-visible value that has been shipping in the JSON
      payload since at least Sprint 14). This freeze test now pins the
      unification: both constants MUST be equal.

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
from analytics.casper.casper_payload import (
    build_casper_payload,
)
from analytics.contracts_v14 import (
    CASPER_CONTRACT_VERSION as CONTRACTS_CASPER_CONTRACT_VERSION,
)
from analytics.contracts_v14 import (
    CasperResult,
    ParameterRangeConfig,
    SensitivitySuite,
)
from analytics.sensitivity.adapters import engine_to_tornado_result


def test_payload_casper_contract_version_is_frozen() -> None:
    """analytics.casper.casper_payload.CASPER_CONTRACT_VERSION is the value
    emitted into every CASPER JSON payload (see _casper_to_dict). Pin it.
    """
    assert PAYLOAD_CASPER_CONTRACT_VERSION == "casper_result_v1"


def test_contracts_casper_contract_version_is_frozen() -> None:
    """analytics.contracts_v14.CASPER_CONTRACT_VERSION must equal the
    payload-level constant. Unified in Sprint 18D (D.X+5) to
    "casper_result_v1" — previously the two locations silently disagreed
    ("v1.0" here vs "casper_result_v1" in casper_payload) since at least
    Sprint 14.

    This test now also pins the unification: both constants MUST be equal.
    """
    assert CONTRACTS_CASPER_CONTRACT_VERSION == "casper_result_v1"
    assert CONTRACTS_CASPER_CONTRACT_VERSION == PAYLOAD_CASPER_CONTRACT_VERSION


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


def test_casper_result_contract_version_attribute_matches_contracts_constant() -> None:
    """CasperResult.contract_version is a class-level frozen attribute
    (resolved in Sprint 18D, D.X+6 — previously a no-args method, which
    silently became a bound method whenever callers used attribute access).

    The value must equal the contracts_v14-level constant, which is itself
    unified with the payload-level constant (test above).
    """
    result = CasperResult(scenario="<frozen-contract-stub>")
    # Attribute access — NOT a method call. Pinned to catch any future
    # accidental reversion to method form.
    assert result.contract_version == CONTRACTS_CASPER_CONTRACT_VERSION
    assert isinstance(result.contract_version, str)

    # init=False: contract_version cannot be passed to the constructor.
    import pytest

    with pytest.raises(TypeError):
        CasperResult(scenario="stub", contract_version="hacked")  # type: ignore[call-arg]


def test_casper_result_has_documented_canonical_fields() -> None:
    """The CasperResult dataclass must expose exactly the canonical
    field set. New fields require an explicit contract version bump.

    Sprint 18D, D.X+6 update: ``contract_version`` is now a class-level
    frozen attribute (was previously a method) and therefore appears in
    ``__annotations__``. Adding it to the canonical set is the explicit
    "contract version bump" this test asks for: the public payload key
    is unchanged ("casper_result_v1") but the Python attribute surface
    grew by one. Pinned here so any further field additions still trip.
    """
    canonical_fields = {
        "scenario",
        "baseline_kpis",
        "sensitivities",
        "monte_carlo",
        "generation",  # Sprint 19 (#60): re-instated (consumed by casper_payload)
        "multi_tech_generation_breakdown",  # Sprint 19 (#60): re-instated
        "multi_tech_wbs",  # ARCH-3 (#475): per-tech cost/return work-breakdown
        "metadata",
        "contract_version",  # D.X+6: was method, now init=False frozen attr
    }
    annotations = set(CasperResult.__annotations__.keys())
    # Use set equality so additions are caught loudly.
    assert annotations == canonical_fields, (
        f"CasperResult field set drifted. "
        f"Added: {annotations - canonical_fields}. "
        f"Removed: {canonical_fields - annotations}."
    )


def test_casper_v1_tornado_row_is_labelled_and_rankable() -> None:
    """Existing v1 tornado keys carry the real adapter's non-null driver metadata."""
    parameter = ParameterRangeConfig(
        variable_name="capex.usd_total",
        base_value=159_600_000.0,
        low_pct=-0.10,
        high_pct=0.10,
        label="CAPEX",
    )
    tornado = engine_to_tornado_result(
        parameter=parameter,
        metric_key="project_irr",
        base_value=0.014551597740253388,
        cases=[
            {"label": "capex=low", "value": 0.025129198450968886},
            {"label": "capex=high", "value": 0.005493346017928717},
        ],
    )
    suite = SensitivitySuite(
        base_config_path="scenarios/dutchbay_lendercase_2025Q4.yaml",
        metric="project_irr",
        tornado_results=[tornado],
        base_kpis={"project_irr": 0.014551597740253388},
    )

    payload = build_casper_payload(scenario="contract-freeze", sensitivity=suite)
    row = payload["sensitivity"]["tornado"][0]

    assert payload["contract_version"] == "casper_result_v1"
    assert set(row) == {
        "variable",
        "base_irr",
        "low_irr",
        "high_irr",
        "impact_abs",
        "impact_pct",
    }
    assert row == {
        "variable": "CAPEX",
        "base_irr": 0.014551597740253388,
        "low_irr": 0.025129198450968886,
        "high_irr": 0.005493346017928717,
        "impact_abs": 0.01963585243304017,
        "impact_pct": -0.01963585243304017,
    }
