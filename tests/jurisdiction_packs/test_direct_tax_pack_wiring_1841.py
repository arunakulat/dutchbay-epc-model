"""Tests for direct-tax jurisdiction pack wiring (#1841 PR 4)."""

from __future__ import annotations

import copy
import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest
import yaml

from analytics.feasibility_report_contract.project_case import (
    ContractSupportStatus,
    JurisdictionBinding,
    JurisdictionSubject,
)
from analytics.jurisdiction_packs import (
    PACKS_ROOT,
    JurisdictionPack,
    JurisdictionRefusal,
    RefusalReason,
)
from analytics.jurisdiction_packs.resolver import InMemoryPackSource
from analytics.pipeline_v14_enhanced import PipelineValidationError, run_v14_pipeline
from finance.cashflow_v14 import build_annual_rows
from finance.cashflow_v14_tax import (
    DirectTaxJurisdictionError,
    TaxConfig,
    resolve_direct_tax_from_pack,
)
from finance.equity_distribution_v14_hydra import _build_distribution_config
from finance.wacc_v14 import compute_build_up_wacc

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER_PATH = REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"
BLUE_WHALE_PATH = REPO_ROOT / "scenarios" / "blue_whale_wind_lot5b_2026.yaml"
LK_PACK_PATH = PACKS_ROOT / "lk" / "1.0.0.yaml"


def _load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def _raw_lk_pack() -> dict[str, Any]:
    return _load_yaml(LK_PACK_PATH)


def _pack_from_dict(data: dict[str, Any]) -> JurisdictionPack:
    return JurisdictionPack.model_validate_json(json.dumps(data, default=str))


def _binding(
    subject: JurisdictionSubject,
    *,
    code: str = "LK",
    pack_id: str = "dutchbay.jurisdiction.lk",
    version: str = "1.0.0",
    support: ContractSupportStatus = ContractSupportStatus.DECLARED,
    binding_id: str | None = None,
) -> JurisdictionBinding:
    return JurisdictionBinding(
        binding_id=binding_id or f"jb:{code.lower()}:{subject.value}",
        jurisdiction_code=code,
        subject=subject,
        support_status=support,
        contract_pack_id=pack_id,
        contract_pack_version=version,
    )


def _modified_lk_source(
    *,
    cit_rate: float | None = None,
    dividend_wht_rate: float | None = None,
    status: str | None = None,
) -> InMemoryPackSource:
    data = _raw_lk_pack()
    if status is not None:
        data["status"] = status
    for param in data["parameters"]:
        if cit_rate is not None and param["parameter_id"] == "lk.cit.standard_rate":
            param["value"] = cit_rate
        if (
            dividend_wht_rate is not None
            and param["parameter_id"] == "lk.wht.dividend_rate"
        ):
            param["value"] = dividend_wht_rate
    return InMemoryPackSource([_pack_from_dict(data)])


# ---------------------------------------------------------------------------
# 1. Pack-backed direct tax resolution & omitted statutory YAML keys
# ---------------------------------------------------------------------------


def test_lender_and_blue_whale_resolve_direct_tax_from_lk_pack() -> None:
    for path in (LENDER_PATH, BLUE_WHALE_PATH):
        cfg = _load_yaml(path)
        resolved = resolve_direct_tax_from_pack(cfg)
        assert resolved.corporate_tax_rate == pytest.approx(0.30)
        assert resolved.loss_carryforward_years == 6
        assert resolved.plant_depreciation_years == 5
        assert resolved.civil_depreciation_years == 20
        assert resolved.wht_on_interest_to_nonresidents == pytest.approx(0.10)
        assert resolved.wht_on_dividends == pytest.approx(0.15)
        assert resolved.corporate_tax_rate_by_year is None
        assert resolved.wht_on_interest_by_year is None

        tc = TaxConfig.from_yaml(cfg)
        assert tc.corporate_tax_rate == pytest.approx(0.30)
        assert tc.loss_carryforward_years == 6
        assert tc.plant_depreciation_years == 5
        assert tc.civil_depreciation_years == 20
        assert tc.wht_on_interest_to_nonresidents == pytest.approx(0.10)


def test_statutory_tax_fields_omitted_from_scenario_are_supplied_by_pack() -> None:
    cfg = _load_yaml(LENDER_PATH)
    for key in (
        "corporate_tax_rate",
        "loss_carryforward_years",
        "plant_depreciation_years",
        "civil_depreciation_years",
        "wht_on_interest_to_nonresidents",
        "wht_on_dividends",
    ):
        cfg["tax"].pop(key, None)

    tc = TaxConfig.from_yaml(cfg)
    assert tc.corporate_tax_rate == pytest.approx(0.30)
    assert tc.loss_carryforward_years == 6
    assert tc.plant_depreciation_years == 5
    assert tc.civil_depreciation_years == 20
    assert tc.wht_on_interest_to_nonresidents == pytest.approx(0.10)

    eq_cfg = _build_distribution_config(cfg)
    assert eq_cfg.wht_on_interest_rate == pytest.approx(0.10)
    assert eq_cfg.wht_on_dividends_rate == pytest.approx(0.15)

    wacc = compute_build_up_wacc(cfg, debt_to_value=0.6, cost_of_debt_pretax=0.08)
    assert wacc["tax_rate"] == pytest.approx(0.30)


# ---------------------------------------------------------------------------
# 2. Closed-form responsiveness (TEST-01): modified pack moves tax & CFADS
# ---------------------------------------------------------------------------


def test_modified_pack_cit_rate_overrides_yaml_copy_and_moves_tax_closed_form(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Changing lk.cit.standard_rate in the pack moves tax & CFADS in closed form,
    even though the scenario YAML still carries ``tax.corporate_tax_rate: 0.30``."""
    cfg = _load_yaml(LENDER_PATH)
    assert cfg["tax"]["corporate_tax_rate"] == 0.30

    base_rows = build_annual_rows(cfg)
    modified_source = _modified_lk_source(cit_rate=0.40)

    # Direct TaxConfig check without monkeypatching
    tc_mod = TaxConfig.from_yaml(cfg, pack_source=modified_source)
    assert tc_mod.corporate_tax_rate == pytest.approx(0.40)

    # Full engine check through build_annual_rows + pipeline + build_up WACC
    monkeypatch.setattr(
        "finance.cashflow_v14_tax.DirectoryPackSource",
        lambda *_a, **_kw: modified_source,
    )
    mod_rows = build_annual_rows(cfg)

    checked = 0
    for base_row, mod_row in zip(base_rows, mod_rows, strict=True):
        if float(base_row["taxable_income_lkr"]) <= 0.0:
            continue
        checked += 1
        # Unlevered taxable income is independent of tax rate; only rate moves 0.30 -> 0.40.
        assert mod_row["taxable_income_lkr"] == pytest.approx(
            base_row["taxable_income_lkr"], rel=1e-12
        )
        taxable = float(base_row["taxable_income_lkr"])
        expected_delta_tax = (0.40 - 0.30) * taxable
        assert float(mod_row["tax_lkr"]) - float(base_row["tax_lkr"]) == pytest.approx(
            expected_delta_tax, rel=1e-12
        )
        haircut = float(base_row["risk_haircut_pct"])
        expected_delta_posttax = -expected_delta_tax
        assert float(mod_row["posttax_cfads_lkr"]) - float(
            base_row["posttax_cfads_lkr"]
        ) == pytest.approx(expected_delta_posttax, rel=1e-12)
        expected_delta_cfads_lkr = expected_delta_posttax * (1.0 - haircut)
        fx_rate = float(base_row["fx_rate"])
        assert float(mod_row["cfads_usd"]) - float(
            base_row["cfads_usd"]
        ) == pytest.approx(expected_delta_cfads_lkr / fx_rate, rel=1e-12)
    assert checked >= 5, "expected multiple positive-taxable-income years"

    wacc_mod = compute_build_up_wacc(cfg, debt_to_value=0.6, cost_of_debt_pretax=0.08)
    assert wacc_mod["tax_rate"] == pytest.approx(0.40)

    pipe_mod = run_v14_pipeline(cfg, validation_mode="strict")
    assert pipe_mod["status"] == "success"
    assert pipe_mod["wacc_result"] if "wacc_result" in pipe_mod else True


def test_modified_pack_dividend_wht_updates_equity_distribution_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg = _load_yaml(LENDER_PATH)
    modified_source = _modified_lk_source(dividend_wht_rate=0.25)
    monkeypatch.setattr(
        "finance.cashflow_v14_tax.DirectoryPackSource",
        lambda *_a, **_kw: modified_source,
    )
    eq_cfg = _build_distribution_config(cfg)
    assert eq_cfg.wht_on_dividends_rate == pytest.approx(0.25)


# ---------------------------------------------------------------------------
# 3. Valuation dates: construction excluded, pre-floor refused, no pro-rating
# ---------------------------------------------------------------------------


def test_construction_periods_before_pack_floor_do_not_block_post_cod_operations() -> (
    None
):
    """Lender case has construction_years=2 and cod_year=2027 (construction spans
    2025-2026, before LK 1.0.0's 2026-07-05 floor). Direct tax resolves operating
    periods 2027..2046 and succeeds."""
    cfg = _load_yaml(LENDER_PATH)
    resolved = resolve_direct_tax_from_pack(cfg)
    assert resolved.resolution is not None
    assert resolved.resolution.valuation_dates[0] == date(2027, 12, 31)
    assert resolved.resolution.valuation_dates[-1] == date(2046, 12, 31)
    assert len(resolved.resolution.valuation_dates) == 20


def test_operating_date_before_pack_effective_floor_is_refused() -> None:
    cfg = _load_yaml(LENDER_PATH)
    cfg["project"]["cod_year"] = 2025
    with pytest.raises(JurisdictionRefusal) as excinfo:
        resolve_direct_tax_from_pack(cfg)
    assert excinfo.value.reason is RefusalReason.NO_VALUE_IN_FORCE


def test_mid_period_rate_change_takes_period_end_rate_without_prorating(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """#1841#issuecomment-7060938247 item 3: each operating period takes the single value
    in force on its year-end valuation date (YYYY-12-31) with no mid-year pro-rating."""
    data = _raw_lk_pack()
    cit_param = next(
        p for p in data["parameters"] if p["parameter_id"] == "lk.cit.standard_rate"
    )
    cit_param["effective_to"] = "2029-07-01"
    later_cit = copy.deepcopy(cit_param)
    later_cit["effective_from"] = "2029-07-01"
    later_cit.pop("effective_to", None)
    later_cit["value"] = 0.20
    data["parameters"].append(later_cit)

    source = InMemoryPackSource([_pack_from_dict(data)])
    cfg = _load_yaml(LENDER_PATH)
    cfg["project"]["cod_year"] = 2027
    cfg["timeline"]["ops_years"] = 5
    cfg["returns"]["project_life_years"] = 5
    cfg["project"]["life_years"] = 5

    tc = TaxConfig.from_yaml(cfg, pack_source=source)
    assert tc.corporate_tax_rate == pytest.approx(0.30)
    assert tc.corporate_tax_rate_by_year == (
        (1, 0.30),  # 2027-12-31
        (2, 0.30),  # 2028-12-31
        (3, 0.20),  # 2029-12-31 (rate changed 2029-07-01 -> takes 0.20, not pro-rated)
        (4, 0.20),  # 2030-12-31
        (5, 0.20),  # 2031-12-31
    )

    monkeypatch.setattr(
        "finance.cashflow_v14_tax.DirectoryPackSource",
        lambda *_a, **_kw: source,
    )
    rows = build_annual_rows(
        cfg,
        # Force positive taxable income in year 1-5 to observe the exact step
        capex_depreciable_lkr=0.0,
    )
    # Year 2 (2028) uses 0.30; Year 3 (2029) uses 0.20
    assert float(rows[1]["tax_lkr"]) == pytest.approx(
        float(rows[1]["taxable_income_lkr"]) * 0.30, rel=1e-12
    )
    assert float(rows[2]["tax_lkr"]) == pytest.approx(
        float(rows[2]["taxable_income_lkr"]) * 0.20, rel=1e-12
    )


# ---------------------------------------------------------------------------
# 4. Hostile refusal tests: conflicts, unsupported packs, unknown jurisdictions
# ---------------------------------------------------------------------------


def test_two_packs_on_tax_subject_refuses_not_run_conflict() -> None:
    """#1841#issuecomment-7060938247 item 1: resolver emits not_run_conflict and engine refuses."""
    lk_data = _raw_lk_pack()
    alt_data = _raw_lk_pack()
    alt_data["pack_id"] = "dutchbay.jurisdiction.lk.alt"
    alt_data["jurisdiction_code"] = "LA"
    for p in alt_data["parameters"]:
        if p["parameter_id"] == "lk.cit.standard_rate":
            p["value"] = 0.25
    source = InMemoryPackSource([_pack_from_dict(lk_data), _pack_from_dict(alt_data)])
    bindings = (
        _binding(JurisdictionSubject.TAX, binding_id="jb:lk:tax"),
        _binding(
            JurisdictionSubject.TAX,
            code="LA",
            pack_id="dutchbay.jurisdiction.lk.alt",
            binding_id="jb:la:tax",
        ),
    )
    cfg = _load_yaml(LENDER_PATH)
    with pytest.raises(DirectTaxJurisdictionError, match="not_run_conflict"):
        TaxConfig.from_yaml(cfg, bindings=bindings, pack_source=source)


def test_override_without_provenance_refuses_not_run_conflict() -> None:
    cfg = _load_yaml(LENDER_PATH)
    cfg["tax"]["pack_overrides"] = {"corporate_tax_rate": None}
    with pytest.raises(DirectTaxJurisdictionError, match="not_run_conflict"):
        TaxConfig.from_yaml(cfg)

    cfg["tax"]["pack_overrides"] = {
        "corporate_tax_rate": {"value": 0.25, "provenance": ""}
    }
    with pytest.raises(DirectTaxJurisdictionError, match="not_run_conflict"):
        TaxConfig.from_yaml(cfg)


def test_unsupported_pack_status_is_refused() -> None:
    cfg = _load_yaml(LENDER_PATH)
    unsupported_source = _modified_lk_source(status="unsupported")
    with pytest.raises(
        DirectTaxJurisdictionError, match="not_run_unsupported_jurisdiction"
    ):
        TaxConfig.from_yaml(cfg, pack_source=unsupported_source)


def test_unsupported_binding_with_unregistered_country_is_refused() -> None:
    """#1841#issuecomment-7060938247 item 4: an unsupported binding for an unregistered
    country resolves to not_run_unsupported_jurisdiction; direct tax must refuse."""
    cfg = _load_yaml(LENDER_PATH)
    bindings = (
        _binding(
            JurisdictionSubject.TAX,
            code="ZZ",
            pack_id="test.jurisdiction.zz",
            support=ContractSupportStatus.UNSUPPORTED,
        ),
    )
    with pytest.raises(
        DirectTaxJurisdictionError, match="not_run_unsupported_jurisdiction"
    ):
        TaxConfig.from_yaml(cfg, bindings=bindings)


def test_unknown_jurisdiction_and_unknown_override_refuse_in_pipeline() -> None:
    cfg = _load_yaml(LENDER_PATH)
    cfg.pop("taxes_indirect", None)
    cfg["project"]["jurisdiction"] = "Wonderland"
    with pytest.raises(PipelineValidationError, match="unknown_jurisdiction"):
        run_v14_pipeline(cfg, validation_mode="strict")

    cfg_ovr = _load_yaml(LENDER_PATH)
    cfg_ovr["tax"]["pack_overrides"] = {"not_a_pack_param": "reason"}
    with pytest.raises(JurisdictionRefusal) as excinfo:
        TaxConfig.from_yaml(cfg_ovr)
    assert excinfo.value.reason is RefusalReason.UNKNOWN_OVERRIDE
