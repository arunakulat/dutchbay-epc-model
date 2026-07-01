"""Development-readiness / E&S register — analytics/development_readiness.py (review C11).

Covers the config-sourced taxonomy, the soft-by-default policy, the pure report builder
(build_readiness_report — coverage, RAG rollup, findings) and the policy-applying guard
(validate_development_readiness: warn / raise / no-op). KPI-neutral: a pure detector, so no
canonical-KPI assertions belong here — the guarantee is that it raises or no-ops and never
mutates the config.
"""

from __future__ import annotations

import logging

import pytest

from analytics import development_readiness as dr
from analytics.development_readiness import (
    DevelopmentReadinessError,
    build_readiness_report,
    default_readiness_policy,
    load_readiness_taxonomy,
    resolve_readiness_policy,
    validate_development_readiness,
)


def _full_items(**status_over):
    tax = load_readiness_taxonomy()
    return {
        "development_readiness": {
            "items": {
                w: {"status": status_over.get(w, "green")} for w in tax.workstreams
            }
        }
    }


# ── taxonomy + default policy (config-sourced) ──────────────────────────────────
def test_taxonomy_loads_ordered_rag_and_workstreams() -> None:
    tax = load_readiness_taxonomy()
    assert tax.statuses == ("green", "amber", "red")  # best -> worst
    assert "environmental_social" in tax.workstreams and "financing" in tax.workstreams
    assert tax.worst(["green", "red", "amber"]) == "red"
    assert tax.worst(["green", "amber"]) == "amber"
    assert tax.worst([]) is None


def test_default_policy_is_soft() -> None:
    pol = default_readiness_policy()
    assert pol.enforce is False
    assert pol.require_complete is False


# ── graceful default: no register declared is a clean no-op ─────────────────────
def test_no_register_is_clean_noop() -> None:
    report = validate_development_readiness({}, "<none>")
    assert report.is_clean
    assert report.items == ()
    assert report.overall_status is None


def test_block_without_items_is_clean_noop() -> None:
    report = build_readiness_report({"development_readiness": {"enforce": False}})
    assert report.items == () and report.is_clean


def test_full_register_rolls_up_to_worst_status() -> None:
    cfg = _full_items(financing="red", land="amber")
    report = validate_development_readiness(cfg, "lender.yaml")
    assert report.is_clean
    assert report.overall_status == "red"  # worst declared
    assert report.counts["green"] == len(load_readiness_taxonomy().workstreams) - 2
    assert set(report.covered) == set(load_readiness_taxonomy().workstreams)
    assert report.missing == ()


def test_all_green_rolls_up_to_green() -> None:
    report = build_readiness_report(_full_items())
    assert report.overall_status == "green"


# ── findings: content issues reported (soft) not raised ─────────────────────────
def test_unknown_workstream_is_a_soft_finding(caplog) -> None:
    cfg = {"development_readiness": {"items": {"made_up": {"status": "green"}}}}
    with caplog.at_level(logging.WARNING):
        report = validate_development_readiness(cfg, "x.yaml")
    assert any(f.kind == "unknown_workstream" for f in report.findings)
    assert "development-readiness findings" in caplog.text.lower()


def test_unknown_status_is_a_finding() -> None:
    cfg = {"development_readiness": {"items": {"land": {"status": "purple"}}}}
    report = build_readiness_report(cfg)
    assert any(f.kind == "unknown_status" for f in report.findings)
    # an invalid status does not contribute to the rollup
    assert report.overall_status is None


def test_missing_status_field_is_a_finding() -> None:
    cfg = {"development_readiness": {"items": {"epc": {"note": "no status"}}}}
    report = build_readiness_report(cfg)
    assert any(
        f.kind == "missing_field" and f.workstream == "epc" for f in report.findings
    )


def test_non_mapping_entry_is_a_finding() -> None:
    cfg = {"development_readiness": {"items": {"land": "green"}}}  # value not a record
    report = build_readiness_report(cfg)
    assert any(
        f.kind == "missing_field" and "not a mapping" in f.detail
        for f in report.findings
    )


def test_require_complete_flags_missing_workstreams() -> None:
    cfg = {
        "development_readiness": {
            "require_complete": True,
            "items": {"land": {"status": "green"}},
        }
    }
    report = build_readiness_report(cfg)
    incomplete = {f.workstream for f in report.findings if f.kind == "incomplete"}
    assert "financing" in incomplete and "land" not in incomplete


def test_enforce_true_raises_on_findings() -> None:
    cfg = {
        "development_readiness": {
            "enforce": True,
            "items": {"bogus": {"status": "green"}},
        }
    }
    with pytest.raises(DevelopmentReadinessError, match="not lender-grade"):
        validate_development_readiness(cfg, "lender.yaml")


def test_lender_grade_complete_register_passes_under_hard_enforcement() -> None:
    cfg = _full_items()
    cfg["development_readiness"]["enforce"] = True
    cfg["development_readiness"]["require_complete"] = True
    report = validate_development_readiness(cfg, "lender.yaml")  # must NOT raise
    assert report.is_clean and report.overall_status == "green"


# ── input shapes + structural guards ────────────────────────────────────────────
def test_list_form_items_accepted() -> None:
    cfg = {
        "development_readiness": {
            "items": [
                {"workstream": "land", "status": "green"},
                {"workstream": "ppa", "status": "amber", "note": "template"},
            ]
        }
    }
    report = build_readiness_report(cfg)
    assert {i.workstream for i in report.items} == {"land", "ppa"}
    assert report.overall_status == "amber"
    assert report.is_clean


def test_malformed_items_container_raises() -> None:
    with pytest.raises(DevelopmentReadinessError, match="must be a mapping or a list"):
        build_readiness_report({"development_readiness": {"items": 7}})


def test_list_item_without_workstream_raises() -> None:
    with pytest.raises(DevelopmentReadinessError, match="'workstream' key"):
        build_readiness_report(
            {"development_readiness": {"items": [{"status": "green"}]}}
        )


def test_non_bool_override_raises() -> None:
    with pytest.raises(ValueError, match="must be a boolean"):
        resolve_readiness_policy({"development_readiness": {"enforce": "yes"}})


def test_guard_does_not_mutate_config() -> None:
    cfg = _full_items()
    before = repr(cfg)
    validate_development_readiness(cfg, "x.yaml")
    assert repr(cfg) == before  # pure detector — byte-identical economics


# ── fail-loud config contract (CESSPIT) ─────────────────────────────────────────
def test_load_taxonomy_fails_loud_on_malformed_file(tmp_path, monkeypatch) -> None:
    bad = tmp_path / "development_readiness.yaml"
    bad.write_text("rag_statuses: [green]\n")  # missing workstreams
    monkeypatch.setattr(dr, "_TAXONOMY_PATH", bad)
    load_readiness_taxonomy.cache_clear()
    try:
        with pytest.raises(ValueError, match="workstreams"):
            load_readiness_taxonomy()
    finally:
        load_readiness_taxonomy.cache_clear()


def test_load_taxonomy_fails_loud_on_empty_lists(tmp_path, monkeypatch) -> None:
    bad = tmp_path / "development_readiness.yaml"
    bad.write_text("rag_statuses: []\nworkstreams: []\n")
    monkeypatch.setattr(dr, "_TAXONOMY_PATH", bad)
    load_readiness_taxonomy.cache_clear()
    try:
        with pytest.raises(ValueError, match="non-empty"):
            load_readiness_taxonomy()
    finally:
        load_readiness_taxonomy.cache_clear()


def test_default_policy_fails_loud_on_missing_block(tmp_path, monkeypatch) -> None:
    bad = tmp_path / "defaults.yaml"
    bad.write_text("defaults: {}\n")
    monkeypatch.setattr(dr, "_DEFAULTS_PATH", bad)
    default_readiness_policy.cache_clear()
    try:
        with pytest.raises(ValueError, match="missing defaults.development_readiness"):
            default_readiness_policy()
    finally:
        default_readiness_policy.cache_clear()


# ── integration: the seeded canonical scenarios carry a register ────────────────
def test_seeded_lendercase_scenario_rolls_up_red() -> None:
    from pathlib import Path

    import yaml

    repo = Path(__file__).resolve().parents[2]
    cfg = yaml.safe_load(
        (repo / "scenarios" / "dutchbay_lendercase_2025Q4.yaml").read_text()
    )
    report = build_readiness_report(cfg)
    assert report.is_clean  # the seed is well-formed against the taxonomy
    assert report.overall_status == "red"  # financing is red
    assert "environmental_social" in report.covered
