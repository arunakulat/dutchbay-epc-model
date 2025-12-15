import pandas as pd
import pytest

import analytics.sensitivity_tail_risk as tr
from analytics import evaluation_v14
from analytics.contracts_v14 import SensitivitySuite, TornadoResult
from analytics.sensitivity_tail_risk import (
    tornado_suite_to_dataframe as _original_tornado_df,
)


def test_evaluate_with_casper_tail_risk_smoke(
    tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    CASPER + tail-risk orchestrator smoke test.

    - Patches run_v14_pipeline and run_monte_carlo_analysis.
    - Patches tornado_suite_to_dataframe to avoid sensitivity_export.
    - Creates toy YAML configs on disk so evaluation_v14 can resolve paths.
    - Asserts that CASPER result + tail_risk metadata are populated.
    """
    # --- 1. Create toy config files on disk ---------------------------------
    conf_dir = tmp_path_factory.mktemp("conf")

    cfg_path = conf_dir / "toy.yaml"
    mc_cfg_path = conf_dir / "monte_carlo_toy.yaml"

    # Minimal YAML bodies; content is irrelevant because we monkeypatch
    # the actual pipeline + MC orchestrators.
    cfg_path.write_text(
        "project:\n" "  name: Toy Scenario\n" "  capex_usd_per_kw: 1500\n"
    )
    mc_cfg_path.write_text("monte_carlo:\n" "  iterations: 10\n")

    # --- 2. Patch pipeline + MC orchestrators inside evaluation_v14 ---------
    from tests.analytics_layer._casper_fakes import (
        fake_run_monte_carlo_analysis as _fake_run_monte_carlo_analysis,
    )
    from tests.analytics_layer._casper_fakes import (
        fake_run_v14_pipeline as _fake_run_v14_pipeline,  # type: ignore[import]
    )

    monkeypatch.setattr(evaluation_v14, "run_v14_pipeline", _fake_run_v14_pipeline)
    monkeypatch.setattr(
        evaluation_v14,
        "run_monte_carlo_analysis",
        _fake_run_monte_carlo_analysis,
    )

    # --- 3. Patch tornado_df so tail-risk code doesn't touch export module ---
    def fake_tornado_df(_suite: SensitivitySuite) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "Variable": ["project.capex_usd_per_kw"],
                "Low Metric": [0.11],
                "High Metric": [0.13],
            }
        )

    monkeypatch.setattr(tr, "tornado_suite_to_dataframe", fake_tornado_df)

    # --- 4. Minimal SensitivitySuite for tail-risk enrichment ----------------
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
