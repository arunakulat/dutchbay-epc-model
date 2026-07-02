"""Conditions-precedent (CP) checklist — analytics/conditions_precedent.py (issue #616).

Covers the config-sourced taxonomy, the soft-by-default policy, the pure report builder
(build_cp_report — outstanding rollup, per-workstream counts, findings) and the policy-applying
guard (validate_conditions_precedent: warn / raise / no-op). KPI-neutral: a pure detector, so
no canonical-KPI assertions belong here — the guarantee is that it raises or no-ops and never
mutates the config.
"""

from __future__ import annotations

import logging

import pytest

from analytics import conditions_precedent as cp
from analytics.conditions_precedent import (
    ConditionsPrecedentError,
    build_cp_report,
    default_cp_policy,
    load_cp_taxonomy,
    resolve_cp_policy,
    validate_conditions_precedent,
)


def _full_items(**status_over):
    tax = load_cp_taxonomy()
    return {
        "conditions_precedent": {
            "items": {
                name: {"status": status_over.get(name, "satisfied")}
                for name in tax.item_names
            }
        }
    }


# ── taxonomy + default policy (config-sourced) ──────────────────────────────────
def test_taxonomy_loads_ordered_statuses_workstreams_and_items() -> None:
    tax = load_cp_taxonomy()
    assert tax.statuses == ("satisfied", "waived", "pending")  # best -> worst
    assert "financing" in tax.workstreams and "ppa" in tax.workstreams
    assert "ppa_executed" in tax.item_names and "esia_approved" in tax.item_names
    # every canonical item is tagged to a canonical workstream
    for name, ws in tax.workstream_of.items():
        assert ws in tax.workstreams, (name, ws)


def test_default_policy_is_soft() -> None:
    pol = default_cp_policy()
    assert pol.enforce is False
    assert pol.require_complete is False


# ── graceful default: no checklist declared is a clean no-op ────────────────────
def test_no_checklist_is_clean_noop() -> None:
    report = validate_conditions_precedent({}, "<none>")
    assert report.is_clean
    assert report.items == ()
    assert report.n_outstanding == 0
    assert report.all_satisfied is False  # nothing declared => not "all satisfied"


def test_block_without_items_is_clean_noop() -> None:
    report = build_cp_report({"conditions_precedent": {"enforce": False}})
    assert report.items == () and report.is_clean


# ── rollup: outstanding counts + all_satisfied gate ─────────────────────────────
def test_full_checklist_all_satisfied() -> None:
    report = validate_conditions_precedent(_full_items(), "lender.yaml")
    assert report.is_clean
    assert report.all_satisfied is True
    assert report.n_outstanding == 0
    assert report.n_satisfied == len(load_cp_taxonomy().item_names)
    assert set(report.covered) == set(load_cp_taxonomy().item_names)
    assert report.missing == ()


def test_pending_item_is_outstanding_and_blocks_all_satisfied() -> None:
    cfg = _full_items(ppa_executed="pending", epc_contract_signed="pending")
    report = build_cp_report(cfg)
    assert report.n_outstanding == 2
    assert report.all_satisfied is False
    # per-workstream outstanding rollup attributes to the CANONICAL workstream
    assert report.by_workstream_outstanding.get("ppa") == 1
    assert report.by_workstream_outstanding.get("epc") == 1


def test_waived_is_not_outstanding() -> None:
    cfg = _full_items(security_package_perfected="waived")
    report = build_cp_report(cfg)
    assert report.n_waived == 1
    assert report.n_outstanding == 0
    assert report.all_satisfied is True  # waived does not gate drawdown


def test_waived_reason_is_carried_through() -> None:
    cfg = {
        "conditions_precedent": {
            "items": {
                "insurance_in_place": {
                    "status": "waived",
                    "waived_reason": "bridged by sponsor guarantee until COD",
                }
            }
        }
    }
    report = build_cp_report(cfg)
    (item,) = report.items
    assert item.waived_reason == "bridged by sponsor guarantee until COD"
    assert item.is_outstanding is False


# ── findings: content issues reported (soft) not raised ─────────────────────────
def test_unknown_item_is_a_soft_finding(caplog) -> None:
    cfg = {"conditions_precedent": {"items": {"made_up_cp": {"status": "satisfied"}}}}
    with caplog.at_level(logging.WARNING):
        report = validate_conditions_precedent(cfg, "x.yaml")
    assert any(f.kind == "unknown_item" for f in report.findings)
    assert "conditions-precedent findings" in caplog.text.lower()


def test_unknown_status_is_a_finding() -> None:
    cfg = {"conditions_precedent": {"items": {"ppa_executed": {"status": "purple"}}}}
    report = build_cp_report(cfg)
    assert any(f.kind == "unknown_status" for f in report.findings)
    # an invalid status does not render an item nor contribute to the rollup
    assert report.items == ()
    assert report.n_outstanding == 0


def test_missing_status_field_is_a_finding() -> None:
    cfg = {"conditions_precedent": {"items": {"epc_contract_signed": {"note": "x"}}}}
    report = build_cp_report(cfg)
    assert any(
        f.kind == "missing_field" and f.item == "epc_contract_signed"
        for f in report.findings
    )


def test_non_mapping_entry_is_a_finding() -> None:
    cfg = {"conditions_precedent": {"items": {"ppa_executed": "satisfied"}}}
    report = build_cp_report(cfg)
    assert any(
        f.kind == "missing_field" and "not a mapping" in f.detail
        for f in report.findings
    )


def test_require_complete_flags_missing_items() -> None:
    cfg = {
        "conditions_precedent": {
            "require_complete": True,
            "items": {"ppa_executed": {"status": "satisfied"}},
        }
    }
    report = build_cp_report(cfg)
    incomplete = {f.item for f in report.findings if f.kind == "incomplete"}
    assert "esia_approved" in incomplete and "ppa_executed" not in incomplete


def test_enforce_true_raises_on_findings() -> None:
    cfg = {
        "conditions_precedent": {
            "enforce": True,
            "items": {"bogus_cp": {"status": "satisfied"}},
        }
    }
    with pytest.raises(ConditionsPrecedentError, match="not lender-grade"):
        validate_conditions_precedent(cfg, "lender.yaml")


def test_lender_grade_complete_checklist_passes_under_hard_enforcement() -> None:
    cfg = _full_items()
    cfg["conditions_precedent"]["enforce"] = True
    cfg["conditions_precedent"]["require_complete"] = True
    report = validate_conditions_precedent(cfg, "lender.yaml")  # must NOT raise
    assert report.is_clean and report.all_satisfied is True


# ── input shapes + structural guards ────────────────────────────────────────────
def test_list_form_items_accepted() -> None:
    cfg = {
        "conditions_precedent": {
            "items": [
                {"name": "ppa_executed", "status": "satisfied"},
                {"name": "esia_approved", "status": "pending", "note": "draft"},
            ]
        }
    }
    report = build_cp_report(cfg)
    assert {i.name for i in report.items} == {"ppa_executed", "esia_approved"}
    assert report.n_outstanding == 1
    assert report.is_clean


def test_malformed_items_container_raises() -> None:
    with pytest.raises(ConditionsPrecedentError, match="must be a mapping or a list"):
        build_cp_report({"conditions_precedent": {"items": 7}})


def test_list_item_without_name_raises() -> None:
    with pytest.raises(ConditionsPrecedentError, match="'name' key"):
        build_cp_report({"conditions_precedent": {"items": [{"status": "satisfied"}]}})


def test_non_bool_override_raises() -> None:
    with pytest.raises(ValueError, match="must be a boolean"):
        resolve_cp_policy({"conditions_precedent": {"enforce": "yes"}})


def test_guard_does_not_mutate_config() -> None:
    cfg = _full_items()
    before = repr(cfg)
    validate_conditions_precedent(cfg, "x.yaml")
    assert repr(cfg) == before  # pure detector — byte-identical economics


# ── fail-loud config contract (CESSPIT) ─────────────────────────────────────────
def test_load_taxonomy_fails_loud_on_malformed_file(tmp_path, monkeypatch) -> None:
    bad = tmp_path / "conditions_precedent.yaml"
    bad.write_text("cp_statuses: [satisfied]\n")  # missing workstreams + items
    monkeypatch.setattr(cp, "_TAXONOMY_PATH", bad)
    load_cp_taxonomy.cache_clear()
    try:
        with pytest.raises(ValueError, match="cp_workstreams"):
            load_cp_taxonomy()
    finally:
        load_cp_taxonomy.cache_clear()


def test_load_taxonomy_fails_loud_on_empty_lists(tmp_path, monkeypatch) -> None:
    bad = tmp_path / "conditions_precedent.yaml"
    bad.write_text("cp_statuses: []\ncp_workstreams: []\ncp_items: []\n")
    monkeypatch.setattr(cp, "_TAXONOMY_PATH", bad)
    load_cp_taxonomy.cache_clear()
    try:
        with pytest.raises(ValueError, match="non-empty"):
            load_cp_taxonomy()
    finally:
        load_cp_taxonomy.cache_clear()


def test_load_taxonomy_fails_loud_on_item_with_unknown_workstream(
    tmp_path, monkeypatch
) -> None:
    bad = tmp_path / "conditions_precedent.yaml"
    bad.write_text(
        "cp_statuses: [satisfied, waived, pending]\n"
        "cp_workstreams: [ppa]\n"
        "cp_items:\n"
        "  - {name: ppa_executed, workstream: not_a_workstream}\n"
    )
    monkeypatch.setattr(cp, "_TAXONOMY_PATH", bad)
    load_cp_taxonomy.cache_clear()
    try:
        with pytest.raises(ValueError, match="not in cp_workstreams"):
            load_cp_taxonomy()
    finally:
        load_cp_taxonomy.cache_clear()
