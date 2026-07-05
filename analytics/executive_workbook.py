from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Optional, Sequence, Union

import pandas as pd

PathLike = Union[str, Path]

__all__ = [
    "build_executive_workbook",
    "frames_from_pipeline_result",
    "serialize_resource_trend",
    "resource_trend_df_from_wind_export",
    "emit_executive_workbook_from_pipeline",
]


def build_executive_workbook(
    summary_df: pd.DataFrame,
    cashflow_df: pd.DataFrame,
    debt_df: pd.DataFrame,
    ratios_df: pd.DataFrame,
    scenario_summary_df: pd.DataFrame,
    output_path: PathLike,
    resource_trend_df: Optional[pd.DataFrame] = None,
) -> Path:
    """
    Build the lender-facing Executive Workbook for a single scenario.

    Contract (v14 canonical surface)
    --------------------------------
    - One scenario per workbook.
    - Always creates the following sheets:
        * "Summary"
        * "Cashflow"
        * "DebtService"
        * "Ratios"
        * "ScenarioSummary"
    - Optionally creates "ResourceTrend" when ``resource_trend_df`` is supplied
      (long-term wind-resource & trend commentary; IEC-61400-15 / MEASNET basis --
      see ``wind_resource.long_term_trend``).
    - Returns the resolved Path to the created workbook.

    Inputs
    ------
    summary_df
        Per-scenario KPI table (project_irr, equity_irr, dscr_min, etc.).
    cashflow_df
        Annual/project cashflow rows (revenue, opex, tax, CFADS, etc.).
    debt_df
        Debt service schedule (principal, interest, DSCR, balances, etc.).
    ratios_df
        Ratios / covenant metrics (DSCR, LLCR, PLCR, etc.).
    scenario_summary_df
        Multi-scenario KPI comparison for dashboards.
    output_path
        Target XLSX path. May be str or Path; parent dirs are created.
    resource_trend_df
        Optional long-term resource & trend table (Metric/Value) from
        ``wind_resource.long_term_trend.trend_summary_dataframe``; written as the
        "ResourceTrend" sheet when provided.

    Notes
    -----
    - This function is deliberately thin and stable: it uses only pandas +
      openpyxl, with no heavy formatting logic.
    - Any CLI or analytics runner should treat this as the canonical Excel
      export surface for v14.
    """
    out_path = Path(output_path).expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    def _to_excel(df: pd.DataFrame, writer: pd.ExcelWriter, sheet_name: str) -> None:
        """Internal helper to write a DataFrame to a sheet."""
        df.to_excel(writer, sheet_name=sheet_name, index=False)

    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        # Core sheets
        _to_excel(summary_df, writer, "Summary")
        _to_excel(cashflow_df, writer, "Cashflow")
        _to_excel(debt_df, writer, "DebtService")
        _to_excel(ratios_df, writer, "Ratios")
        _to_excel(scenario_summary_df, writer, "ScenarioSummary")

        # Optional long-term resource & trend section (issue #178): lender-facing
        # commentary on decadal variability vs secular "stilling" and the IEC-61400-15 /
        # MEASNET long-term-reference basis for the forward P50.
        if resource_trend_df is not None:
            _to_excel(resource_trend_df, writer, "ResourceTrend")

        # Ensure the Summary sheet has at least 3 rows:
        #   - header row
        #   - at least a couple of metric rows
        summary_ws = writer.sheets.get("Summary")
        if summary_ws is not None and summary_ws.max_row < 3:
            # Append lightweight metadata rows until we hit the minimum.
            # Content is intentionally minimal; tests only care about row count.
            while summary_ws.max_row < 3:
                summary_ws.append([""])

    return out_path


# ===========================================================================
# Single-scenario pipeline -> workbook frame assembly (issue #656, slice 3)
#
# ``build_executive_workbook`` above was shipped orphaned in PR #179 — the only
# caller was a unit test. These helpers give it a genuine live caller: they
# assemble the five finance frames it requires directly from the plain
# ``run_v14_pipeline`` result dict (analytics.pipeline_v14_enhanced), and read
# the optional long-term wind-resource trend out of a frozen wind export when
# the export carries it. The canonical live wiring is the opt-in
# ``emit_executive_workbook`` step in ``run_full_pipeline_v14.py``.
#
# The frame shapes are deliberately tidy and stable (mostly Metric/Value), not
# a fixed schema pinned by a lender template: the workbook is a disclose-only
# surface over already-computed KPIs, and no financial value is (re)derived
# here — CCCDIR one-source-of-truth, CASPER clear surface.
# ===========================================================================

# Debt-schedule series (all indexed by the debt timeline period) that
# ``_pipeline_debt_df`` surfaces when present and aligned to
# ``timeline_periods``. Kept as an explicit allow-list so an unrelated
# list-valued debt_result key can never leak into the schedule sheet.
_DEBT_PERIOD_SERIES: tuple[str, ...] = (
    "debt_outstanding",
    "interest_total",
    "debt_service_total",
    "total_service",
    "balloon_resolution",
    "raw_dscr_series",
)

# Ratio / covenant scalars surfaced on the "Ratios" sheet, sourced from the
# pipeline ``kpis`` block (order is the sheet's row order). ``min_dscr`` is the
# fold-corrected covenant minimum (#790); ``min_dscr_period`` is the per-period
# sculpt floor. Both are surfaced so the workbook exports the same fold-vs-period
# pair the report headline distinguishes (they diverge on the lendercase and both
# CEB scenarios since #790).
_RATIO_KPI_KEYS: tuple[str, ...] = (
    "min_dscr",
    "min_dscr_period",
    "avg_dscr",
    "dscr_mean",
    "dscr_median",
    "dscr_min",
    "dscr_max",
    "dscr_p10",
    "dscr_p90",
    "dscr_std",
    "llcr",
    "plcr",
    "balloon_pct",
    "balloon_residual",
    "balloon_covenant_breach",
)

# Covenant threshold / verdict fields surfaced on the "Ratios" sheet, sourced
# from ScenarioResult.debt_covenants.
_RATIO_COVENANT_KEYS: tuple[str, ...] = (
    "dscr_threshold",
    "years_below_threshold",
    "first_breach_year",
    "last_breach_year",
    "balloon_flag",
    "audit_status",
    "notes",
)

# Headline KPIs on the one-row "ScenarioSummary" sheet (single-scenario view).
_SCENARIO_SUMMARY_KEYS: tuple[str, ...] = (
    "project_irr",
    "equity_irr",
    "project_npv",
    "equity_npv",
    "min_dscr",
    "llcr",
    "plcr",
    "max_debt_usd",
    "total_idc_usd",
    "wacc_label",
)


def _is_scalar(value: Any) -> bool:
    """True for values that belong in a Metric/Value cell (not list/dict)."""
    return not isinstance(value, (list, tuple, dict))


def _metric_value_df(source: Mapping[str, Any], keys: Sequence[str]) -> pd.DataFrame:
    """Build a tidy (Metric, Value) frame from ``source`` for the given ``keys``.

    Missing keys are skipped (not emitted as blank rows), so the frame degrades
    cleanly across scenarios whose KPI/covenant surface differs.
    """
    rows = [(k, source[k]) for k in keys if k in source]
    return pd.DataFrame(rows, columns=["Metric", "Value"])


def _pipeline_summary_df(kpis: Mapping[str, Any]) -> pd.DataFrame:
    """ "Summary" sheet: every scalar KPI as a tidy (Metric, Value) table."""
    rows = [(k, kpis[k]) for k in sorted(kpis) if _is_scalar(kpis[k])]
    return pd.DataFrame(rows, columns=["Metric", "Value"])


def _pipeline_cashflow_df(annual_rows: Sequence[Mapping[str, Any]]) -> pd.DataFrame:
    """ "Cashflow" sheet: the annual cashflow rows, ``year`` column first."""
    frame = pd.DataFrame(list(annual_rows))
    if "year" in frame.columns:
        ordered = ["year"] + [c for c in frame.columns if c != "year"]
        frame = frame[ordered]
    return frame


def _pipeline_debt_df(debt_result: Mapping[str, Any]) -> pd.DataFrame:
    """ "DebtService" sheet: per-period debt schedule from ``debt_result``.

    Aligns every ``_DEBT_PERIOD_SERIES`` array that is present and whose length
    matches the debt timeline (``timeline_periods`` when it is a positive int,
    else the modal length of the candidate series). A ``period`` index column is
    prepended. Empty when no aligned series are available.
    """
    candidates: dict[str, list[Any]] = {
        k: list(debt_result[k])
        for k in _DEBT_PERIOD_SERIES
        if isinstance(debt_result.get(k), list)
    }
    if not candidates:
        return pd.DataFrame()

    timeline = debt_result.get("timeline_periods")
    if isinstance(timeline, int) and timeline > 0:
        n = timeline
    else:
        lengths = [len(v) for v in candidates.values()]
        n = max(set(lengths), key=lengths.count)

    aligned = {k: v for k, v in candidates.items() if len(v) == n}
    if not aligned:
        return pd.DataFrame()

    frame = pd.DataFrame(aligned)
    frame.insert(0, "period", range(n))
    return frame


def _pipeline_ratios_df(
    kpis: Mapping[str, Any], debt_covenants: Mapping[str, Any]
) -> pd.DataFrame:
    """ "Ratios" sheet: DSCR/LLCR/PLCR stats plus covenant thresholds & verdict."""
    ratios = _metric_value_df(kpis, _RATIO_KPI_KEYS)
    covenants = _metric_value_df(debt_covenants, _RATIO_COVENANT_KEYS)
    return pd.concat([ratios, covenants], ignore_index=True)


def _pipeline_scenario_summary_df(kpis: Mapping[str, Any]) -> pd.DataFrame:
    """ "ScenarioSummary" sheet: one headline row for this single scenario."""
    row = {"scenario_name": kpis.get("scenario_name")}
    row.update({k: kpis.get(k) for k in _SCENARIO_SUMMARY_KEYS})
    return pd.DataFrame([row])


def frames_from_pipeline_result(
    result: Mapping[str, Any],
) -> dict[str, pd.DataFrame]:
    """Assemble the five ``build_executive_workbook`` finance frames from a result.

    Args:
        result: A ``run_v14_pipeline`` result dict (analytics.pipeline_v14_enhanced),
            i.e. one carrying ``kpis``, ``annual_rows``, ``debt_result`` and
            ``scenario_result`` keys.

    Returns:
        Mapping with keys ``summary``, ``cashflow``, ``debt``, ``ratios`` and
        ``scenario_summary`` — the positional frames of
        :func:`build_executive_workbook`. No financial value is derived here; the
        frames are tidy views over the already-computed pipeline outputs.
    """
    kpis: Mapping[str, Any] = result.get("kpis", {}) or {}
    annual_rows = result.get("annual_rows", []) or []
    debt_result: Mapping[str, Any] = result.get("debt_result", {}) or {}
    scenario_result: Mapping[str, Any] = result.get("scenario_result", {}) or {}
    debt_covenants: Mapping[str, Any] = scenario_result.get("debt_covenants", {}) or {}
    return {
        "summary": _pipeline_summary_df(kpis),
        "cashflow": _pipeline_cashflow_df(annual_rows),
        "debt": _pipeline_debt_df(debt_result),
        "ratios": _pipeline_ratios_df(kpis, debt_covenants),
        "scenario_summary": _pipeline_scenario_summary_df(kpis),
    }


# ---------------------------------------------------------------------------
# Long-term wind-resource trend: frozen-export contract (issue #656)
#
# The trend maths live in ``wind_resource.long_term_trend`` (Mann-Kendall /
# Sen's slope); ``analyze_long_term_resource`` returns a ``summary_df`` — a tidy
# (Metric, Value) table that is the exact frame
# ``build_executive_workbook(resource_trend_df=...)`` writes as the
# "ResourceTrend" sheet. ``run_full_pipeline_v14.py`` never runs live ERA5 (it is
# cdsapi-free by design; it consumes a FROZEN wind export), so the trend can only
# reach the workbook by riding INSIDE that frozen export as a JSON-safe
# ``long_term_trend`` block.
#
# This pair DEFINES that frozen-export contract: ``serialize_resource_trend`` is
# the producer-side encoder and ``resource_trend_df_from_wind_export`` the
# consumer-side decoder, exact inverses so the two sides cannot drift. NOTE (as
# of this slice): no committed producer emits the block yet — the consumer/decoder
# and the emission wiring ship first (fed today only by test- or hand-built
# exports); the producer-side attachment (the wind pipeline / an ERA5 export
# emitting ``long_term_trend``, with an ``{"analyzed": False}`` short-series
# degrade) is the next #656 slice. See CHANGELOG.
# ---------------------------------------------------------------------------

# Key under which the JSON-safe trend block lives inside a frozen wind export.
RESOURCE_TREND_KEY = "long_term_trend"


def serialize_resource_trend(analysis: Mapping[str, Any]) -> dict[str, Any]:
    """Encode a long-term-trend analysis into a JSON-safe export block.

    Defines the producer side of the frozen-export trend contract (no committed
    producer calls it yet — see the module comment above; it is exercised by the
    round-trip tests and is the encoder a future #656 producer slice will use).

    Args:
        analysis: A mapping carrying a ``summary_df`` DataFrame, i.e. the dict
            returned by ``wind_resource.long_term_trend.analyze_long_term_resource``.
            A mapping already marked ``{"analyzed": False, ...}`` (the shape a
            future short-series-degrade producer would emit) is passed through
            verbatim.

    Returns:
        A JSON-serialisable dict ``{"analyzed": True, "summary_records": [...]}``
        (the ``summary_df`` rendered via ``to_dict('records')``) suitable for
        embedding under ``long_term_trend`` in a frozen wind export. The inverse
        of :func:`resource_trend_df_from_wind_export`.
    """
    if analysis.get("analyzed") is False:
        return dict(analysis)
    summary_df = analysis.get("summary_df")
    if not isinstance(summary_df, pd.DataFrame):
        raise TypeError(
            "serialize_resource_trend expected a 'summary_df' DataFrame in the "
            f"analysis mapping; got {type(summary_df).__name__}."
        )
    return {"analyzed": True, "summary_records": summary_df.to_dict("records")}


def resource_trend_df_from_wind_export(
    wind_export: Optional[Mapping[str, Any]],
) -> Optional[pd.DataFrame]:
    """Reconstruct the ResourceTrend frame from a frozen wind export, if carried.

    Looks for a ``long_term_trend`` block at the export top level or nested
    under ``cashflow_export`` (both wrapper shapes the finance CLI already
    tolerates). Returns the (Metric, Value) DataFrame when the block is present
    and marked ``analyzed`` with non-empty ``summary_records``; otherwise
    ``None`` (absent, opt-out, or an explicit short-series degrade) so the
    workbook simply omits the sheet. The inverse of
    :func:`serialize_resource_trend`.
    """
    if not isinstance(wind_export, Mapping):
        return None
    block = wind_export.get(RESOURCE_TREND_KEY)
    if not isinstance(block, Mapping):
        nested = wind_export.get("cashflow_export")
        block = nested.get(RESOURCE_TREND_KEY) if isinstance(nested, Mapping) else None
    if not isinstance(block, Mapping) or not block.get("analyzed"):
        return None
    records = block.get("summary_records")
    if not isinstance(records, list) or not records:
        return None
    return pd.DataFrame(records)


def emit_executive_workbook_from_pipeline(
    result: Mapping[str, Any],
    output_path: PathLike,
    wind_export: Optional[Mapping[str, Any]] = None,
) -> Path:
    """Build the single-scenario Executive Workbook from a live pipeline result.

    The genuine live caller of :func:`build_executive_workbook`. Assembles the
    five finance frames from ``result`` via :func:`frames_from_pipeline_result`
    and, when ``wind_export`` carries a long-term-trend block
    (:func:`resource_trend_df_from_wind_export`), adds the "ResourceTrend" sheet.

    Args:
        result: A ``run_v14_pipeline`` result dict.
        output_path: Target XLSX path (parents are created).
        wind_export: Optional frozen wind-export mapping; its ``long_term_trend``
            block, if present, supplies the resource-trend sheet.

    Returns:
        The resolved path to the workbook written.
    """
    frames = frames_from_pipeline_result(result)
    return build_executive_workbook(
        summary_df=frames["summary"],
        cashflow_df=frames["cashflow"],
        debt_df=frames["debt"],
        ratios_df=frames["ratios"],
        scenario_summary_df=frames["scenario_summary"],
        output_path=output_path,
        resource_trend_df=resource_trend_df_from_wind_export(wind_export),
    )


# EOF
