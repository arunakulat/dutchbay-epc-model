"""
analytics.sensitivity.tail_risk

Tail-risk enrichment for a one-way SensitivitySuite.

What the LIVE path computes (``enrich_suite_with_tail_risk``):
- A **3-point tornado snapshot** per parameter: the base value plus the worst-outcome
  ``downside`` and best-outcome ``upside`` KPI across that parameter's low/high shocks,
  and the largest ``|impact|``. These are keyed to the KPI OUTCOME, not the shock
  direction, so a cost driver (higher CAPEX/opex/rate -> worse KPI) labels correctly
  (audit D5/D10, #576).
- A per-metric aggregate (worst downside / best upside / largest impact across parameters),
  in the shape ``analytics.casper.casper_payload._tail_risk_from_metadata`` consumes.

What the live path does NOT compute:
- Distributional **VaR (P5/P10), CVaR / expected-shortfall, or covenant-breach probability**.
  Those require Monte Carlo trial arrays per case, which a one-way tornado does not have.
  The ``_build_case_tail_snapshot`` / ``_cvar`` / ``_prob_breach`` helpers below implement
  that distributional path, but they are a SEPARATE, currently-unwired API: a caller must
  attach per-case MC arrays to each scenario's metadata and call the snapshot builder
  explicitly. They are NOT invoked by ``enrich_suite_with_tail_risk``, and the tornado
  snapshot must not be read as if it produced VaR/CVaR/breach (audit D5, #576). For real
  distributional tail risk, use the Monte Carlo engine (``analytics.mc``).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

import numpy as np

from analytics.contracts_v14 import SensitivitySuite, TornadoResult


@dataclass(frozen=True)
class TailRiskConfig:
    # The live tornado enrichment (`enrich_suite_with_tail_risk`) uses only `enabled`.
    # `percentiles` / `cvar_alpha` / `dscr_floor` / `require_trials` parameterize the
    # SEPARATE, currently-unwired distributional path (`_build_case_tail_snapshot`) that
    # needs per-case Monte Carlo trial arrays; they are NOT consumed by the tornado
    # snapshot and are no longer echoed into it (audit D5, #576).
    enabled: bool = True
    percentiles: Tuple[int, int, int] = (5, 10, 95)  # downside p5/p10; upside p95
    cvar_alpha: float = 0.05
    dscr_floor: float = 1.30
    # If True, expects raw trial arrays present for accurate stats.
    require_trials: bool = True


def _percentile(arr: np.ndarray, p: int) -> float:
    return float(np.percentile(arr, int(p)))


def _cvar(arr: np.ndarray, alpha: float) -> float:
    """
    CVaR / Expected Shortfall (ES) on the downside:
    mean of values <= VaR_alpha

    Small-sample caveat: the tail mean rests on only ~alpha * n trials — at
    n=1000 an alpha of 0.01 averages ~10 raw trials (noisy for a covenant or
    pricing input), and ES converges slower than the mean; a tight mean CI from
    ``analytics.mc.convergence`` (#643) does not certify the tail.
    """
    if arr.size == 0:
        return float("nan")
    var = np.percentile(arr, alpha * 100.0)
    tail = arr[arr <= var]
    if tail.size == 0:
        return float(var)
    return float(tail.mean())


# Relative tolerance for the covenant-breach comparison. A dual-DSCR sculpt pins
# every trial's per-year minimum DSCR at the covenant floor *by construction*, so the
# resulting per-trial ``dscr_min`` array clusters at the floor to within floating-point
# representation noise (values like ``1.2999999999999996`` for a 1.30 floor, spread
# ~1e-16). A strict ``arr < floor`` miscounts that sub-ULP noise as covenant breaches
# and fabricates an 85-93% breach probability on a case whose TRUE breach probability is
# 0.0 (#657, Fable blocker). ``1e-9`` relative is many orders of magnitude above the
# ~1e-16 pin scatter yet far below any economically-meaningful DSCR margin (0.001 of a
# 1.30 covenant is 0.0013), so a value counts as a breach only if it is below the floor
# by more than representation noise. Mirrors ``numpy.isclose``'s default ``rtol`` scale.
_PROB_BREACH_RTOL: float = 1e-9


def _prob_breach(arr: np.ndarray, floor: float) -> float:
    """Fraction of trials that breach ``floor``, robust to floating-point pin noise.

    A trial counts as a breach only when it sits below ``floor`` by *more than*
    representation noise: ``arr < floor`` **and not** ``np.isclose(arr, floor)`` at
    ``_PROB_BREACH_RTOL``. Without the tolerance, a sculpted-amortization DSCR array
    pinned at the covenant floor (all trials within ~1e-16 of the floor, some just
    below it) would report a spurious 85-93% breach probability where the true value is
    0.0 (#657). The tolerance is representation-noise-scale (1e-9 relative), far tighter
    than any real DSCR margin, so genuine breaches below the floor are still counted.
    """
    if arr.size == 0:
        return float("nan")
    floor_f = float(floor)
    below = arr < floor_f
    at_floor = np.isclose(arr, floor_f, rtol=_PROB_BREACH_RTOL, atol=0.0)
    return float(np.mean(below & ~at_floor))


def _is_pinned_at_floor(arr: np.ndarray, floor: float) -> bool:
    """Whether every trial's min-DSCR sits at the covenant floor (sculpt degeneracy).

    A dual-DSCR sculpt sets each year's debt service so the binding DSCR equals the
    covenant floor, which makes the per-trial *minimum* DSCR invariant at that floor to
    within floating-point noise. When that holds, the min-DSCR breach probability is a
    structural 0.0 and carries no distributional signal — the caller discloses that
    rather than presenting an uninformative statistic as if it were a risk read (#657).
    Uses the same ``_PROB_BREACH_RTOL`` representation-noise scale as the breach count.
    """
    if arr.size == 0:
        return False
    return bool(np.all(np.isclose(arr, float(floor), rtol=_PROB_BREACH_RTOL, atol=0.0)))


def enrich_suite_with_tail_risk(
    *,
    suite: SensitivitySuite,
    base_config: Mapping[str, Any],
    run_cfg: TailRiskConfig = TailRiskConfig(),
) -> SensitivitySuite:
    """Enrich ``suite.metadata`` with lender-grade tail-risk blocks.

    Produces two complementary views and attaches them to the suite metadata:

    * ``metadata["tail_risk"]`` — a per-parameter table (one row per tornado)
      carrying the base value plus the downside/upside/impact observed across
      that parameter's shocks.
    * ``metadata["tail_risk_summary"]`` — a ``{metric_name: {snapshot}}``
      mapping aggregating the worst downside / best upside / largest impact
      across all parameters. This is the shape consumed by
      :func:`analytics.casper.casper_payload._tail_risk_from_metadata`, so the
      CASPER payload can surface it directly (a flat run-summary would have been
      silently dropped by that consumer).

    The suite is a frozen dataclass, so a new instance carrying the enriched
    metadata is returned rather than mutating in place.

    Note:
        Snapshots are derived from the suite's tornado/shock data. For full
        distributional VaR/CVaR from Monte Carlo trial arrays, see the
        ``_build_case_tail_snapshot`` trial-array path below — a caller can wire
        it once per-case MC arrays are attached to each scenario's metadata.
    """
    if not run_cfg.enabled:
        return suite

    md = dict(getattr(suite, "metadata", {}) or {})

    tail_table: list[dict[str, Any]] = []
    summary: dict[str, Any] = {}

    # SensitivitySuite shape (single metric). An empty tornado set leaves both
    # blocks empty rather than fabricating a snapshot.
    if getattr(suite, "tornado_results", None):
        metric_key = str(suite.metric)
        rows = [
            _tornado_tail_stats(tornado=tornado) for tornado in suite.tornado_results
        ]
        tail_table.extend(rows)
        summary[metric_key] = _aggregate_metric_snapshot(rows=rows, run_cfg=run_cfg)

    md["tail_risk"] = tail_table
    md["tail_risk_summary"] = summary

    # SensitivitySuite is a frozen dataclass — build a new instance carrying the
    # enriched metadata rather than mutating in place. A prior setattr-based
    # implementation always raised FrozenInstanceError (silently caught),
    # dropping the tail-risk enrichment entirely.
    return replace(suite, metadata=md)


def _tornado_tail_stats(*, tornado: TornadoResult) -> dict[str, Any]:
    """Honest per-parameter tail snapshot from a tornado's shock results.

    ``downside`` / ``upside`` are keyed to the KPI OUTCOME, not the shock direction:
    the worst and best KPI achieved across ALL of this parameter's shock cases (both
    ``low_case`` and ``high_case``). Keying by direction — ``min(low_case)`` /
    ``max(high_case)`` — inverted the labels for cost drivers (CAPEX/opex/rate), whose
    low-cost case is the *better* outcome (audit D5/D10, #576). ``impact_abs`` fields are
    optional on :class:`~analytics.contracts_v14.ShockResult`, so missing values are
    skipped; a tornado with no usable shocks collapses to its base value.
    """
    base = float(tornado.base_metric)
    cases = [
        c
        for s in tornado.shock_results
        for c in (s.low_case, s.high_case)
        if c is not None
    ]
    impacts = [s.impact_abs for s in tornado.shock_results if s.impact_abs is not None]
    return {
        "parameter": str(tornado.label or tornado.metric_name),
        "metric": str(tornado.metric_name),
        "base_value": base,
        "downside": float(min(cases)) if cases else base,
        "upside": float(max(cases)) if cases else base,
        "worst_impact_abs": (
            float(max(impacts)) if impacts else float(tornado.impact_abs)
        ),
        "n_shocks": len(tornado.shock_results),
    }


def _aggregate_metric_snapshot(
    *,
    rows: Sequence[Mapping[str, Any]],
    run_cfg: TailRiskConfig,
) -> dict[str, Any]:
    """Aggregate per-parameter rows into one per-metric tail snapshot.

    Shaped for the CASPER consumer (``{metric_name: {snapshot}}``): the worst downside /
    best upside / largest impact across all parameters. It deliberately does NOT echo
    ``cvar_alpha`` / ``percentiles`` / ``dscr_floor``: the tornado path computes no VaR,
    CVaR, or breach probability, so surfacing those config knobs implied a distributional
    computation that never happened (audit D5, #576). ``run_cfg`` is retained for the
    unwired MC-backed distributional path, not consumed here beyond ``enabled``.
    """
    base = float(rows[0]["base_value"]) if rows else float("nan")
    downsides = [float(r["downside"]) for r in rows]
    upsides = [float(r["upside"]) for r in rows]
    impacts = [float(r["worst_impact_abs"]) for r in rows]
    return {
        "base_value": base,
        "downside": min(downsides) if downsides else base,
        "upside": max(upsides) if upsides else base,
        "worst_impact_abs": max(impacts) if impacts else 0.0,
        "n_parameters": len(rows),
    }


def _extract_trials_from_case(
    case: Mapping[str, Any], metric_key: str
) -> Optional[np.ndarray]:
    meta = case.get("metadata", None)
    if not isinstance(meta, Mapping):
        return None
    for bucket in ("trials", "mc_trials"):
        b = meta.get(bucket, None)
        if isinstance(b, Mapping) and metric_key in b:
            arr = np.asarray(b[metric_key], dtype=float)
            if arr.ndim != 1:
                arr = arr.reshape(-1)
            return arr
    return None


def _build_case_tail_snapshot(
    *,
    case: Mapping[str, Any],
    metric_keys: Sequence[str],
    run_cfg: TailRiskConfig,
) -> Dict[str, Any]:
    label = str(case.get("label", "case"))
    rows: list[dict[str, Any]] = []

    for m in metric_keys:
        arr = _extract_trials_from_case(case, m)
        if arr is None:
            if run_cfg.require_trials:
                # No trials => can't compute credible VaR/CVaR
                rows.append(
                    {
                        "case": label,
                        "metric": m,
                        "note": "no_trials",
                    }
                )
                continue

            # fallback: single-point value only
            v = case.get("value", None)
            if v is None and "values" in case:
                v = case["values"].get(m, None)
            rows.append(
                {
                    "case": label,
                    "metric": m,
                    "p5": float("nan"),
                    "p10": float("nan"),
                    "p95": float("nan"),
                    "cvar": float("nan"),
                    "value": float(v) if v is not None else float("nan"),
                }
            )
            continue

        row: Dict[str, Any] = {
            "case": label,
            "metric": m,
            "p5": _percentile(arr, 5),
            "p10": _percentile(arr, 10),
            "p95": _percentile(arr, 95),
            "cvar": _cvar(arr, run_cfg.cvar_alpha),
            "mean": float(arr.mean()),
            "std": float(arr.std(ddof=1)) if arr.size > 1 else 0.0,
        }
        # covenant breach probability for DSCR-like metrics
        if "dscr" in m.lower():
            row["prob_breach"] = _prob_breach(arr, run_cfg.dscr_floor)
            row["dscr_floor"] = float(run_cfg.dscr_floor)
            if _is_pinned_at_floor(arr, run_cfg.dscr_floor):
                # Disclose-don't-mislead: a dual-DSCR sculpt makes the per-trial
                # minimum DSCR invariant at the covenant floor by construction, so
                # prob_breach here is 0.0 and carries no distributional information.
                # The informative lender tail lives in LLCR/PLCR and the balloon,
                # not in min-DSCR. Say so on the row (#657).
                row["degeneracy"] = "dscr_min_pinned_at_floor"
                row["degeneracy_note"] = (
                    "Sculpted amortization pins per-trial min-DSCR at the covenant "
                    "floor by construction; prob_breach is 0.0 and non-informative. "
                    "Read the distributional lender tail from LLCR/PLCR and the "
                    "balloon, not min-DSCR."
                )

        rows.append(row)

    return {"rows": rows}
