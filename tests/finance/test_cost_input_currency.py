"""Negative controls for misleading LKR project-cost inputs (#1627)."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
import yaml

from analytics.schema_guard import ConfigValidationError, validate_config_for_v14
from finance.cashflow_v14 import build_annual_rows
from finance.cashflow_v14_params import _build_cashflow_params
from finance.cost_input_currency import validate_cost_input_currencies
from finance.debt.capex import _extract_capex_base_usd

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(params=["wind", "solar_bess"])
def scenario(request: pytest.FixtureRequest) -> dict[str, Any]:
    """Load each committed Blue Whale scenario without editing its input data."""
    path = ROOT / "scenarios" / f"blue_whale_{request.param}_lot5b_2026.yaml"
    return dict(yaml.safe_load(path.read_text()))


@pytest.mark.parametrize("amount", [0.0, 1.0, None, float("nan")])
def test_native_lkr_opex_is_refused_even_beside_usd(
    scenario: dict[str, Any], amount: object
) -> None:
    """A supplied LKR amount must never vanish behind the supported USD value."""
    scenario["opex"]["lkr_per_year"] = amount
    with pytest.raises(ConfigValidationError, match=r"opex\.lkr_per_year"):
        validate_config_for_v14(
            scenario, config_path="currency-input-test", modules=["cashflow", "debt"]
        )
    with pytest.raises(ValueError, match=r"opex\.lkr_per_year.*opex\.usd_per_year"):
        _build_cashflow_params(scenario)
    with pytest.raises(ValueError, match=r"opex\.lkr_per_year"):
        build_annual_rows(scenario)


@pytest.mark.parametrize(
    "key", ["lkr_annual", "annual_opex_lkr", "LKR_per_year", "lkr_per_yaer"]
)
def test_alternate_native_lkr_keys_cannot_bypass_guard(key: str) -> None:
    """Unknown amount aliases and typos fail rather than select USD silently."""
    with pytest.raises(ValueError, match="native-LKR opex"):
        validate_cost_input_currencies({"opex": {"usd_per_year": 10.0, key: 1000.0}})


@pytest.mark.parametrize("amount", [0.0, 1.0, None, float("nan")])
def test_mixed_capex_currencies_are_refused(
    scenario: dict[str, Any], amount: object
) -> None:
    """Debt and tax cannot select different project-cost currencies."""
    scenario["capex"]["lkr_total"] = amount
    with pytest.raises(ConfigValidationError, match=r"capex\.lkr_total"):
        validate_config_for_v14(
            scenario, config_path="currency-input-test", modules=["cashflow", "debt"]
        )
    with pytest.raises(
        ValueError, match=r"capex\.lkr_total.*tax\.depreciable_capex_lkr"
    ):
        _extract_capex_base_usd(scenario)
    with pytest.raises(ValueError, match=r"capex\.lkr_total"):
        build_annual_rows(scenario)


@pytest.mark.parametrize(
    "usd_config",
    [
        {"finance": {"capex_usd": 10.0}},
        {"costs": {"total_capex": 10.0}},
        {"capex_total_usd": 10.0},
        {"CAPEX": {"USD_TOTAL": 10.0}},
        {"capex": {"derive_from_breakdown": True, "breakdown": {"plant_usd": 10.0}}},
    ],
)
def test_legacy_usd_paths_do_not_hide_capex_conflict(
    usd_config: dict[str, Any],
) -> None:
    """The guard covers aliases and a bottom-up USD breakdown, too."""
    cfg = deepcopy(usd_config)
    section = "CAPEX" if "CAPEX" in cfg else "capex"
    cfg.setdefault(section, {})["lkr_total"] = 200.0
    with pytest.raises(ValueError, match=r"capex\.lkr_total"):
        _extract_capex_base_usd(cfg)


def test_committed_usd_inputs_remain_supported(scenario: dict[str, Any]) -> None:
    """The refusal guard leaves the original configured USD amounts untouched."""
    validate_config_for_v14(
        scenario, config_path="currency-input-test", modules=["cashflow", "debt"]
    )
    assert (
        _build_cashflow_params(scenario).opex_usd_per_year
        == scenario["opex"]["usd_per_year"]
    )
    assert _extract_capex_base_usd(scenario) == scenario["capex"]["usd_total"]


@pytest.mark.parametrize("tax_key", ["depreciable_capex_lkr", "dep_base_lkr"])
def test_explicit_tax_only_basis_does_not_change_debt_cost(
    scenario: dict[str, Any], tax_key: str
) -> None:
    """An intentional tax-only basis remains distinct from financed project cost."""
    scenario["tax"][tax_key] = 123456789.0
    validate_config_for_v14(
        scenario, config_path="currency-input-test", modules=["cashflow", "debt"]
    )
    validate_cost_input_currencies(scenario)
    assert _extract_capex_base_usd(scenario) == scenario["capex"]["usd_total"]


def test_lkr_only_capex_is_not_promoted_to_supported_financing(
    scenario: dict[str, Any],
) -> None:
    """Legacy direct tax fallback is not a native-LKR financing contract."""
    scenario["capex"] = {"lkr_total": 123456789.0}
    validate_cost_input_currencies(scenario)
    with pytest.raises(ConfigValidationError, match="epc_usd_total"):
        validate_config_for_v14(
            scenario, config_path="currency-input-test", modules=["cashflow", "debt"]
        )
    with pytest.raises(ValueError, match="CAPEX extractor"):
        _extract_capex_base_usd(scenario)


@pytest.mark.parametrize(
    "section,key", [("capex", "lkr_total"), ("opex", "lkr_per_year")]
)
@pytest.mark.parametrize("variant_first", [False, True])
def test_case_colliding_sections_cannot_mask_consumed_costs(
    scenario: dict[str, Any], section: str, key: str, variant_first: bool
) -> None:
    """Refuse the consumed canonical block regardless of alias insertion order."""
    scenario[section][key] = 123456789.0
    variant = {section.upper(): {}}
    cfg = {**variant, **scenario} if variant_first else {**scenario, **variant}
    with pytest.raises(ValueError, match=rf"{section}\.{key}"):
        _build_cashflow_params(cfg)
    with pytest.raises(ValueError, match=rf"{section}\.{key}"):
        _extract_capex_base_usd(cfg)
    with pytest.raises(ValueError, match=rf"{section}\.{key}"):
        build_annual_rows(cfg)
    with pytest.raises(ConfigValidationError, match=rf"{section}\.{key}"):
        validate_config_for_v14(
            cfg, config_path="case-collision", modules=["cashflow", "debt"]
        )


@pytest.mark.parametrize("variant_first", [False, True])
def test_null_colliding_alias_cannot_erase_financed_usd(
    scenario: dict[str, Any], variant_first: bool
) -> None:
    """A null case alias must not grant the LKR-only tax-fallback exception."""
    capex = scenario["capex"]
    variant = {"USD_TOTAL": None}
    scenario["capex"] = {**variant, **capex} if variant_first else {**capex, **variant}
    scenario["capex"]["lkr_total"] = 123456789.0
    with pytest.raises(ValueError, match=r"capex\.lkr_total"):
        _extract_capex_base_usd(scenario)
    with pytest.raises(ValueError, match=r"capex\.lkr_total"):
        build_annual_rows(scenario)
