"""Long-term wind resource & trend analysis for the bankability report (issue #178).

Runs a Mann-Kendall + Sen's-slope (Theil-Sen) trend test on the annual hub-height wind
series, computes net AEP across candidate reference periods (recent 5 yr / current decade
/ 20 yr long-term / full record), classifies the result as decadal variability vs a
secular "stilling" trend, recommends the forward-looking P50 basis, and renders an
IEC-61400-15 / MEASNET-aware commentary section for the lender report.

Encodes the 2026-06-19 DutchBay finding: a 40-yr Kalpitiya series shows a Mann-Kendall-
significant but weak, recent-decade step-down (a regime shift, not smooth stilling), so the
current-climate decade (~402 GWh) is the central P50 -- not the higher 20/40-yr long-term
mean (~422/428) which over-weights the windier pre-2015 climate.

GWTF: typed, config-first, no hardcoded site constants. The trend math is pure
numpy/scipy; ERA5 retrieval + AEP are reused from ``wind_resource.era5_retrieval``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats as _st

logger = logging.getLogger(__name__)

# Classifier thresholds (a significant MK trend below this OLS R^2 is read as a weak,
# recent-decade regime shift rather than a smooth secular decline).
MK_ALPHA = 0.05
WEAK_TREND_R2 = 0.20

# Minimum distinct calendar years for a meaningful Mann-Kendall / Sen's-slope trend test.
# A bankable long-term reference is 10-20+ yr (IEC 61400-15-1 / MEASNET); below this a trend
# statistic is unstable, so callers degrade EXPLICITLY rather than emit a spurious tau on a
# handful of years (the producer build_resource_trend_export_block and the live
# era5_retrieval.run report path both gate on this).
MIN_TREND_YEARS = 10


@dataclass(frozen=True)
class TrendResult:
    """Mann-Kendall / Sen / OLS trend summary for an annual-mean wind series."""

    start_year: int
    end_year: int
    n_years: int
    mean_ws_ms: float
    cov_pct: float
    mk_tau: float
    mk_pvalue: float
    significant: bool
    sen_slope_per_decade: float
    sen_ci_low_per_decade: float
    sen_ci_high_per_decade: float
    ols_slope_per_decade: float
    ols_r2: float
    decade_means: Dict[str, float]
    classification: str
    classification_note: str


def annual_mean_series(series: pd.DataFrame, ws_col: str) -> pd.Series:
    """Calendar-year mean of the hub-height wind series."""
    return series.groupby(pd.DatetimeIndex(series.index).year)[ws_col].mean()


def _decade_means(annual: pd.Series) -> Dict[str, float]:
    out: Dict[str, float] = {}
    y0 = (int(annual.index.min()) // 10) * 10
    for d in range(y0, int(annual.index.max()) + 1, 10):
        sub = annual[(annual.index >= d) & (annual.index <= d + 9)]
        if len(sub):
            out[f"{d}-{d + 9}"] = round(float(sub.mean()), 3)
    return out


def _classify(mk_p: float, ols_r2: float) -> Tuple[str, str]:
    if mk_p >= MK_ALPHA:
        return (
            "decadal_variability",
            "No statistically significant monotonic trend (Mann-Kendall p>=0.05): the "
            "interannual differences are decadal variability (ENSO/IOD-type). Use a "
            "long-term mean (10-20+ yr) as the central P50.",
        )
    if ols_r2 < WEAK_TREND_R2:
        return (
            "decadal_regime_shift",
            "Mann-Kendall significant but WEAK (OLS R2 < 0.20) and concentrated in the recent "
            "decade -- a decadal regime shift / low phase, NOT a smooth secular 'stilling' ramp. "
            "The recent ('current-climate') decade is the forward-looking P50; the full long-term "
            "mean over-weights an older, windier regime.",
        )
    return (
        "secular_trend",
        "Mann-Kendall significant with material variance explained (OLS R2 >= 0.20): a sustained "
        "decline consistent with secular stilling. Weight the recent period and consider a trend "
        "haircut on the long-term mean.",
    )


def compute_trend(annual: pd.Series) -> TrendResult:
    """Mann-Kendall + Theil-Sen (Sen's slope) + OLS trend on the annual-mean series."""
    yrs = np.asarray(annual.index.values, dtype="float64")
    vals = np.asarray(annual.values, dtype="float64")
    _kt = _st.kendalltau(yrs, vals)
    tau = float(_kt.statistic)
    p_mk = float(_kt.pvalue)
    sen = _st.theilslopes(vals, yrs)
    ols = _st.linregress(yrs, vals)
    r2 = float(ols.rvalue**2)
    classification, note = _classify(float(p_mk), r2)
    return TrendResult(
        start_year=int(yrs.min()),
        end_year=int(yrs.max()),
        n_years=int(len(yrs)),
        mean_ws_ms=round(float(vals.mean()), 3),
        cov_pct=round(float(vals.std() / vals.mean() * 100.0), 2),
        mk_tau=round(float(tau), 3),
        mk_pvalue=round(float(p_mk), 4),
        significant=bool(p_mk < MK_ALPHA),
        sen_slope_per_decade=round(float(sen[0] * 10.0), 4),
        sen_ci_low_per_decade=round(float(sen[2] * 10.0), 4),
        sen_ci_high_per_decade=round(float(sen[3] * 10.0), 4),
        ols_slope_per_decade=round(float(ols.slope * 10.0), 4),
        ols_r2=round(r2, 4),
        decade_means=_decade_means(annual),
        classification=classification,
        classification_note=note,
    )


def reference_periods(
    start_year: int, end_year: int
) -> List[Tuple[int, int, str, str]]:
    """``(start, end, key, role)`` for recent-5yr / current-decade / 20yr / full record."""
    candidates = [
        (end_year - 4, end_year, "recent_5yr", "downside (recent 5 yr)"),
        (end_year - 9, end_year, "current_decade", "central (current-climate decade)"),
        (end_year - 19, end_year, "longterm_20yr", "long-term (20 yr)"),
        (
            start_year,
            end_year,
            "full_record",
            f"full record ({end_year - start_year + 1} yr)",
        ),
    ]
    return [(max(s, start_year), e, k, r) for (s, e, k, r) in candidates]


def period_aep_table(
    series: pd.DataFrame, config: Any, periods: List[Tuple[int, int, str, str]]
) -> List[Dict[str, Any]]:
    """Net AEP for each reference period via the canonical EnergyCalculator path."""
    from wind_resource.era5_retrieval import compute_site_aep

    rows: List[Dict[str, Any]] = []
    idx_year = pd.DatetimeIndex(series.index).year
    for s, e, key, role in periods:
        sub = series[(idx_year >= s) & (idx_year <= e)]
        if sub.empty:
            continue
        r = compute_site_aep(sub, config)
        rows.append(
            {
                "period": f"{s}-{e}",
                "key": key,
                "role": role,
                "years": round(len(sub) / 8760.0, 1),
                "mean_ws_ms": r["mean_ws_hub_ms"],
                "net_aep_p50_gwh": r["net_aep_p50_gwh"],
                "capacity_factor": r["capacity_factor_p50"],
            }
        )
    return rows


def recommend_p50(trend: TrendResult, table: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Pick the forward-looking central P50 basis from the trend classification."""
    by = {row["key"]: row for row in table}
    if trend.classification == "secular_trend":
        central_key = "recent_5yr"
    elif trend.classification == "decadal_regime_shift":
        central_key = "current_decade"
    else:
        central_key = "longterm_20yr"
    central = (
        by.get(central_key) or by.get("longterm_20yr") or (table[0] if table else {})
    )
    downside = by.get("recent_5yr", {})
    upside = by.get("longterm_20yr", {})
    return {
        "central_basis": central_key,
        "p50_gwh": central.get("net_aep_p50_gwh"),
        "p50_cf": central.get("capacity_factor"),
        "downside_gwh": downside.get("net_aep_p50_gwh"),
        "upside_gwh": upside.get("net_aep_p50_gwh"),
    }


def render_trend_markdown(
    trend: TrendResult, table: List[Dict[str, Any]], rec: Dict[str, Any]
) -> str:
    """Render the 'Long-Term Resource & Trend' commentary section as Markdown."""
    sig = "significant" if trend.significant else "not significant"
    lines = [
        "## Long-Term Wind Resource & Trend",
        "",
        f"**Reference:** {trend.start_year}-{trend.end_year} ({trend.n_years} yr), mean "
        f"{trend.mean_ws_ms} m/s (interannual CoV {trend.cov_pct}%).",
        "",
        "**Trend test (Mann-Kendall + Sen's slope):**",
        f"- MK tau {trend.mk_tau}, p={trend.mk_pvalue} ({sig} at 5%); Sen slope "
        f"{trend.sen_slope_per_decade:+.3f} m/s/decade (95% CI "
        f"[{trend.sen_ci_low_per_decade:+.3f}, {trend.sen_ci_high_per_decade:+.3f}]); "
        f"OLS R2 {trend.ols_r2}.",
        "- Decade means: "
        + " · ".join(f"{k} {v}" for k, v in trend.decade_means.items()),
        f"- **Classification: {trend.classification.replace('_', ' ')}.** "
        f"{trend.classification_note}",
        "",
        "**Net AEP by reference period** (canonical power curve):",
        "",
        "| Period | Role | Mean ws (m/s) | AEP P50 (GWh) | CF |",
        "|---|---|---|---|---|",
    ]
    for r in table:
        lines.append(
            f"| {r['period']} | {r['role']} | {r['mean_ws_ms']} | "
            f"{r['net_aep_p50_gwh']} | {r['capacity_factor']} |"
        )
    lines += [
        "",
        f"**Recommended P50 basis: {rec['central_basis'].replace('_', ' ')} = "
        f"{rec['p50_gwh']} GWh (CF {rec['p50_cf']})** -- downside {rec['downside_gwh']} GWh, "
        f"upside {rec['upside_gwh']} GWh.",
        "",
        "**Bankability basis (IEC 61400-15-1 / MEASNET):** a bankable assessment uses a long-term "
        "reference period (typically 10-20+ yr) to average out interannual and decadal "
        "variability, rather than a short recent window. Where a regime shift or secular trend is "
        "detected, the long-term mean is adjusted toward the current-climate period for the "
        "forward-looking P50 (as applied above).",
    ]
    return "\n".join(lines)


def trend_summary_dataframe(
    trend: TrendResult, table: List[Dict[str, Any]], rec: Dict[str, Any]
) -> pd.DataFrame:
    """Tidy (Metric, Value) table for the lender workbook 'ResourceTrend' sheet."""
    rows: List[Tuple[str, Any]] = [
        (
            "Reference period",
            f"{trend.start_year}-{trend.end_year} ({trend.n_years} yr)",
        ),
        ("Mean wind speed (m/s)", trend.mean_ws_ms),
        ("Interannual CoV (%)", trend.cov_pct),
        ("Mann-Kendall tau", trend.mk_tau),
        ("Mann-Kendall p-value", trend.mk_pvalue),
        ("Trend significant (5%)", trend.significant),
        ("Sen slope (m/s/decade)", trend.sen_slope_per_decade),
        ("OLS R2", trend.ols_r2),
        ("Classification", trend.classification.replace("_", " ")),
        ("Classification note", trend.classification_note),
    ]
    for k, v in trend.decade_means.items():
        rows.append((f"Decade mean {k} (m/s)", v))
    for r in table:
        rows.append(
            (f"AEP P50 {r['period']} [{r['role']}] (GWh)", r["net_aep_p50_gwh"])
        )
        rows.append((f"CF {r['period']}", r["capacity_factor"]))
    rows += [
        ("Recommended P50 basis", rec["central_basis"].replace("_", " ")),
        ("Recommended P50 (GWh)", rec["p50_gwh"]),
        ("Recommended P50 CF", rec["p50_cf"]),
        ("Downside P50 (GWh)", rec["downside_gwh"]),
        ("Upside P50 (GWh)", rec["upside_gwh"]),
        (
            "Bankability basis",
            "IEC 61400-15-1 / MEASNET long-term reference; regime-shift-adjusted to the "
            "current-climate period for the forward P50.",
        ),
    ]
    return pd.DataFrame(rows, columns=["Metric", "Value"])


def analyze_long_term_resource(
    config: Any, series: Optional[pd.DataFrame] = None
) -> Dict[str, Any]:
    """Retrieve (or accept) a long series; run trend + period AEPs + recommendation.

    Returns a dict with ``trend`` (:class:`TrendResult`), ``period_aep``, ``recommendation``,
    ``markdown`` (the report section), and ``summary_df`` (the lender-workbook sheet).
    """
    if series is None:
        from wind_resource.era5_retrieval import (
            build_hub_height_series,
            retrieve_era5_timeseries,
        )

        series = build_hub_height_series(retrieve_era5_timeseries(config), config)
    col = f"ws_{int(config.hub_height_m)}m"
    annual = annual_mean_series(series, col)
    trend = compute_trend(annual)
    periods = reference_periods(int(annual.index.min()), int(annual.index.max()))
    table = period_aep_table(series, config, periods)
    rec = recommend_p50(trend, table)
    logger.info(
        "%s long-term trend: %s; recommended P50 %s = %s GWh",
        getattr(config, "project_name", "site"),
        trend.classification,
        rec["central_basis"],
        rec["p50_gwh"],
    )
    return {
        "trend": trend,
        "period_aep": table,
        "recommendation": rec,
        "markdown": render_trend_markdown(trend, table, rec),
        "summary_df": trend_summary_dataframe(trend, table, rec),
    }


def build_resource_trend_export_block(
    config: Any,
    series: pd.DataFrame,
    *,
    min_years: int = MIN_TREND_YEARS,
) -> Dict[str, Any]:
    """Compute the JSON-safe ``long_term_trend`` block for a frozen wind export.

    The producer-side counterpart of the consumer decoder
    ``analytics.executive_workbook.resource_trend_df_from_wind_export`` (issue
    #656): a wind producer (e.g. :class:`wind_resource.wind_pipeline.WindPipeline`)
    calls this on its ALREADY-retrieved multi-year hub series — no second CDS
    fetch — and embeds the returned dict under ``long_term_trend`` in the export
    JSON. The finance CLI then surfaces it as the workbook "ResourceTrend" sheet
    without ever running live ERA5.

    Degrades EXPLICITLY on a short record (CESSPIT fail-loud, no silent default):
    a Mann-Kendall / Sen's-slope trend needs a bankable long-term reference
    (IEC 61400-15-1 / MEASNET, 10-20+ yr). Gating on the ACTUAL number of distinct
    calendar years in ``series`` (not a requested window) prevents a spurious tau
    on a handful of years — the trend is simply not attempted, with a recorded
    reason, rather than emitting a misleading statistic.

    Args:
        config: A config exposing ``hub_height_m``, ``turbine_model``,
            ``num_turbines`` and site identity — i.e. an
            :class:`wind_resource.era5_retrieval.ERA5RequestConfig` — as consumed
            by :func:`analyze_long_term_resource`.
        series: The hub-height wind series, indexed by timestamp, carrying the
            ``ws_<hub>m`` column.
        min_years: Minimum distinct calendar years for a trend test
            (default :data:`MIN_TREND_YEARS`).

    Returns:
        ``{"analyzed": True, "summary_records": [...]}`` (the encoded live
        ``summary_df``) on a sufficient record, else
        ``{"analyzed": False, "reason": ...}``. Report/VALIDATE-only: it changes
        no committed AEP or KPI.
    """
    n_years = int(pd.DatetimeIndex(series.index).year.nunique())
    if n_years < min_years:
        return {
            "analyzed": False,
            "reason": (
                f"long-term trend not computed: the series spans {n_years} calendar "
                f"year(s), shorter than the {min_years}-yr minimum for a Mann-Kendall "
                "/ Sen's-slope trend test (IEC 61400-15-1 / MEASNET). Extend the "
                "reference window to enable the trend section."
            ),
        }
    # Lazy import keeps the encoder edge (wind_resource -> analytics) off module load.
    from analytics.executive_workbook import serialize_resource_trend

    return serialize_resource_trend(analyze_long_term_resource(config, series=series))
