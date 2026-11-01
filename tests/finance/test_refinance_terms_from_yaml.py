"""A balloon refinance takes its terms from YAML only, and its tranche is disclosed (#1396).

P3-COV-03: the lender case's scheduled-maturity balloon (about 46% of principal after IDC)
is cash-swept, which retires only part of it and leaves the rest unpaid at project end.
The owner chose a refinance assumption whose rate and tenor come from YAML and "should
never be hardcoded" (2026-10-26). This change makes the refinance path honest; switching
the canonical case onto it is a separate, owner-held re-baseline, so the lender-case
tests here select ``refinance`` by override. These tests pin:

* no code default: a ``refinance`` without both ``constraints.refinancing`` terms is
  refused by the engine resolver and by the v14 pre-flight, naming the missing path;
* a tenor that runs past the modelled timeline is refused, not compressed;
* the refinance stream matches an independent closed-form annuity;
* the lender case, refinanced, publishes the tranche, its assumption basis, an
  interest/principal split that retires exactly the balloon, and a coverage test that
  recomputes from an independent branch;
* the three statements tie out under refinance (the interest inside the payments is an
  expense, not debt retirement).
"""

from __future__ import annotations

import copy
import importlib
import pkgutil
from pathlib import Path
from types import ModuleType
from typing import Any, Dict, cast

import pytest
import yaml

import finance.debt_v14 as debt_v14
from analytics.schema_guard import ConfigValidationError, validate_config_for_v14
from finance.debt_v14 import (
    REFINANCE_TERMS_BASIS,
    _balloon_resolution_stream,
    resolve_refinance_terms,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER_CONFIG = REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"


def _lender_raw() -> Dict[str, Any]:
    from analytics.scenario_loader import load_scenario_config

    return copy.deepcopy(dict(load_scenario_config(str(LENDER_CONFIG))))


def _refinance(terms: Dict[str, Any] | None) -> Dict[str, Any]:
    cfg: Dict[str, Any] = {"Financing_Terms": {"balloon_treatment": "refinance"}}
    if terms is not None:
        cfg["constraints"] = {"refinancing": terms}
    return cfg


# --------------------------------------------------------------------------- #
# The resolver: YAML or refusal, never a default
# --------------------------------------------------------------------------- #
def _debt_engine_modules() -> list[ModuleType]:
    """The façade plus every module of the ``finance.debt`` package behind it."""
    import finance.debt

    modules = [debt_v14]
    for info in pkgutil.iter_modules(finance.debt.__path__):
        modules.append(importlib.import_module(f"finance.debt.{info.name}"))
    return modules


def test_the_code_defaults_are_gone() -> None:
    assert not hasattr(debt_v14, "_REFINANCE_TENOR_DEFAULT")
    assert not hasattr(debt_v14, "_REFINANCE_PREMIUM_DEFAULT")
    assert not hasattr(debt_v14, "_refinance_terms")


def test_no_engine_module_defines_a_code_default() -> None:
    """The engine's code lives behind the façade, so look in every module of it."""
    modules = _debt_engine_modules()
    # The façade alone would make this vacuous: prove the package was enumerated.
    assert len(modules) >= 15, [m.__name__ for m in modules]
    for module in modules:
        for name in (
            "_REFINANCE_TENOR_DEFAULT",
            "_REFINANCE_PREMIUM_DEFAULT",
            "_refinance_terms",
        ):
            assert not hasattr(module, name), f"{module.__name__}.{name}"


def test_terms_are_read_from_yaml() -> None:
    cfg = _refinance({"refinance_tenor_years": 4, "refinance_rate_premium": 0.015})
    assert resolve_refinance_terms(cfg) == (4, 0.015)


@pytest.mark.parametrize(
    ("terms", "missing"),
    [
        (None, "refinance_tenor_years is missing"),
        ({"refinance_rate_premium": 0.02}, "refinance_tenor_years is missing"),
        ({"refinance_tenor_years": 3}, "refinance_rate_premium is missing"),
    ],
)
def test_a_missing_term_is_refused_by_path(
    terms: Dict[str, Any] | None, missing: str
) -> None:
    with pytest.raises(ValueError, match=f"constraints.refinancing.{missing}"):
        resolve_refinance_terms(_refinance(terms))


@pytest.mark.parametrize("tenor", [0, -1, 2.5, True, "three", float("nan")])
def test_a_malformed_tenor_is_refused(tenor: Any) -> None:
    cfg = _refinance({"refinance_tenor_years": tenor, "refinance_rate_premium": 0.02})
    with pytest.raises(
        ValueError, match="refinance_tenor_years must be a whole number"
    ):
        resolve_refinance_terms(cfg)


@pytest.mark.parametrize("premium", [True, "two", float("inf")])
def test_a_malformed_premium_is_refused(premium: Any) -> None:
    cfg = _refinance({"refinance_tenor_years": 3, "refinance_rate_premium": premium})
    with pytest.raises(ValueError, match="refinance_rate_premium must be a finite"):
        resolve_refinance_terms(cfg)


@pytest.mark.parametrize("treatment", ["cash_sweep", "bullet", "amortize", None])
def test_other_treatments_need_no_terms(treatment: Any) -> None:
    cfg: Dict[str, Any] = {"Financing_Terms": {}}
    if treatment is not None:
        cfg["Financing_Terms"]["balloon_treatment"] = treatment
    assert resolve_refinance_terms(cfg) is None


# --------------------------------------------------------------------------- #
# The v14 pre-flight reuses the resolver
# --------------------------------------------------------------------------- #
def test_preflight_refuses_a_refinance_without_yaml_terms() -> None:
    raw = _lender_raw()
    raw["Financing_Terms"]["balloon_treatment"] = "refinance"
    del raw["constraints"]["refinancing"]["refinance_tenor_years"]
    with pytest.raises(ConfigValidationError, match="refinance_tenor_years is missing"):
        validate_config_for_v14(raw, "lendercase", ["cashflow", "debt"])


def test_preflight_passes_the_committed_lender_case() -> None:
    validate_config_for_v14(_lender_raw(), "lendercase", ["cashflow", "debt"])


def test_preflight_passes_the_lender_case_refinanced_on_its_yaml_terms() -> None:
    raw = _lender_raw()
    raw["Financing_Terms"]["balloon_treatment"] = "refinance"
    validate_config_for_v14(raw, "lendercase", ["cashflow", "debt"])


def test_preflight_ignores_missing_terms_when_not_refinancing() -> None:
    raw = _lender_raw()
    # The committed case refinances since #1396 part B; pin a non-refinance treatment.
    raw["Financing_Terms"]["balloon_treatment"] = "cash_sweep"
    del raw["constraints"]["refinancing"]
    validate_config_for_v14(raw, "lendercase", ["cashflow", "debt"])


# --------------------------------------------------------------------------- #
# The stream: closed-form oracle, and no silent compression
# --------------------------------------------------------------------------- #
def _stream(n: int, last_service: int, tenor: int) -> list[float]:
    ds = [0.0] * n
    ds[last_service] = 10.0
    resolution, residual = _balloon_resolution_stream(
        treatment="refinance",
        balloon=100.0,
        cfads_ext=[0.0] * n,
        debt_service_total=ds,
        construction_periods=0,
        timeline_periods=n,
        avg_rate=0.08,
        refi_tenor_years=tenor,
        refi_rate_premium=0.02,
    )
    assert residual == 0.0
    return resolution


def test_refinance_stream_matches_the_closed_form_annuity() -> None:
    # Independent oracle: a level annuity repaying 100 over 3 periods at 10%.
    annuity = 100.0 * 0.10 / (1.0 - 1.10**-3)
    assert _stream(n=6, last_service=1, tenor=3) == pytest.approx(
        [0.0, 0.0, annuity, annuity, annuity, 0.0], rel=1e-12
    )


def test_a_tenor_that_fits_exactly_is_accepted() -> None:
    assert sum(1 for v in _stream(n=5, last_service=1, tenor=3) if v > 0) == 3


def test_a_tenor_past_the_timeline_is_refused_not_compressed() -> None:
    with pytest.raises(ValueError, match="runs past the modelled timeline"):
        _stream(n=5, last_service=2, tenor=3)


# --------------------------------------------------------------------------- #
# The lender case: the tranche is disclosed and its coverage recomputes
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def lender_debt() -> Dict[str, Any]:
    from analytics.evaluation_v14 import evaluate_with_overrides

    result = cast(
        Dict[str, Any],
        evaluate_with_overrides(
            str(LENDER_CONFIG),
            overrides={"Financing_Terms.balloon_treatment": "refinance"},
            return_full_result=True,
        ),
    )
    return cast(Dict[str, Any], result["debt_result"])


def test_lender_case_refinances_on_its_yaml_terms(lender_debt: Dict[str, Any]) -> None:
    refi_yaml = yaml.safe_load(LENDER_CONFIG.read_text(encoding="utf-8"))[
        "constraints"
    ]["refinancing"]
    refi = lender_debt["refinance"]
    assert lender_debt["balloon_treatment"] == "refinance"
    assert lender_debt["balloon_residual"] == 0.0
    assert refi["terms_basis"] == REFINANCE_TERMS_BASIS == "assumption_no_term_sheet"
    assert refi["tenor_years"] == refi_yaml["refinance_tenor_years"]
    assert refi["rate_premium"] == refi_yaml["refinance_rate_premium"]
    assert refi["rate"] == pytest.approx(
        lender_debt["avg_debt_rate"] + refi_yaml["refinance_rate_premium"], abs=1e-15
    )
    assert refi["principal_usd"] == lender_debt["balloon_remaining"]
    assert refi["total_service_usd"] == pytest.approx(
        sum(lender_debt["balloon_resolution"]), rel=1e-12
    )


def test_refinance_split_retires_exactly_the_balloon(
    lender_debt: Dict[str, Any],
) -> None:
    refi = lender_debt["refinance"]
    rows = refi["coverage_by_period"]
    # Independent amortisation of a level annuity at the published rate.
    balance = refi["principal_usd"]
    for row in rows:
        assert row["interest_usd"] == pytest.approx(balance * refi["rate"], rel=1e-12)
        assert row["principal_usd"] == pytest.approx(
            row["service_usd"] - row["interest_usd"], rel=1e-12
        )
        balance -= row["principal_usd"]
    assert balance == pytest.approx(0.0, abs=1e-4)
    assert refi["total_interest_usd"] == pytest.approx(
        refi["total_service_usd"] - refi["principal_usd"], rel=1e-12
    )


def test_three_statements_tie_out_under_refinance() -> None:
    from analytics.pipeline_v14_enhanced import run_v14_pipeline
    from analytics.three_statement import build_three_statement_from_run

    raw = _lender_raw()
    raw["Financing_Terms"]["balloon_treatment"] = "refinance"
    statements = build_three_statement_from_run(run_v14_pipeline(config=raw), raw)
    assert statements is not None and statements.tie_outs is not None
    tie_outs = statements.tie_outs
    assert tie_outs.debt_retires_to_residual is True
    assert tie_outs.debt_retirement_residual == pytest.approx(0.0, abs=1.0)
    assert tie_outs.balance_sheet_balances is True


def test_lender_case_refinance_coverage_recomputes(lender_debt: Dict[str, Any]) -> None:
    from analytics.evaluation_v14 import evaluate_with_overrides

    refi = lender_debt["refinance"]
    resolution = lender_debt["balloon_resolution"]
    periods = [p for p, v in enumerate(resolution) if v > 1.0]
    assert [c["period"] for c in refi["coverage_by_period"]] == periods
    assert len(periods) == refi["tenor_years"]
    # Independent source for the cash available: the cash-sweep branch pays out all of
    # a period's post-fee cash while the balloon is larger than it, which holds in each
    # of these periods, so its swept amount IS the cash available to the refinance.
    sweep = cast(
        Dict[str, Any],
        evaluate_with_overrides(
            str(LENDER_CONFIG),
            overrides={"Financing_Terms.balloon_treatment": "cash_sweep"},
            return_full_result=True,
        ),
    )["debt_result"]
    for row in refi["coverage_by_period"]:
        p = row["period"]
        assert row["service_usd"] == pytest.approx(resolution[p], rel=1e-12)
        assert row["cash_available_usd"] == pytest.approx(
            sweep["balloon_resolution"][p], rel=1e-12
        )
        assert row["coverage"] == pytest.approx(
            sweep["balloon_resolution"][p] / resolution[p], rel=1e-12
        )
    assert refi["min_coverage"] == min(
        c["coverage"] for c in refi["coverage_by_period"]
    )
    assert refi["coverage_floor"] == 1.3
    # The assumed refinance is not covered by project cash: equity funds most of it.
    assert refi["min_coverage"] < 0.5
    assert refi["coverage_breach"] is True


@pytest.mark.parametrize("treatment", ["cash_sweep", "bullet", "amortize"])
def test_no_refinance_block_for_other_treatments(treatment: str) -> None:
    from analytics.evaluation_v14 import evaluate_with_overrides

    result = cast(
        Dict[str, Any],
        evaluate_with_overrides(
            str(LENDER_CONFIG),
            overrides={"Financing_Terms.balloon_treatment": treatment},
            return_full_result=True,
        ),
    )
    assert result["debt_result"]["refinance"] is None
