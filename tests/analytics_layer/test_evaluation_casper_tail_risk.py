"""CASPER + tail-risk orchestrator smoke test (revived from quarantine).

History:
    Originally quarantined by scripts/quarantine_bad_irr_mc_tests.py with the
    reason "absolute IRR band assertions without frozen/regression labeling".
    Investigation (Sprint 18D) determined the quarantine reason was a false
    positive: this test asserts no absolute IRR bands — only structural
    properties of the assembled CASPER result.

Why revived:
    - Sprint 18B aligned EquityPerformance to a canonical 4-field surface.
    - casper_payload.py was reading legacy attributes (ep.downside, ep.moic,
      etc.) and raising AttributeError on real CASPER runs.
    - This test is the only canonical integration-shaped guard that
      exercises evaluate_with_casper_tail_risk end-to-end with deterministic
      fakes, making it the highest-leverage regression test for the bug
      class fixed on branch fix/casper-equity-performance-contract-alignment.

Adaptations vs the quarantined version:
    - TornadoResult fields updated to the canonical Sprint 18C/18B surface
      (metric_name / base_metric / shock_results / impact_abs / metadata).
    - SensitivitySuite.base_metric was removed in Sprint 18C and replaced
      by base_kpis: dict[str, float]. Updated accordingly.
    - Sprint 19 (#60 unpark): the tail-risk enrichment block in
      evaluation_v14 was removed (it lazily imported helpers that no longer
      exist anywhere; the live API is analytics.sensitivity.tail_risk.
      enrich_suite_with_tail_risk, which is suite-centric with a different
      shape). Re-enabling tail-risk is a tracked follow-up. This test no
      longer stubs the enrichment helpers; instead it pins the deferred
      state (no tail_risk metadata) so the re-enable PR flips it deliberately.

Framework Compliance:
    - TEST-01: integration-shaped regression pin with deterministic fakes
    - TYPE-01: full type hints
    - ARCH-04: canonical contracts_v14 surface only
    - GWTF R23/R25: lives on a feature branch with PR + CI

Author: Aruna Kulatunga
Sprint: 18D (CASPER contract alignment); 19 (#60 unpark)
"""

from __future__ import annotations

import pytest

from analytics import evaluation_v14
from analytics.contracts_v14 import (
    SensitivitySuite,
    ShockResult,
    TornadoResult,
)


def test_evaluate_with_casper_tail_risk_smoke(
    tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CASPER + tail-risk orchestrator smoke test.

    - Patches run_v14_pipeline and run_monte_carlo_analysis with the
      deterministic fakes in tests/analytics_layer/_casper_fakes.py.
    - Creates toy YAML configs on disk so evaluation_v14 can resolve paths.
    - Asserts the CASPER result is assembled end-to-end (scenario,
      baseline_kpis, monte_carlo, attached sensitivity suite).
    - Tail-risk enrichment is currently deferred (#60 re-enable follow-up),
      so metadata must NOT carry a tail_risk block; this pins that state.
    """
    # --- 1. Create toy config files on disk ---------------------------------
    conf_dir = tmp_path_factory.mktemp("conf")

    cfg_path = conf_dir / "toy.yaml"
    mc_cfg_path = conf_dir / "monte_carlo_toy.yaml"

    # Minimal YAML bodies; content is irrelevant because we monkeypatch the
    # actual pipeline + MC orchestrators.
    cfg_path.write_text(
        "project:\n  name: Toy Scenario\n  capex_usd_per_kw: 1500\n"
    )
    mc_cfg_path.write_text("monte_carlo:\n  iterations: 10\n")

    # --- 2. Patch pipeline + MC orchestrators inside evaluation_v14 ---------
    from tests.analytics_layer._casper_fakes import (
        fake_run_monte_carlo_analysis as _fake_run_monte_carlo_analysis,
    )
    from tests.analytics_layer._casper_fakes import (
        fake_run_v14_pipeline as _fake_run_v14_pipeline,
    )

    monkeypatch.setattr(evaluation_v14, "run_v14_pipeline", _fake_run_v14_pipeline)
    monkeypatch.setattr(
        evaluation_v14,
        "run_monte_carlo_analysis",
        _fake_run_monte_carlo_analysis,
    )

    # --- 3. Tail-risk enrichment is deferred (#60 re-enable follow-up) -------
    # evaluation_v14 no longer imports/calls the tail-risk enrichment helpers
    # (they targeted functions that no longer exist anywhere), so there is
    # nothing to stub here; we assert below that metadata carries no tail_risk
    # block. The re-enable PR will rewire onto enrich_suite_with_tail_risk and
    # flip these assertions back.

    # --- 4. Minimal SensitivitySuite (attached to the CASPER result) --------
    suite = SensitivitySuite(
        base_config_path=str(cfg_path),
        metric="project_irr",
        tornado_results=[
            TornadoResult(
                metric_name="project_irr",
                base_metric=0.12,
                shock_results=[
                    ShockResult(
                        variable_name="project.capex_usd_per_kw",
                        label="capex",
                        low_case=0.10,
                        high_case=0.14,
                        base_case=0.12,
                        impact=0.04,
                        impact_abs=0.04,
                        metric_name="project_irr",
                    ),
                ],
                label="capex",
                impact_abs=0.04,
            ),
        ],
    )

    # --- 5. Run orchestrator under test --------------------------------------
    result = evaluation_v14.evaluate_with_casper_tail_risk(
        config_path=str(cfg_path),
        monte_carlo_config_path=str(mc_cfg_path),
        sensitivity_suite=suite,
        metric="project_irr",
        confidence=0.9,
        validation_mode="strict",
        validation_modules=("cashflow", "debt"),
    )

    # --- 6. Assertions: CASPER result assembled end-to-end -------------------
    assert result.scenario is not None
    assert result.baseline_kpis["project_irr"] == pytest.approx(0.12)
    assert result.monte_carlo is not None
    assert result.sensitivities is suite

    # Tail-risk enrichment is deferred (#60 re-enable follow-up): the assembly
    # block was removed, so no tail_risk metadata is produced. Pin that state
    # so the re-enable PR flips these assertions back deliberately.
    assert "tail_risk" not in result.metadata
    assert "tail_risk_summary" not in result.metadata


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
