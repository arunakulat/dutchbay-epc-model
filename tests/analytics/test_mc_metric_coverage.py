"""O-5 independent three-trial oracle and nullable-metric consumer controls."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
import yaml

from analytics.contracts_v14 import MonteCarloResult
from analytics.mc.aggregate import aggregate_trials


def _rows() -> list[dict[str, float | None]]:
    """Reproduce the pre-existing independent O-5 measurement6422196112."""
    return [
        {"dscr_min": 1.05, "project_irr": 0.02, "equity_irr": None},
        {"dscr_min": 1.31, "project_irr": 0.09, "equity_irr": 0.11},
        {"dscr_min": 1.35, "project_irr": 0.10, "equity_irr": 0.12},
    ]


def _aggregate(rows: list[dict]) -> MonteCarloResult:
    return aggregate_trials(
        trial_metrics=rows,
        base_config={},
        param_names=["capex.usd_total"],
        samples=np.zeros((len(rows), 1)),
        meta={"seed": 42, "n_trials": len(rows)},
    )


def test_independent_o5_oracle_keeps_the_worst_dscr_and_project_trial() -> None:
    result = _aggregate(_rows())
    # These numbers predate this change; they are not a new writer-pinned canon.
    assert result.summary["dscr_min"]["min"] == 1.05
    assert result.dscr_min_p10 == pytest.approx(1.102)
    assert result.project_irr_p10 == pytest.approx(0.034)
    assert result.summary["equity_irr"]["min"] == 0.11
    assert result.summary["equity_irr"]["percentiles"][10] == pytest.approx(0.111)
    assert result.trials["equity_irr"] == [None, 0.11, 0.12]
    assert result.trials["dscr_min"] == [1.05, 1.31, 1.35]
    assert result.failed_iterations == 0
    assert result.success_rate() == 100
    assert result.metadata["partial_trial_count"] == 1
    assert result.metadata["metric_coverage"]["equity_irr"]["defined_count"] == 2
    assert result.metadata["metric_coverage"]["equity_irr"]["undefined_count"] == 1
    assert result.metadata["metric_coverage"]["dscr_min"]["defined_count"] == 3


def test_responsiveness_worst_dscr_changes_its_percentile_despite_undefined_equity() -> (
    None
):
    rows = _rows()
    rows[0]["dscr_min"] = 0.5
    result = _aggregate(rows)
    assert result.summary["dscr_min"]["min"] == 0.5
    assert result.dscr_min_p10 == pytest.approx(0.662)
    assert result.summary["equity_irr"]["percentiles"][10] == pytest.approx(0.111)


def test_all_undefined_metric_stays_visible_without_fabricating_zero() -> None:
    rows = _rows()
    for row in rows:
        row["equity_irr"] = None
    result = _aggregate(rows)
    assert result.trials["equity_irr"] == [None, None, None]
    assert result.summary["equity_irr"]["status"] == "undefined"
    for key in ("mean", "std", "min", "max"):
        assert result.summary["equity_irr"][key] is None
    coverage = result.metadata["metric_coverage"]["equity_irr"]
    assert coverage["defined_count"] == 0
    assert coverage["undefined_count"] == coverage["total_count"] == 3
    assert result.failed_iterations == 0
    assert result.dscr_min_p10 == pytest.approx(1.102)
    json.dumps(result.model_dump(), allow_nan=False)


def test_zero_is_defined_and_missing_is_distinguished_from_explicit_undefined() -> None:
    rows = _rows()
    rows[0]["equity_irr"] = 0.0
    del rows[1]["equity_irr"]
    result = _aggregate(rows)
    assert result.trials["equity_irr"] == [0.0, None, 0.12]
    assert result.summary["equity_irr"]["min"] == 0.0
    coverage = result.metadata["metric_coverage"]["equity_irr"]
    assert coverage["missing_count"] == 1
    assert coverage["undefined_count"] == 0
    assert coverage["defined_count"] == 2
    assert result.trials["dscr_min"] == [1.05, 1.31, 1.35]


def test_genuine_failure_keeps_original_row_identity_and_counts_failure() -> None:
    rows = _rows()
    rows.insert(1, {})
    result = _aggregate(rows)
    assert result.iterations == 4
    assert result.failed_iterations == 1
    assert result.success_rate() == 75
    assert result.trials["dscr_min"] == [1.05, None, 1.31, 1.35]
    assert result.trials["equity_irr"] == [None, None, 0.11, 0.12]
    assert {len(values) for values in result.trials.values()} == {4}
    assert result.dscr_min_p10 == pytest.approx(1.102)


@pytest.mark.parametrize("invalid", ["n/a", True, float("nan"), float("inf"), 10**400])
def test_invalid_metric_is_disclosed_without_erasing_other_defined_metrics(
    invalid: object,
) -> None:
    rows = _rows()
    rows[0]["equity_irr"] = invalid  # type: ignore[assignment]
    result = _aggregate(rows)
    assert result.metadata["metric_coverage"]["equity_irr"]["invalid_count"] == 1
    assert result.failed_iterations == 1
    assert result.dscr_min_p10 == pytest.approx(1.102)
    assert result.trials["equity_irr"][0] is None
    json.dumps(result.model_dump(), allow_nan=False)


def test_equal_length_contract_retains_null_positions_and_refuses_ragged_data() -> None:
    MonteCarloResult(trials={"equity_irr": [None, 0.11], "dscr_min": [1.05, 1.31]})
    with pytest.raises(ValueError, match="same length"):
        MonteCarloResult(trials={"equity_irr": [0.11], "dscr_min": [1.05, 1.31]})


def test_lender_table_uses_metric_denominators_and_never_calls_unknown_a_nonbreach() -> (
    None
):
    from analytics.mc.exports import build_casper_risk_blocks, build_lender_risk_table

    result = _aggregate(_rows())
    frame = build_lender_risk_table(result, metric_map={"project_irr": "equity_irr"})
    irr = frame.loc[frame["metric"] == "Project IRR"].iloc[0]
    assert irr["P90"] == pytest.approx(0.111)
    assert irr["defined_trials"] == 2
    assert irr["total_trials"] == 3
    assert irr["unavailable_trials"] == 1
    block = build_casper_risk_blocks(result)
    assert block["covenant"]["prob_breach"] == pytest.approx(1 / 3)
    assert block["covenant"]["n_trials"] == block["covenant"]["n_total_trials"] == 3
    missing_dscr = _rows()
    missing_dscr[1]["dscr_min"] = None
    block = build_casper_risk_blocks(_aggregate(missing_dscr))
    assert block["covenant"]["prob_breach"] == 0.5
    assert block["covenant"]["n_trials"] == 2
    assert block["covenant"]["n_total_trials"] == 3


def test_all_undefined_export_is_disclosed_and_serializes_to_null() -> None:
    from analytics.casper.casper_payload import _json_safe_cell, _monte_carlo_to_dict
    from analytics.mc.exports import build_lender_risk_table

    rows = _rows()
    for row in rows:
        row["equity_irr"] = None
    result = _aggregate(rows)
    frame = build_lender_risk_table(result, metric_map={"project_irr": "equity_irr"})
    records = [
        {key: _json_safe_cell(key, value) for key, value in row.items()}
        for row in frame.to_dict(orient="records")
    ]
    irr = next(row for row in records if row["metric"] == "Project IRR")
    assert irr["P50"] is irr["P90"] is irr["mean"] is None
    assert irr["defined_trials"] == 0
    assert irr["total_trials"] == 3
    payload = _monte_carlo_to_dict(result)
    assert payload is not None
    assert payload["failed_iterations"] == 0
    assert payload["metric_coverage"]["equity_irr"]["undefined_count"] == 3
    json.dumps(records, allow_nan=False)
    json.dumps(payload, allow_nan=False)


def test_convergence_uses_each_metric_sample_and_cli_discloses_partial_coverage() -> (
    None
):
    from analytics.cli.cli_monte_carlo_hydra import _derive_run_status
    from analytics.mc.convergence import (
        convergence_diagnostic,
        percentile_ci_diagnostic,
    )

    result = _aggregate(_rows())
    convergence = convergence_diagnostic(result.trials, min_n=2)
    tails = percentile_ci_diagnostic(result.trials, min_n=2)
    assert convergence["dscr_min"]["n"] == tails["dscr_min"]["n"] == 3
    assert convergence["equity_irr"]["n"] == tails["equity_irr"]["n"] == 2
    assert _derive_run_status(3, 0, 0, partial_trial_count=1) == "degraded"
    assert _derive_run_status(3, 0, 0, partial_trial_count=0) == "success"


def test_core_breach_primitive_refuses_implicit_unknown_as_nonbreach() -> None:
    from analytics.core.covenant_breach import prob_breach

    with pytest.raises(ValueError, match="coverage denominator"):
        prob_breach(np.array([1.05, np.nan, 1.35]), 1.3)
    assert prob_breach(np.array([1.05, 1.35]), 1.3) == 0.5


def test_engine_gateway_keeps_independent_samples_through_tail_diagnostics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from analytics.mc import engine

    rows = iter(_rows())
    monkeypatch.setattr(engine, "evaluate_with_overrides", lambda **kwargs: next(rows))
    config_path = (
        Path(__file__).resolve().parents[2]
        / "scenarios/dutchbay_lendercase_2025Q4.yaml"
    )
    result = engine.run_monte_carlo_analysis(
        base_config=yaml.safe_load(config_path.read_text()), n_trials=3, seed=42
    )
    assert result.dscr_min_p10 == pytest.approx(1.102)
    assert result.trials["equity_irr"] == [None, 0.11, 0.12]
    assert result.metadata["toy_fallback_count"] == result.failed_iterations == 0
    assert result.metadata["var_cvar"]["dscr_min"]["var"] == pytest.approx(1.076)
    assert result.metadata["var_cvar"]["equity_irr"]["var"] == pytest.approx(0.1105)
    # The default convergence minimum is larger than this diagnostic fixture.
    assert result.metadata["metric_coverage"]["equity_irr"]["defined_count"] == 2


def test_joint_report_refuses_partial_cohorts_and_metadata_bridge_keeps_json_null(
    tmp_path,
) -> None:
    from analytics.capital_risk_layer_v14 import (
        build_capital_risk_report_from_trials,
        build_case_metadata_from_trials,
    )
    from analytics.core.risk_metrics import RiskConfig

    trials = {
        key: [1.0] * 20
        for key in (
            "equity_irr",
            "project_irr",
            "equity_npv",
            "project_npv",
            "dscr_min",
            "llcr",
            "plcr",
        )
    }
    trials["equity_irr"][0] = None  # type: ignore[call-overload]
    metadata = build_case_metadata_from_trials(trials)
    assert metadata["metadata"]["trials"]["equity_irr"][0] is None
    json.dumps(metadata, allow_nan=False)
    with pytest.raises(ValueError, match="complete aligned metric observations"):
        build_capital_risk_report_from_trials(
            trials,
            tmp_path,
            risk_config=RiskConfig(
                confidence_level=0.95,
                target_return=0.1,
                min_dscr=1.3,
                min_llcr=1.4,
                min_plcr=1.5,
            ),
            scenario="synthetic_partial",
        )
    assert not list(tmp_path.iterdir())
