"""Feasibility-report section schema — analytics/feasibility_sections.py (issue #616).

Covers the config-sourced 20-section taxonomy, the soft-by-default policy, the pure report
builder (build_feasibility_report — coverage rollup, per-group missing counts, findings) and
the policy-applying guard (validate_feasibility_sections: warn / raise / no-op). KPI-neutral:
a pure presentation schema, so no canonical-KPI assertions belong here — the guarantee is
that it raises or no-ops and never mutates the config.
"""

from __future__ import annotations

import logging

import pydantic
import pytest

from analytics import feasibility_sections as fs
from analytics.feasibility_sections import (
    FeasibilitySectionsError,
    build_feasibility_report,
    default_feasibility_policy,
    load_feasibility_taxonomy,
    resolve_feasibility_policy,
    validate_feasibility_sections,
)


def _full_sections(**status_over):
    tax = load_feasibility_taxonomy()
    return {
        "feasibility_sections": {
            "sections": {
                name: {"status": status_over.get(name, "complete")}
                for name in tax.section_names
            }
        }
    }


# ── taxonomy + default policy (config-sourced) ──────────────────────────────────
def test_taxonomy_loads_the_canonical_20_section_skeleton() -> None:
    tax = load_feasibility_taxonomy()
    # the static-audit §11 list is exactly twenty sections, ordered
    assert len(tax.sections) == 20
    assert tax.statuses == ("complete", "draft", "not_applicable")  # best -> worst
    assert tax.groups == (
        "technical",
        "financial",
        "legal",
        "environmental_social",
        "grid",
        "logistics",
        "risk",
    )
    # report order: thesis opens, appendices close
    assert tax.section_names[0] == "executive_investment_thesis"
    assert tax.section_names[-1] == "appendices_provenance_audit_trail"
    # every canonical section is tagged to a canonical group
    for name, group in tax.group_of.items():
        assert group in tax.groups, (name, group)
    # every group is actually used by at least one section
    assert set(tax.group_of.values()) == set(tax.groups)


def test_default_policy_is_soft() -> None:
    pol = default_feasibility_policy()
    assert pol.enforce is False
    assert pol.require_complete is False


def test_models_are_frozen_and_extra_forbid() -> None:
    tax = load_feasibility_taxonomy()
    section = tax.sections[0]
    with pytest.raises(pydantic.ValidationError):
        section.title = "mutated"  # frozen — post-construction mutation raises
    with pytest.raises(pydantic.ValidationError):
        fs.SectionDefinition(
            name="x", group="technical", title="X", bogus_field="nope"
        )  # extra="forbid"


# ── graceful default: no sections declared is a clean no-op ─────────────────────
def test_no_sections_is_clean_noop() -> None:
    report = validate_feasibility_sections({}, "<none>")
    assert report.is_clean
    assert report.sections == ()
    assert report.all_complete is False  # nothing declared => not "all complete"
    assert len(report.missing) == 20


def test_block_without_sections_is_clean_noop() -> None:
    report = build_feasibility_report({"feasibility_sections": {"enforce": False}})
    assert report.sections == () and report.is_clean


# ── rollup: coverage counts + all_complete gate ─────────────────────────────────
def test_full_coverage_all_complete() -> None:
    report = validate_feasibility_sections(_full_sections(), "ic.yaml")
    assert report.is_clean
    assert report.all_complete is True
    assert report.n_complete == 20
    assert report.missing == ()
    assert set(report.covered) == set(load_feasibility_taxonomy().section_names)


def test_draft_section_blocks_all_complete() -> None:
    cfg = _full_sections(climate_resilience_assessment="draft")
    report = build_feasibility_report(cfg)
    assert report.n_draft == 1
    assert report.all_complete is False  # a draft is not IC-ready


def test_not_applicable_is_a_documented_exclusion_not_a_hole() -> None:
    cfg = _full_sections(optimization_alternatives_analysis="not_applicable")
    report = build_feasibility_report(cfg)
    assert report.n_not_applicable == 1
    assert report.all_complete is True  # documented exclusion does not block
    (excluded,) = [s for s in report.sections if s.is_excluded]
    assert excluded.name == "optimization_alternatives_analysis"


def test_na_reason_and_narrative_are_carried_through() -> None:
    cfg = {
        "feasibility_sections": {
            "sections": {
                "monte_carlo_risk_distribution": {
                    "status": "complete",
                    "narrative": "10k-run LHS with calibrated FX block.",
                },
                "optimization_alternatives_analysis": {
                    "status": "not_applicable",
                    "na_reason": "single fixed configuration mandated by the PPA",
                },
            }
        }
    }
    report = build_feasibility_report(cfg)
    by_name = {s.name: s for s in report.sections}
    assert (
        by_name["monte_carlo_risk_distribution"].narrative
        == "10k-run LHS with calibrated FX block."
    )
    assert (
        by_name["optimization_alternatives_analysis"].na_reason
        == "single fixed configuration mandated by the PPA"
    )


def test_missing_rollup_counts_per_group() -> None:
    cfg = {
        "feasibility_sections": {
            "sections": {"executive_investment_thesis": {"status": "complete"}}
        }
    }
    report = build_feasibility_report(cfg)
    assert len(report.missing) == 19
    tax = load_feasibility_taxonomy()
    expected = {}
    for name in report.missing:
        g = tax.group_of[name]
        expected[g] = expected.get(g, 0) + 1
    assert dict(report.by_group_missing) == expected


def test_rendered_sections_keep_taxonomy_report_order() -> None:
    # declare out of order — the rendered tuple must follow the canonical skeleton order
    cfg = {
        "feasibility_sections": {
            "sections": {
                "appendices_provenance_audit_trail": {"status": "complete"},
                "executive_investment_thesis": {"status": "complete"},
                "resource_and_energy_yield": {"status": "draft"},
            }
        }
    }
    report = build_feasibility_report(cfg)
    assert [s.name for s in report.sections] == [
        "executive_investment_thesis",
        "resource_and_energy_yield",
        "appendices_provenance_audit_trail",
    ]
    # canonical group + title come from the taxonomy, not the declaration
    assert report.sections[0].group == "financial"
    assert report.sections[0].title == "Executive investment thesis"


# ── findings: content issues reported (soft) not raised ─────────────────────────
def test_unknown_section_is_a_soft_finding_and_not_rendered(caplog) -> None:
    cfg = {
        "feasibility_sections": {
            "sections": {"made_up_section": {"status": "complete"}}
        }
    }
    with caplog.at_level(logging.WARNING):
        report = validate_feasibility_sections(cfg, "x.yaml")
    assert any(f.kind == "unknown_section" for f in report.findings)
    assert "feasibility-section findings" in caplog.text.lower()
    # a scenario cannot invent report sections — the skeleton is fixed config
    assert report.sections == ()


def test_unknown_status_is_a_finding() -> None:
    cfg = {
        "feasibility_sections": {
            "sections": {"executive_investment_thesis": {"status": "purple"}}
        }
    }
    report = build_feasibility_report(cfg)
    assert any(f.kind == "unknown_status" for f in report.findings)
    assert report.sections == ()
    assert report.n_complete == 0


def test_missing_status_field_is_a_finding() -> None:
    cfg = {
        "feasibility_sections": {
            "sections": {"base_case_financial_outputs": {"narrative": "x"}}
        }
    }
    report = build_feasibility_report(cfg)
    assert any(
        f.kind == "missing_field" and f.section == "base_case_financial_outputs"
        for f in report.findings
    )


def test_non_mapping_entry_is_a_finding() -> None:
    cfg = {
        "feasibility_sections": {
            "sections": {"executive_investment_thesis": "complete"}
        }
    }
    report = build_feasibility_report(cfg)
    assert any(
        f.kind == "missing_field" and "not a mapping" in f.detail
        for f in report.findings
    )


def test_require_complete_flags_missing_sections() -> None:
    cfg = {
        "feasibility_sections": {
            "require_complete": True,
            "sections": {"executive_investment_thesis": {"status": "complete"}},
        }
    }
    report = build_feasibility_report(cfg)
    incomplete = {f.section for f in report.findings if f.kind == "incomplete"}
    assert "risk_register_and_mitigations" in incomplete
    assert "executive_investment_thesis" not in incomplete


def test_enforce_true_raises_on_findings() -> None:
    cfg = {
        "feasibility_sections": {
            "enforce": True,
            "sections": {"bogus_section": {"status": "complete"}},
        }
    }
    with pytest.raises(FeasibilitySectionsError, match="not IC-grade"):
        validate_feasibility_sections(cfg, "ic.yaml")


def test_ic_grade_full_coverage_passes_under_hard_enforcement() -> None:
    cfg = _full_sections()
    cfg["feasibility_sections"]["enforce"] = True
    cfg["feasibility_sections"]["require_complete"] = True
    report = validate_feasibility_sections(cfg, "ic.yaml")  # must NOT raise
    assert report.is_clean and report.all_complete is True


# ── input shapes + structural guards ────────────────────────────────────────────
def test_list_form_sections_accepted() -> None:
    cfg = {
        "feasibility_sections": {
            "sections": [
                {"name": "executive_investment_thesis", "status": "complete"},
                {"name": "resource_and_energy_yield", "status": "draft"},
            ]
        }
    }
    report = build_feasibility_report(cfg)
    assert {s.name for s in report.sections} == {
        "executive_investment_thesis",
        "resource_and_energy_yield",
    }
    assert report.n_draft == 1
    assert report.is_clean


def test_malformed_sections_container_raises() -> None:
    with pytest.raises(FeasibilitySectionsError, match="must be a mapping or a list"):
        build_feasibility_report({"feasibility_sections": {"sections": 7}})


def test_list_section_without_name_raises() -> None:
    with pytest.raises(FeasibilitySectionsError, match="'name' key"):
        build_feasibility_report(
            {"feasibility_sections": {"sections": [{"status": "complete"}]}}
        )


def test_non_bool_override_raises() -> None:
    with pytest.raises(ValueError, match="must be a boolean"):
        resolve_feasibility_policy({"feasibility_sections": {"enforce": "yes"}})


def test_guard_does_not_mutate_config() -> None:
    cfg = _full_sections()
    before = repr(cfg)
    validate_feasibility_sections(cfg, "x.yaml")
    assert repr(cfg) == before  # pure presentation schema — byte-identical economics


# ── fail-loud config contract (CESSPIT) ─────────────────────────────────────────
def test_load_taxonomy_fails_loud_on_malformed_file(tmp_path, monkeypatch) -> None:
    bad = tmp_path / "feasibility_sections.yaml"
    bad.write_text("section_statuses: [complete]\n")  # missing groups + sections
    monkeypatch.setattr(fs, "_TAXONOMY_PATH", bad)
    load_feasibility_taxonomy.cache_clear()
    try:
        with pytest.raises(ValueError, match="section_groups"):
            load_feasibility_taxonomy()
    finally:
        load_feasibility_taxonomy.cache_clear()


def test_load_taxonomy_fails_loud_on_empty_lists(tmp_path, monkeypatch) -> None:
    bad = tmp_path / "feasibility_sections.yaml"
    bad.write_text("section_statuses: []\nsection_groups: []\nsections: []\n")
    monkeypatch.setattr(fs, "_TAXONOMY_PATH", bad)
    load_feasibility_taxonomy.cache_clear()
    try:
        with pytest.raises(ValueError, match="non-empty"):
            load_feasibility_taxonomy()
    finally:
        load_feasibility_taxonomy.cache_clear()


def test_load_taxonomy_fails_loud_on_section_with_unknown_group(
    tmp_path, monkeypatch
) -> None:
    bad = tmp_path / "feasibility_sections.yaml"
    bad.write_text(
        "section_statuses: [complete, draft, not_applicable]\n"
        "section_groups: [technical]\n"
        "sections:\n"
        "  - {name: resource_and_energy_yield, group: not_a_group, title: R}\n"
    )
    monkeypatch.setattr(fs, "_TAXONOMY_PATH", bad)
    load_feasibility_taxonomy.cache_clear()
    try:
        with pytest.raises(ValueError, match="not in section_groups"):
            load_feasibility_taxonomy()
    finally:
        load_feasibility_taxonomy.cache_clear()


def test_load_taxonomy_fails_loud_on_duplicate_section_names(
    tmp_path, monkeypatch
) -> None:
    bad = tmp_path / "feasibility_sections.yaml"
    bad.write_text(
        "section_statuses: [complete, draft, not_applicable]\n"
        "section_groups: [technical]\n"
        "sections:\n"
        "  - {name: dupe, group: technical, title: A}\n"
        "  - {name: dupe, group: technical, title: B}\n"
    )
    monkeypatch.setattr(fs, "_TAXONOMY_PATH", bad)
    load_feasibility_taxonomy.cache_clear()
    try:
        with pytest.raises(ValueError, match="unique names"):
            load_feasibility_taxonomy()
    finally:
        load_feasibility_taxonomy.cache_clear()
