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
      existed). Re-enabled in #165 onto the live suite-centric API
      analytics.sensitivity.tail_risk.enrich_suite_with_tail_risk: the
      orchestrator now surfaces metadata["tail_risk"] (per-parameter table)
      and metadata["tail_risk_summary"] ({metric: snapshot}, consumer-shaped).
      This test asserts enrichment is present and end-to-end consumer-readable.

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
    - Tail-risk enrichment is re-enabled (#165): metadata carries a
      tail_risk table and a consumer-shaped tail_risk_summary.
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

    # --- 3. Tail-risk enrichment runs for real (#165) -----------------------
    # evaluation_v14 now calls the real enrich_suite_with_tail_risk on the
    # attached suite (no stubbing needed — it is deterministic and derives its
    # snapshot from the suite's tornado/shock data, not from MC arrays). We
    # assert below that the metadata is populated and consumer-shaped.

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
    # monte_carlo is the engine's MonteCarloResult dataclass (not a dict). The
    # orchestrator must have called the engine with n_trials = the config's
    # iterations (10) and surfaced the dataclass — the previous wiring passed
    # config=/n_iterations= and did dict .get() on the frozen result.
    assert result.monte_carlo is not None
    assert result.monte_carlo.iterations == 10
    assert result.monte_carlo.project_irr_p10 == pytest.approx(0.11)
    assert result.sensitivities is suite

    # Tail-risk enrichment re-enabled (#165): metadata carries both the
    # per-parameter table and the {metric: snapshot} summary.
    assert "tail_risk" in result.metadata
    assert "tail_risk_summary" in result.metadata

    # Per-parameter table: one honest row per tornado, derived from the shock
    # cases (low_case=0.10 / high_case=0.14 on the single capex shock).
    table = result.metadata["tail_risk"]
    assert isinstance(table, list) and len(table) == 1
    assert table[0]["metric"] == "project_irr"
    assert table[0]["downside"] == pytest.approx(0.10)
    assert table[0]["upside"] == pytest.approx(0.14)

    # Per-metric summary keyed by metric name (consumer contract).
    summary = result.metadata["tail_risk_summary"]
    assert "project_irr" in summary
    snap = summary["project_irr"]
    assert snap["base_value"] == pytest.approx(0.12)
    assert snap["downside"] == pytest.approx(0.10)
    assert snap["upside"] == pytest.approx(0.14)
    # alpha is derived from `confidence` (0.9 -> 0.10), not hardcoded.
    assert snap["cvar_alpha"] == pytest.approx(0.10)

    # End-to-end producer -> consumer contract: the CASPER payload helper must
    # surface the suite-centric summary. Guards the silent-None shape mismatch
    # (a flat run-summary would be dropped by _tail_risk_from_metadata).
    from analytics.casper.casper_payload import _tail_risk_from_metadata

    surfaced = _tail_risk_from_metadata(result.metadata)
    assert surfaced is not None
    assert "project_irr" in surfaced


def test_evaluate_with_casper_tail_risk_real_engine(tmp_path: object) -> None:
    """End-to-end with NO fakes: the real pipeline + real MC engine on the
    canonical lender scenario must drive CASPER tail-risk to a populated
    MonteCarloResult. This is the guard the faked smoke test could not provide —
    it exercises the exact wiring that was dead (engine kwargs + dataclass
    result handling) against real code.
    """
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[2]
    lender = repo_root / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"
    mc_cfg = Path(tmp_path) / "mc_small.yaml"  # type: ignore[arg-type]
    mc_cfg.write_text("monte_carlo:\n  iterations: 6\n  seed: 42\n", encoding="utf-8")

    result = evaluation_v14.evaluate_with_casper_tail_risk(
        config_path=str(lender),
        monte_carlo_config_path=str(mc_cfg),
        metric="project_irr",
        confidence=0.9,
    )

    assert result.monte_carlo is not None
    assert result.monte_carlo.iterations == 6
    assert result.monte_carlo.failed_iterations == 0
    assert result.monte_carlo.success_rate() == 100.0
    # Real distribution, ordered, finite.
    p10 = result.monte_carlo.project_irr_p10
    p90 = result.monte_carlo.project_irr_p90
    assert isinstance(p10, float) and isinstance(p90, float)
    assert p10 <= result.monte_carlo.project_irr_p50 <= p90


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
