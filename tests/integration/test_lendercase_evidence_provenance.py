"""The committed lender case declares full assumption provenance (#481 RPT-2 follow-up).

The evidence register is a pure detector (KPI-neutral), but for a lender-grade deliverable the
committed lender scenario should declare a source / as-of / tier for EVERY material assumption — so
the report's Evidence Register renders "N of N covered" and the deepened Assumptions Register shows
real provenance instead of em-dash. This locks that completeness (and that nothing rests on the
weakest `placeholder` tier) against accidental regression.
"""

from __future__ import annotations

from pathlib import Path

from analytics.evidence_register import build_evidence_report, load_taxonomy
from analytics.scenario_loader import load_scenario_config

_LENDERCASE = (
    Path(__file__).resolve().parents[2]
    / "scenarios"
    / "dutchbay_lendercase_2025Q4.yaml"
)


def test_lendercase_evidence_register_is_complete_and_lender_grade() -> None:
    cfg = load_scenario_config(str(_LENDERCASE))
    report = build_evidence_report(cfg)
    material = set(load_taxonomy().assumptions)

    # Every canonical material assumption carries declared evidence — nothing missing, and no
    # stray/typo'd non-canonical key (which would only warn, not fail, at load).
    assert (
        not report.missing
    ), f"unevidenced material assumptions: {sorted(report.missing)}"
    assert set(report.entries) == material

    # No assumption rests on the weakest `placeholder` tier (must be retired before close).
    assert all(rec.get("tier") != "placeholder" for rec in report.entries.values())
