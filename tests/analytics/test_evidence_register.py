"""Assumption evidence register — analytics/evidence_register.py (review chunk C5).

Covers the config-sourced taxonomy, the soft-by-default policy resolution, the pure
coverage report (build_evidence_report), and the policy-applying guard
(validate_evidence_register: warn vs raise vs no-op). KPI-neutral: a pure detector, so no
canonical-KPI assertions belong here — the byte-identical-economics guarantee is that the
guard raises or no-ops and never mutates the config.
"""
from __future__ import annotations

import logging

import pytest

from analytics import evidence_register as er
from analytics.evidence_register import (
    EvidenceRegisterError,
    build_evidence_report,
    default_evidence_policy,
    load_taxonomy,
    resolve_evidence_policy,
    validate_evidence_register,
)


def _entry(tier="benchmark", source="IRENA 2024", as_of="2024-01-01"):
    return {"source": source, "as_of": as_of, "tier": tier}


def _full_register(**over):
    """A register covering every material assumption (each well-formed)."""
    tax = load_taxonomy()
    entries = {a: _entry() for a in tax.assumptions}
    block = {"evidence_register": {"entries": entries}}
    block["evidence_register"].update(over)
    return block


# ── taxonomy + default policy (config-sourced) ──────────────────────────────────
def test_taxonomy_loads_ordered_tiers_and_assumptions() -> None:
    tax = load_taxonomy()
    assert tax.tiers[0] == "measured"  # strongest first
    assert tax.tiers[-1] == "placeholder"  # weakest last
    assert "tariff" in tax.assumptions and "capex" in tax.assumptions
    # ordering: a stronger tier ranks below (smaller index) a weaker one
    assert tax.is_weaker("placeholder", "benchmark")
    assert not tax.is_weaker("measured", "benchmark")


def test_default_policy_is_soft() -> None:
    pol = default_evidence_policy()
    assert pol.enforce is False
    assert pol.require_complete is False
    assert pol.min_tier is None


# ── graceful default: no register declared is a clean no-op ─────────────────────
def test_no_register_is_clean_noop() -> None:
    report = validate_evidence_register({}, "<none>")
    assert report.is_clean
    assert report.entries == {}


def test_well_formed_full_register_is_clean() -> None:
    report = validate_evidence_register(_full_register(), "lender.yaml")
    assert report.is_clean
    assert set(report.covered) == set(load_taxonomy().assumptions)
    assert report.missing == ()


# ── findings: content issues are reported (soft) not raised ─────────────────────
def test_unknown_assumption_is_a_soft_finding(caplog) -> None:
    cfg = {"evidence_register": {"entries": {"not_a_real_assumption": _entry()}}}
    with caplog.at_level(logging.WARNING):
        report = validate_evidence_register(cfg, "x.yaml")
    kinds = {f.kind for f in report.findings}
    assert "unknown_assumption" in kinds
    assert not report.is_clean
    assert "evidence-register findings" in caplog.text.lower()


def test_unknown_tier_is_a_finding() -> None:
    cfg = {"evidence_register": {"entries": {"tariff": _entry(tier="rumour")}}}
    report = build_evidence_report(cfg)
    assert any(f.kind == "unknown_tier" for f in report.findings)


def test_missing_required_field_is_a_finding() -> None:
    cfg = {"evidence_register": {"entries": {"capex": {"source": "EPC quote"}}}}  # no as_of/tier
    report = build_evidence_report(cfg)
    f = next(f for f in report.findings if f.kind == "missing_field")
    assert "as_of" in f.detail and "tier" in f.detail


# ── policy knobs ───────────────────────────────────────────────────────────────
def test_min_tier_flags_weak_evidence() -> None:
    cfg = {
        "evidence_register": {
            "min_tier": "benchmark",
            "entries": {"tariff": _entry(tier="placeholder")},
        }
    }
    report = build_evidence_report(cfg)
    assert any(f.kind == "below_min_tier" and f.assumption == "tariff" for f in report.findings)


def test_require_complete_flags_missing_assumptions() -> None:
    cfg = {
        "evidence_register": {
            "require_complete": True,
            "entries": {"tariff": _entry()},
        }
    }
    report = build_evidence_report(cfg)
    incomplete = {f.assumption for f in report.findings if f.kind == "incomplete"}
    assert "capex" in incomplete and "tariff" not in incomplete


def test_enforce_true_raises_on_findings() -> None:
    cfg = {"evidence_register": {"enforce": True, "entries": {"bogus": _entry()}}}
    with pytest.raises(EvidenceRegisterError, match="not lender-grade"):
        validate_evidence_register(cfg, "lender.yaml")


def test_lender_grade_full_register_passes_under_hard_enforcement() -> None:
    cfg = _full_register(enforce=True, require_complete=True, min_tier="benchmark")
    report = validate_evidence_register(cfg, "lender.yaml")  # must NOT raise
    assert report.is_clean


# ── input shapes + structural guards ───────────────────────────────────────────
def test_list_form_entries_accepted() -> None:
    cfg = {
        "evidence_register": {
            "entries": [
                {"assumption": "tariff", **_entry()},
                {"assumption": "capex", **_entry(tier="vendor_quote")},
            ]
        }
    }
    report = build_evidence_report(cfg)
    assert set(report.covered) >= {"tariff", "capex"}
    assert report.is_clean


def test_malformed_entries_container_raises() -> None:
    with pytest.raises(EvidenceRegisterError, match="must be a mapping or a list"):
        build_evidence_report({"evidence_register": {"entries": 42}})


def test_list_item_without_assumption_raises() -> None:
    with pytest.raises(EvidenceRegisterError, match="'assumption' key"):
        build_evidence_report({"evidence_register": {"entries": [_entry()]}})


def test_bad_min_tier_override_raises() -> None:
    with pytest.raises(ValueError, match="not a known evidence tier"):
        resolve_evidence_policy({"evidence_register": {"min_tier": "platinum"}})


def test_non_bool_override_raises() -> None:
    with pytest.raises(ValueError, match="must be a boolean"):
        resolve_evidence_policy({"evidence_register": {"enforce": "yes"}})


def test_guard_does_not_mutate_config() -> None:
    cfg = _full_register()
    before = repr(cfg)
    validate_evidence_register(cfg, "x.yaml")
    assert repr(cfg) == before  # pure detector — byte-identical economics


def test_block_without_entries_is_clean_noop() -> None:
    # An evidence_register block that only sets policy (no entries) is a clean no-op.
    report = build_evidence_report({"evidence_register": {"min_tier": "benchmark"}})
    assert report.entries == {} and report.is_clean


def test_non_mapping_entry_value_is_a_finding() -> None:
    cfg = {"evidence_register": {"entries": {"tariff": "21 LKR/kWh"}}}  # value not a record
    report = build_evidence_report(cfg)
    f = next(f for f in report.findings if f.kind == "missing_field")
    assert "not a mapping" in f.detail


# ── fail-loud config contract (CESSPIT): a malformed taxonomy / policy file raises ──
def test_load_taxonomy_fails_loud_on_malformed_file(tmp_path, monkeypatch) -> None:
    bad = tmp_path / "evidence_register.yaml"
    bad.write_text("evidence_tiers: [measured]\n")  # missing material_assumptions
    monkeypatch.setattr(er, "_REGISTER_PATH", bad)
    load_taxonomy.cache_clear()
    try:
        with pytest.raises(ValueError, match="material_assumptions"):
            load_taxonomy()
    finally:
        load_taxonomy.cache_clear()


def test_load_taxonomy_fails_loud_on_empty_lists(tmp_path, monkeypatch) -> None:
    bad = tmp_path / "evidence_register.yaml"
    bad.write_text("evidence_tiers: []\nmaterial_assumptions: []\n")
    monkeypatch.setattr(er, "_REGISTER_PATH", bad)
    load_taxonomy.cache_clear()
    try:
        with pytest.raises(ValueError, match="must both be non-empty"):
            load_taxonomy()
    finally:
        load_taxonomy.cache_clear()


def test_default_policy_fails_loud_on_missing_block(tmp_path, monkeypatch) -> None:
    bad = tmp_path / "defaults.yaml"
    bad.write_text("defaults: {}\n")  # no evidence_register block
    monkeypatch.setattr(er, "_DEFAULTS_PATH", bad)
    default_evidence_policy.cache_clear()
    try:
        with pytest.raises(ValueError, match="missing defaults.evidence_register"):
            default_evidence_policy()
    finally:
        default_evidence_policy.cache_clear()
