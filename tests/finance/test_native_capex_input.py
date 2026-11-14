"""Independent arithmetic and refusal controls for native CAPEX."""

import copy
import re
from collections.abc import Callable
from datetime import date
from typing import Any

import pytest

from analytics.core.metrics import _derive_capex_usd
from analytics.schema_guard import ConfigValidationError, validate_config_for_v14
from finance.capex_price_basis import apply_capex_price_basis
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


def priced_config() -> dict[str, Any]:
    """Add a dated price basis: two default construction periods put COD in 2029."""
    cfg = config()
    cfg["project"] = {"cod_year": 2029}
    cfg["capex"]["price_basis"] = {
        "price_year": 2026,
        "escalation_pct": 5.0,
        "source": "test",
    }
    return cfg


def priced_resolved() -> dict[str, Any]:
    """Resolve the native amount, then apply its price basis, as the pipeline does."""
    return apply_capex_price_basis(normalize_native_capex(priced_config()))


def test_usd_currency_input_is_not_converted() -> None:
    """A USD amount is already the model currency; the LKR rate must not touch it."""
    cfg = config()
    cfg["capex"]["input"].update(currency="USD", amount=20000.0)
    resolved = normalize_native_capex(cfg)
    assert resolved["capex"]["usd_total"] == 20000.0
    assert resolved["capex"]["native_input_applied"]["usd_at_price_date"] == 20000.0
    assert normalize_native_capex(resolved) == resolved


def test_priced_native_input_resolves_once_and_is_idempotent() -> None:
    """The saved price basis reproduces the escalated amount without re-escalating it."""
    resolved = priced_resolved()
    applied = resolved["capex"]["price_basis_applied"]
    assert applied["usd_total_at_price_year"] == 20000.0
    assert resolved["capex"]["usd_total"] == 20000.0 * applied["factor"]
    assert normalize_native_capex(resolved) == resolved


Mutation = Callable[[dict[str, Any]], None]

# Each row names the one check it exercises, by that check's own message, so a
# refusal raised later by a different layer cannot stand in for it (ASSURANCE-1645-03).
REFUSALS: list[tuple[str, Callable[[], dict[str, Any]], Mutation, str]] = [
    (
        "bool amount",
        config,
        lambda c: c["capex"]["input"].update(amount=True),
        "capex.input.amount must be a finite positive number",
    ),
    (
        "nan amount",
        config,
        lambda c: c["capex"]["input"].update(amount=float("nan")),
        "capex.input.amount must be a finite positive number",
    ),
    (
        "infinite amount",
        config,
        lambda c: c["capex"]["input"].update(amount=float("inf")),
        "capex.input.amount must be a finite positive number",
    ),
    (
        "negative amount",
        config,
        lambda c: c["capex"]["input"].update(amount=-1),
        "capex.input.amount must be a finite positive number",
    ),
    (
        "empty price date",
        config,
        lambda c: c["capex"]["input"].update(price_date=""),
        "capex.input.price_date must be an ISO date",
    ),
    (
        "basic-format price date",
        config,
        lambda c: c["capex"]["input"].update(price_date="20260201"),
        "capex.input.price_date must be an ISO date",
    ),
    (
        "zero rate",
        config,
        lambda c: c["capex"]["input"]["conversion"].update(rate_lkr_per_usd=0),
        "capex.input.conversion.rate_lkr_per_usd must be a finite positive number",
    ),
    (
        "blank source",
        config,
        lambda c: c["capex"]["input"]["conversion"].update(source=" "),
        "capex.input.conversion.source must be a non-empty provenance string",
    ),
    (
        "quote-date rate",
        config,
        lambda c: c["capex"]["input"]["conversion"].update(date="2026-02-01"),
        "dated financial_close rate",
    ),
    (
        "quote basis",
        config,
        lambda c: c["capex"]["input"]["conversion"].update(basis="quote"),
        "dated financial_close rate",
    ),
    (
        "unknown currency",
        config,
        lambda c: c["capex"]["input"].update(currency="EUR"),
        "capex.input.currency must be LKR or USD",
    ),
    (
        "lower-case currency",
        config,
        lambda c: c["capex"]["input"].update(currency="lkr"),
        "capex.input.currency must be LKR or USD",
    ),
    (
        "mixed-case currency",
        config,
        lambda c: c["capex"]["input"].update(currency="Usd"),
        "capex.input.currency must be LKR or USD",
    ),
    (
        "unquoted YAML price date",
        config,
        lambda c: c["capex"]["input"].update(price_date=date(2026, 2, 1)),
        "capex.input.price_date must be an ISO date",
    ),
    (
        "non-string source",
        config,
        lambda c: c["capex"]["input"]["conversion"].update(source=7),
        "capex.input.conversion.source must be a non-empty provenance string",
    ),
    (
        "case-variant fx key",
        config,
        lambda c: c["fx"].update(START_LKR_PER_USD=317.25),
        "fx contains duplicate case variants",
    ),
    (
        "case-variant conversion key",
        config,
        lambda c: c["capex"]["input"]["conversion"].update(Source="x"),
        "capex.input.conversion contains duplicate case variants",
    ),
    (
        "case-variant capex key",
        config,
        lambda c: c["capex"].update(note="x", NOTE="y"),
        "capex contains duplicate case variants",
    ),
    (
        "lkr_total",
        config,
        lambda c: c["capex"].update(lkr_total=1),
        "capex.lkr_total conflicts with capex.input",
    ),
    (
        "freight_pct",
        config,
        lambda c: c["capex"].update(freight_pct=0.05),
        "capex.freight_pct conflicts with capex.input",
    ),
    (
        "contingency_pct",
        config,
        lambda c: c["capex"].update(contingency_pct=0.1),
        "capex.contingency_pct conflicts with capex.input",
    ),
    (
        "top-level LKR alias",
        config,
        lambda c: c.update(capex_lkr=1),
        "top-level CAPEX alias conflicts",
    ),
    (
        "price date after close",
        config,
        lambda c: c["capex"]["input"].update(price_date="2027-02-01"),
        "capex.input.price_date cannot be after financial close",
    ),
    (
        "close year off COD",
        config,
        lambda c: c.update(project={"cod_year": 2030}),
        "financial_close_date must match the model financial-close year",
    ),
    (
        "close year off COD with a timeline",
        config,
        lambda c: c.update(
            project={"cod_year": 2030}, timeline={"construction_years": 2}
        ),
        "financial_close_date must match the model financial-close year",
    ),
    (
        "fractional COD",
        config,
        lambda c: c.update(project={"cod_year": 2029.5}),
        "project.cod_year must be a whole calendar year",
    ),
    (
        "spot differs from rate",
        config,
        lambda c: c["fx"].update(start_lkr_per_usd=300.0),
        "capex.input conversion rate must equal fx.start_lkr_per_usd",
    ),
    (
        "cost basis year differs",
        config,
        lambda c: c["capex"].update(cost_basis_year=2025),
        "capex.cost_basis_year must match capex.input.price_date",
    ),
    (
        "extra input key",
        config,
        lambda c: c["capex"]["input"].update(note="x"),
        "capex.input requires exactly currency",
    ),
    (
        "extra conversion key",
        config,
        lambda c: c["capex"]["input"]["conversion"].update(note="x"),
        "capex.input.conversion requires rate_lkr_per_usd",
    ),
    (
        "case-variant input key",
        config,
        lambda c: c["capex"]["input"].update(Amount=1),
        "capex.input contains duplicate case variants",
    ),
    (
        "case-variant fx section",
        config,
        lambda c: c.update(FX={"start_lkr_per_usd": 317.25}),
        "config contains duplicate case variants",
    ),
    (
        "noncanonical input key",
        config,
        lambda c: c["capex"].update(Input=c["capex"].pop("input")),
        "canonical lowercase capex.input keys",
    ),
    (
        "noncanonical capex section",
        config,
        lambda c: c.update(Capex=c.pop("capex")),
        "canonical lowercase capex.input keys",
    ),
    (
        "upper-case usd_total",
        config,
        lambda c: c["capex"].update(USD_TOTAL=20000),
        "capex.USD_TOTAL conflicts with capex.input",
    ),
    (
        "usd_total",
        config,
        lambda c: c["capex"].update(usd_total=20000),
        "capex.usd_total conflicts with capex.input",
    ),
    (
        "derive_from_breakdown",
        config,
        lambda c: c["capex"].update(derive_from_breakdown=True),
        "capex.derive_from_breakdown conflicts with capex.input",
    ),
    (
        "breakdown",
        config,
        lambda c: c["capex"].update(breakdown={"x": 1}),
        "capex.breakdown conflicts with capex.input",
    ),
    (
        "contingency",
        config,
        lambda c: c["capex"].update(contingency={"method": "qra"}),
        "capex.contingency conflicts with capex.input",
    ),
    (
        "unknown monetary key",
        config,
        lambda c: c["capex"].update(mystery_lkr=1),
        "unsupported monetary key capex.mystery_lkr",
    ),
    (
        "finance alias",
        config,
        lambda c: c.update(finance={"capex_usd": 20000}),
        "finance CAPEX alias conflicts",
    ),
    (
        "costs alias",
        config,
        lambda c: c.update(costs={"capex_usd": 20000}),
        "costs CAPEX alias conflicts",
    ),
    (
        "project alias",
        config,
        lambda c: c.update(project={"capex_total_usd": 20000}),
        "project CAPEX alias conflicts",
    ),
    (
        "top-level alias",
        config,
        lambda c: c.update(capex_usd=20000),
        "top-level CAPEX alias conflicts",
    ),
    (
        "price year differs",
        priced_config,
        lambda c: c["capex"]["price_basis"].update(price_year=2025),
        "capex.input.price_date must match capex.price_basis.price_year",
    ),
    (
        "unrepresentable escalation",
        priced_config,
        lambda c: c["capex"]["price_basis"].update(escalation_pct=10**400),
        "capex.price_basis contains an invalid numeric input",
    ),
    (
        "input with applied price basis",
        priced_config,
        lambda c: c["capex"].update(price_basis_applied=c["capex"].pop("price_basis")),
        "capex.input cannot coexist with an applied price basis",
    ),
    (
        "input with resolved provenance",
        lambda: normalize_native_capex(config()),
        lambda c: c["capex"].update(input=config()["capex"]["input"]),
        "capex.input conflicts with already resolved native input",
    ),
    (
        "provenance shape",
        lambda: normalize_native_capex(config()),
        lambda c: c["capex"]["native_input_applied"].update(note="x"),
        "invalid capex.native_input_applied provenance",
    ),
    (
        "stale provenance amount",
        lambda: normalize_native_capex(config()),
        lambda c: c["capex"]["native_input_applied"].update(usd_at_price_date=1.0),
        "native CAPEX provenance is stale",
    ),
    (
        "price basis beside its applied form",
        priced_resolved,
        lambda c: c["capex"].update(
            price_basis={"price_year": 2026, "escalation_pct": 5.0, "source": "test"}
        ),
        "capex.price_basis cannot coexist with price_basis_applied",
    ),
    (
        "tampered priced usd_total",
        priced_resolved,
        lambda c: c["capex"].update(usd_total=c["capex"]["usd_total"] * 2),
        "native CAPEX resolved USD is stale",
    ),
    (
        "stale price-year amount",
        priced_resolved,
        lambda c: c["capex"]["price_basis_applied"].update(usd_total_at_price_year=1.0),
        "native CAPEX price basis is stale",
    ),
]


@pytest.mark.parametrize(
    ("build", "mutation", "message"),
    [pytest.param(b, m, msg, id=name) for name, b, m, msg in REFUSALS],
)
def test_bad_or_ambiguous_input_refused(
    build: Callable[[], dict[str, Any]],
    mutation: Mutation,
    message: str,
) -> None:
    """Reject each malformed or conflicting monetary input at its own check."""
    cfg = build()
    assert normalize_native_capex(copy.deepcopy(cfg)) is not None
    mutation(cfg)
    with pytest.raises(ValueError, match=re.escape(message)):
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


@pytest.mark.parametrize("path", ["amount", "conversion.rate_lkr_per_usd"])
def test_unrepresentable_numbers_keep_the_validation_error_contract(path: str) -> None:
    """Out-of-range YAML integers are path-specific failures, never raw overflow."""
    cfg = config()
    target = cfg["capex"]["input"]
    if path.startswith("conversion."):
        target = target["conversion"]
    target[path.split(".")[-1]] = 10**400
    with pytest.raises(ValueError, match=f"capex.input.{path}"):
        normalize_native_capex(cfg)
    with pytest.raises(ConfigValidationError, match=f"capex.input.{path}"):
        validate_config_for_v14(
            cfg, config_path="large-native-input", modules=["cashflow", "debt"]
        )


@pytest.mark.parametrize("key", ["Price_basis", "PRICE_BASIS", "Cost_basis_year"])
def test_native_contract_refuses_noncanonical_price_keys(key: str) -> None:
    """An authored pricing key must never disappear through case-sensitive lookup."""
    cfg = config()
    cfg["capex"][key] = (
        2026
        if key.lower() == "cost_basis_year"
        else {"price_year": 2026, "escalation_pct": 5.0, "source": "test"}
    )
    with pytest.raises(ValueError, match=key):
        normalize_native_capex(cfg)


def test_price_dated_at_close_is_accepted() -> None:
    """A price dated on the financial-close day itself is not after close."""
    cfg = config()
    cfg["capex"]["input"]["price_date"] = cfg["capex"]["input"]["financial_close_date"]
    assert normalize_native_capex(cfg)["capex"]["usd_total"] == 20000


def test_provenance_is_a_copy_of_the_authored_input() -> None:
    """Later edits to the authored input must not rewrite the saved provenance."""
    cfg = config()
    resolved = normalize_native_capex(cfg)
    cfg["capex"]["input"]["amount"] = 1.0
    cfg["capex"]["input"]["conversion"]["source"] = "changed"
    saved = resolved["capex"]["native_input_applied"]["input"]
    assert saved == config()["capex"]["input"]
