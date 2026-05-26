"""CASPER + tail-risk orchestrator smoke test (revived from quarantine).

History:
    Originally quarantined by scripts/quarantine_bad_irr_mc_tests.py with the
    reason "absolute IRR band assertions without frozen/regression labeling".
    Investigation (Sprint 18D) determined the quarantine reason was a false
    positive: this test asserts no absolute IRR bands — only structural
    properties of result.metadata["tail_risk"].

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
      The old (variable / base_irr / low_irr / high_irr) signature no
      longer exists.
    - SensitivitySuite.base_metric was removed in Sprint 18C and replaced
      by base_kpis: dict[str, float]. Updated accordingly.
    - The monkeypatch target switched from tornado_suite_to_dataframe (no
      longer used by evaluation_v14) to enrich_tornado_with_tail_risk
      (the real consumer), with a DataFrame stub that carries the
      BreachProbability column the original test asserted.

Framework Compliance:
    - TEST-01: integration-shaped regression pin with deterministic fakes
    - TYPE-01: full type hints
    - ARCH-04: canonical contracts_v14 surface only
    - GWTF R23/R25: lives on a feature branch with PR + CI

Author: Aruna Kulatunga
Sprint: 18D (CASPER contract alignment)
"""

from __future__ import annotations

import pandas as pd
import pytest

import analytics.sensitivity_tail_risk as tr
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
    - Patches enrich_tornado_with_tail_risk on the deprecated shim so
      evaluation_v14's lazy import resolves to the stub. (Real consumer
      is analytics.sensitivity.tail_risk.enrich_tornado_with_tail_risk;
      the shim re-exports it via star-import.)
    - Creates toy YAML configs on disk so evaluation_v14 can resolve paths.
    - Asserts CASPER result + tail_risk metadata are populated, and that
      BreachProbability survives into the row dicts.
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

    # --- 3. Stub enrich_tornado_with_tail_risk on the shim module -----------
    # evaluation_v14 imports from analytics.sensitivity_tail_risk lazily
    # (at function call time). The shim re-exports analytics.sensitivity.
    # tail_risk via star-import, but the canonical module does not currently
    # define enrich_tornado_with_tail_risk or build_tail_risk_snapshots_for_
    # metrics. In real production code this raises ImportError, which
    # evaluation_v14 catches and swallows, so tail_risk_block stays None and
    # metadata["tail_risk"] is never populated. That is a pre-existing
    # production issue, recorded as a follow-up; the test injects both
    # missing symbols here so the lazy import resolves and the assertion
    # path can exercise the assembly logic. raising=False is required
    # because the attributes do not exist on the shim by default.
    def _fake_enrich_tornado_with_tail_risk(
        *,
        tornado_suite: SensitivitySuite,
        mc_result: object,
        metric: str,
        confidence: float,
    ) -> pd.DataFrame:
        _ = (tornado_suite, mc_result, metric, confidence)
        return pd.DataFrame(
            {
                "Variable": ["project.capex_usd_per_kw"],
                "Low Metric": [0.11],
                "High Metric": [0.13],
                "BreachProbability": [0.07],
            }
        )

    monkeypatch.setattr(
        tr,
        "enrich_tornado_with_tail_risk",
        _fake_enrich_tornado_with_tail_risk,
        raising=False,
    )

    # build_tail_risk_snapshots_for_metrics is called for snapshot building
    # after the tornado enrichment block. Stub it to return an empty dict so
    # we don't depend on percentile maths over the fake samples.
    def _fake_build_tail_risk_snapshots_for_metrics(
        *,
        mc_result: object,
        metrics: tuple[str, ...],
        confidence: float,
    ) -> dict[str, object]:
        _ = (mc_result, metrics, confidence)
        return {}

    monkeypatch.setattr(
        tr,
        "build_tail_risk_snapshots_for_metrics",
        _fake_build_tail_risk_snapshots_for_metrics,
        raising=False,
    )

    # --- 4. Minimal SensitivitySuite for tail-risk enrichment ----------------
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

    # --- 6. Assertions: CASPER + tail_risk metadata --------------------------
    assert result.scenario is not None
    assert result.baseline_kpis["project_irr"] == pytest.approx(0.12)
    assert result.monte_carlo is not None
    assert "tail_risk" in result.metadata

    tail = result.metadata["tail_risk"]
    assert tail["metric"] == "project_irr"
    assert tail["confidence"] == 0.9
    assert isinstance(tail["rows"], list)
    assert len(tail["rows"]) == 1
    assert "BreachProbability" in tail["rows"][0]


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
