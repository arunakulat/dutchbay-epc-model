"""Measure-Correlate-Predict (MCP) for long-term on-site wind resource (WIND-1, #477).

The deep-research audit flagged that the wind resource is taken from raw ERA5 with no MCP
step against on-site measurement — which weakens the bankability of the long-term estimate,
because reanalysis at a single grid cell carries a site-specific bias (terrain, roughness,
height) that only concurrent on-site data can correct.

MCP closes that gap (IEC 61400-15-2 / MEASNET practice): a SHORT on-site mast record is
correlated against the CONCURRENT long-term reference (ERA5) to fit a transfer function, and
that transfer is applied to the FULL long-term reference to PREDICT the long-term on-site
wind-speed distribution — capturing the site bias the mast reveals while retaining the
inter-annual coverage only the long reference has.

Two transfer methods are provided:

* ``variance_ratio`` (default, the bankable choice): ``slope = std(mast)/std(ref)``,
  ``intercept = mean(mast) - slope*mean(ref)``. It reproduces the on-site **variance** (and
  hence the high-wind tail that drives ``E[v^3]`` energy), which is what a P50/P90 needs.
* ``linear_regression`` (ordinary least squares): minimises residual error but regresses
  toward the mean, **deflating** variance — offered for completeness/diagnostics, not energy.

This is an OPT-IN producer-side method: sites without a mast keep raw ERA5 (the default), so
committed scenarios are byte-identical. Like the other producer physics it feeds the FROZEN
export only at a dated, authorized re-baseline; running MCP here never silently moves committed
economics. Wiring a mast data file + re-freezing the AEP is the integration step (a scenario
declares ``resource.wind.mcp``); this module is the validated method + config gate behind it.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from wind_resource.weibull_fit import fit_weibull_on_series

logger = logging.getLogger(__name__)

#: Transfer methods. ``variance_ratio`` preserves on-site variance (bankable / energy);
#: ``linear_regression`` is OLS (variance-deflating; diagnostic only).
MCP_METHODS: Tuple[str, ...] = ("variance_ratio", "linear_regression")

#: Hard statistical floor on concurrent samples: below this the transfer cannot be fit at
#: all and :func:`run_mcp` raises unconditionally. This tier only guards the statistics from
#: being fit on too few points; bankability is the SEPARATE, higher tier below.
DEFAULT_MIN_CONCURRENT: int = 24

#: Lender-disclosure floor on concurrent samples: ~4 months of hourly data (4 x 30 x 24).
#: Sheridan et al. (Wind Energy Science, 2025) report long-term capacity-factor errors of
#: ~47%/26%/16% for 1/3/6-month campaigns, so a transfer fit on less than ~4 months is
#: statistically fittable but must not be put in front of a lender at all. :func:`run_mcp`
#: fails loud in the band ``min_concurrent <= n < LENDER_DISCLOSURE_MIN_CONCURRENT`` unless
#: the caller explicitly opts out (``allow_below_bankable=True``), which downgrades the
#: failure to a recorded disclosure (CESSPIT: no silent sub-threshold fits).
#:
#: THIS IS NOT A BANKABILITY THRESHOLD. Clearing it means the estimate is showable, not
#: bankable — the standards require roughly three times as much data
#: (:data:`IEC_BANKABLE_MIN_CONCURRENT`). It was previously named
#: ``BANKABLE_MIN_CONCURRENT``, which asserted bankability at ~4 months and so overclaimed
#: against MEASNET v3.1 / IEC 61400-15-1:2025 by a factor of three (#961).
LENDER_DISCLOSURE_MIN_CONCURRENT: int = 2880

#: Deprecated alias for :data:`LENDER_DISCLOSURE_MIN_CONCURRENT`, retained so existing
#: importers keep working. Prefer the new name: this value never meant "bankable".
BANKABLE_MIN_CONCURRENT: int = LENDER_DISCLOSURE_MIN_CONCURRENT

#: The concurrent-sample count a bankable campaign actually requires: >= 12 months of
#: hourly data (365 x 24). MEASNET v3.1 and IEC 61400-15-1:2025 mandate >= 12 concurrent
#: months of on-site measurement long-term-adjusted against a reanalysis reference, and
#: IEC 61400-15-2 wants the same span to cover seasonality. Named so the standard is
#: representable in code and in emitted artefacts rather than living only in a comment.
IEC_BANKABLE_MIN_CONCURRENT: int = 8760

#: Campaign-adequacy states recorded on :class:`MCPResult`. Ordered worst to best.
CAMPAIGN_BELOW_DISCLOSURE_FLOOR = "below_lender_disclosure_floor"
CAMPAIGN_BELOW_IEC_BANKABLE = "below_iec_bankable"
CAMPAIGN_IEC_BANKABLE = "iec_bankable"


@dataclass(frozen=True)
class MCPResult:
    """A measure-correlate-predict long-term on-site wind estimate (WIND-1)."""

    method: str
    slope: float
    intercept: float
    pearson_r: float
    n_concurrent: int
    ref_long_term_mean_ms: float
    predicted_long_term_mean_ms: float
    weibull_a: float
    weibull_k: float
    uplift_pct: float  # predicted on-site vs raw reference long-term mean
    #: Fraction of long-term steps where the transfer predicted a negative speed and was
    #: clipped to 0. A non-trivial value means the clip lifts the predicted mean and shrinks
    #: its variance, so the variance-preservation property degrades — disclosed, not silent.
    fraction_clipped: float = 0.0
    #: Campaign adequacy against the standards, one of :data:`CAMPAIGN_IEC_BANKABLE`,
    #: :data:`CAMPAIGN_BELOW_IEC_BANKABLE`, :data:`CAMPAIGN_BELOW_DISCLOSURE_FLOOR`.
    #: Recorded on the result, not only logged, so the shortfall travels with the estimate
    #: into artefacts and reports instead of dying in a log nobody reads (FIN-01).
    campaign_adequacy: str = CAMPAIGN_IEC_BANKABLE
    #: Concurrent samples still required to reach :data:`IEC_BANKABLE_MIN_CONCURRENT`;
    #: 0 when the campaign already clears it.
    concurrent_shortfall_to_iec_bankable: int = 0

    def as_dict(self) -> Dict[str, Any]:
        return {
            "method": self.method,
            "slope": round(self.slope, 5),
            "intercept": round(self.intercept, 5),
            "pearson_r": round(self.pearson_r, 5),
            "n_concurrent": self.n_concurrent,
            "ref_long_term_mean_ms": round(self.ref_long_term_mean_ms, 4),
            "predicted_long_term_mean_ms": round(self.predicted_long_term_mean_ms, 4),
            "weibull_a": round(self.weibull_a, 4),
            "weibull_k": round(self.weibull_k, 4),
            "uplift_pct": round(self.uplift_pct, 3),
            "fraction_clipped": round(self.fraction_clipped, 5),
            "campaign_adequacy": self.campaign_adequacy,
            "concurrent_shortfall_to_iec_bankable": (
                self.concurrent_shortfall_to_iec_bankable
            ),
        }


def pearson_r(mast: np.ndarray, ref: np.ndarray) -> float:
    """Pearson correlation of two concurrent series (0.0 if either is constant)."""
    if mast.std() == 0.0 or ref.std() == 0.0:
        return 0.0
    return float(np.corrcoef(mast, ref)[0, 1])


def variance_ratio_transfer(
    mast: np.ndarray, ref_concurrent: np.ndarray
) -> Tuple[float, float]:
    """Variance-ratio transfer ``(slope, intercept)`` (IEC 61400-15-2; variance-preserving)."""
    ref_std = float(ref_concurrent.std())
    if ref_std == 0.0:
        raise ValueError(
            "reference concurrent series has zero variance; cannot fit MCP"
        )
    slope = float(mast.std()) / ref_std
    intercept = float(mast.mean()) - slope * float(ref_concurrent.mean())
    return slope, intercept


def linear_regression_transfer(
    mast: np.ndarray, ref_concurrent: np.ndarray
) -> Tuple[float, float]:
    """Ordinary-least-squares transfer ``(slope, intercept)`` (variance-deflating)."""
    slope, intercept = np.polyfit(ref_concurrent, mast, 1)
    return float(slope), float(intercept)


def predict_long_term(
    slope: float, intercept: float, ref_long_term: np.ndarray
) -> np.ndarray:
    """Apply a transfer to the long-term reference; clip to physical (>= 0) wind speeds."""
    predicted = slope * ref_long_term + intercept
    return np.clip(predicted, 0.0, None)


def run_mcp(
    mast_concurrent: Sequence[float],
    ref_concurrent: Sequence[float],
    ref_long_term: Sequence[float],
    *,
    method: str = "variance_ratio",
    min_concurrent: int = DEFAULT_MIN_CONCURRENT,
    allow_below_bankable: bool = False,
) -> MCPResult:
    """Run measure-correlate-predict and return the long-term on-site estimate.

    Campaign-duration guard is TIERED (CESSPIT — no silent sub-bankable fits):

    * ``n < min_concurrent`` (hard statistical floor, default
      :data:`DEFAULT_MIN_CONCURRENT`): ``ValueError`` unconditionally — too few points to
      fit a transfer at all. ``allow_below_bankable`` does NOT bypass this tier.
    * ``min_concurrent <= n < BANKABLE_MIN_CONCURRENT`` (~4 months of hourly data):
      ``ValueError`` unless ``allow_below_bankable=True``, which downgrades the failure to
      a ``logger.warning`` bankability disclosure (Sheridan et al., WES 2025: capacity-
      factor errors ~47%/26%/16% at 1/3/6 months).
    * ``n >= BANKABLE_MIN_CONCURRENT``: clean.

    Args:
        mast_concurrent: On-site mast wind speeds (m/s) over the measurement window.
        ref_concurrent: Long-term reference (ERA5) wind speeds over the SAME window, aligned
            element-wise with ``mast_concurrent``.
        ref_long_term: The full long-term reference series (m/s) to predict on-site from.
        method: ``"variance_ratio"`` (default) or ``"linear_regression"``.
        min_concurrent: Hard minimum aligned concurrent samples required to fit the
            transfer (the fail-loud lower tier; raising it above
            :data:`BANKABLE_MIN_CONCURRENT` makes the hard floor the only gate).
        allow_below_bankable: Explicit opt-out for the bankability tier only (defaults
            OFF). Scenario knob: ``resource.wind.mcp.allow_below_bankable``.

    Returns:
        An :class:`MCPResult` with the fitted transfer, the predicted long-term on-site mean,
        and a Weibull fit of the predicted on-site distribution.

    Raises:
        ValueError: unknown ``method``; concurrent series differ in length or fall below
            ``min_concurrent``; concurrent samples below :data:`BANKABLE_MIN_CONCURRENT`
            without ``allow_below_bankable=True``; the long-term reference is empty; or the
            reference has zero variance (CESSPIT — fail loud rather than emit a meaningless
            transfer).
    """
    if method not in MCP_METHODS:
        raise ValueError(f"Unknown MCP method {method!r}; choose from {MCP_METHODS}")
    mast = np.asarray(mast_concurrent, dtype=float)
    ref_c = np.asarray(ref_concurrent, dtype=float)
    ref_lt = np.asarray(ref_long_term, dtype=float)
    # Fail loud on gaps: real ERA5 / mast records routinely carry NaN/inf, which would
    # otherwise silently corrupt the means while still yielding a plausible Weibull (CESSPIT).
    for name, arr in (
        ("mast_concurrent", mast),
        ("ref_concurrent", ref_c),
        ("ref_long_term", ref_lt),
    ):
        if arr.size and not np.all(np.isfinite(arr)):
            raise ValueError(
                f"{name} contains non-finite (NaN/inf) values; clean the series before MCP"
            )
    if mast.shape != ref_c.shape:
        raise ValueError(
            f"mast and reference concurrent series must align; got {mast.shape} vs "
            f"{ref_c.shape}"
        )
    if mast.size < min_concurrent:
        raise ValueError(
            f"need >= {min_concurrent} concurrent samples to fit MCP; got {mast.size}"
        )
    if ref_lt.size == 0:
        raise ValueError("ref_long_term is empty")
    # Both methods need a non-degenerate reference; guard here so linear_regression (OLS)
    # fails loud identically to variance_ratio rather than emitting a garbage np.polyfit.
    if float(ref_c.std()) == 0.0:
        raise ValueError(
            "reference concurrent series has zero variance; cannot fit MCP"
        )
    # Bankability tier: gated LAST so it only fires on otherwise fit-worthy data — the
    # data-integrity errors above are the actionable ones when both conditions hold.
    if mast.size < LENDER_DISCLOSURE_MIN_CONCURRENT:
        if not allow_below_bankable:
            raise ValueError(
                f"MCP campaign has {mast.size} concurrent samples, below the "
                f"lender-disclosure floor of {LENDER_DISCLOSURE_MIN_CONCURRENT} "
                "(~4 months of hourly data); short campaigns carry large long-term "
                "capacity-factor errors (Sheridan et al., Wind Energy Science 2025: "
                "~47%/26%/16% at 1/3/6 months). Note that clearing this floor still would "
                f"not make the estimate bankable: that needs "
                f">= {IEC_BANKABLE_MIN_CONCURRENT} samples (12 months, MEASNET v3.1 / "
                "IEC 61400-15-1:2025). Pass allow_below_bankable=True (scenario knob: "
                "resource.wind.mcp.allow_below_bankable) to proceed with a recorded "
                "disclosure."
            )
        logger.warning(
            "MCP transfer fit on %d concurrent samples, below the lender-disclosure floor "
            "of %d (~4 months of hourly data; Sheridan et al., Wind Energy Science 2025: "
            "capacity-factor errors ~47%%/26%%/16%% at 1/3/6 months) and far below the "
            "%d samples (12 months) MEASNET v3.1 / IEC 61400-15-1:2025 require for a "
            "bankable campaign. Proceeding under allow_below_bankable — the long-term "
            "estimate is NOT bankable.",
            mast.size,
            LENDER_DISCLOSURE_MIN_CONCURRENT,
            IEC_BANKABLE_MIN_CONCURRENT,
        )
    elif mast.size < IEC_BANKABLE_MIN_CONCURRENT:
        # Clearing the disclosure floor is NOT bankability. This band was previously
        # silent, so a ~4-month campaign emitted an estimate carrying no record that it
        # was a third of the required span (#961).
        logger.warning(
            "MCP transfer fit on %d concurrent samples: above the lender-disclosure floor "
            "of %d but below the %d samples (12 concurrent months) MEASNET v3.1 / "
            "IEC 61400-15-1:2025 require for a bankable long-term estimate. The result is "
            "showable with disclosure, NOT bankable; campaign_adequacy records this.",
            mast.size,
            LENDER_DISCLOSURE_MIN_CONCURRENT,
            IEC_BANKABLE_MIN_CONCURRENT,
        )

    if mast.size >= IEC_BANKABLE_MIN_CONCURRENT:
        campaign_adequacy = CAMPAIGN_IEC_BANKABLE
    elif mast.size >= LENDER_DISCLOSURE_MIN_CONCURRENT:
        campaign_adequacy = CAMPAIGN_BELOW_IEC_BANKABLE
    else:
        campaign_adequacy = CAMPAIGN_BELOW_DISCLOSURE_FLOOR
    concurrent_shortfall = max(0, IEC_BANKABLE_MIN_CONCURRENT - int(mast.size))

    if method == "variance_ratio":
        slope, intercept = variance_ratio_transfer(mast, ref_c)
    else:
        slope, intercept = linear_regression_transfer(mast, ref_c)

    fraction_clipped = float(np.mean((slope * ref_lt + intercept) < 0.0))
    if fraction_clipped > 0.01:
        logger.warning(
            "MCP transfer predicted negative speeds at %.1f%% of long-term steps; clipping "
            "to 0 lifts the predicted mean and shrinks its variance.",
            fraction_clipped * 100.0,
        )
    predicted = predict_long_term(slope, intercept, ref_lt)
    weibull = fit_weibull_on_series(
        pd.DataFrame({"ws": predicted}), ws_column="ws", method="mle"
    )
    ref_mean = float(ref_lt.mean())
    pred_mean = float(predicted.mean())
    uplift = ((pred_mean - ref_mean) / ref_mean * 100.0) if ref_mean > 0 else 0.0

    return MCPResult(
        method=method,
        slope=slope,
        intercept=intercept,
        pearson_r=pearson_r(mast, ref_c),
        n_concurrent=int(mast.size),
        ref_long_term_mean_ms=ref_mean,
        predicted_long_term_mean_ms=pred_mean,
        weibull_a=weibull.weibull_a,
        weibull_k=weibull.weibull_k,
        uplift_pct=uplift,
        fraction_clipped=fraction_clipped,
        campaign_adequacy=campaign_adequacy,
        concurrent_shortfall_to_iec_bankable=concurrent_shortfall,
    )


def mcp_settings(config: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    """Resolve the opt-in ``resource.wind.mcp`` settings, or ``None`` when MCP is off.

    Returns ``{"method": ..., "min_concurrent": ..., "allow_below_bankable": ...}`` only
    when ``resource.wind.mcp.enabled`` is truthy; otherwise ``None`` so the caller keeps
    the raw ERA5 path (the default — committed scenarios are byte-identical). The
    mast/reference series themselves are supplied by the caller's data-ingest step (a
    scenario points ``resource.wind.mcp`` at its mast record); this only resolves the
    method knobs. ``allow_below_bankable`` (the bankability-tier opt-out fed to
    :func:`run_mcp`) defaults OFF and is resolved strictly: a non-boolean value is a
    fail-loud ``ValueError``, not a truthiness coercion (CESSPIT).
    """
    wind = config.get("resource", {}) if isinstance(config, Mapping) else {}
    wind = wind.get("wind", {}) if isinstance(wind, Mapping) else {}
    mcp = wind.get("mcp") if isinstance(wind, Mapping) else None
    if not isinstance(mcp, Mapping) or not mcp.get("enabled"):
        return None
    method = str(mcp.get("method", "variance_ratio")).strip().lower()
    if method not in MCP_METHODS:
        raise ValueError(
            f"resource.wind.mcp.method={method!r} is invalid; choose from {MCP_METHODS}"
        )
    try:
        min_concurrent = int(mcp.get("min_concurrent", DEFAULT_MIN_CONCURRENT))
    except (TypeError, ValueError) as exc:
        raise ValueError("resource.wind.mcp.min_concurrent must be an integer") from exc
    allow_below_bankable = mcp.get("allow_below_bankable", False)
    if not isinstance(allow_below_bankable, bool):
        raise ValueError(
            "resource.wind.mcp.allow_below_bankable must be a boolean; got "
            f"{allow_below_bankable!r}"
        )
    return {
        "method": method,
        "min_concurrent": min_concurrent,
        "allow_below_bankable": allow_below_bankable,
    }


__all__ = [
    "MCP_METHODS",
    "DEFAULT_MIN_CONCURRENT",
    "BANKABLE_MIN_CONCURRENT",
    "MCPResult",
    "pearson_r",
    "variance_ratio_transfer",
    "linear_regression_transfer",
    "predict_long_term",
    "run_mcp",
    "mcp_settings",
]
