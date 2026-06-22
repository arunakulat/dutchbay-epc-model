"""Coverage tests for ``finance.epc_helper_v14``.

This module centralises EPC / capex resolution for v14 lender-grade analytics:
FX rate resolution, percentage normalisation, multi-path capex resolution, the
two breakdown builders (``epc_breakdown_from_config`` / ``epc_breakdown_dict``),
and schema registration of the broadened ``epc_usd_total`` spec (#301).

Every expected value below is DERIVED inside the test from first principles
(freight = base * pct, contingency = base * pct, total = base + freight +
contingency, LKR = total * fx) rather than asserted against an opaque economic
constant. The single reference FX rate used for the no-argument fallback path is
read from the SAME config source of truth the module reads
(``analytics.fx.fx_fetch.default_fx_lkr_per_usd``), never a Python literal.
"""

from __future__ import annotations

import math
from typing import Any, Dict

import pytest

from analytics.config_schema import get_required_fields
from analytics.fx.fx_fetch import default_fx_lkr_per_usd
from finance.epc_helper_v14 import (
    _pct_or_zero,
    _resolve_capex_usd_total,
    _resolve_fx_rate,
    epc_breakdown_dict,
    epc_breakdown_from_config,
)


# ---------------------------------------------------------------------------
# _resolve_fx_rate (lines 105-127)
# ---------------------------------------------------------------------------


def test_resolve_fx_base_rate_wins_first() -> None:
    """fx.base_rate is highest precedence among the mapping keys."""
    cfg = {"fx": {"base_rate": 350.0, "rate": 400.0, "start_lkr_per_usd": 300.0}}
    assert _resolve_fx_rate(cfg) == 350.0


def test_resolve_fx_rate_second_precedence() -> None:
    """fx.rate is used when base_rate is absent."""
    cfg = {"fx": {"rate": 410.0, "start_lkr_per_usd": 300.0}}
    assert _resolve_fx_rate(cfg) == 410.0


def test_resolve_fx_start_lkr_per_usd_third() -> None:
    """fx.start_lkr_per_usd is used when base_rate/rate absent."""
    cfg = {"fx": {"start_lkr_per_usd": 333.79}}
    assert _resolve_fx_rate(cfg) == 333.79


def test_resolve_fx_scalar_at_root_v13_style() -> None:
    """A non-mapping scalar fx at the config root is honoured (historical v13)."""
    cfg = {"fx": 321.5}
    assert _resolve_fx_rate(cfg) == 321.5


def test_resolve_fx_default_argument_fallback() -> None:
    """When no fx info is in config, the default_fx_rate argument is used."""
    assert _resolve_fx_rate({}, default_fx_rate=300.0) == 300.0


def test_resolve_fx_skips_nonpositive_candidate() -> None:
    """A non-positive first candidate is skipped in favour of a positive one."""
    # base_rate is zero (invalid) -> the loop must fall through to rate.
    cfg = {"fx": {"base_rate": 0.0, "rate": 360.0}}
    assert _resolve_fx_rate(cfg) == 360.0


def test_resolve_fx_skips_unparseable_candidate() -> None:
    """A non-numeric candidate becomes None (via as_float) and is skipped."""
    cfg = {"fx": {"base_rate": "not-a-number", "rate": 365.0}}
    assert _resolve_fx_rate(cfg) == 365.0


def test_resolve_fx_raises_when_unresolvable() -> None:
    """No fx anywhere and no default -> ValueError with a descriptive message."""
    with pytest.raises(ValueError, match="Unable to resolve FX rate"):
        _resolve_fx_rate({})


def test_resolve_fx_raises_when_all_candidates_nonpositive() -> None:
    """Negative default and zero rate exhaust candidates -> ValueError."""
    cfg = {"fx": {"rate": 0.0}}
    with pytest.raises(ValueError, match="Unable to resolve FX rate"):
        _resolve_fx_rate(cfg, default_fx_rate=-5.0)


# ---------------------------------------------------------------------------
# _pct_or_zero (lines 155-171)
# ---------------------------------------------------------------------------


def test_pct_fraction_passthrough() -> None:
    """A value already in [0,1] is returned unchanged."""
    assert _pct_or_zero(0.05) == 0.05


def test_pct_whole_percent_divided() -> None:
    """A whole-percent value > 1 is divided by 100."""
    assert _pct_or_zero(10) == 0.10
    assert _pct_or_zero(5) == 0.05


def test_pct_none_is_zero() -> None:
    """None coalesces to 0.0 (as_float default)."""
    assert _pct_or_zero(None) == 0.0


def test_pct_unparseable_is_zero() -> None:
    """A non-numeric string coalesces to 0.0 via as_float's default."""
    assert _pct_or_zero("abc") == 0.0


def test_pct_negative_clamped_to_zero() -> None:
    """A negative percent is clamped up to 0.0."""
    assert _pct_or_zero(-10) == 0.0
    assert _pct_or_zero(-0.2) == 0.0


def test_pct_over_hundred_clamped_to_one() -> None:
    """A value that normalises above 1.0 is clamped down to 1.0.

    150 -> /100 -> 1.5 -> clamp -> 1.0 exercises the final clamp branch.
    """
    assert _pct_or_zero(150) == 1.0


def test_pct_exactly_one_passthrough() -> None:
    """Boundary: exactly 1.0 (== 100%) is not divided (heuristic uses > 1.0)."""
    assert _pct_or_zero(1.0) == 1.0


# ---------------------------------------------------------------------------
# _resolve_capex_usd_total (lines 201-218)
# ---------------------------------------------------------------------------


def test_capex_usd_total_canonical_path() -> None:
    """capex.usd_total is the canonical, first-checked path."""
    assert _resolve_capex_usd_total({"capex": {"usd_total": 1.0e8}}) == 1.0e8


def test_capex_epc_usd_alias() -> None:
    """capex.epc_usd alias is used when usd_total is absent."""
    assert _resolve_capex_usd_total({"capex": {"epc_usd": 9.0e7}}) == 9.0e7


def test_capex_usd_total_precedence_over_alias() -> None:
    """usd_total wins over epc_usd when both present (first hit wins)."""
    cfg = {"capex": {"usd_total": 1.0e8, "epc_usd": 2.0e8}}
    assert _resolve_capex_usd_total(cfg) == 1.0e8


def test_capex_legacy_finance_path() -> None:
    """Legacy finance.capex_usd is the fallback when capex.* is absent."""
    assert _resolve_capex_usd_total({"finance": {"capex_usd": 5.0e7}}) == 5.0e7


def test_capex_skips_nonpositive_canonical() -> None:
    """A zero usd_total is skipped; legacy finance path is then used."""
    cfg = {"capex": {"usd_total": 0.0}, "finance": {"capex_usd": 4.2e7}}
    assert _resolve_capex_usd_total(cfg) == 4.2e7


def test_capex_returns_none_when_absent() -> None:
    """No capex anywhere returns None (callers convert to their own errors)."""
    assert _resolve_capex_usd_total({}) is None


def test_capex_non_mapping_blocks_are_ignored() -> None:
    """capex / finance present but non-mapping -> skipped, returns None."""
    cfg = {"capex": "oops", "finance": 123}
    assert _resolve_capex_usd_total(cfg) is None


def test_capex_finance_nonpositive_returns_none() -> None:
    """Legacy finance.capex_usd present but non-positive -> None."""
    assert _resolve_capex_usd_total({"finance": {"capex_usd": -1.0}}) is None


# ---------------------------------------------------------------------------
# epc_breakdown_from_config (lines 264-294)
# ---------------------------------------------------------------------------


def test_breakdown_from_config_full_derivation() -> None:
    """Every output field derived from first principles; no magic constants."""
    base = 1.0e8
    freight_pct = 0.05
    cont_pct = 0.10
    fx = 333.79
    cfg = {
        "capex": {
            "usd_total": base,
            "freight_pct": freight_pct,
            "contingency_pct": cont_pct,
        },
        "fx": {"base_rate": fx},
    }
    out = epc_breakdown_from_config(cfg)

    freight = base * freight_pct
    cont = base * cont_pct
    total = base + freight + cont

    assert out["epc_base_usd"] == base
    assert math.isclose(out["epc_freight_usd"], freight, rel_tol=1e-12)
    assert math.isclose(out["epc_contingency_usd"], cont, rel_tol=1e-12)
    assert math.isclose(out["epc_total_usd"], total, rel_tol=1e-12)
    assert math.isclose(out["epc_total_lkr"], total * fx, rel_tol=1e-12)
    # Conservation: total == base + freight + contingency exactly.
    assert math.isclose(
        out["epc_total_usd"],
        out["epc_base_usd"] + out["epc_freight_usd"] + out["epc_contingency_usd"],
        rel_tol=1e-12,
    )


def test_breakdown_from_config_whole_percent_inputs() -> None:
    """Whole-percent inputs (5, 10) normalise identically to fractions."""
    base = 2.0e8
    cfg = {
        "capex": {"usd_total": base, "freight_pct": 5, "contingency_pct": 10},
        "fx": {"base_rate": 300.0},
    }
    out = epc_breakdown_from_config(cfg)
    assert math.isclose(out["epc_freight_usd"], base * 0.05, rel_tol=1e-12)
    assert math.isclose(out["epc_contingency_usd"], base * 0.10, rel_tol=1e-12)


def test_breakdown_from_config_defaults_zero_pcts() -> None:
    """Absent freight/contingency default to 0; total == base."""
    base = 7.5e7
    cfg = {"capex": {"usd_total": base}, "fx": {"rate": 333.0}}
    out = epc_breakdown_from_config(cfg)
    assert out["epc_freight_usd"] == 0.0
    assert out["epc_contingency_usd"] == 0.0
    assert out["epc_total_usd"] == base


def test_breakdown_from_config_uses_default_fx_argument() -> None:
    """No fx in config -> the default_fx_rate argument is applied to LKR."""
    base = 1.0e8
    cfg = {"capex": {"usd_total": base}}
    out = epc_breakdown_from_config(cfg, default_fx_rate=320.0)
    assert math.isclose(out["epc_total_lkr"], base * 320.0, rel_tol=1e-12)


def test_breakdown_from_config_non_mapping_capex_branch() -> None:
    """Legacy finance path resolves base; non-mapping capex -> zero pcts.

    This exercises the ``if not isinstance(capex, Mapping): capex = {}`` guard
    inside epc_breakdown_from_config (capex is the string sentinel here).
    """
    base = 4.0e7
    cfg = {"capex": "sentinel", "finance": {"capex_usd": base}, "fx": {"rate": 300.0}}
    out = epc_breakdown_from_config(cfg)
    assert out["epc_base_usd"] == base
    assert out["epc_freight_usd"] == 0.0
    assert out["epc_contingency_usd"] == 0.0


def test_breakdown_from_config_raises_on_missing_base() -> None:
    """No capex anywhere -> ValueError mentioning the accepted paths."""
    with pytest.raises(ValueError, match="Base EPC USD must be a positive number"):
        epc_breakdown_from_config({"fx": {"rate": 300.0}})


def test_breakdown_from_config_raises_on_zero_base() -> None:
    """A zero base (resolver returns None) -> ValueError."""
    with pytest.raises(ValueError, match="Base EPC USD must be a positive number"):
        epc_breakdown_from_config({"capex": {"usd_total": 0.0}, "fx": {"rate": 300.0}})


# ---------------------------------------------------------------------------
# epc_breakdown_dict (lines 356-394)
# ---------------------------------------------------------------------------


def test_breakdown_dict_full_contract_and_derivation() -> None:
    """All 11 contract keys present; USD and LCY layers derived from inputs."""
    base = 1.0e8
    freight_pct = 0.05
    cont_pct = 0.10
    fx = 350.0
    cfg = {
        "capex": {
            "usd_total": base,
            "freight_pct": freight_pct,
            "contingency_pct": cont_pct,
        },
        "fx": {"base_rate": fx},
    }
    out = epc_breakdown_dict(cfg)

    expected_keys = {
        "base_cost_usd",
        "freight_pct",
        "freight_usd",
        "contingency_pct",
        "contingency_usd",
        "total_usd",
        "fx_rate",
        "base_cost_lcy",
        "freight_lcy",
        "contingency_lcy",
        "total_lcy",
    }
    assert set(out.keys()) == expected_keys

    freight = base * freight_pct
    cont = base * cont_pct
    total = base + freight + cont

    assert out["base_cost_usd"] == base
    assert out["freight_pct"] == freight_pct
    assert out["contingency_pct"] == cont_pct
    assert math.isclose(out["freight_usd"], freight, rel_tol=1e-12)
    assert math.isclose(out["contingency_usd"], cont, rel_tol=1e-12)
    assert math.isclose(out["total_usd"], total, rel_tol=1e-12)
    assert out["fx_rate"] == fx
    # LCY layer == USD layer * fx (each component and the total).
    assert math.isclose(out["base_cost_lcy"], base * fx, rel_tol=1e-12)
    assert math.isclose(out["freight_lcy"], freight * fx, rel_tol=1e-12)
    assert math.isclose(out["contingency_lcy"], cont * fx, rel_tol=1e-12)
    assert math.isclose(out["total_lcy"], total * fx, rel_tol=1e-12)
    # Conservation across the LCY layer.
    assert math.isclose(
        out["total_lcy"],
        out["base_cost_lcy"] + out["freight_lcy"] + out["contingency_lcy"],
        rel_tol=1e-12,
    )


def test_breakdown_dict_default_fx_from_config_source() -> None:
    """No fx + no default_fx_rate -> fall back to config-sourced reference rate.

    The expected fx is read from the SAME source of truth the module reads
    (default_fx_lkr_per_usd), never a literal. This exercises lines 377-380.
    """
    base = 1.0e8
    cfg = {"capex": {"usd_total": base}}
    out = epc_breakdown_dict(cfg)
    expected_fx = default_fx_lkr_per_usd()
    assert out["fx_rate"] == expected_fx
    assert math.isclose(out["total_lcy"], base * expected_fx, rel_tol=1e-12)


def test_breakdown_dict_explicit_default_fx_argument() -> None:
    """An explicit default_fx_rate short-circuits the config-source fallback."""
    base = 5.0e7
    cfg = {"finance": {"capex_usd": base}}
    out = epc_breakdown_dict(cfg, default_fx_rate=300.0)
    assert out["fx_rate"] == 300.0
    assert math.isclose(out["base_cost_lcy"], base * 300.0, rel_tol=1e-12)


def test_breakdown_dict_non_mapping_capex_zero_pcts() -> None:
    """Non-mapping capex -> the guard resets it to {} so pcts are 0.0."""
    base = 4.0e7
    cfg = {"capex": ["not", "a", "map"], "finance": {"capex_usd": base}, "fx": {"rate": 300.0}}
    out = epc_breakdown_dict(cfg)
    assert out["base_cost_usd"] == base
    assert out["freight_pct"] == 0.0
    assert out["contingency_pct"] == 0.0


def test_breakdown_dict_raises_keyerror_on_missing_base() -> None:
    """epc_breakdown_dict raises KeyError (not ValueError) on missing base."""
    with pytest.raises(KeyError, match="EPC base cost required"):
        epc_breakdown_dict({"fx": {"rate": 300.0}})


# ---------------------------------------------------------------------------
# Schema registration (#301 broadened epc_usd_total spec)
# ---------------------------------------------------------------------------


def _spec_by_name(name: str) -> Any:
    specs = [s for s in get_required_fields("cashflow") if s.name == name]
    assert specs, f"expected a registered spec named {name!r}"
    return specs[0]


def test_schema_registers_epc_usd_total_required() -> None:
    """epc_usd_total is registered as a required, error-severity field."""
    spec = _spec_by_name("epc_usd_total")
    assert spec.required is True
    assert spec.severity == "error"
    assert spec.module == "cashflow"


def test_schema_epc_usd_total_paths_broadened() -> None:
    """The broadened (#301) path set mirrors the engine's capex resolvers."""
    spec = _spec_by_name("epc_usd_total")
    paths = set(spec.paths)
    # Canonical + capex.* aliases the engine honours.
    assert ("capex", "usd_total") in paths
    assert ("capex", "epc_usd") in paths
    assert ("capex", "capex_total_usd") in paths
    assert ("capex", "total_capex_usd") in paths
    assert ("capex", "total_capex") in paths
    # finance.* / costs.* legacy aliases.
    assert ("finance", "capex_total_usd") in paths
    assert ("finance", "capex_usd") in paths
    assert ("costs", "capex_total_usd") in paths
    assert ("costs", "capex_usd") in paths
    assert ("costs", "total_capex_usd") in paths
    assert ("costs", "total_capex") in paths


def test_schema_registers_optional_pct_fields() -> None:
    """freight/contingency pct are optional, warning-severity fields."""
    for name, path in (
        ("epc_freight_pct", ("capex", "freight_pct")),
        ("epc_contingency_pct", ("capex", "contingency_pct")),
    ):
        spec = _spec_by_name(name)
        assert spec.required is False
        assert spec.severity == "warning"
        assert path in set(spec.paths)


# ---------------------------------------------------------------------------
# Cross-builder consistency on the canonical lender scenario
# ---------------------------------------------------------------------------


def test_two_builders_agree_on_totals() -> None:
    """epc_breakdown_from_config and epc_breakdown_dict agree on USD/LKR totals.

    Both consume the SAME resolvers; their totals must be identical, which is a
    structural invariant rather than a hardcoded economic magnitude.
    """
    cfg: Dict[str, Any] = {
        "capex": {"usd_total": 1.0e8, "freight_pct": 7, "contingency_pct": 12},
        "fx": {"base_rate": 333.79},
    }
    a = epc_breakdown_from_config(cfg)
    b = epc_breakdown_dict(cfg)
    assert math.isclose(a["epc_total_usd"], b["total_usd"], rel_tol=1e-12)
    assert math.isclose(a["epc_total_lkr"], b["total_lcy"], rel_tol=1e-12)
    assert math.isclose(a["epc_base_usd"], b["base_cost_usd"], rel_tol=1e-12)
