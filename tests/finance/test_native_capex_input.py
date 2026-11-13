"""Independent arithmetic and refusal controls for native CAPEX."""

import copy
from collections.abc import Callable
from typing import Any

import pytest

from analytics.core.metrics import _derive_capex_usd
from analytics.schema_guard import ConfigValidationError, validate_config_for_v14
from finance.debt_v14 import _extract_capex_usd
from finance.epc_helper_v14 import _resolve_capex_usd_total
from finance.equity_distribution_v14_hydra import _extract_capex_usd as equity_capex
from finance.native_cost_inputs import normalize_native_capex


def config() -> dict[str, Any]:
    """Supply an explicitly synthetic conversion input at a non-round FX rate."""
    return {
        "fx": {"start_lkr_per_usd": 317.25},
        "capex": {
            "input": {
                "currency": "LKR",
                "amount": 6345000.0,
                "price_date": "2026-02-01",
                "financial_close_date": "2027-01-10",
                "conversion": {
                    "rate_lkr_per_usd": 317.25,
                    "date": "2027-01-10",
                    "source": "test quotation",
                    "basis": "financial_close",
                },
            }
        },
    }


def test_nonround_fx_and_all_direct_resolvers() -> None:
    """One algebraic value feeds all direct consumers and responds to drivers."""
    cfg = config()
    before = copy.deepcopy(cfg)
    assert _extract_capex_usd(cfg) == 20000
    assert _derive_capex_usd(cfg) == 20000
    assert equity_capex(cfg) == 20000
    assert _resolve_capex_usd_total(cfg) == 20000
    assert cfg == before
    resolved = normalize_native_capex(cfg)
    assert normalize_native_capex(resolved) == resolved
    cfg["capex"]["input"]["amount"] *= 2
    assert _extract_capex_usd(cfg) == 40000
    cfg["fx"]["start_lkr_per_usd"] *= 2
    cfg["capex"]["input"]["conversion"]["rate_lkr_per_usd"] *= 2
    assert _extract_capex_usd(cfg) == 20000


@pytest.mark.parametrize(
    "mutation",
    [
        lambda c: c["capex"]["input"].update(amount=True),
        lambda c: c["capex"]["input"].update(amount=float("nan")),
        lambda c: c["capex"]["input"].update(amount=-1),
        lambda c: c["capex"]["input"].update(price_date=""),
        lambda c: c["capex"]["input"]["conversion"].update(rate_lkr_per_usd=0),
        lambda c: c["capex"]["input"]["conversion"].update(source=" "),
        lambda c: c["capex"]["input"]["conversion"].update(date="2026-02-01"),
        lambda c: c["capex"]["input"]["conversion"].update(basis="quote"),
        lambda c: c["capex"].update(USD_TOTAL=20000),
        lambda c: c["capex"].update(usd_total=20000),
        lambda c: c["capex"].update(derive_from_breakdown=True),
        lambda c: c["capex"].update(breakdown={"x": 1}),
        lambda c: c["capex"].update(contingency={"method": "qra"}),
        lambda c: c["capex"]["input"].update(Amount=1),
        lambda c: c["capex"].update(mystery_lkr=1),
        lambda c: c["finance"].update(capex_usd=20000),
    ],
)
def test_bad_or_ambiguous_input_refused(
    mutation: Callable[[dict[str, Any]], None],
) -> None:
    """Reject a single malformed or conflicting authored monetary input."""
    cfg = config()
    cfg["finance"] = {}
    mutation(cfg)
    with pytest.raises(ValueError):
        normalize_native_capex(cfg)


def test_stale_resolved_value_refused() -> None:
    """Do not reuse provenance after a monetary override invalidates it."""
    cfg = normalize_native_capex(config())
    cfg["capex"]["usd_total"] *= 2
    with pytest.raises(ValueError, match="stale"):
        normalize_native_capex(cfg)


def test_strict_preflight_preserves_its_error_contract() -> None:
    """Bad native currency data is reported as a path-specific schema failure."""
    cfg = config()
    cfg["capex"]["input"]["amount"] = True
    with pytest.raises(ConfigValidationError, match=r"native-case.*capex.input.amount"):
        validate_config_for_v14(
            cfg, config_path="native-case", modules=["cashflow", "debt"]
        )
