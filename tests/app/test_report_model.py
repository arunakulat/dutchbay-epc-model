"""Tests for the report content model (pure presentation over a CaseResult)."""

from __future__ import annotations

from typing import Dict

import pytest
from pydantic import ValidationError

from app.api.responses import CaseResult
from app.models.inputs import WindFarmInputs
from app.reports.renderer import render_report_html
from app.reports.report_config import (
    Covenants,
    ReportConfig,
    ReportMeta,
    RiskItem,
)
from app.reports.report_model import (
    ReportContext,
    Verdict,
    WaterfallRow,
    build_report_context,
    fmt_gwh,
    fmt_pct,
    fmt_pp,
    fmt_ratio_pct,
    fmt_usd,
    fmt_x,
    format_kpi_value,
)

GENERATED_AT = "2026-06-22T12:00:00+00:00"

#: The frozen value-destructive economics (#280/#281): IRR below the WACC hurdle,
#: negative equity NPV, DSCR at the 1.30 sculpt target, balloon within ceiling.
_VALUE_DESTRUCTIVE_KPIS: Dict[str, float] = {
    "project_irr": 0.0422,
    "equity_irr": -0.0246,
    "project_npv": -57994285.93,
    "equity_npv": -60926463.83,
    "min_dscr": 1.2999999,
    "avg_dscr": 1.3873,
    "llcr": 1.1277,
    "plcr": 1.1895,
    "equity_moic": 0.7554,
    "discount_rate_used": 0.0854,
    "balloon_pct": 0.3467,
}


def _case(kpis: Dict[str, float], *, variant: str = "lendercase") -> CaseResult:
    return CaseResult(
        status="success", scenario_variant=variant, kpis=kpis, run_manifest=None
    )


def _inputs() -> WindFarmInputs:
    return WindFarmInputs(
        site_name="Dutch Bay",
        location="Kalpitiya",
        capacity_mw=150.0,
        capacity_factor=0.339,
        project_life_years=20,
        ppa_price_lkr_per_kwh=26.0,
        ppa_term_years=20,
        capex_total_usd=195_000_000,
        opex_annual_usd=6_000_000,
        fx_start_lkr_per_usd=333.79,
    )


# --------------------------------------------------------------------------- #
# Formatting
# --------------------------------------------------------------------------- #
def test_format_pct() -> None:
    assert format_kpi_value(0.0422, "pct") == "4.22%"
    assert format_kpi_value(-0.0246, "pct") == "-2.46%"


def test_format_multiple() -> None:
    assert format_kpi_value(1.2999999, "multiple") == "1.30x"


def test_format_usd_sign_handling() -> None:
    assert format_kpi_value(110662500.0, "usd") == "$110,662,500"
    assert format_kpi_value(-57994285.93, "usd") == "-$57,994,286"


# --------------------------------------------------------------------------- #
# Finance-table format helpers (RPT-1)
# --------------------------------------------------------------------------- #
def test_fmt_helpers_none_is_em_dash() -> None:
    assert fmt_usd(None) == "—"
    assert fmt_gwh(None) == "—"
    assert fmt_x(None) == "—"
    assert fmt_ratio_pct(None) == "—"
    assert fmt_pct(None) == "—"


def test_fmt_helpers_values() -> None:
    assert fmt_usd(159_600_000.0) == "$159,600,000"
    assert fmt_usd(-65_455_817.0) == "-$65,455,817"  # accounting-style negative
    assert fmt_gwh(464.34) == "464.3 GWh"
    assert fmt_x(1.308) == "1.31x"
    assert fmt_ratio_pct(0.4125) == "41.25%"  # ratio -> percent
    assert fmt_pct(13.39) == "13.39%"  # already a percent


# --------------------------------------------------------------------------- #
# Finance blocks wiring (RPT-1): production / sources-and-uses / DSCR profile
# --------------------------------------------------------------------------- #
_SCENARIO_CFG = {
    "resource": {
        "wind": {"aep_gwh": 464.3, "capacity_factor": 0.332, "source_id": "test-source"}
    },
    "project": {"capacity_mw": 159.6},
    "finance": {"capex_total_usd": 159_600_000.0},
}
_DEBT_RESULT = {
    "debt_total": 65_835_000.0,
    "total_idc": 10_287_933.22,
    "tenor_years": 15,
    "construction_years": 2,
    "min_dscr": 1.2999,
    "avg_debt_rate": 0.08,
    "balloon_pct": 0.36,
    "balloon_remaining": 23_700_000.0,
    "dual_dscr": {
        "solved_gearing": 0.4125,
        "binding_constraint": "dscr",
        "binding_production_case": "P50",
    },
    "principal_by_tranche": {"senior": 65_835_000.0},
    "idc_by_tranche": {"senior": 10_287_933.22},
    "raw_dscr_series": [None, None, 1.308, 1.31, 1.30],
    "debt_outstanding": [65_835_000.0, 65_835_000.0, 60_000_000.0, 55e6, 50e6],
    "debt_service_total": [0.0, 0.0, 8_000_000.0, 8_000_000.0, 8_000_000.0],
    "funding": {
        "sources_and_uses": {
            "uses": {"capex_usd": 159_600_000.0, "idc_usd": 10_287_933.22},
            "sources": {"senior_debt_usd": 76_122_933.22, "equity_usd": 93_765_000.0},
            "uses_total_usd": 169_887_933.22,
            "sources_total_usd": 169_887_933.22,
            "balanced": True,
        }
    },
}


def test_finance_blocks_populated_with_scenario_and_debt() -> None:
    ctx = build_report_context(
        _case(_VALUE_DESTRUCTIVE_KPIS),
        generated_at=GENERATED_AT,
        scenario_config=_SCENARIO_CFG,
        debt_result=_DEBT_RESULT,
    )
    assert ctx.finance is not None
    assert ctx.finance.aep.net_p50_gwh == 464.3
    assert ctx.finance.funding.balanced is True
    # A real sources-and-uses table balances.
    assert ctx.finance.funding.uses_total_usd == ctx.finance.funding.sources_total_usd
    assert ctx.finance.debt.tenor_years == 15
    # Full-timeline DSCR profile: construction years carry None, operating years a value.
    assert [r.dscr for r in ctx.finance.debt.schedule[:3]] == [None, None, 1.308]
    assert ctx.finance.kpis.project_irr == _VALUE_DESTRUCTIVE_KPIS["project_irr"]


def test_report_omits_p90_sizing_rows_for_p50_only_debt() -> None:
    """The default P50-only debt result renders NO P90 sizing-detail rows (#613).

    The lender report keeps the single binding-constraint row (present for every dual_dscr
    scenario) but omits the P90 gearing-solve / target / downside-ratio rows unless a
    scenario opts into the downside-binding solve.
    """
    ctx = build_report_context(
        _case(_VALUE_DESTRUCTIVE_KPIS),
        generated_at=GENERATED_AT,
        scenario_config=_SCENARIO_CFG,
        debt_result=_DEBT_RESULT,
    )
    html = render_report_html(ctx)
    assert "Binding sizing constraint" in html
    assert "Gearing solves (P50 / P90)" not in html
    assert "P90 target DSCR" not in html
    assert "Downside CFADS ratio" not in html


def test_report_surfaces_p90_sizing_rows_when_bind_downside() -> None:
    """A bind_downside debt result renders the full P90 sizing-detail block (#613).

    Pure render-when-present serialisation: the two gearing solves, the P90 DSCR target,
    and the downside CFADS ratio (with a human-readable source label) all appear.
    """
    debt = {
        **_DEBT_RESULT,
        "dual_dscr": {
            "solved_gearing": 0.365,
            "binding_constraint": "dscr",
            "binding_production_case": "P90",
            "sizing_mode": "dual_dscr",
            "solved_gearing_p50": 0.4175,
            "solved_gearing_p90": 0.365,
            "target_dscr_p90": 1.30,
            "downside_ratio": 0.875302,
            "downside_source": "p90_aep",
        },
    }
    ctx = build_report_context(
        _case(_VALUE_DESTRUCTIVE_KPIS),
        generated_at=GENERATED_AT,
        scenario_config=_SCENARIO_CFG,
        debt_result=debt,
    )
    assert ctx.finance is not None
    d = ctx.finance.debt
    assert d.solved_gearing_p50 == pytest.approx(0.4175)
    assert d.solved_gearing_p90 == pytest.approx(0.365)
    assert d.target_dscr_p90 == pytest.approx(1.30)
    assert d.downside_ratio == pytest.approx(0.875302)
    assert d.downside_source == "p90_aep"

    html = render_report_html(ctx)
    assert "Gearing solves (P50 / P90)" in html
    assert "41.75% / 36.50%" in html  # fmt_ratio_pct of the two solves
    assert "P90 target DSCR" in html
    assert "Downside CFADS ratio (P90/P50)" in html
    assert "P90 AEP" in html  # source label, not the raw "p90_aep" token


def test_finance_blocks_none_without_debt_result() -> None:
    # scenario_config alone (no debt_result) -> no finance section (legacy-safe).
    ctx = build_report_context(
        _case(_VALUE_DESTRUCTIVE_KPIS),
        generated_at=GENERATED_AT,
        scenario_config=_SCENARIO_CFG,
    )
    assert ctx.finance is None


def test_finance_blocks_none_without_scenario_config() -> None:
    ctx = build_report_context(
        _case(_VALUE_DESTRUCTIVE_KPIS),
        generated_at=GENERATED_AT,
        debt_result=_DEBT_RESULT,
    )
    assert ctx.finance is None


def test_tornado_stored_when_supplied() -> None:
    # build_report_context only stores the pre-computed tornado (it stays pure).
    from app.services.report_tornado import TornadoBlock, TornadoRow

    tornado = TornadoBlock(
        metric="project_irr",
        rows=[TornadoRow(label="Tariff", base=0.0116, impact_abs=0.028)],
    )
    ctx = build_report_context(
        _case(_VALUE_DESTRUCTIVE_KPIS), generated_at=GENERATED_AT, tornado=tornado
    )
    assert ctx.tornado is not None and ctx.tornado.rows[0].label == "Tariff"


def test_tornado_none_by_default() -> None:
    ctx = build_report_context(
        _case(_VALUE_DESTRUCTIVE_KPIS), generated_at=GENERATED_AT
    )
    assert ctx.tornado is None


# --------------------------------------------------------------------------- #
# Global sensitivity (Morris) wiring (MC-1)
# --------------------------------------------------------------------------- #
def test_global_sa_stored_when_supplied() -> None:
    # build_report_context only stores the pre-computed global-SA block (stays pure).
    from app.services.report_global_sa import GlobalSABlock, GlobalSADriver

    block = GlobalSABlock(
        method="morris",
        metric="project_irr",
        n_runs=112,
        drivers=[
            GlobalSADriver(name="tariff.lkr_per_kwh", mu_star=0.0493, sigma=0.005)
        ],
    )
    ctx = build_report_context(
        _case(_VALUE_DESTRUCTIVE_KPIS), generated_at=GENERATED_AT, global_sa=block
    )
    assert ctx.global_sa is not None
    assert ctx.global_sa.drivers[0].name == "tariff.lkr_per_kwh"


def test_global_sa_none_by_default() -> None:
    ctx = build_report_context(
        _case(_VALUE_DESTRUCTIVE_KPIS), generated_at=GENERATED_AT
    )
    assert ctx.global_sa is None


# --------------------------------------------------------------------------- #
# Two-factor interaction grid wiring (#739 slice-2)
# --------------------------------------------------------------------------- #
def _interaction_grid_fixture() -> "TwoFactorInteractionGrid":  # noqa: F821
    """A 3x3 IRR interaction grid with one FAILED interior cell + honesty metadata.

    Base cell (0,0) = 0.05. A super-additive corner at (2,2) drives max_abs_interaction, and one
    interior cell carries NaN so the projection's failed-cell handling and disclosure are exercised.
    """
    from analytics.contracts_v14 import TwoFactorInteractionGrid

    nan = float("nan")
    values = [
        [0.050, 0.052, 0.048],
        [0.055, 0.060, nan],
        [0.045, 0.049, 0.070],
    ]
    interaction = [
        [0.000, 0.000, 0.000],
        [0.000, 0.001, nan],
        [0.000, -0.002, 0.015],
    ]
    return TwoFactorInteractionGrid(
        metric_name="project_irr",
        param_a_name="tariff.lkr_per_kwh",
        param_b_name="fx.usdlkr_depreciation_pct",
        a_labels=["tariff.lkr_per_kwh=base", "=low", "=high"],
        b_labels=["fx=base", "=low", "=high"],
        values=values,
        interaction=interaction,
        base_metric=0.050,
        max_abs_interaction=0.015,
        metadata={
            "base_config_path": "scenarios/example.yaml",
            "n_evaluations": 10,
            "n_failed_cells": 1,
            "base_mismatch": False,
            "declared_base_cell": 0.050,
            "unresolved_drivers": [],
            "param_a_label": "PPA tariff",
            "param_b_label": "FX depreciation",
        },
    )


def test_interaction_grid_projected_and_surfaces_honesty_metadata() -> None:
    from app.reports.report_model import build_report_context as _brc

    grid = _interaction_grid_fixture()
    ctx = _brc(
        _case(_VALUE_DESTRUCTIVE_KPIS),
        generated_at=GENERATED_AT,
        interaction_grid=grid,
    )
    block = ctx.interaction_grid
    assert block is not None
    # Labels + shape mapped 1:1.
    assert block.param_a_label == "PPA tariff"
    assert block.param_b_label == "FX depreciation"
    assert block.b_labels == ["fx=base", "=low", "=high"]
    assert len(block.rows) == 3 and len(block.rows[0].cells) == 3
    assert block.is_ratio_metric is True  # project_irr → ratio, not USD
    # Honesty metadata surfaced as first-class fields.
    assert block.n_failed_cells == 1
    assert block.base_mismatch is False
    assert block.unresolved_drivers == []
    assert block.n_evaluations == 10
    assert block.max_abs_interaction == pytest.approx(0.015)
    # The failed interior cell (1,2) maps NaN -> None (never zero-filled).
    failed = block.rows[1].cells[2]
    assert (
        failed.value is None and failed.interaction is None and failed.intensity is None
    )
    # The strongest corner (2,2) gets full positive intensity.
    corner = block.rows[2].cells[2]
    assert corner.interaction == pytest.approx(0.015)
    assert corner.intensity == pytest.approx(1.0)
    # A negative interaction cell gets a negative intensity.
    neg = block.rows[2].cells[1]
    assert neg.intensity is not None and neg.intensity < 0


def test_interaction_grid_none_by_default() -> None:
    ctx = build_report_context(
        _case(_VALUE_DESTRUCTIVE_KPIS), generated_at=GENERATED_AT
    )
    assert ctx.interaction_grid is None


def test_interaction_grid_default_off_is_byte_identical() -> None:
    """Passing no grid must produce a report context identical to before the feature."""
    case = _case(_VALUE_DESTRUCTIVE_KPIS)
    without = build_report_context(case, generated_at=GENERATED_AT)
    explicit_none = build_report_context(
        case, generated_at=GENERATED_AT, interaction_grid=None
    )
    assert without.interaction_grid is None
    assert explicit_none.interaction_grid is None
    # The rendered HTML omits the section entirely and is byte-identical either way.
    html_without = render_report_html(without)
    html_none = render_report_html(explicit_none)
    assert html_without == html_none
    assert "Interaction Grid" not in html_without


def test_interaction_grid_renders_failed_cell_and_disclosure() -> None:
    """The rendered section discloses the failed cell (em-dash) and integrity note (#657)."""
    grid = _interaction_grid_fixture()
    ctx = build_report_context(
        _case(_VALUE_DESTRUCTIVE_KPIS),
        generated_at=GENERATED_AT,
        interaction_grid=grid,
    )
    html = render_report_html(ctx)
    assert "Interaction Grid" in html
    # Honesty disclosure: the failed-cell count is surfaced, not hidden.
    assert "1 of 9 interior cell(s)" in html


# --------------------------------------------------------------------------- #
# Evidence register (#435 -> RPT-1)
# --------------------------------------------------------------------------- #
def test_evidence_register_projected_from_scenario_config() -> None:
    scenario = {
        "evidence_register": {
            "entries": {
                "capex": {
                    "source": "SINOHYDRO EPC quote",
                    "as_of": "2025-09",
                    "tier": "A",
                },
                "tariff": {
                    "source": "CEB SPPA",
                    "as_of": "2025-06",
                    "tier": "A",
                    "note": "flat LKR",
                },
            }
        }
    }
    ctx = build_report_context(
        _case(_VALUE_DESTRUCTIVE_KPIS),
        generated_at=GENERATED_AT,
        scenario_config=scenario,
    )
    assert ctx.evidence is not None
    assert ctx.evidence.covered == 2
    assert (
        ctx.evidence.total > ctx.evidence.covered
    )  # uncovered material assumptions remain
    labels = {r.assumption for r in ctx.evidence.rows}
    assert {"capex", "tariff"} <= labels
    tariff = next(r for r in ctx.evidence.rows if r.assumption == "tariff")
    assert (
        tariff.source == "CEB SPPA" and tariff.tier == "A" and tariff.note == "flat LKR"
    )
    assert (
        "capex" not in ctx.evidence.missing
    )  # capex has evidence; not in the gap list


def test_evidence_block_shows_gap_when_no_entries() -> None:
    # A scenario with no evidence block still gets a block: 0 covered, the gap listed.
    ctx = build_report_context(
        _case(_VALUE_DESTRUCTIVE_KPIS), generated_at=GENERATED_AT, scenario_config={}
    )
    assert ctx.evidence is not None
    assert ctx.evidence.covered == 0 and ctx.evidence.rows == []
    assert len(ctx.evidence.missing) == ctx.evidence.total > 0


def test_evidence_none_without_scenario_config() -> None:
    ctx = build_report_context(
        _case(_VALUE_DESTRUCTIVE_KPIS), generated_at=GENERATED_AT
    )
    assert ctx.evidence is None


def test_evidence_none_on_malformed_register() -> None:
    # A structurally malformed entries container degrades to no section (not a 500).
    scenario = {"evidence_register": {"entries": 42}}
    ctx = build_report_context(
        _case(_VALUE_DESTRUCTIVE_KPIS),
        generated_at=GENERATED_AT,
        scenario_config=scenario,
    )
    assert ctx.evidence is None


# --------------------------------------------------------------------------- #
# Assumptions register deepening (#481, RPT-2): value · source · as-of · impact
# --------------------------------------------------------------------------- #
def test_assumptions_carry_impact_notes_without_fabricating_sources() -> None:
    ctx = build_report_context(
        _case(_VALUE_DESTRUCTIVE_KPIS), generated_at=GENERATED_AT, inputs=_inputs()
    )
    by_label = {r.label: r for r in ctx.assumptions}
    # Mapped assumptions carry a model-grounded impact note...
    assert "Revenue" in by_label["PPA tariff"].impact
    assert by_label["Capacity factor"].impact and by_label["Total CAPEX"].impact
    # ...but with no scenario config, no source/as-of is fabricated.
    assert by_label["PPA tariff"].source == "" and by_label["PPA tariff"].as_of == ""


def test_assumptions_cross_reference_evidence_register() -> None:
    scenario = {
        "evidence_register": {
            "entries": {
                "capex": {
                    "source": "SINOHYDRO EPC quote",
                    "as_of": "2025-09",
                    "tier": "A",
                },
                "tariff": {"source": "CEB SPPA", "as_of": "2025-06", "tier": "A"},
            }
        }
    }
    ctx = build_report_context(
        _case(_VALUE_DESTRUCTIVE_KPIS),
        generated_at=GENERATED_AT,
        inputs=_inputs(),
        scenario_config=scenario,
    )
    by_label = {r.label: r for r in ctx.assumptions}
    # CAPEX + tariff lines pick up source/as-of from the matching evidence entries.
    assert by_label["Total CAPEX"].source == "SINOHYDRO EPC quote"
    assert by_label["Total CAPEX"].as_of == "2025-09"
    assert by_label["PPA tariff"].source == "CEB SPPA"
    # A line with no mapped material assumption (Site) stays blank — no borrowed provenance.
    assert by_label["Site"].source == "" and by_label["Site"].as_of == ""


def test_assumptions_table_renders_new_columns() -> None:
    from app.reports.renderer import render_report_html

    scenario = {
        "evidence_register": {
            "entries": {
                "capex": {
                    "source": "SINOHYDRO EPC quote",
                    "as_of": "2025-09",
                    "tier": "A",
                }
            }
        }
    }
    ctx = build_report_context(
        _case(_VALUE_DESTRUCTIVE_KPIS),
        generated_at=GENERATED_AT,
        inputs=_inputs(),
        scenario_config=scenario,
    )
    html = render_report_html(ctx)
    assert "SINOHYDRO EPC quote" in html  # source column populated from the register
    assert ">Impact<" in html  # the new Impact column header
    assert "dominant value driver" in html  # the tariff impact note


def test_manifest_values_render_left_aligned() -> None:
    from app.reports.renderer import render_report_html

    case = CaseResult(
        status="success",
        scenario_variant="lendercase",
        kpis=_VALUE_DESTRUCTIVE_KPIS,
        run_manifest={"engine_version": "15.1.0", "git_sha": "abc1234"},
    )
    ctx = build_report_context(case, generated_at=GENERATED_AT)
    html = render_report_html(ctx)
    # Manifest metadata strings are left-aligned, not numeric-right-aligned (RPT-4).
    assert "<td>engine_version</td>" in html
    assert "<td>15.1.0</td>" in html
    assert '<td class="num">15.1.0</td>' not in html


def test_malformed_register_degrades_gracefully_not_a_500() -> None:
    # A bad min_tier raises a plain ValueError inside build_evidence_report; the assumptions
    # cross-ref and the evidence section must both degrade gracefully, not crash the report.
    scenario = {"evidence_register": {"min_tier": "NOT_A_TIER"}}
    ctx = build_report_context(
        _case(_VALUE_DESTRUCTIVE_KPIS),
        generated_at=GENERATED_AT,
        inputs=_inputs(),
        scenario_config=scenario,
    )
    assert ctx.evidence is None  # _build_evidence degraded to no section
    by_label = {r.label: r for r in ctx.assumptions}
    assert by_label["Total CAPEX"].source == ""  # _evidence_lookup degraded to {}
    assert by_label["Total CAPEX"].impact  # the static impact note is still present


# --------------------------------------------------------------------------- #
# Context assembly
# --------------------------------------------------------------------------- #
def test_build_context_basic_shape() -> None:
    ctx = build_report_context(
        _case(_VALUE_DESTRUCTIVE_KPIS), generated_at=GENERATED_AT, inputs=_inputs()
    )
    assert isinstance(ctx, ReportContext)
    assert ctx.generated_at == GENERATED_AT
    assert ctx.site_name == "Dutch Bay"
    assert ctx.status == "success"
    assert ctx.scenario_variant == "lendercase"


# --------------------------------------------------------------------------- #
# Frozen-contract semantics (#608): built once, consumed read-only
# --------------------------------------------------------------------------- #
def test_report_context_is_frozen() -> None:
    ctx = build_report_context(
        _case(_VALUE_DESTRUCTIVE_KPIS), generated_at=GENERATED_AT, inputs=_inputs()
    )
    with pytest.raises(ValidationError):
        ctx.site_name = "Mutated Bay"
    # Construct-anew is the sanctioned way to derive a variant.
    variant = ctx.model_copy(update={"site_name": "Copied Bay"})
    assert variant.site_name == "Copied Bay"
    assert ctx.site_name == "Dutch Bay"


def test_verdict_is_frozen() -> None:
    verdict = build_report_context(
        _case(_VALUE_DESTRUCTIVE_KPIS), generated_at=GENERATED_AT
    ).verdict
    assert isinstance(verdict, Verdict)
    with pytest.raises(ValidationError):
        verdict.project_viable = True


def test_waterfall_row_is_frozen() -> None:
    row = WaterfallRow(
        year=3,
        cfads=10_000_000.0,
        scheduled_debt_service=8_000_000.0,
        balloon_sweep=0.0,
        cash_to_equity=2_000_000.0,
    )
    with pytest.raises(ValidationError):
        row.cfads = 0.0


def test_risk_register_projected_from_config() -> None:
    ctx = build_report_context(
        _case(_VALUE_DESTRUCTIVE_KPIS), generated_at=GENERATED_AT
    )
    assert ctx.risk_register, "the default config seeds risks"
    # Rows are faithful passthroughs with a renderable severity.
    for row in ctx.risk_register:
        assert row.category and row.risk and row.mitigation
        assert row.severity in {"low", "medium", "high"}
    assert any(r.severity == "high" for r in ctx.risk_register)


def test_risk_register_climate_category_passthrough() -> None:
    """_build_risk_register threads the TCFD climate tag onto the render row (and None stays None)."""
    cfg = ReportConfig(
        report=ReportMeta(
            title="t",
            subtitle="s",
            organization="o",
            version="1.0",
            confidentiality="c",
            disclaimer="d",
        ),
        covenants=Covenants(
            min_dscr_floor=1.2, min_dscr_target=1.3, max_balloon_pct=0.4
        ),
        kpi_table=[],
        risk_register=[
            RiskItem(
                category="Resource",
                risk="r",
                mitigation="m",
                severity="medium",
                climate_risk_category="physical",
            ),
            RiskItem(
                category="Regulatory",
                risk="r",
                mitigation="m",
                severity="medium",
                climate_risk_category="transition",
            ),
            RiskItem(category="EPC", risk="r", mitigation="m", severity="low"),
        ],
    )
    ctx = build_report_context(
        _case(_VALUE_DESTRUCTIVE_KPIS), generated_at=GENERATED_AT, config=cfg
    )
    tags = [row.climate_risk_category for row in ctx.risk_register]
    assert tags == ["physical", "transition", None]


def test_risk_register_html_renders_tcfd_tag_only_when_present() -> None:
    """The template renders a TCFD tag for a tagged risk and omits it for an untagged one."""
    from app.reports.renderer import render_report_html

    cfg = ReportConfig(
        report=ReportMeta(
            title="t",
            subtitle="s",
            organization="o",
            version="1.0",
            confidentiality="c",
            disclaimer="d",
        ),
        covenants=Covenants(
            min_dscr_floor=1.2, min_dscr_target=1.3, max_balloon_pct=0.4
        ),
        kpi_table=[],
        risk_register=[
            RiskItem(
                category="Resource",
                risk="yield",
                mitigation="m",
                severity="medium",
                climate_risk_category="physical",
            ),
            RiskItem(category="EPC", risk="overrun", mitigation="m", severity="low"),
        ],
    )
    ctx = build_report_context(
        _case(_VALUE_DESTRUCTIVE_KPIS), generated_at=GENERATED_AT, config=cfg
    )
    html = render_report_html(ctx)
    # The tagged Resource row renders a physical TCFD tag span...
    assert "TCFD: Physical" in html
    assert 'class="badge tcfd-physical"' in html
    # ...and the untagged EPC row emits no TCFD tag span at all. (The .tcfd-* CSS classes
    # always live in the <style> block, so we assert on the rendered <span>, not the class.)
    assert "TCFD: Transition" not in html
    assert 'class="badge tcfd-transition"' not in html


def test_readiness_projected_from_scenario_config() -> None:
    scenario = {
        "development_readiness": {
            "items": {
                "environmental_social": {"status": "green", "note": "ESIA done"},
                "financing": {"status": "red"},
            }
        }
    }
    ctx = build_report_context(
        _case(_VALUE_DESTRUCTIVE_KPIS),
        generated_at=GENERATED_AT,
        scenario_config=scenario,
    )
    assert {r.workstream for r in ctx.readiness} == {
        "environmental_social",
        "financing",
    }
    assert ctx.overall_readiness == "red"  # worst declared
    assert all(r.status in {"green", "amber", "red"} for r in ctx.readiness)


def test_readiness_empty_when_no_scenario_config() -> None:
    ctx = build_report_context(
        _case(_VALUE_DESTRUCTIVE_KPIS), generated_at=GENERATED_AT
    )
    assert ctx.readiness == []
    assert ctx.overall_readiness is None


def test_risk_register_empty_when_config_has_none() -> None:
    cfg = ReportConfig(
        report=ReportMeta(
            title="t",
            subtitle="s",
            organization="o",
            version="1.0",
            confidentiality="c",
            disclaimer="d",
        ),
        covenants=Covenants(
            min_dscr_floor=1.2, min_dscr_target=1.3, max_balloon_pct=0.4
        ),
        kpi_table=[],
    )  # no risk_register -> defaults to []
    ctx = build_report_context(
        _case(_VALUE_DESTRUCTIVE_KPIS), generated_at=GENERATED_AT, config=cfg
    )
    assert ctx.risk_register == []


def test_kpi_rows_formatted_in_config_order() -> None:
    ctx = build_report_context(
        _case(_VALUE_DESTRUCTIVE_KPIS), generated_at=GENERATED_AT
    )
    by_key = {row.key: row for row in ctx.kpi_rows}
    assert by_key["project_irr"].display == "4.22%"
    assert by_key["min_dscr"].display == "1.30x"
    assert by_key["project_npv"].display == "-$57,994,286"
    # Order follows the config table, not dict insertion.
    assert [r.key for r in ctx.kpi_rows][0] == "project_irr"


def test_missing_kpi_is_skipped() -> None:
    kpis = dict(_VALUE_DESTRUCTIVE_KPIS)
    del kpis["plcr"]
    ctx = build_report_context(_case(kpis), generated_at=GENERATED_AT)
    assert "plcr" not in {row.key for row in ctx.kpi_rows}


def test_verdict_value_destructive() -> None:
    ctx = build_report_context(
        _case(_VALUE_DESTRUCTIVE_KPIS), generated_at=GENERATED_AT
    )
    v: Verdict = ctx.verdict
    assert v.project_viable is False
    assert v.equity_positive is False
    assert v.dscr_covenant_met is True  # 1.30 >= 1.20 floor
    assert v.balloon_within_limit is True  # 34.67% <= 40%
    assert v.headline == "Value-destructive at the modeled assumptions."
    assert any("below the" in n for n in v.notes)


def test_verdict_bankable() -> None:
    kpis = {
        "project_irr": 0.12,
        "discount_rate_used": 0.08,
        "equity_npv": 25_000_000.0,
        "equity_irr": 0.15,
        "min_dscr": 1.55,
        "balloon_pct": 0.20,
    }
    v = build_report_context(_case(kpis), generated_at=GENERATED_AT).verdict
    assert v.project_viable and v.equity_positive and v.dscr_covenant_met
    assert v.balloon_within_limit
    assert v.headline == "Bankable at the modeled assumptions."


def test_verdict_not_bankable_on_balloon_breach() -> None:
    # Returns and DSCR all pass, but the balloon covenant breaches: the headline
    # must NOT claim "Bankable" (it would contradict the covenant table).
    kpis = {
        "project_irr": 0.12,
        "discount_rate_used": 0.08,
        "equity_npv": 25_000_000.0,
        "equity_irr": 0.15,
        "min_dscr": 1.55,
        "balloon_pct": 0.55,  # > 0.40 ceiling
    }
    v = build_report_context(_case(kpis), generated_at=GENERATED_AT).verdict
    assert v.project_viable and v.equity_positive and v.dscr_covenant_met
    assert v.balloon_within_limit is False
    assert v.headline == "Not bankable — covenant breach at the modeled assumptions."


def test_verdict_honors_engine_balloon_breach_over_report_ceiling() -> None:
    # Round-9 fix: the report must honor the engine's published balloon_covenant_breach
    # (evaluated against the SCENARIO's own covenant, e.g. 10%) and NOT re-derive "within
    # limit" against its more lenient presentation default (40%). 37.96% is BELOW the report
    # 40% ceiling but the engine flagged a breach against the scenario's 10% covenant.
    kpis = {
        "project_irr": 0.12,
        "discount_rate_used": 0.08,
        "equity_npv": 25_000_000.0,
        "equity_irr": 0.15,
        "min_dscr": 1.55,
        "balloon_pct": 0.3796,  # < 0.40 report default, but...
        "balloon_covenant_breach": 1.0,  # ...the engine flagged a breach (vs scenario 10%)
    }
    v = build_report_context(_case(kpis), generated_at=GENERATED_AT).verdict
    assert (
        v.balloon_within_limit is False
    )  # honors the engine, not the 40% report default
    assert any("BREACHES the modeled refinance-risk covenant" in n for n in v.notes)
    assert v.headline == "Not bankable — covenant breach at the modeled assumptions."


def test_verdict_falls_back_to_report_ceiling_without_engine_flag() -> None:
    # When the engine did NOT publish a breach flag, the report-config ceiling still governs.
    kpis = {
        "project_irr": 0.12,
        "discount_rate_used": 0.08,
        "equity_npv": 25_000_000.0,
        "equity_irr": 0.15,
        "min_dscr": 1.55,
        "balloon_pct": 0.3467,  # <= 0.40, no engine flag -> within limit
    }
    v = build_report_context(_case(kpis), generated_at=GENERATED_AT).verdict
    assert v.balloon_within_limit is True
    assert any("within the 40% refinance-risk ceiling" in n for n in v.notes)


def test_equity_irr_note_reflects_irr_sign_not_npv_flag() -> None:
    """Round-11 fix: the equity-IRR note's sign word must follow the IRR's OWN sign, not the
    equity-NPV value flag. A positive IRR below the hurdle (NPV<0) was falsely printed as
    'negative to sponsors'. The basecase (equity IRR ~+5.8%, below the ~12% equity hurdle,
    NPV<0) is the real-world example; the synthetic fixture below uses +2.42%. (Post the 5.9%
    FX-drift re-baseline the canonical LENDER equity IRR is itself negative, ~-0.46%.)
    """

    def note(kpis):
        v = build_report_context(_case(kpis), generated_at=GENERATED_AT).verdict
        return next(n for n in v.notes if "Equity IRR" in n)

    # positive IRR, negative NPV (the basecase reality) -> NOT "negative"
    pos_below = note(
        {
            "project_irr": 0.05,
            "discount_rate_used": 0.078,
            "equity_irr": 0.0242,
            "equity_npv": -35_000_000.0,
            "min_dscr": 1.30,
        }
    )
    assert "2.42%" in pos_below
    assert "positive but below the equity hurdle" in pos_below
    assert "negative" not in pos_below  # the bug: it used to say "negative to sponsors"

    # genuinely negative IRR -> "negative to sponsors"
    neg = note(
        {
            "project_irr": -0.03,
            "discount_rate_used": 0.078,
            "equity_irr": -0.0862,
            "equity_npv": -43_000_000.0,
            "min_dscr": 1.30,
        }
    )
    assert "negative to sponsors" in neg

    # positive IRR clearing the hurdle (NPV>0) -> "positive to sponsors"
    pos_ok = note(
        {
            "project_irr": 0.12,
            "discount_rate_used": 0.08,
            "equity_irr": 0.15,
            "equity_npv": 25_000_000.0,
            "min_dscr": 1.55,
        }
    )
    assert "positive to sponsors" in pos_ok


def test_equity_irr_note_at_exact_break_even_is_not_negative() -> None:
    """#769: at exactly equity_irr == 0.0 the note must NOT say 'negative to sponsors'.

    A break-even 0.00% return is not negative (same literal-falsehood class as the #706
    _build_ic_summary <= 0 -> < 0 fix). finance.irr / metrics can emit an exact 0.0, so the
    boundary is reachable. Committed scenarios carry a non-zero equity IRR, so this is pure
    presentation and the KPI oracle is unaffected.
    """

    def note(kpis):
        v = build_report_context(_case(kpis), generated_at=GENERATED_AT).verdict
        return next(n for n in v.notes if "Equity IRR" in n)

    break_even = note(
        {
            "project_irr": 0.05,
            "discount_rate_used": 0.078,
            "equity_irr": 0.0,
            "equity_npv": -20_000_000.0,
            "min_dscr": 1.30,
        }
    )
    assert "0.00%" in break_even
    assert "break-even to sponsors" in break_even
    assert (
        "negative" not in break_even
    )  # the #769 bug: it used to say "negative to sponsors"


def test_verdict_not_bankable_on_dscr_breach() -> None:
    # DSCR floor breached while returns are acceptable -> explicit covenant breach.
    kpis = {
        "project_irr": 0.12,
        "discount_rate_used": 0.08,
        "equity_npv": 25_000_000.0,
        "min_dscr": 1.05,  # < 1.20 floor
        "balloon_pct": 0.20,
    }
    v = build_report_context(_case(kpis), generated_at=GENERATED_AT).verdict
    assert v.dscr_covenant_met is False
    assert v.headline == "Not bankable — covenant breach at the modeled assumptions."


def test_verdict_marginal() -> None:
    # Project clears the hurdle but equity is negative -> marginal, not bankable.
    kpis = {
        "project_irr": 0.10,
        "discount_rate_used": 0.08,
        "equity_npv": -1_000_000.0,
        "min_dscr": 1.40,
        "balloon_pct": 0.30,
    }
    v = build_report_context(_case(kpis), generated_at=GENERATED_AT).verdict
    assert v.project_viable is True
    assert v.equity_positive is False
    assert v.headline == "Marginal — covenant-sensitive at the modeled assumptions."


def test_equity_positive_falls_back_to_irr_when_no_npv() -> None:
    kpis = {"project_irr": 0.10, "discount_rate_used": 0.08, "equity_irr": 0.05}
    v = build_report_context(_case(kpis), generated_at=GENERATED_AT).verdict
    assert v.equity_positive is True


def test_equity_positive_false_when_no_equity_metrics() -> None:
    kpis = {"project_irr": 0.10, "discount_rate_used": 0.08, "min_dscr": 1.4}
    v = build_report_context(_case(kpis), generated_at=GENERATED_AT).verdict
    assert v.equity_positive is False
    assert v.dscr_covenant_met is True


def test_balloon_absent_is_within_limit() -> None:
    kpis = {"project_irr": 0.10, "discount_rate_used": 0.08, "min_dscr": 1.4}
    v = build_report_context(_case(kpis), generated_at=GENERATED_AT).verdict
    assert v.balloon_within_limit is True
    assert v.dscr_covenant_met is True


def test_dscr_breach_flagged() -> None:
    kpis = {"project_irr": 0.05, "discount_rate_used": 0.08, "min_dscr": 1.05}
    v = build_report_context(_case(kpis), generated_at=GENERATED_AT).verdict
    assert v.dscr_covenant_met is False
    assert any("breaches" in n for n in v.notes)


# --------------------------------------------------------------------------- #
# Assumptions register
# --------------------------------------------------------------------------- #
def test_assumptions_from_inputs_include_location() -> None:
    ctx = build_report_context(
        _case(_VALUE_DESTRUCTIVE_KPIS), generated_at=GENERATED_AT, inputs=_inputs()
    )
    labels = [a.label for a in ctx.assumptions]
    assert "Location" in labels
    assert "Total CAPEX" in labels
    capex = next(a for a in ctx.assumptions if a.label == "Total CAPEX")
    assert capex.display == "$195,000,000"


def test_no_inputs_yields_empty_assumptions_and_variant_sitename() -> None:
    ctx = build_report_context(
        _case(_VALUE_DESTRUCTIVE_KPIS, variant="basecase"), generated_at=GENERATED_AT
    )
    assert ctx.assumptions == []
    assert ctx.site_name == "basecase"


def test_assumptions_omit_location_when_absent() -> None:
    inp = _inputs()
    inp = inp.model_copy(update={"location": None})
    ctx = build_report_context(
        _case(_VALUE_DESTRUCTIVE_KPIS), generated_at=GENERATED_AT, inputs=inp
    )
    assert "Location" not in [a.label for a in ctx.assumptions]


# --------------------------------------------------------------------------- #
# Multi-technology breakdown (ARCH-4, #476)
# --------------------------------------------------------------------------- #
_HYBRID_SCENARIO = {
    "fx": {"start_lkr_per_usd": 300.0, "annual_depr": 0.02},
    "revenue": {"tariff_lkr_per_kwh": 30.0},
    "capex": {"usd_total": 200_000_000.0},
    "opex": {"usd_per_year": 5_000_000.0},
    "generation": {
        "technologies": {
            "wind": {
                "type": "wind",
                "aep_gwh": 400.0,
                "capacity_factor": 0.34,
                "capex_usd": 150_000_000.0,
                "opex_usd_per_year": 3_500_000.0,
            },
            "solar": {
                "type": "solar",
                "aep_gwh": 100.0,
                "capacity_factor": 0.20,
                "capex_usd": 30_000_000.0,
                "opex_usd_per_year": 800_000.0,
            },
        }
    },
}
_HYBRID_KPIS = {**_VALUE_DESTRUCTIVE_KPIS, "mean_operational_cfads_usd": 20_000_000.0}


def test_multi_tech_block_populated_for_hybrid() -> None:
    ctx = build_report_context(
        _case(_HYBRID_KPIS, variant="hybrid"),
        generated_at=GENERATED_AT,
        scenario_config=_HYBRID_SCENARIO,
    )
    assert ctx.multi_tech is not None
    techs = {r.technology for r in ctx.multi_tech.rows}
    assert techs == {"wind", "solar"}
    assert ctx.multi_tech.total_aep_gwh == 500.0
    wind = next(r for r in ctx.multi_tech.rows if r.technology == "wind")
    assert wind.capex_usd == 150_000_000.0
    assert wind.opex_usd_per_year == 3_500_000.0
    assert wind.share_of_aep_pct is not None
    # Reconciliation: 200M financed, 180M attributed, 20M shared/BOP residual.
    assert ctx.multi_tech.financed_capex_usd == 200_000_000.0
    assert ctx.multi_tech.allocated_capex_usd == 180_000_000.0
    assert ctx.multi_tech.capex_residual_usd == 20_000_000.0
    assert ctx.multi_tech.capex_reconciled is True


def test_multi_tech_none_for_single_tech() -> None:
    single = {
        "fx": {"start_lkr_per_usd": 300.0, "annual_depr": 0.02},
        "generation": {
            "technologies": {
                "wind": {"type": "wind", "aep_gwh": 400.0, "capacity_factor": 0.34}
            }
        },
    }
    ctx = build_report_context(
        _case(_HYBRID_KPIS), generated_at=GENERATED_AT, scenario_config=single
    )
    assert ctx.multi_tech is None


def test_multi_tech_none_without_scenario_config() -> None:
    ctx = build_report_context(
        _case(_VALUE_DESTRUCTIVE_KPIS), generated_at=GENERATED_AT
    )
    assert ctx.multi_tech is None


def test_multi_tech_section_renders_in_html() -> None:
    """The multi-tech section renders in the HTML (Jinja step; no weasyprint needed)."""
    from app.reports.renderer import render_report_html

    ctx = build_report_context(
        _case(_HYBRID_KPIS, variant="hybrid"),
        generated_at=GENERATED_AT,
        scenario_config=_HYBRID_SCENARIO,
    )
    html = render_report_html(ctx)
    assert "Multi-Technology Breakdown" in html
    assert "wind" in html and "solar" in html

    # Single-tech omits the section entirely.
    ctx_single = build_report_context(
        _case(_VALUE_DESTRUCTIVE_KPIS), generated_at=GENERATED_AT
    )
    assert "Multi-Technology Breakdown" not in render_report_html(ctx_single)


def test_multi_tech_block_surfaces_poi_curtailment_when_configured() -> None:
    """A hybrid declaring a shared-POI limit + per-tech hourly profiles surfaces the
    curtailment disclosure (ARCH-5); committed scenarios without them omit it."""
    cfg = {
        **_HYBRID_SCENARIO,
        "generation": {
            "shared_poi": {"limit_mw": 150.0},
            "technologies": {
                "wind": {
                    "type": "wind",
                    "aep_gwh": 400.0,
                    "capacity_factor": 0.34,
                    "capex_usd": 150_000_000.0,
                    "hourly_profile_mw": [120.0, 80.0, 130.0],
                },
                "solar": {
                    "type": "solar",
                    "aep_gwh": 100.0,
                    "capacity_factor": 0.20,
                    "capex_usd": 30_000_000.0,
                    "hourly_profile_mw": [50.0, 40.0, 40.0],
                },
            },
        },
    }
    ctx = build_report_context(
        _case(_HYBRID_KPIS, variant="hybrid"),
        generated_at=GENERATED_AT,
        scenario_config=cfg,
    )
    assert ctx.multi_tech is not None
    assert ctx.multi_tech.poi_limit_mw == 150.0
    assert ctx.multi_tech.poi_curtailment_pct is not None
    assert ctx.multi_tech.poi_curtailed_energy_mwh == pytest.approx(40.0)  # 20+0+20

    # The committed-style hybrid (no POI limit / hourly profiles) omits curtailment.
    ctx_plain = build_report_context(
        _case(_HYBRID_KPIS, variant="hybrid"),
        generated_at=GENERATED_AT,
        scenario_config=_HYBRID_SCENARIO,
    )
    assert ctx_plain.multi_tech is not None
    assert ctx_plain.multi_tech.poi_curtailment_pct is None


# --------------------------------------------------------------------------- #
# Three-statement output + tie-outs (#479)
# --------------------------------------------------------------------------- #
def _annual_rows_3s(n: int = 3) -> list:
    # Enriched rows: LKR P&L + per-year USD debt columns. interest 10/8/6, service 30/28/26
    # -> principal 20 each, retiring the 60 drawn debt (debt_total 55 + IDC 5) to 0. The engine
    # CFADS columns (cf_pre_debt 40/38/36, deliberately distinct from the ~7 the P&L would
    # reconstruct) prove the waterfall reads the engine's published figure, not a reconstruction.
    interest = [10.0, 8.0, 6.0]
    service = [30.0, 28.0, 26.0]
    cf_pre_debt = [40.0, 38.0, 36.0]
    return [
        {
            "year": t + 1,
            "revenue_lkr": 1000.0,
            "opex_lkr": 200.0,
            "ebitda_lkr": 800.0,
            "total_depreciation_lkr": 500.0,
            "tax_lkr": 100.0,
            "fx_rate": 100.0,
            "interest_usd": interest[t],
            "debt_service_total": service[t],
            "balloon_resolution": 0.0,
            "cf_pre_debt": cf_pre_debt[t],
            "cf_after_debt": cf_pre_debt[t] - service[t],
        }
        for t in range(n)
    ]


_DEBT_RESULT_3S = {
    "debt_total": 55.0,
    "total_idc": 5.0,
    "balloon_residual": 0.0,
}
_SCEN_3S = {"capex": {"usd_total": 55.0}, "fx": {"start_lkr_per_usd": 100.0}}


def test_three_statement_block_populated_and_ties_out() -> None:
    ctx = build_report_context(
        _case(_VALUE_DESTRUCTIVE_KPIS, variant="hybrid"),
        generated_at=GENERATED_AT,
        scenario_config=_SCEN_3S,
        debt_result=_DEBT_RESULT_3S,
        annual_rows=_annual_rows_3s(3),
    )
    assert ctx.three_statement is not None
    ts = ctx.three_statement
    assert ts.currency == "USD"
    assert ts.tie_outs_pass is True
    assert ts.balance_sheet_balances and ts.debt_retires_to_residual
    assert len(ts.income_statement) == 3 and len(ts.balance_sheet) == 3


def test_three_statement_none_without_annual_rows() -> None:
    ctx = build_report_context(
        _case(_VALUE_DESTRUCTIVE_KPIS),
        generated_at=GENERATED_AT,
        scenario_config=_SCEN_3S,
        debt_result=_DEBT_RESULT_3S,
    )
    assert ctx.three_statement is None


def test_three_statement_section_renders_in_html() -> None:
    from app.reports.renderer import render_report_html

    ctx = build_report_context(
        _case(_VALUE_DESTRUCTIVE_KPIS, variant="hybrid"),
        generated_at=GENERATED_AT,
        scenario_config=_SCEN_3S,
        debt_result=_DEBT_RESULT_3S,
        annual_rows=_annual_rows_3s(3),
    )
    html = render_report_html(ctx)
    assert "Financial Statements" in html
    assert "All tie-outs pass" in html
    assert "Income statement" in html and "Balance sheet" in html


def _debt_result_3s_with_funding(import_levies_usd) -> dict:
    """_DEBT_RESULT_3S plus a Sources & Uses funding block (#738 footnote surface).

    ``import_levies_usd=None`` omits the key entirely (a pre-#738 engine result);
    ``0.0`` carries the disclosure key at zero (a levy-free #738 result). The two
    must render BYTE-IDENTICALLY (render-when-present).
    """
    uses: dict = {"capex_usd": 60.0, "idc_usd": 5.0, "initial_dsra_usd": 0.0}
    if import_levies_usd is not None:
        uses["import_levies_usd"] = import_levies_usd
    return {
        **_DEBT_RESULT_3S,
        "funding": {
            "fund_at_close": False,
            "dsra_target_months": 6.0,
            "initial_dsra_usd": 0.0,
            "financing_fees_in_capex_usd": 0.0,
            "sources_and_uses": {
                "uses": uses,
                "sources": {"senior_debt_usd": 60.0, "equity_usd": 5.0},
                "uses_total_usd": 65.0,
                "sources_total_usd": 65.0,
                "balanced": True,
            },
        },
    }


def test_811_removed_the_pre_levy_reconciliation_footnote() -> None:
    """#811: the #738 pre-levy reconciliation footnote is gone.

    #738 (R1) papered over a pre-levy PP&E / paid-in-equity gap with a prose
    footnote. #811 makes ``analytics.three_statement`` book the SAME levy-inclusive
    financed-capex base the debt sizing / NPV / equity / Sources & Uses use, so the
    statements reconcile in the numbers, not in prose. Even with a nonzero
    ``import_levies_usd`` in the funding block, the rendered report must NO LONGER
    carry the reconciliation footnote (its text asserted a pre-levy basis that is no
    longer how the statements are booked).
    """
    from app.reports.renderer import render_report_html

    ctx = build_report_context(
        _case(_VALUE_DESTRUCTIVE_KPIS, variant="hybrid"),
        generated_at=GENERATED_AT,
        scenario_config=_SCEN_3S,
        debt_result=_debt_result_3s_with_funding(5.0),
        annual_rows=_annual_rows_3s(3),
    )
    assert ctx.finance is not None
    assert ctx.finance.funding.import_levies_usd == pytest.approx(5.0)
    html = render_report_html(ctx)
    assert "Reconciliation note: paid-in equity above" not in html
    assert "pre-levy capex basis" not in html


def test_three_statement_levy_footnote_absent_and_identical_when_levy_free() -> None:
    """#811: with the #738 footnote removed it is absent in every report, and a
    funding block carrying ``import_levies_usd: 0.0`` renders BYTE-IDENTICALLY
    to one omitting the key entirely (the disclosure key at zero perturbs
    nothing in the document).
    """
    from app.reports.renderer import render_report_html

    def _html(import_levies_usd) -> str:
        ctx = build_report_context(
            _case(_VALUE_DESTRUCTIVE_KPIS, variant="hybrid"),
            generated_at=GENERATED_AT,
            scenario_config=_SCEN_3S,
            debt_result=_debt_result_3s_with_funding(import_levies_usd),
            annual_rows=_annual_rows_3s(3),
        )
        return render_report_html(ctx)

    html_zero = _html(0.0)
    html_absent = _html(None)
    assert "Reconciliation note: paid-in equity above" not in html_zero
    assert "pre-levy capex basis" not in html_zero
    assert html_zero == html_absent  # byte-identical rendering


def test_cashflow_waterfall_block_populated() -> None:
    ctx = build_report_context(
        _case(_VALUE_DESTRUCTIVE_KPIS, variant="hybrid"),
        generated_at=GENERATED_AT,
        scenario_config=_SCEN_3S,
        debt_result=_DEBT_RESULT_3S,
        annual_rows=_annual_rows_3s(3),
    )
    assert ctx.cashflow_waterfall is not None
    wf = ctx.cashflow_waterfall
    assert wf.currency == "USD"
    assert len(wf.rows) == 3
    # The waterfall sources the engine's published cf_pre_debt (40/38/36), NOT a P&L reconstruction.
    assert [r.cfads for r in wf.rows] == pytest.approx([40.0, 38.0, 36.0])
    # Scheduled debt service equals the engine's debt_service_total (ties to the DSCR section).
    assert [r.scheduled_debt_service for r in wf.rows] == pytest.approx(
        [30.0, 28.0, 26.0]
    )
    assert wf.total_cfads == pytest.approx(114.0)
    assert wf.total_scheduled_debt_service == pytest.approx(84.0)


def test_cashflow_waterfall_none_without_annual_rows() -> None:
    ctx = build_report_context(
        _case(_VALUE_DESTRUCTIVE_KPIS),
        generated_at=GENERATED_AT,
        scenario_config=_SCEN_3S,
        debt_result=_DEBT_RESULT_3S,
    )
    assert ctx.cashflow_waterfall is None


def test_cashflow_waterfall_section_renders_in_html() -> None:
    from app.reports.renderer import render_report_html

    ctx = build_report_context(
        _case(_VALUE_DESTRUCTIVE_KPIS, variant="hybrid"),
        generated_at=GENERATED_AT,
        scenario_config=_SCEN_3S,
        debt_result=_DEBT_RESULT_3S,
        annual_rows=_annual_rows_3s(3),
    )
    html = render_report_html(ctx)
    assert "Cash-Flow Waterfall by Payment Priority" in html
    assert "Scheduled debt service" in html
    assert "Cash to equity" in html


# --------------------------------------------------------------------------- #
# Long-term wind resource & trend section (#178 → #656) — disclose-only.
# --------------------------------------------------------------------------- #
def _trend_analysis() -> Dict[str, object]:
    """A real analyze_long_term_resource() output over a synthetic 20-yr series."""
    import numpy as np
    import pandas as pd

    from wind_resource.era5_retrieval import ERA5RequestConfig
    from wind_resource.long_term_trend import analyze_long_term_resource

    idx = pd.date_range("2005-01-01", "2024-12-31 23:00", freq="h")
    rng = np.random.default_rng(7)
    series = pd.DataFrame({"ws_150m": rng.weibull(2.5, len(idx)) * 8.0}, index=idx)
    cfg = ERA5RequestConfig(
        project_name="T",
        latitude=8.27,
        longitude=79.75,
        start_year=2005,
        end_year=2024,
        hub_height_m=150.0,
        turbine_model="iea_reference_10mw",
        num_turbines=15,
    )
    return analyze_long_term_resource(cfg, series=series)


def test_resource_trend_none_by_default() -> None:
    ctx = build_report_context(
        _case(_VALUE_DESTRUCTIVE_KPIS), generated_at=GENERATED_AT
    )
    assert ctx.resource_trend is None


def test_resource_trend_projected_from_live_analysis() -> None:
    analysis = _trend_analysis()
    ctx = build_report_context(
        _case(_VALUE_DESTRUCTIVE_KPIS),
        generated_at=GENERATED_AT,
        resource_trend=analysis,
    )
    block = ctx.resource_trend
    assert block is not None
    # Sourced verbatim from the analysis (not re-derived).
    assert block.markdown == analysis["markdown"]
    assert block.recommended_basis == analysis["recommendation"][
        "central_basis"
    ].replace("_", " ")
    # The summary table mirrors trend_summary_dataframe row-for-row.
    assert len(block.summary_rows) == len(analysis["summary_df"])
    assert any(r.metric == "Bankability basis" for r in block.summary_rows)


def test_resource_trend_section_renders_in_html() -> None:
    ctx = build_report_context(
        _case(_VALUE_DESTRUCTIVE_KPIS),
        generated_at=GENERATED_AT,
        resource_trend=_trend_analysis(),
    )
    html = render_report_html(ctx)
    assert "Long-Term Wind Resource &amp; Trend" in html
    assert "Mann-Kendall" in html
    assert "recommended forward p50 basis" in html.lower()
    # Disclose-only wording: it must state it does NOT change the committed P50.
    assert "does" in html and "not" in html and "frozen scenario P50" in html


def test_resource_trend_omitted_section_absent_from_html() -> None:
    ctx = build_report_context(
        _case(_VALUE_DESTRUCTIVE_KPIS), generated_at=GENERATED_AT
    )
    html = render_report_html(ctx)
    assert "Long-Term Wind Resource &amp; Trend" not in html


# --------------------------------------------------------------------------- #
# Project → equity IRR bridge (#621) — additive, default-off
# --------------------------------------------------------------------------- #
def _irr_bridge_run_result() -> Dict[str, object]:
    """A minimal full run result carrying a computed equity distribution (bridge input)."""
    from finance.irr import irr as _irr

    cfads = [18.0] * 10
    project_irr = _irr([-100.0] + cfads)
    annual_rows = [
        {"cfads_usd": 18.0, "interest_usd": 2.0, "effective_tax_rate": 0.3}
        for _ in range(10)
    ]
    return {
        "kpis": {"project_irr": project_irr, "equity_irr": 0.05},
        "annual_rows": annual_rows,
        "debt_result": {"construction_years": 0},
        "equity_distribution": {
            "status": "computed",
            "equity_summary": {"equity_investment_usd": 30.0},
            "equity_cashflows_usd": [-30.0] + [11.0] * 10,
        },
        "scenario_result": {"config": {"finance": {"capex_usd": 100.0}}},
    }


def test_irr_bridge_none_by_default_without_run_result() -> None:
    """Default-off: absent a run_result, the bridge section is omitted (KPI-neutral)."""
    ctx = build_report_context(
        _case(_VALUE_DESTRUCTIVE_KPIS),
        generated_at=GENERATED_AT,
        scenario_config=_SCENARIO_CFG,
        debt_result=_DEBT_RESULT,
    )
    assert ctx.irr_bridge is None


def test_irr_bridge_populated_from_run_result() -> None:
    """When a run_result with a computed equity distribution is supplied, the bridge builds."""
    ctx = build_report_context(
        _case(_VALUE_DESTRUCTIVE_KPIS),
        generated_at=GENERATED_AT,
        scenario_config=_SCENARIO_CFG,
        debt_result=_DEBT_RESULT,
        run_result=_irr_bridge_run_result(),
    )
    assert ctx.irr_bridge is not None
    bridge = ctx.irr_bridge
    assert bridge.reconciled is True
    # Legs + residual reconcile exactly to the published uplift.
    assert bridge.total_uplift is not None
    named = sum(leg.contribution for leg in bridge.legs)
    assert named + bridge.residual == pytest.approx(bridge.total_uplift, abs=1e-9)
    assert {leg.name for leg in bridge.legs} == {
        "leverage",
        "cost_of_debt",
        "tax_shield",
    }


def test_irr_bridge_none_when_equity_distribution_failed() -> None:
    """A run whose equity distribution failed yields no bridge (additive, no fabrication)."""
    run = _irr_bridge_run_result()
    run["equity_distribution"]["status"] = "failed"  # type: ignore[index]
    ctx = build_report_context(
        _case(_VALUE_DESTRUCTIVE_KPIS),
        generated_at=GENERATED_AT,
        scenario_config=_SCENARIO_CFG,
        debt_result=_DEBT_RESULT,
        run_result=run,
    )
    assert ctx.irr_bridge is None


def test_irr_bridge_section_renders_in_html() -> None:
    from app.reports.renderer import render_report_html

    ctx = build_report_context(
        _case(_VALUE_DESTRUCTIVE_KPIS, variant="lendercase"),
        generated_at=GENERATED_AT,
        scenario_config=_SCENARIO_CFG,
        debt_result=_DEBT_RESULT,
        run_result=_irr_bridge_run_result(),
    )
    html = render_report_html(ctx)
    assert (
        "Project &rarr; Equity IRR Bridge" in html
        or "Project → Equity IRR Bridge" in html
    )
    assert "Leverage" in html
    assert "Cost of debt" in html
    assert "Tax shield" in html


def test_fmt_pp_signed_percentage_points() -> None:
    assert fmt_pp(0.012) == "+1.20 pp"
    assert fmt_pp(-0.201939) == "-20.19 pp"
    assert fmt_pp(0.0) == "+0.00 pp"
    assert fmt_pp(None) == "—"


def test_733c_report_grade_stamps_declared_mode_and_is_absent_otherwise() -> None:
    """#733c: a declared run mode stamps its grade on the report; an undeclared
    mode leaves the report byte-identically ungraded (no 'Run grade' line)."""
    from app.reports.renderer import render_report_html

    def _ctx(scenario_config):
        return build_report_context(
            _case(_VALUE_DESTRUCTIVE_KPIS, variant="hybrid"),
            generated_at=GENERATED_AT,
            scenario_config=scenario_config,
        )

    # No declared mode -> no grade stamp.
    ctx_none = _ctx(_SCEN_3S)
    assert ctx_none.report_grade is None
    assert "Run grade:" not in render_report_html(ctx_none)

    # A declared lender mode -> stamped in the cover metadata.
    ctx_lender = _ctx({**_SCEN_3S, "run": {"mode": "lender"}})
    assert ctx_lender.report_grade == "lender"
    assert "Run grade: Lender" in render_report_html(ctx_lender)

    # The alias key and IC grade resolve too.
    assert _ctx({**_SCEN_3S, "run_mode": "ic"}).report_grade == "ic"
