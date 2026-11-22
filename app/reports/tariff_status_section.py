"""Tariff legal status in the lender report (#1837).

Builds the :class:`~app.reports.report_model.TariffLegalStatusBlock` for one scenario from the
shared registry (:mod:`analytics.tariff_legal_status`), and labels the site-analysis figures
that rest on a rate whose status must be shown beside it. Labelling only: no tariff value and
no KPI changes here, and nothing is a legal opinion.
"""

from __future__ import annotations

import datetime as _dt
from typing import Any, List, Mapping, Optional

from analytics.tariff_legal_status import (
    REGISTRY_PATH,
    STATUS_MISMATCH,
    STATUS_NOT_RECORDED,
    RevenueUse,
    ScenarioTariffStatus,
    TariffRegistry,
    resolve_scenario_status,
)
from app.reports.report_model import TariffLegalStatusBlock, TariffStatusRow
from app.reports.site_analysis_model import (
    STATUS_COMPLETED,
    STATUS_STALE,
    SiteAnalysesBlock,
    SiteAnalysisSection,
    SiteAnalysisTable,
)

#: The site-analysis section whose revenue bases the registry can record.
STORAGE_OPTIONS_KEY = "storage_options"
#: The figure that names the storage-options revenue basis (site_analysis_sections).
REVENUE_BASIS_FIGURE = "Revenue basis for the options"

USE_HEADLINE = "Headline revenue (tariff.lkr_per_kwh)"


def _value(rate_value: Optional[float]) -> str:
    return "n/a" if rate_value is None else f"{rate_value:,.2f} LKR/kWh"


def _row(use_text: str, use: RevenueUse) -> TariffStatusRow:
    rate = use.rate
    return TariffStatusRow(
        use=use_text,
        rate_id=use.rate_id,
        value=_value(rate.lkr_per_kwh if rate is not None else None),
        status=use.status,
        status_label=use.label,
        needs_label=use.needs_label,
        instrument=rate.instrument if rate is not None else "none recorded",
        clause=use.detail if rate is None else rate.clause,
        window=rate.window_text() if rate is not None else "none recorded",
        conditions=list(rate.conditions) if rate is not None else [],
        open_questions=list(rate.open_questions) if rate is not None else [],
    )


def _dates_checked(status: ScenarioTariffStatus) -> str:
    cod = (
        f"COD year {status.cod_year}"
        if status.cod_year is not None
        else "no COD year declared"
    )
    signing = (
        f"SPPA signing {status.signing_date.isoformat()}"
        if isinstance(status.signing_date, _dt.date)
        else "no SPPA signing date declared (ppa.signing_date)"
    )
    return f"{cod}; {signing}"


def tariff_status_block(status: ScenarioTariffStatus) -> TariffLegalStatusBlock:
    """Turn a resolved scenario status into the report block."""
    head = status.headline
    rows: List[TariffStatusRow] = [_row(USE_HEADLINE, head)]
    for basis in sorted(status.storage_options):
        rows.append(
            _row(
                f"Battery options, revenue basis {basis}", status.storage_options[basis]
            )
        )
    headline_line = f"Revenue rests on: {head.label}. {head.detail}"
    if head.rate is not None and head.status != STATUS_MISMATCH:
        headline_line = (
            f"Revenue rests on {_value(head.rate.lkr_per_kwh)}: {head.label} "
            f"({head.rate.instrument}; effective {head.rate.window_text()})."
        )
    return TariffLegalStatusBlock(
        recorded=status.recorded,
        headline_line=headline_line,
        headline_status=head.status,
        headline_status_label=head.label,
        headline_needs_label=head.needs_label,
        rows=rows,
        window_flags=list(status.window_flags),
        dates_checked=_dates_checked(status),
        registry=REGISTRY_PATH.as_posix(),
    )


def build_tariff_status(
    scenario: Mapping[str, Any],
    scenario_name: str,
    registry: Optional[TariffRegistry] = None,
) -> tuple[ScenarioTariffStatus, TariffLegalStatusBlock]:
    """Resolve the scenario's tariff status and build its report block."""
    status = resolve_scenario_status(scenario, scenario_name, registry)
    return status, tariff_status_block(status)


def _label_text(use: RevenueUse) -> str:
    return f"{use.label.upper()}: {use.detail}"


def _labelled_storage_section(
    section: SiteAnalysisSection, status: ScenarioTariffStatus
) -> SiteAnalysisSection:
    basis: Optional[str] = None
    for name, value in section.figures:
        if name == REVENUE_BASIS_FIGURE:
            basis = value
    if basis is None:
        return section
    use = status.storage_label(basis) or RevenueUse(
        use=f"storage_options.{basis}",
        rate_id=None,
        status=STATUS_NOT_RECORDED,
        detail=(
            f"no legal status is recorded for the revenue basis {basis} of this scenario "
            f"in {REGISTRY_PATH.as_posix()}"
        ),
    )
    if not use.needs_label:
        return section
    tag = f"[{use.label}]"
    figures = [
        (name, f"{value} {tag}" if name == REVENUE_BASIS_FIGURE else value)
        for name, value in section.figures
    ]
    tables = [
        SiteAnalysisTable(caption=f"{t.caption} {tag}", columns=t.columns, rows=t.rows)
        for t in section.tables
    ]
    labels = [f"Tariff legal status. {_label_text(use)}", *section.labels]
    return section.model_copy(
        update={"figures": figures, "tables": tables, "labels": labels}
    )


def label_site_analyses(
    block: Optional[SiteAnalysesBlock], status: ScenarioTariffStatus
) -> Optional[SiteAnalysesBlock]:
    """Print the rate status beside every site-analysis figure that rests on a labelled rate.

    Only the storage-options section prices a rate today. Its revenue-basis figure and its
    tables carry the status in brackets, and the section's first label quotes the rate's
    instrument and clause. A section that did not complete is left as it is.
    """
    if block is None:
        return None
    sections = [
        (
            _labelled_storage_section(s, status)
            if s.key == STORAGE_OPTIONS_KEY
            and s.status in (STATUS_COMPLETED, STATUS_STALE)
            else s
        )
        for s in block.sections
    ]
    return block.model_copy(update={"sections": sections})


__all__ = [
    "REVENUE_BASIS_FIGURE",
    "STORAGE_OPTIONS_KEY",
    "build_tariff_status",
    "label_site_analyses",
    "tariff_status_block",
]
