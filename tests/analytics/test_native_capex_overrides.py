"""Native input overrides, financial parity, provenance and report reload."""

import copy
from pathlib import Path
from typing import Any

import pytest
import yaml

from analytics.evaluation_v14 import evaluate_with_overrides, evaluated_scenario_config
from analytics.pipeline_v14_enhanced import PipelineValidationError
from analytics.run_manifest import build_run_manifest, config_sha256
from finance.native_cost_inputs import normalize_native_capex


def cases() -> tuple[dict[str, Any], dict[str, Any]]:
    """Author equivalent flat USD and LKR cases from existing public inputs."""
    path = (
        Path(__file__).resolve().parents[2]
        / "scenarios/blue_whale_wind_lot5b_2026.yaml"
    )
    usd = yaml.safe_load(path.read_text())
    amount = usd["capex"]["usd_total"]
    rate = usd["fx"]["start_lkr_per_usd"]
    native = copy.deepcopy(usd)
    native["capex"].pop("usd_total")
    native["capex"].pop("capex_per_kw_usd")
    # The scalar is a derived, unused annotation, excluded by the flat contract.
    usd["capex"].pop("capex_per_kw_usd")
    native["capex"]["input"] = {
        "currency": "LKR",
        "amount": amount * rate,
        "price_date": "2026-01-01",
        "financial_close_date": "2027-01-01",
        "conversion": {
            "rate_lkr_per_usd": rate,
            "date": "2027-01-01",
            "source": "synthetic test",
            "basis": "financial_close",
        },
    }
    return usd, native


def test_usd_lkr_parity_reload_manifest_and_override() -> None:
    """Preserve financial parity, single escalation and live override provenance."""
    usd, native = cases()
    baseline = evaluate_with_overrides(raw_config=usd, return_full_result=True)
    actual = evaluate_with_overrides(raw_config=native, return_full_result=True)
    assert actual["annual_rows"] == baseline["annual_rows"]
    assert actual["debt_result"] == baseline["debt_result"]
    assert actual["kpis"] == baseline["kpis"]
    resolved = evaluated_scenario_config(native)
    assert evaluated_scenario_config(resolved) == resolved
    assert actual["run_manifest"]["config_sha256"] == config_sha256(resolved)
    assert (
        actual["run_manifest"]["native_capex"]
        == resolved["capex"]["native_input_applied"]
    )
    assert actual["run_manifest"]["native_capex"]["input"] == native["capex"]["input"]
    changed = evaluate_with_overrides(
        raw_config=native,
        overrides={"capex.input.amount": native["capex"]["input"]["amount"] * 2},
        return_full_result=True,
    )
    assert changed["debt_result"]["funding"]["sources_and_uses"]["uses"][
        "capex_usd"
    ] == pytest.approx(
        2 * actual["debt_result"]["funding"]["sources_and_uses"]["uses"]["capex_usd"]
    )
    assert (
        changed["run_manifest"]["native_capex"]["input"]["amount"]
        == 2 * native["capex"]["input"]["amount"]
    )
    assert changed["kpis"]["project_npv"] < actual["kpis"]["project_npv"]
    with pytest.raises(Exception, match="conflict|stale"):
        evaluate_with_overrides(raw_config=native, overrides={"capex.usd_total": 1})
    with pytest.raises(ValueError, match="stale"):
        altered = normalize_native_capex(native)
        altered["capex"]["usd_total"] = 1
        normalize_native_capex(altered)


def test_mc_perturbs_native_amount_and_records_each_trial(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Native Monte Carlo samples the source amount rather than a stale USD alias."""
    import analytics.pipeline_v14_enhanced as pipeline
    from analytics.cost.mc_capex import run_capex_mc

    _, native = cases()
    before = copy.deepcopy(native)
    manifests: list[dict[str, Any]] = []
    real_run = pipeline.run_v14_pipeline

    def capture(*args: Any, **kwargs: Any) -> Any:
        result = real_run(*args, **kwargs)
        manifests.append(result["run_manifest"]["native_capex"])
        return result

    monkeypatch.setattr(pipeline, "run_v14_pipeline", capture)
    result = run_capex_mc(native, n_samples=3, sigma_pct=15, seed=12)
    assert len(manifests) == 3
    assert len({x["input"]["amount"] for x in manifests}) == 3
    assert result.capex_usd["p10"] < result.capex_usd["p90"]
    for entry in manifests:
        assert (
            entry["usd_at_price_date"]
            == entry["input"]["amount"]
            / entry["input"]["conversion"]["rate_lkr_per_usd"]
        )
    assert native == before
    with pytest.raises(ValueError, match="authored"):
        run_capex_mc(normalize_native_capex(native), n_samples=1, sigma_pct=15)


def test_fx_perturbation_matches_equivalent_usd_ledger() -> None:
    """A changed close FX reconciles to the corresponding independent USD case."""
    usd, native = cases()
    rate = native["fx"]["start_lkr_per_usd"] * 1.2
    native["fx"]["start_lkr_per_usd"] = rate
    native["capex"]["input"]["conversion"].update(
        rate_lkr_per_usd=rate, source="synthetic changed close rate"
    )
    usd["fx"]["start_lkr_per_usd"] = rate
    usd["capex"]["usd_total"] = native["capex"]["input"]["amount"] / rate
    left = evaluate_with_overrides(raw_config=native, return_full_result=True)
    right = evaluate_with_overrides(raw_config=usd, return_full_result=True)
    assert left["annual_rows"] == right["annual_rows"]
    assert left["debt_result"] == right["debt_result"]
    assert left["kpis"] == right["kpis"]


def test_manifest_freezes_native_provenance_and_declares_its_schema() -> None:
    """Later input mutation must not detach provenance from its original hash."""
    usd, native = cases()
    resolved = normalize_native_capex(native)
    manifest = build_run_manifest(resolved)
    before = manifest.as_dict()
    resolved["capex"]["native_input_applied"]["input"]["amount"] = 1.0
    assert manifest.as_dict() == before
    assert before["manifest_schema_version"] == "1.1"
    legacy = build_run_manifest(usd).as_dict()
    assert legacy["manifest_schema_version"] == "1.0"
    assert "native_capex" not in legacy


def test_resolved_native_config_refuses_changed_construction_phasing() -> None:
    """Saved price escalation cannot conceal a changed construction draw basis."""
    _, native = cases()
    native["project"]["cod_year"] = 2029
    native["timeline"]["construction_years"] = 2
    native["Financing_Terms"].update(
        construction_periods=2, construction_schedule=[1, 0]
    )
    resolved = evaluated_scenario_config(native)
    assert evaluated_scenario_config(resolved) == resolved
    override = {"Financing_Terms.construction_schedule": [0, 1]}
    fresh = evaluate_with_overrides(
        raw_config=native, overrides=override, return_full_result=True
    )
    assert fresh["debt_result"]["funding"]["sources_and_uses"]["uses"][
        "capex_usd"
    ] == pytest.approx(
        native["capex"]["input"]["amount"] / native["fx"]["start_lkr_per_usd"] * 1.05**2
    )
    stale = copy.deepcopy(resolved)
    stale["Financing_Terms"]["construction_schedule"] = [0, 1]
    with pytest.raises(ValueError, match="stale.*price|price.*stale"):
        normalize_native_capex(stale)
    with pytest.raises(PipelineValidationError, match="stale.*price|price.*stale"):
        evaluate_with_overrides(
            raw_config=resolved, overrides=override, return_full_result=True
        )
