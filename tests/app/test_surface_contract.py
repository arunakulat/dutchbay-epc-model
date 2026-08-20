"""#844 — pin the *result-surfacing* contract the wizard client consumes (#788 P1).

The frontend stack (#843, HTMX vs SPA) is an undecided user gate, so #844 ships only the
server-side contract: the typed :class:`app.api.surface.CaseSurface` payload (KPI cards +
tornado/global-SA charts + capital-risk headline + artifact links) and the workbook/report
download routes. These tests PIN the response SHAPE (the frozen public field sets and the
concrete projected values), not a bare ``200`` — a breaking change to the surface fails here,
so ``API_CONTRACT_VERSION`` must be bumped deliberately alongside it.

A real finance run is projected once (``build_case_surface``) to assert the KPI cards carry
genuine values while typed, deterministic sensitivity blocks exercise the chart projection. The
capital-risk projector (heavy MC, out-of-band and absent from the synchronous path) is exercised
with a hand-built block so its mapping is covered on real data, not by construction.
"""

from __future__ import annotations

from typing import Any, Dict

import pytest
from pydantic import ValidationError

from app.api.responses import API_CONTRACT_VERSION, CaseResult
from app.api.surface import (
    ArtifactLinks,
    CapitalRiskMetric,
    CapitalRiskSurface,
    CaseSurface,
    GlobalSaBar,
    GlobalSaChart,
    KpiCard,
    TornadoBar,
    TornadoChart,
    _project_capital_risk,
    _project_global_sa,
    _project_tornado,
)
from app.reports.report_model import CapitalRiskBlock, CapitalRiskMetricRow
from app.services.report_global_sa import GlobalSABlock, GlobalSADriver
from app.services.report_tornado import TornadoBlock, TornadoRow


def _valid_kwargs(**overrides: Any) -> Dict[str, Any]:
    """The same reconciling lender-case inputs used across the API tests."""
    base: Dict[str, Any] = {
        "site_name": "DutchBay",
        "capacity_mw": 159.6,
        "capacity_factor": 0.332,
        "project_life_years": 20,
        "ppa_price_lkr_per_kwh": 20.30,
        "ppa_term_years": 20,
        "capex_total_usd": 159_600_000.0,
        "opex_annual_usd": 5_000_000.0,
        "fx_start_lkr_per_usd": 333.79,
    }
    base.update(overrides)
    return base


# --------------------------------------------------------------------------- #
# Frozen public field sets — the CONTRACT. Changing any of these is a contract
# change: bump API_CONTRACT_VERSION and the matching assertion together.
# --------------------------------------------------------------------------- #
def test_case_surface_public_field_set_is_frozen() -> None:
    assert set(CaseSurface.model_fields) == {
        "status",
        "scenario_variant",
        "site_name",
        "report_grade",
        "generated_at",
        "kpi_cards",
        "tornado",
        "global_sa_morris",
        "global_sa_pawn",
        "capital_risk",
        "artifacts",
        "contract_version",
    }


def test_kpi_card_field_set_is_frozen() -> None:
    assert set(KpiCard.model_fields) == {"key", "label", "value", "display"}


def test_tornado_field_sets_are_frozen() -> None:
    assert set(TornadoChart.model_fields) == {"metric", "bars"}
    assert set(TornadoBar.model_fields) == {
        "label",
        "base",
        "low_case",
        "high_case",
        "impact_abs",
    }


def test_global_sa_field_sets_are_frozen() -> None:
    assert set(GlobalSaChart.model_fields) == {"method", "metric", "n_runs", "bars"}
    assert set(GlobalSaBar.model_fields) == {
        "name",
        "mu_star",
        "sigma",
        "median_ks",
        "ks_cv",
    }


def test_capital_risk_field_sets_are_frozen() -> None:
    assert set(CapitalRiskSurface.model_fields) == {
        "scenario",
        "model_version",
        "method",
        "n_trials",
        "dscr_breach_probability",
        "llcr_breach_probability",
        "plcr_breach_probability",
        "dscr_floor",
        "llcr_floor",
        "plcr_floor",
        "probability_below_hurdle",
        "target_equity_irr",
        "metrics",
        "npv_distribution_filename",
    }
    assert set(CapitalRiskMetric.model_fields) == {
        "metric",
        "unit",
        "mean",
        "var",
        "cvar",
        "var_label",
        "cvar_label",
    }


def test_artifact_links_are_the_download_routes() -> None:
    """The artifact links are constants (the download endpoints), not per-run URLs."""
    links = ArtifactLinks()
    assert links.report_html == "/v1/cases/report.html"
    assert links.report_pdf == "/v1/cases/report.pdf"
    assert links.workbook_xlsx == "/v1/cases/report.xlsx"


def test_surface_models_are_frozen() -> None:
    """Every surface model is immutable (frozen) — a projected payload cannot be mutated."""
    card = KpiCard(key="project_irr", label="Project IRR", value=0.01, display="1.00%")
    with pytest.raises(ValidationError):
        card.value = 0.02  # type: ignore[misc]


def test_case_surface_stamps_the_contract_version() -> None:
    surface = CaseSurface(
        status="success",
        scenario_variant="lendercase",
        site_name="DutchBay",
        generated_at="2026-07-06T00:00:00+00:00",
        kpi_cards=[],
    )
    assert surface.contract_version == API_CONTRACT_VERSION


# --------------------------------------------------------------------------- #
# Projection helpers — pure re-shaping, None-degrades-to-None (CASPER).
# --------------------------------------------------------------------------- #
def test_project_tornado_maps_rows_to_bars() -> None:
    block = TornadoBlock(
        metric="project_irr",
        rows=[
            TornadoRow(
                label="Tariff",
                base=0.014,
                low_case=-0.01,
                high_case=0.04,
                impact_abs=0.05,
            ),
            TornadoRow(label="CAPEX", impact_abs=0.02),
        ],
    )
    chart = _project_tornado(block)
    assert isinstance(chart, TornadoChart)
    assert chart.metric == "project_irr"
    assert [b.label for b in chart.bars] == ["Tariff", "CAPEX"]
    # The widest-swing-first ordering the report builder applied is preserved verbatim.
    assert chart.bars[0].impact_abs == 0.05
    assert chart.bars[0].low_case == -0.01
    assert chart.bars[1].base is None  # optional fields pass through unset


def test_project_tornado_none_stays_none() -> None:
    assert _project_tornado(None) is None


def test_project_global_sa_maps_morris_and_pawn_indices() -> None:
    block = GlobalSABlock(
        method="morris",
        metric="project_irr",
        n_runs=112,
        drivers=[
            GlobalSADriver(name="tariff", mu_star=0.3, sigma=0.1),
            GlobalSADriver(name="fx", median_ks=0.42, ks_cv=0.2),
        ],
    )
    chart = _project_global_sa(block)
    assert isinstance(chart, GlobalSaChart)
    assert chart.method == "morris"
    assert chart.n_runs == 112
    assert chart.bars[0].mu_star == 0.3
    assert chart.bars[0].sigma == 0.1
    assert chart.bars[1].median_ks == 0.42
    assert chart.bars[1].ks_cv == 0.2


def test_project_global_sa_none_stays_none() -> None:
    assert _project_global_sa(None) is None


def _capital_risk_block() -> CapitalRiskBlock:
    return CapitalRiskBlock(
        scenario="lendercase",
        model_version="v15.3.0",
        method="lhs sampling, rank correlation",
        n_trials=1000,
        dscr_breach_probability=0.12,
        llcr_breach_probability=0.03,
        plcr_breach_probability=0.05,
        dscr_floor=1.20,
        llcr_floor=1.10,
        plcr_floor=1.10,
        probability_below_hurdle=0.61,
        target_equity_irr=0.15,
        metrics=[
            CapitalRiskMetricRow(
                metric="equity_irr",
                unit="pct",
                mean=-0.05,
                var=-0.12,
                cvar=-0.18,
                var_label="VaR(95%)",
                cvar_label="CVaR/ES(95%)",
            )
        ],
        npv_distribution_filename="npv_dist.png",
        npv_distribution_img="data:image/png;base64,AAAA",
    )


def test_project_capital_risk_maps_headline_and_drops_embedded_image() -> None:
    surface = _project_capital_risk(_capital_risk_block())
    assert isinstance(surface, CapitalRiskSurface)
    assert surface.n_trials == 1000
    assert surface.dscr_breach_probability == 0.12
    assert surface.probability_below_hurdle == 0.61
    assert surface.metrics[0].metric == "equity_irr"
    assert surface.metrics[0].cvar == -0.18
    # The base64 chart image is intentionally NOT part of the JSON surface (linked by name).
    assert surface.npv_distribution_filename == "npv_dist.png"
    assert "npv_distribution_img" not in CapitalRiskSurface.model_fields


def test_project_capital_risk_none_stays_none() -> None:
    assert _project_capital_risk(None) is None


# --------------------------------------------------------------------------- #
# End-to-end: a real run projects into the pinned surface shape with genuine values.
# --------------------------------------------------------------------------- #
def test_build_case_surface_projects_a_real_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.api.main as api_main
    from app.api.main import build_case_surface
    from app.models.inputs import WindFarmInputs
    from app.reports.report_orchestration import (
        ORDINARY_REPORT_SENSITIVITY_PROFILE,
        compute_report_sensitivity,
    )

    # This response-projection test keeps the canonical finance run live and patches only the
    # typed report-sensitivity orchestration boundary. The production sensitivity matrix is
    # qualified once in the dedicated TEST-04 lane; rerunning it here would duplicate the same
    # model evaluations without adding surface-contract assurance.
    sensitivity = compute_report_sensitivity(
        WindFarmInputs(**_valid_kwargs()).to_scenario_config(),
        profile=ORDINARY_REPORT_SENSITIVITY_PROFILE,
        tornado_computer=lambda _scenario: TornadoBlock(
            metric="project_irr",
            rows=[TornadoRow(label="Tariff", impact_abs=0.05)],
        ),
        morris_computer=lambda _scenario, **_kwargs: GlobalSABlock(
            method="morris",
            metric="project_irr",
            n_runs=28,
            drivers=[GlobalSADriver(name="tariff", mu_star=0.3, sigma=0.1)],
        ),
        pawn_computer=lambda _scenario, **_kwargs: GlobalSABlock(
            method="pawn",
            metric="project_irr",
            n_runs=128,
            drivers=[GlobalSADriver(name="tariff", median_ks=0.42, ks_cv=0.2)],
        ),
    )
    monkeypatch.setattr(
        api_main,
        "compute_report_sensitivity",
        lambda _scenario: sensitivity,
    )

    surface = build_case_surface(WindFarmInputs(**_valid_kwargs()))
    assert isinstance(surface, CaseSurface)
    assert surface.status == "success"
    assert surface.scenario_variant == "lendercase"
    assert surface.site_name == "DutchBay"
    assert surface.contract_version == API_CONTRACT_VERSION

    # KPI cards carry the lender headlines, each with a raw value AND the report's own
    # formatted display string (so a client renders numbers identical to the PDF).
    card_keys = {c.key for c in surface.kpi_cards}
    assert {"project_irr", "equity_irr", "min_dscr"} <= card_keys
    project_card = next(c for c in surface.kpi_cards if c.key == "project_irr")
    assert isinstance(project_card.value, float)
    assert project_card.display.endswith("%")  # IRR formatted as a percentage
    min_dscr_card = next(c for c in surface.kpi_cards if c.key == "min_dscr")
    assert min_dscr_card.display.endswith("x")  # DSCR formatted as a multiple

    # The supplementary charts computed on the synchronous path are present and typed.
    assert surface.tornado is not None
    assert surface.tornado.metric == "project_irr"
    assert len(surface.tornado.bars) >= 1
    assert surface.global_sa_morris is not None
    assert surface.global_sa_morris.method == "morris"
    assert surface.global_sa_pawn is not None
    assert surface.global_sa_pawn.method == "pawn"

    # Capital-risk (heavy MC) is out-of-band and absent from the synchronous path — the
    # surface degrades to None exactly as the report omits the section (CASPER).
    assert surface.capital_risk is None

    # The artifact links name the concrete download routes.
    assert surface.artifacts.workbook_xlsx == "/v1/cases/report.xlsx"


# --------------------------------------------------------------------------- #
# HTTP wiring: the surface + download routes are ROUTED and auth-gated.
# --------------------------------------------------------------------------- #
def test_surface_and_download_routes_are_registered() -> None:
    from app.api.main import app

    spec_paths = set(app.openapi()["paths"])
    assert "/v1/cases/surface" in spec_paths
    assert "/v1/cases/report.xlsx" in spec_paths


def test_surface_and_workbook_routes_require_auth() -> None:
    """Both new routes are compute reads behind the auth gate: no token → 401, never 404."""
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from app.api.main import app

    client = TestClient(app)  # no auth override -> no bearer token presented
    for path in ("/v1/cases/surface", "/v1/cases/report.xlsx"):
        resp = client.post(path, json=_valid_kwargs())
        assert resp.status_code == 401, f"{path} -> {resp.status_code} (expected 401)"


def _canned_pipeline_result() -> Dict[str, Any]:
    """A minimal canonical-shaped pipeline result to stand in for a real engine run.

    Carries only the keys the two projection paths read — the numeric lender ``kpis`` the
    workbook's ``frames_from_pipeline_result`` and the report's KPI table consume, plus the
    manifest — so the endpoints exercise their REAL projection/emission on canned compute.
    The remaining pipeline sections default to empty in the consumers, which is enough for the
    workbook to serialise a valid (if sparse) .xlsx and for the KPI cards to render.
    """
    return {
        "status": "success",
        "kpis": {
            "project_irr": 0.014551597740253388,
            "equity_irr": -0.05841298678542661,
            "project_npv": -79_273_514.0,
            "min_dscr": 1.285740985294611,
            "discount_rate_used": 0.09,
        },
        "annual_rows": [],
        "debt_result": {},
        "scenario_result": {},
        "run_manifest": {"commit": "abc123"},
    }


def test_workbook_download_streams_a_real_xlsx(monkeypatch: pytest.MonkeyPatch) -> None:
    """The workbook route returns a real .xlsx (ZIP magic bytes + xlsx content-type) as an
    attachment — proving it streams the existing executive-workbook artifact, not a stub.

    The ~30s executive-case compute (``run_finance_case``) is the intermittent CI 504 here, so
    it is stubbed with a canned canonical-shaped result and the REAL executive-workbook emitter
    runs on it — the asserted PK-magic bytes, xlsx content-type, and attachment disposition are
    all produced by the real endpoint/emitter, not fabricated, so the wire contract is still
    verified truthfully (only the finance recompute is skipped). The full real projection stays
    covered by ``test_build_case_surface_projects_a_real_run``.
    """
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    import app.api.main as api_main
    from app.api.auth import get_current_subject
    from app.api.main import app

    monkeypatch.setattr(
        api_main, "run_finance_case", lambda _scenario: _canned_pipeline_result()
    )
    app.dependency_overrides[get_current_subject] = lambda: "smoke-user"
    try:
        client = TestClient(app)
        resp = client.post("/v1/cases/report.xlsx", json=_valid_kwargs())
        assert resp.status_code == 200
        assert resp.content[:2] == b"PK"  # ZIP local-file-header magic (xlsx is a zip)
        assert (
            resp.headers["content-type"]
            == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        assert "attachment" in resp.headers["content-disposition"]
        assert "lendercase" in resp.headers["content-disposition"]
    finally:
        app.dependency_overrides.clear()


def test_surface_endpoint_returns_the_pinned_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End-to-end over HTTP: the /v1/cases/surface JSON has exactly the frozen top-level keys and
    a KPI-card list of the pinned per-card shape — pins the wire contract, not a bare 200.

    The ~30s executive-case compute (``_build_report_context`` → ``run_finance_case`` + the SA
    sweeps) is the intermittent CI 504 here, so it is stubbed with a canned
    :class:`~app.reports.report_model.ReportContext` built (cheaply, no engine run) from a
    canonical-shaped result. The REAL ``build_case_surface`` projection
    (``CaseSurface.from_report_context``) and the endpoint's ``response_model`` serialisation
    still run, so the asserted frozen key set, ``success`` status, contract version, KPI-card
    shape, and artifact links are produced by the real code path — not a hand-built dict that
    trivially matches. Only the finance recompute is skipped; the full real projection stays
    covered by ``test_build_case_surface_projects_a_real_run``.
    """
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    import app.api.main as api_main
    from app.api.auth import get_current_subject
    from app.api.main import app
    from app.reports.report_model import build_report_context

    def _canned_context(inputs: Any) -> Any:
        case_result = CaseResult.from_pipeline_result(
            _canned_pipeline_result(), scenario_variant=inputs.scenario_variant
        )
        return build_report_context(
            case_result,
            generated_at="2026-07-06T00:00:00+00:00",
            inputs=inputs,
        )

    monkeypatch.setattr(api_main, "_build_report_context", _canned_context)
    app.dependency_overrides[get_current_subject] = lambda: "smoke-user"
    try:
        client = TestClient(app)
        resp = client.post("/v1/cases/surface", json=_valid_kwargs())
        assert resp.status_code == 200
        body = resp.json()
        assert set(body) == set(CaseSurface.model_fields)
        assert body["status"] == "success"
        assert body["contract_version"] == API_CONTRACT_VERSION
        assert body["kpi_cards"], "expected at least one KPI card"
        assert set(body["kpi_cards"][0]) == set(KpiCard.model_fields)
        assert body["artifacts"] == {
            "report_html": "/v1/cases/report.html",
            "report_pdf": "/v1/cases/report.pdf",
            "workbook_xlsx": "/v1/cases/report.xlsx",
        }
    finally:
        app.dependency_overrides.clear()
