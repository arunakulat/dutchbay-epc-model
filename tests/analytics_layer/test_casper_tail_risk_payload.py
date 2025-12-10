from __future__ import annotations

import pandas as pd
import pytest

from analytics import evaluation_v14
from analytics import sensitivity_tail_risk as tr
from analytics.contracts_v14 import (
    SensitivitySuite,
    TornadoResult,
    build_casper_payload,
)
from tests.analytics_layer._casper_fakes import (  # type: ignore[import]
    fake_run_monte_carlo_analysis,
    fake_run_v14_pipeline,
)


def test_casper_payload_includes_tail_risk_metadata(
    tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Ensure build_casper_payload preserves tail-risk metadata coming from
    evaluate_with_casper_tail_risk.

    This is deliberately end-to-end-ish but with cheap fakes:
    - Toy config files on disk so evaluation_v14 can resolve paths.
    - Fake pipeline + MC orchestrators from _casper_fakes.
    - Patched tornado_df so tail-risk enrichment doesn't touch export module.
    """
    # --- 1. Create toy config files on disk -------------------------------------
    conf_dir = tmp_path_factory.mktemp("conf")

    cfg_path = conf_dir / "toy.yaml"
    mc_cfg_path = conf_dir / "monte_carlo_toy.yaml"

    cfg_path.write_text(
        "project:\n" "  name: Toy Scenario\n" "  capex_usd_per_kw: 1500\n"
    )
    mc_cfg_path.write_text("monte_carlo:\n" "  iterations: 10\n")

    # --- 2. Patch pipeline + MC orchestrators inside evaluation_v14 -------------
    monkeypatch.setattr(evaluation_v14, "run_v14_pipeline", fake_run_v14_pipeline)
    monkeypatch.setattr(
        evaluation_v14,
        "run_monte_carlo_analysis",
        fake_run_monte_carlo_analysis,
    )

    # --- 3. Patch tornado_df so tail-risk code doesn't touch export module -----
    def fake_tornado_df(_suite: SensitivitySuite) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "Variable": ["project.capex_usd_per_kw"],
                "Low Metric": [0.11],
                "High Metric": [0.13],
            }
        )

    monkeypatch.setattr(tr, "tornado_suite_to_dataframe", fake_tornado_df)

    # --- 4. Minimal SensitivitySuite for tail-risk enrichment -------------------
    suite = SensitivitySuite(
        tornado_results=[
            TornadoResult(
                variable="project.capex_usd_per_kw",
                base_irr=0.12,
                low_irr=0.10,
                high_irr=0.14,
            ),
        ],
        base_metric=0.12,
        base_config_path=str(cfg_path),
        metric="project_irr",
    )

    # --- 5. Run CASPER + tail-risk orchestrator --------------------------------
    casper_result = evaluation_v14.evaluate_with_casper_tail_risk(
        config_path=str(cfg_path),
        monte_carlo_config_path=str(mc_cfg_path),
        sensitivity_suite=suite,
        metric="project_irr",
        confidence=0.9,
        validation_mode="strict",
        validation_modules=("cashflow", "debt"),
    )

    # --- 6. Build CASPER payload from the result --------------------------------
    payload = build_casper_payload(
        scenario=casper_result.scenario,
        baseline_kpis=casper_result.baseline_kpis,
        sensitivities=casper_result.sensitivities,
        monte_carlo=casper_result.monte_carlo,
        metadata=casper_result.metadata,
    )

    # Basic CASPER surface checks
    assert "scenario" in payload
    assert "baseline_kpis" in payload
    assert "monte_carlo" in payload

    # Tail-risk should be preserved under metadata["tail_risk"]
    assert "metadata" in payload
    metadata = payload["metadata"]
    assert "tail_risk" in metadata

    tail = metadata["tail_risk"]
    assert tail["metric"] == "project_irr"
    assert tail["confidence"] == pytest.approx(0.9)

    # Rows come from tail-risk enrichment; we only need a sanity shape check.
    rows = tail["rows"]
    assert isinstance(rows, list)
    assert rows, "tail_risk.rows should not be empty"

    first_row = rows[0]
    # From enrich_tornado_with_tail_risk: breach probability column must exist
    assert "BreachProbability" in first_row
    assert 0.0 <= first_row["BreachProbability"] <= 1.0
