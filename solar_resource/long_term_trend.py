"""Long-term solar-resource (GHI) trend analysis for the bankable report (issue #727).

The SOLAR analogue of ``wind_resource.long_term_trend`` (#656). It runs a Mann-Kendall +
Sen's-slope (Theil-Sen) trend test on an ANNUAL global-horizontal-irradiance (GHI) series,
classifies the result as decadal variability vs a secular dimming/brightening trend,
computes reference-period GHI (recent 5 yr / current decade / 20 yr long-term / full
record), recommends the forward-looking P50 GHI basis, and renders an IEC-61724-1 /
IEA-PVPS-Task-13-aware commentary section + a lender-workbook "ResourceTrend" sheet.

Data source (DATA-SOURCE DECISION, #727 maintainer pre-call): the multi-decade annual-GHI
series is sourced from **PVGIS SARAH-3** (Copernicus/EUMETSAT CM SAF surface solar radiation,
satellite-derived, ~1983-present at ~5 km). Following the #656 / #469 FROZEN posture, the
series is an INPUT to this module — a frozen/config multi-decade annual-GHI table — NOT fetched
live here or in tests. This module never calls the network; a producer freezes the SARAH-3
annual-GHI table offline (as ``run_wind_analysis_v14`` freezes ERA5) and hands the series in.

Global dimming/brightening is the solar counterpart of wind "stilling": multi-decade GHI
records show a mid-century dimming then a post-1990 brightening over much of the globe (Wild
2009, IPCC AR6). A bankable solar P50 must therefore average over a long-term reference
(10-20+ yr, IEC 61724-1 / IEA-PVPS Task 13), adjusted toward the current-climate period where
a regime shift or secular trend is detected — exactly the wind-side logic, re-signed for GHI.

GWTF: typed, config-first, no hardcoded site constants. The trend math is pure numpy/scipy
and pvlib-free (report-only): it changes no committed solar CF/AEP, no KPI, no finance path.
The reference-period GHI is a linear scaling of the produced (or config-declared) annual
energy by the GHI ratio — it does NOT re-run pvlib, keeping this module network- and
pvlib-free like the finance consumer (contrast the wind side, which re-runs the canonical
EnergyCalculator per period because that path is already cdsapi-only, not finance-facing).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats as _st

logger = logging.getLogger(__name__)

# Classifier thresholds — mirror the wind side (wind_resource.long_term_trend): a
# significant Mann-Kendall trend below this OLS R^2 is read as a weak, recent-decade
# regime shift rather than a smooth secular dimming/brightening ramp.
MK_ALPHA = 0.05
WEAK_TREND_R2 = 0.20

# Minimum distinct calendar years for a meaningful Mann-Kendall / Sen's-slope trend test.
# A bankable long-term solar reference is 10-20+ yr (IEC 61724-1 / IEA-PVPS Task 13); below
# this a trend statistic is unstable, so callers degrade EXPLICITLY rather than emit a
# spurious tau on a handful of years (the producer build_solar_resource_trend_export_block
# gates on this, exactly as the wind side does).
MIN_TREND_YEARS = 10

# Default label for the frozen multi-decade annual-GHI source (documented, not fetched).
DEFAULT_GHI_SOURCE = "PVGIS SARAH-3 (frozen annual GHI)"

# Lender-facing provenance for the per-period energy/CF (MEDIUM #727-review fix): the
# per-period AEP/CF are the full-record base value scaled LINEARLY by the period-to-record
# GHI ratio — a first-order proxy, NOT a per-period pvlib re-run (contrast the wind side,
# whose table IS a canonical-power-curve re-run). Surfaced IN the artifact (the markdown
# table header + a workbook "Method" row) so a lender never reads the proxy as a precise
# modelled P50.
PERIOD_ENERGY_BASIS = (
    "first-order linear GHI-ratio proxy of the full-record P50, not a pvlib re-run"
)


@dataclass(frozen=True)
class SolarTrendResult:
    """Mann-Kendall / Sen / OLS trend summary for an annual-mean GHI series."""

    start_year: int
    end_year: int
    n_years: int
    mean_ghi_kwh_m2: float
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


def annual_mean_ghi_series(series: pd.DataFrame, ghi_col: str) -> pd.Series:
    """Calendar-year mean of a (sub-annual) GHI series.

    Accepts an already-annual series (one row per calendar year) unchanged — a
    per-year groupby-mean of a single value is that value — so a frozen PVGIS
    SARAH-3 annual-GHI table indexed by year-end timestamps flows through as-is.
    """
    return series.groupby(pd.DatetimeIndex(series.index).year)[ghi_col].mean()


def _decade_means(annual: pd.Series) -> Dict[str, float]:
    out: Dict[str, float] = {}
    y0 = (int(annual.index.min()) // 10) * 10
    for d in range(y0, int(annual.index.max()) + 1, 10):
        sub = annual[(annual.index >= d) & (annual.index <= d + 9)]
        if len(sub):
            out[f"{d}-{d + 9}"] = round(float(sub.mean()), 1)
    return out


def _classify(
    mk_p: float, ols_r2: float, sen_slope_per_decade: float
) -> Tuple[str, str]:
    """Classify the GHI trend; the sign names dimming vs brightening in the note."""
    direction = "brightening" if sen_slope_per_decade >= 0 else "dimming"
    if mk_p >= MK_ALPHA:
        return (
            "decadal_variability",
            "No statistically significant monotonic trend (Mann-Kendall p>=0.05): the "
            "interannual GHI differences are decadal variability (aerosol/cloud/ENSO-type). "
            "Use a long-term mean (10-20+ yr) as the central P50.",
        )
    if ols_r2 < WEAK_TREND_R2:
        return (
            "decadal_regime_shift",
            f"Mann-Kendall significant but WEAK (OLS R2 < 0.20) and concentrated in the recent "
            f"decade -- a decadal regime shift / low phase ({direction}), NOT a smooth secular "
            "ramp. The recent ('current-climate') decade is the forward-looking P50; the full "
            "long-term mean over-weights an older, differently-lit regime.",
        )
    return (
        "secular_trend",
        f"Mann-Kendall significant with material variance explained (OLS R2 >= 0.20): a "
        f"sustained {direction} trend consistent with secular global dimming/brightening. "
        "Weight the recent period and consider a trend adjustment on the long-term mean.",
    )


def compute_solar_trend(annual: pd.Series) -> SolarTrendResult:
    """Mann-Kendall + Theil-Sen (Sen's slope) + OLS trend on the annual-mean GHI series."""
    yrs = np.asarray(annual.index.values, dtype="float64")
    vals = np.asarray(annual.values, dtype="float64")
    # Zero-variance guard (LOW #727-review fix, mirrors the wind side's latent risk): a
    # perfectly constant GHI series makes kendalltau / linregress return NaN tau/p/r2,
    # which a strict JSON encoder (json.dumps(allow_nan=False)) or decoder would reject
    # in the frozen export. Not reachable with real PVGIS SARAH-3 (measured GHI always
    # varies), but treat it as an unambiguous no-trend with serializable zeros.
    if float(vals.std()) == 0.0:
        return SolarTrendResult(
            start_year=int(yrs.min()),
            end_year=int(yrs.max()),
            n_years=int(len(yrs)),
            mean_ghi_kwh_m2=round(float(vals.mean()), 1),
            cov_pct=0.0,
            mk_tau=0.0,
            mk_pvalue=1.0,
            significant=False,
            sen_slope_per_decade=0.0,
            sen_ci_low_per_decade=0.0,
            sen_ci_high_per_decade=0.0,
            ols_slope_per_decade=0.0,
            ols_r2=0.0,
            decade_means=_decade_means(annual),
            classification="decadal_variability",
            classification_note=(
                "Constant annual GHI (zero interannual variance): no trend is "
                "computable; treated as no monotonic trend. Use a long-term mean as "
                "the central P50."
            ),
        )
    _kt = _st.kendalltau(yrs, vals)
    tau = float(_kt.statistic)
    p_mk = float(_kt.pvalue)
    sen = _st.theilslopes(vals, yrs)
    ols = _st.linregress(yrs, vals)
    r2 = float(ols.rvalue**2)
    sen_slope_dec = round(float(sen[0] * 10.0), 2)
    classification, note = _classify(float(p_mk), r2, sen_slope_dec)
    return SolarTrendResult(
        start_year=int(yrs.min()),
        end_year=int(yrs.max()),
        n_years=int(len(yrs)),
        mean_ghi_kwh_m2=round(float(vals.mean()), 1),
        cov_pct=round(float(vals.std() / vals.mean() * 100.0), 2),
        mk_tau=round(float(tau), 3),
        mk_pvalue=round(float(p_mk), 4),
        significant=bool(p_mk < MK_ALPHA),
        sen_slope_per_decade=sen_slope_dec,
        sen_ci_low_per_decade=round(float(sen[2] * 10.0), 2),
        sen_ci_high_per_decade=round(float(sen[3] * 10.0), 2),
        ols_slope_per_decade=round(float(ols.slope * 10.0), 2),
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


def period_ghi_table(
    annual: pd.Series,
    periods: List[Tuple[int, int, str, str]],
    *,
    base_energy_gwh: Optional[float] = None,
    base_cf: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """Mean GHI (and GHI-scaled energy/CF, if a base is given) per reference period.

    Pure and pvlib-free: the per-period energy/CF are the base (produced or config-declared,
    full-record) values scaled LINEARLY by the period-to-full-record GHI ratio — a
    first-order proxy that keeps this module network- and pvlib-free (contrast the wind
    side, which re-runs the cdsapi-only EnergyCalculator per period). When no base energy is
    supplied, only the mean GHI per period is emitted. Report-only: derives no committed CF.
    """
    full_mean = float(annual.mean())
    rows: List[Dict[str, Any]] = []
    for s, e, key, role in periods:
        sub = annual[(annual.index >= s) & (annual.index <= e)]
        if not len(sub):
            continue
        mean_ghi = float(sub.mean())
        ratio = mean_ghi / full_mean if full_mean else 1.0
        row: Dict[str, Any] = {
            "period": f"{s}-{e}",
            "key": key,
            "role": role,
            "years": int(len(sub)),
            "mean_ghi_kwh_m2": round(mean_ghi, 1),
        }
        # First-order LINEAR GHI-ratio proxy (NOT a pvlib re-run); round to few sig
        # figs so the artifact does not read as a precise modelled P50 (see
        # PERIOD_ENERGY_BASIS / the caveated table header + workbook "Method" row).
        if base_energy_gwh is not None:
            row["net_aep_p50_gwh"] = round(float(base_energy_gwh) * ratio, 1)
        if base_cf is not None:
            row["capacity_factor"] = round(float(base_cf) * ratio, 3)
        rows.append(row)
    return rows


def recommend_p50(
    trend: SolarTrendResult, table: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Pick the forward-looking central P50 GHI basis from the trend classification."""
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
        "p50_ghi_kwh_m2": central.get("mean_ghi_kwh_m2"),
        "p50_gwh": central.get("net_aep_p50_gwh"),
        "p50_cf": central.get("capacity_factor"),
        "downside_ghi_kwh_m2": downside.get("mean_ghi_kwh_m2"),
        "upside_ghi_kwh_m2": upside.get("mean_ghi_kwh_m2"),
    }


def render_trend_markdown(
    trend: SolarTrendResult,
    table: List[Dict[str, Any]],
    rec: Dict[str, Any],
    *,
    source: str = DEFAULT_GHI_SOURCE,
) -> str:
    """Render the 'Long-Term Solar Resource & Trend' commentary section as Markdown."""
    sig = "significant" if trend.significant else "not significant"
    has_energy = any("net_aep_p50_gwh" in r for r in table)
    lines = [
        "## Long-Term Solar Resource & Trend (GHI)",
        "",
        f"**Source:** {source}. **Reference:** {trend.start_year}-{trend.end_year} "
        f"({trend.n_years} yr), mean GHI {trend.mean_ghi_kwh_m2} kWh/m2/yr "
        f"(interannual CoV {trend.cov_pct}%).",
        "",
        "**Trend test (Mann-Kendall + Sen's slope):**",
        f"- MK tau {trend.mk_tau}, p={trend.mk_pvalue} ({sig} at 5%); Sen slope "
        f"{trend.sen_slope_per_decade:+.1f} kWh/m2/decade (95% CI "
        f"[{trend.sen_ci_low_per_decade:+.1f}, {trend.sen_ci_high_per_decade:+.1f}]); "
        f"OLS R2 {trend.ols_r2}.",
        "- Decade means: "
        + " · ".join(f"{k} {v}" for k, v in trend.decade_means.items()),
        f"- **Classification: {trend.classification.replace('_', ' ')}.** "
        f"{trend.classification_note}",
        "",
        (
            f"**GHI-scaled AEP by reference period ({PERIOD_ENERGY_BASIS}):**"
            if has_energy
            else "**GHI by reference period:**"
        ),
        "",
    ]
    if has_energy:
        lines += [
            "| Period | Role | Mean GHI (kWh/m2) | AEP P50 (GWh) | CF |",
            "|---|---|---|---|---|",
        ]
        for r in table:
            lines.append(
                f"| {r['period']} | {r['role']} | {r['mean_ghi_kwh_m2']} | "
                f"{r.get('net_aep_p50_gwh', '')} | {r.get('capacity_factor', '')} |"
            )
    else:
        lines += ["| Period | Role | Mean GHI (kWh/m2) |", "|---|---|---|"]
        for r in table:
            lines.append(f"| {r['period']} | {r['role']} | {r['mean_ghi_kwh_m2']} |")
    p50_energy = (
        f" = {rec['p50_gwh']} GWh (CF {rec['p50_cf']}; {PERIOD_ENERGY_BASIS})"
        if rec.get("p50_gwh") is not None
        else ""
    )
    lines += [
        "",
        f"**Recommended P50 basis: {rec['central_basis'].replace('_', ' ')} = "
        f"{rec['p50_ghi_kwh_m2']} kWh/m2{p50_energy}** -- downside "
        f"{rec['downside_ghi_kwh_m2']} kWh/m2, upside {rec['upside_ghi_kwh_m2']} kWh/m2.",
        "",
        "**Bankability basis (IEC 61724-1 / IEA-PVPS Task 13):** a bankable solar assessment "
        "uses a long-term reference period (typically 10-20+ yr) to average out interannual "
        "and decadal GHI variability (global dimming/brightening), rather than a short recent "
        "window. Where a regime shift or secular trend is detected, the long-term mean is "
        "adjusted toward the current-climate period for the forward-looking P50 (as applied "
        "above).",
    ]
    return "\n".join(lines)


def trend_summary_dataframe(
    trend: SolarTrendResult,
    table: List[Dict[str, Any]],
    rec: Dict[str, Any],
    *,
    source: str = DEFAULT_GHI_SOURCE,
) -> pd.DataFrame:
    """Tidy (Metric, Value) table for the lender workbook 'ResourceTrend' sheet.

    Same two-column (Metric, Value) shape the wind producer emits — so the same
    JSON-safe ``long_term_trend`` block contract and the same workbook decoder serve
    both technologies unchanged.
    """
    rows: List[Tuple[str, Any]] = [
        ("Resource", "Solar GHI"),
        ("GHI source", source),
        (
            "Reference period",
            f"{trend.start_year}-{trend.end_year} ({trend.n_years} yr)",
        ),
        ("Mean GHI (kWh/m2/yr)", trend.mean_ghi_kwh_m2),
        ("Interannual CoV (%)", trend.cov_pct),
        ("Mann-Kendall tau", trend.mk_tau),
        ("Mann-Kendall p-value", trend.mk_pvalue),
        ("Trend significant (5%)", trend.significant),
        ("Sen slope (kWh/m2/decade)", trend.sen_slope_per_decade),
        ("OLS R2", trend.ols_r2),
        ("Classification", trend.classification.replace("_", " ")),
        ("Classification note", trend.classification_note),
    ]
    # MEDIUM #727-review: when the sheet carries GHI-scaled per-period energy/CF, state
    # their basis IN the artifact so a lender does not read them as precise pvlib P50s.
    if any("net_aep_p50_gwh" in r or "capacity_factor" in r for r in table):
        rows.append(("AEP basis (per-period energy/CF)", PERIOD_ENERGY_BASIS))
    for k, v in trend.decade_means.items():
        rows.append((f"Decade mean GHI {k} (kWh/m2)", v))
    for r in table:
        rows.append((f"GHI {r['period']} [{r['role']}] (kWh/m2)", r["mean_ghi_kwh_m2"]))
        if "net_aep_p50_gwh" in r:
            rows.append((f"AEP P50 {r['period']} (GWh)", r["net_aep_p50_gwh"]))
        if "capacity_factor" in r:
            rows.append((f"CF {r['period']}", r["capacity_factor"]))
    rows += [
        ("Recommended P50 basis", rec["central_basis"].replace("_", " ")),
        ("Recommended P50 GHI (kWh/m2)", rec["p50_ghi_kwh_m2"]),
    ]
    if rec.get("p50_gwh") is not None:
        rows.append(("Recommended P50 (GWh)", rec["p50_gwh"]))
    if rec.get("p50_cf") is not None:
        rows.append(("Recommended P50 CF", rec["p50_cf"]))
    rows += [
        ("Downside P50 GHI (kWh/m2)", rec["downside_ghi_kwh_m2"]),
        ("Upside P50 GHI (kWh/m2)", rec["upside_ghi_kwh_m2"]),
        (
            "Bankability basis",
            "IEC 61724-1 / IEA-PVPS Task 13 long-term reference; regime-shift-adjusted to "
            "the current-climate period for the forward P50.",
        ),
    ]
    return pd.DataFrame(rows, columns=["Metric", "Value"])


def analyze_long_term_solar_resource(
    series: pd.DataFrame,
    ghi_col: str = "ghi_kwh_m2",
    *,
    base_energy_gwh: Optional[float] = None,
    base_cf: Optional[float] = None,
    source: str = DEFAULT_GHI_SOURCE,
) -> Dict[str, Any]:
    """Run the GHI trend + reference-period GHI + recommendation on an annual series.

    Args:
        series: The annual (or sub-annual) GHI series, indexed by timestamp, carrying
            ``ghi_col``. The multi-decade series is a FROZEN input (PVGIS SARAH-3) — this
            function performs no fetch (the #656 / #469 discipline).
        ghi_col: Column holding annual GHI in kWh/m2/yr.
        base_energy_gwh, base_cf: Optional full-record produced (or config-declared) annual
            energy / CF; when supplied, the reference-period table carries GHI-scaled energy
            and CF (linear GHI proxy, pvlib-free). When omitted, only mean GHI per period.
        source: Provenance label for the GHI series (documentation only).

    Returns:
        A dict with ``trend`` (:class:`SolarTrendResult`), ``period_ghi``, ``recommendation``,
        ``markdown`` (the report section), and ``summary_df`` (the lender-workbook sheet).
    """
    annual = annual_mean_ghi_series(series, ghi_col)
    trend = compute_solar_trend(annual)
    periods = reference_periods(int(annual.index.min()), int(annual.index.max()))
    table = period_ghi_table(
        annual, periods, base_energy_gwh=base_energy_gwh, base_cf=base_cf
    )
    rec = recommend_p50(trend, table)
    logger.info(
        "solar long-term GHI trend: %s; recommended P50 %s = %s kWh/m2",
        trend.classification,
        rec["central_basis"],
        rec["p50_ghi_kwh_m2"],
    )
    return {
        "trend": trend,
        "period_ghi": table,
        "recommendation": rec,
        "markdown": render_trend_markdown(trend, table, rec, source=source),
        "summary_df": trend_summary_dataframe(trend, table, rec, source=source),
    }


def build_solar_resource_trend_export_block(
    series: pd.DataFrame,
    ghi_col: str = "ghi_kwh_m2",
    *,
    base_energy_gwh: Optional[float] = None,
    base_cf: Optional[float] = None,
    source: str = DEFAULT_GHI_SOURCE,
    min_years: int = MIN_TREND_YEARS,
) -> Dict[str, Any]:
    """Compute the JSON-safe ``long_term_trend`` block for a frozen SOLAR export.

    The solar analogue of
    ``wind_resource.long_term_trend.build_resource_trend_export_block`` (#656): a solar
    producer freezes a multi-decade PVGIS SARAH-3 annual-GHI table and calls this to embed
    a ``long_term_trend`` block under its frozen solar export. The finance CLI then surfaces
    it as the workbook "ResourceTrend" sheet WITHOUT ever running pvlib or the network — the
    exact same JSON-safe block + workbook decoder the wind side already uses
    (``analytics.executive_workbook.serialize_resource_trend`` /
    ``resource_trend_df_from_solar_export``).

    Degrades EXPLICITLY on a short record (CESSPIT fail-loud, no silent default): a
    Mann-Kendall / Sen's-slope trend needs a bankable long-term reference (IEC 61724-1 /
    IEA-PVPS Task 13, 10-20+ yr). Gating on the ACTUAL number of distinct calendar years in
    ``series`` prevents a spurious tau on a handful of years — the trend is simply not
    attempted, with a recorded reason, rather than emitting a misleading statistic.

    Returns ``{"analyzed": True, "summary_records": [...]}`` on a sufficient record, else
    ``{"analyzed": False, "reason": ...}``. Report/VALIDATE-only: it changes no committed
    solar CF/AEP or KPI.
    """
    n_years = int(pd.DatetimeIndex(series.index).year.nunique())
    if n_years < min_years:
        return {
            "analyzed": False,
            "reason": (
                f"long-term solar-GHI trend not computed: the series spans {n_years} "
                f"calendar year(s), shorter than the {min_years}-yr minimum for a "
                "Mann-Kendall / Sen's-slope trend test (IEC 61724-1 / IEA-PVPS Task 13). "
                "Extend the reference window to enable the trend section."
            ),
        }
    # Lazy import keeps the encoder edge (solar_resource -> analytics) off module load,
    # mirroring the wind producer. The encoder is tech-agnostic (reads only summary_df).
    from analytics.executive_workbook import serialize_resource_trend

    return serialize_resource_trend(
        analyze_long_term_solar_resource(
            series,
            ghi_col,
            base_energy_gwh=base_energy_gwh,
            base_cf=base_cf,
            source=source,
        )
    )
