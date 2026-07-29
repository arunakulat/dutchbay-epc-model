"""Opt-in second-source cross-validation of the ERA5 wind resource (disclose-don't-mutate).

The deep-research benchmarking report flagged that the bankable wind resource rests on a
SINGLE reanalysis (ERA5) with no independent second-source sanity check — ERA5 generally
beats MERRA-2 / NEWA but disagrees by terrain and time-of-day, and a lender wants that
disagreement disclosed, not hidden. This module closes that gap the same way
:mod:`wind_resource.arco_assessment` and :mod:`wind_resource.mcp` already do for their
respective concerns: a VALIDATE-mode comparison that surfaces the deviation of an
independent reference series against the declared ERA5 baseline and **never** mutates the
frozen resource.

Contract (identical in spirit to :func:`wind_resource.arco_assessment.build_arco_assessment`):

* :func:`build_crossval_assessment` takes an **injected** second-source hub-height
  wind-speed series (a ``pd.DataFrame`` the caller already ingested), fits a Weibull, runs
  the canonical analytic engine on that fit to get the *implied* CF / AEP, and reports the
  drift of the second source vs the scenario's declared ``wind_resource.weibull_a/k`` and
  vs the frozen ``resource.wind`` mean-ws / CF / AEP. ``mode`` is always ``"validate"``:
  it NEVER writes ``wind_resource.*``, ``resource.wind.*``, or the frozen AEP export. It is
  a pure function on the injected series, so CI exercises it with zero network (exactly like
  :func:`build_arco_assessment` on synthetic series in
  ``tests/wind/test_arco_assessment_coverage.py``).
* :func:`crossval_settings` resolves the opt-in ``resource.crossval`` config, returning
  ``None`` when the block is absent or ``enabled`` is falsy — so committed scenarios that do
  not declare it are byte-identical (the disclosure block simply does not exist).
* :func:`load_reference_series` / :func:`fetch_merra2_series` are the LIVE ingest path,
  behind a CASPER call-time ``requests`` guard (``requests`` is already a base dependency,
  so this adds NO new import-time dependency; the guard keeps HTTP out of module import). The
  Sri Lanka flagship site (Kalpitiya, ~8.27N/79.75E) is served by MERRA-2 via the no-auth
  NASA POWER endpoint or a user-supplied local series file; NEWA is EU-coverage-only and is
  a labelled ``source_type`` only, never fetched. Nothing here needs a NASA Earthdata
  account or any credentialed/paid API — if that ever changes, the fetch must STOP and the
  user be asked before adding such a dependency.

GWTF: config-first, fully typed, no hardcoded site constants, no argparse, no new hard deps.
"""

from __future__ import annotations

import copy
import logging
from typing import Any, Dict, Mapping, Optional, Sequence

import pandas as pd

from wind_resource.weibull_fit import WeibullFit, fit_weibull_on_series, weibull_drift

logger = logging.getLogger(__name__)


def _require(mapping: Mapping[str, Any], *keys: str) -> Any:
    """Fetch a nested key, raising a precise KeyError instead of defaulting silently.

    Mirrors :func:`wind_resource.arco_assessment._require` (CESSPIT: no silent defaults on
    identity fields); kept local so this module carries no cross-module private coupling.
    """
    cur: Any = mapping
    trail: list[str] = []
    for key in keys:
        trail.append(key)
        if not isinstance(cur, Mapping) or key not in cur:
            raise KeyError(
                "Missing required config key '"
                + ".".join(trail)
                + "' for the wind cross-validation (no silent default — fix the scenario)."
            )
        cur = cur[key]
    return cur


def _implied_aep(scenario: Mapping[str, Any], fit: WeibullFit) -> Dict[str, Any]:
    """Run the canonical analytic engine on the FITTED second-source Weibull (a cross-check).

    Substitutes ``(A_fit, k_fit)`` into a DEEP COPY of the scenario and regenerates the AEP
    summary, so the caller sees the CF / AEP the second source *would* imply — without
    mutating the real scenario. Same technique as
    :func:`wind_resource.arco_assessment._implied_aep`; the analytic engine import is local
    to keep this module import-light.
    """
    from analytics.wind.aep_summary_builder import build_aep_summary_from_config

    probe = copy.deepcopy(dict(scenario))
    probe["wind_resource"] = dict(probe.get("wind_resource", {}))
    probe["wind_resource"]["weibull_a"] = fit.weibull_a
    probe["wind_resource"]["weibull_k"] = fit.weibull_k
    summary = build_aep_summary_from_config(probe)
    return {
        "net_aep_gwh": summary["net_site_aep_gwh"],
        "gross_aep_gwh": summary["gross_aep_gwh"],
        "capacity_factor": summary["capacity_factor"],
    }


#: Recognised second-source labels. ``merra2`` is the implemented fetchable source for the
#: Sri Lanka flagship site (no-auth NASA POWER); ``local`` is a user-supplied series file
#: (no network); ``newa`` is a documented EU-coverage-only label that is NEVER fetched here.
MERRA2: str = "merra2"
LOCAL: str = "local"
NEWA: str = "newa"
CROSSVAL_SOURCES: tuple[str, ...] = (MERRA2, LOCAL, NEWA)

#: Fetchable sources (a live series can be retrieved). ``newa`` and ``local`` are not
#: fetched by this module: NEWA is EU-only (out of scope for the SL site) and ``local``
#: is supplied by the caller as a file path.
FETCHABLE_SOURCES: tuple[str, ...] = (MERRA2,)

_DEFAULT_DRIFT_TOLERANCE_PCT: float = 5.0

#: NASA POWER hourly point endpoint — the no-authentication community-science API that
#: serves MERRA-2-derived meteorology (10 m / 50 m winds). Kept as a module constant so the
#: fetch path has NO hardcoded URL buried in a function and can be swapped in config later.
NASA_POWER_HOURLY_URL: str = "https://power.larc.nasa.gov/api/temporal/hourly/point"


def crossval_settings(config: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    """Resolve the opt-in ``resource.crossval`` settings, or ``None`` when it is off.

    Returns a resolved dict (``source_type``, ``drift_tolerance_pct``, plus the raw
    ``series_path`` / fetch knobs) only when ``resource.crossval.enabled`` is truthy;
    otherwise ``None`` so the caller keeps the pure ERA5 path (the default — committed
    scenarios are byte-identical, and the disclosure block simply does not exist).

    Strict resolution (CESSPIT — no silent defaults on identity fields):

    * ``source_type`` is REQUIRED and must be one of :data:`CROSSVAL_SOURCES`.
    * ``drift_tolerance_pct``, when present, must be a positive finite number.
    * ``enabled`` must be a boolean (a non-boolean is a fail-loud ``ValueError``, not a
      truthiness coercion).
    """
    resource = config.get("resource", {}) if isinstance(config, Mapping) else {}
    crossval = resource.get("crossval") if isinstance(resource, Mapping) else None
    if not isinstance(crossval, Mapping):
        return None
    enabled = crossval.get("enabled", False)
    if not isinstance(enabled, bool):
        raise ValueError(
            "resource.crossval.enabled must be a boolean; got " f"{enabled!r}"
        )
    if not enabled:
        return None

    source_type = str(_require(crossval, "source_type")).strip().lower()
    if source_type not in CROSSVAL_SOURCES:
        raise ValueError(
            f"resource.crossval.source_type={source_type!r} is invalid; choose from "
            f"{CROSSVAL_SOURCES}"
        )

    tol_raw = crossval.get("drift_tolerance_pct", _DEFAULT_DRIFT_TOLERANCE_PCT)
    try:
        tol = float(tol_raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "resource.crossval.drift_tolerance_pct must be a number; got "
            f"{tol_raw!r}"
        ) from exc
    if not tol > 0.0:
        raise ValueError(
            "resource.crossval.drift_tolerance_pct must be > 0; got " f"{tol_raw!r}"
        )

    return {
        "source_type": source_type,
        "drift_tolerance_pct": tol,
        "series_path": crossval.get("series_path"),
        "ws_column": crossval.get("ws_column"),
        "source_id": crossval.get("source_id"),
    }


def _relative_pct(reference: float, declared: float) -> Optional[float]:
    """``100 * (reference - declared) / declared`` (m/s / CF / AEP deviation), or ``None``.

    Returns ``None`` when ``declared`` is non-positive so a zero/absent baseline yields an
    explicit null rather than a divide-by-zero or a misleading number.
    """
    if declared is None or float(declared) == 0.0:
        return None
    return round(100.0 * (float(reference) - float(declared)) / float(declared), 3)


def build_crossval_assessment(
    reference_series: pd.DataFrame,
    scenario: Mapping[str, Any],
    ws_column: str,
    *,
    source_type: str,
    source_id: str | None = None,
    drift_tolerance_pct: float | None = None,
    vintage: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    """Cross-validate an injected second-source series against the declared ERA5 baseline.

    Fits a Weibull on ``reference_series[ws_column]``, computes the analytic CF / AEP the
    fit *would* imply (via the canonical engine, on a throwaway scenario copy), and reports
    the deviation vs the scenario's declared ``wind_resource.weibull_a/k`` and the frozen
    ``resource.wind`` mean-ws / CF / AEP. Nothing is mutated; ``mode`` is always
    ``"validate"`` — this is a DISCLOSURE block only, never a re-baseline. Adopting a second
    source is a deliberate, dated config edit, exactly as for the ARCO / MCP paths.

    Args:
        reference_series: The independent (e.g. MERRA-2) hub-height wind-speed series.
        scenario: The v14 scenario (declares the ERA5 baseline being validated).
        ws_column: The wind-speed column in ``reference_series`` to fit.
        source_type: One of :data:`CROSSVAL_SOURCES` (``merra2`` / ``local`` / ``newa``).
        source_id: Optional provenance label for the second source (e.g. a dataset id).
        drift_tolerance_pct: Override the tolerance; defaults to the scenario's
            ``resource.crossval.drift_tolerance_pct`` or :data:`_DEFAULT_DRIFT_TOLERANCE_PCT`.
        vintage: Optional retrieval-provenance block threaded into the result verbatim.

    Returns:
        A structured ``mode:"validate"`` disclosure: the second-source Weibull fit, its
        implied AEP, the Weibull drift vs declared, and the mean-ws / CF / AEP deviations vs
        the frozen ``resource.wind`` block.

    Raises:
        ValueError: if ``source_type`` is not recognised.
        KeyError: if the declared Weibull / ``resource.wind`` baseline is absent.
    """
    st = str(source_type).strip().lower()
    if st not in CROSSVAL_SOURCES:
        raise ValueError(
            f"source_type={source_type!r} is invalid; choose from {CROSSVAL_SOURCES}"
        )

    wind_resource = _require(scenario, "wind_resource")
    a_declared = float(_require(wind_resource, "weibull_a"))
    k_declared = float(_require(wind_resource, "weibull_k"))
    wind_block = _require(_require(scenario, "resource"), "wind")

    tol = (
        float(drift_tolerance_pct)
        if drift_tolerance_pct is not None
        else float(
            _require(scenario, "resource")
            .get("crossval", {})
            .get("drift_tolerance_pct", _DEFAULT_DRIFT_TOLERANCE_PCT)
        )
    )

    fit = fit_weibull_on_series(reference_series, ws_column)
    drift = weibull_drift(fit.weibull_a, fit.weibull_k, a_declared, k_declared, tol)
    implied = _implied_aep(scenario, fit)

    # Deviation of the second source vs the FROZEN resource.wind headline. These are the
    # numbers a lender reads: is the independent source materially above/below the bankable
    # basis? `.get` (not `_require`) so a slimmer wind block still yields a partial disclosure
    # rather than raising — the drift-vs-declared above is the hard baseline.
    declared_mean_ws = wind_block.get("ws150_mean_ms")
    declared_cf = wind_block.get("capacity_factor")
    declared_aep = wind_block.get("aep_gwh")
    deviation = {
        "mean_ws_pct": (
            _relative_pct(fit.mean_ws_ms, declared_mean_ws)
            if declared_mean_ws is not None
            else None
        ),
        "capacity_factor_pct": (
            _relative_pct(implied["capacity_factor"], declared_cf)
            if declared_cf is not None
            else None
        ),
        "aep_pct": (
            _relative_pct(implied["net_aep_gwh"], declared_aep)
            if declared_aep is not None
            else None
        ),
    }

    if not drift.within_tolerance:
        logger.warning(
            "%s cross-validation Weibull drift exceeds %.1f%%: A %+.2f%% / k %+.2f%% vs "
            "declared ERA5 (A=%.2f,k=%.2f). Declared baseline UNCHANGED (VALIDATE mode); "
            "adopt only via a deliberate dated re-baseline.",
            st,
            tol,
            drift.a_drift_pct,
            drift.k_drift_pct,
            a_declared,
            k_declared,
        )

    return {
        "mode": "validate",
        "source_type": st,
        "source_id": source_id,
        "weibull_fit": fit.as_dict(),
        "drift": drift.as_dict(),
        "implied_aep": implied,
        "deviation_vs_declared": deviation,
        "declared_wind_block": dict(wind_block),
        "vintage": dict(vintage) if vintage is not None else None,
    }


def fetch_merra2_series(
    latitude: float,
    longitude: float,
    start_year: int,
    end_year: int,
    *,
    ws_column: str,
    timeout_s: float = 60.0,
) -> pd.DataFrame:
    """Fetch a MERRA-2-derived hourly wind-speed series for a point (no-auth NASA POWER).

    Uses the community-science NASA POWER hourly-point API (:data:`NASA_POWER_HOURLY_URL`),
    which serves MERRA-2 meteorology with **no** authentication, no Earthdata account, and no
    paid tier — so this stays inside the issue's guard rail (if a source ever required
    credentials or payment, the fetch must STOP and the user be asked first).

    The ``requests`` import is CASPER call-time-guarded so this module imports cleanly
    without any HTTP dependency and CI never touches the network (tests inject a synthetic
    series into :func:`build_crossval_assessment` directly).

    Args:
        latitude / longitude: Site centroid (decimal degrees).
        start_year / end_year: Inclusive calendar-year span to request.
        ws_column: Column name to store the resulting wind speed under.
        timeout_s: HTTP timeout (seconds).

    Returns:
        A ``pd.DataFrame`` with a single ``ws_column`` of hourly wind speeds (m/s).

    Raises:
        ImportError: if ``requests`` is somehow absent from the environment (it is a base
            dependency, so this guard is defensive — the import stays call-time only so this
            module imports even in a stripped env and CI never touches HTTP).
        RuntimeError: if the endpoint returns no usable wind field.
    """
    try:
        # Call-time (CASPER) so importing this module never pulls HTTP. The ignore mirrors
        # the cdsapi probe in run_full_pipeline_v14.py: requests ships no type stubs, so
        # mypy raises import-untyped once it is installed (the common case); import-not-found
        # covers a stripped env, and unused-ignore keeps the suppression silent either way.
        import requests  # type: ignore[import-not-found,import-untyped,unused-ignore]
    except ImportError as exc:  # pragma: no cover - defensive; requests is a base dep
        raise ImportError(
            "MERRA-2 cross-validation fetch requires 'requests' (a base dependency): "
            "pip install requests"
        ) from exc

    # NASA POWER expects YYYYMMDD bounds and the 50 m wind-speed parameter (WS50M), the
    # closest hub-relevant field the no-auth hourly product exposes.
    # Precise value type (str | float) so the request params satisfy the requests
    # stubs' SupportsItems[...] param type across stub versions — an inferred
    # dict[str, object] is rejected by newer types-requests (#992 group bump).
    params: dict[str, str | float] = {
        "parameters": "WS50M",
        "community": "RE",
        "longitude": float(longitude),
        "latitude": float(latitude),
        "start": f"{int(start_year)}0101",
        "end": f"{int(end_year)}1231",
        "format": "JSON",
    }
    logger.info(
        "Fetching MERRA-2 (NASA POWER) WS50M for (%.4f, %.4f) %d-%d",
        latitude,
        longitude,
        start_year,
        end_year,
    )
    resp = requests.get(NASA_POWER_HOURLY_URL, params=params, timeout=timeout_s)
    resp.raise_for_status()
    payload = resp.json()
    try:
        ws_map = payload["properties"]["parameter"]["WS50M"]
    except (KeyError, TypeError) as exc:
        raise RuntimeError(
            "NASA POWER response did not contain a WS50M wind field; cannot cross-validate"
        ) from exc

    values = [
        float(v)
        for v in ws_map.values()
        if v is not None and float(v) > -900.0  # POWER fill value is -999
    ]
    if not values:
        raise RuntimeError(
            "NASA POWER returned no usable WS50M values for the requested window"
        )
    return pd.DataFrame({ws_column: values})


def load_reference_series(
    settings: Mapping[str, Any],
    *,
    latitude: float | None = None,
    longitude: float | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
    ws_column: str,
) -> pd.DataFrame:
    """Ingest the second-source series for a resolved :func:`crossval_settings` block.

    Routing (CESSPIT — explicit, no silent fallbacks):

    * ``local`` — read the user-supplied CSV at ``settings['series_path']`` (no network).
    * ``merra2`` — fetch via :func:`fetch_merra2_series` (no-auth NASA POWER), needing the
      site centroid + year span passed in by the caller (kept out of this block so there is
      still one source of truth for lat/lon: ``resource.era5``).
    * ``newa`` — NOT fetched: NEWA covers Europe only, out of scope for the Sri Lanka site,
      so this raises with a pointer to supply a ``local`` series instead.

    Raises:
        ValueError: for ``newa`` (EU-only, not fetched here), a missing ``series_path`` on
            ``local``, or a ``merra2`` call missing the site/year arguments.
        FileNotFoundError: if the ``local`` series file does not exist.
    """
    source_type = str(_require(settings, "source_type")).strip().lower()

    if source_type == LOCAL:
        series_path = settings.get("series_path")
        if not series_path:
            raise ValueError(
                "resource.crossval.series_path is required for source_type='local'"
            )
        frame = pd.read_csv(series_path)
        if ws_column not in frame.columns:
            raise ValueError(
                f"local cross-validation series has no column {ws_column!r}; got "
                f"{list(frame.columns)}"
            )
        return frame

    if source_type == MERRA2:
        missing = [
            n
            for n, v in (
                ("latitude", latitude),
                ("longitude", longitude),
                ("start_year", start_year),
                ("end_year", end_year),
            )
            if v is None
        ]
        if missing:
            raise ValueError(
                "MERRA-2 cross-validation fetch needs the site centroid + year span "
                f"(missing: {', '.join(missing)}); resolve them from resource.era5"
            )
        return fetch_merra2_series(
            float(latitude),  # type: ignore[arg-type]
            float(longitude),  # type: ignore[arg-type]
            int(start_year),  # type: ignore[arg-type]
            int(end_year),  # type: ignore[arg-type]
            ws_column=ws_column,
        )

    # NEWA (or anything else that slipped past the settings gate): not fetched here.
    raise ValueError(
        f"source_type={source_type!r} is not fetchable by this module. NEWA covers Europe "
        "only (the flagship site is Kalpitiya, Sri Lanka), so supply a local series "
        "(source_type: local, series_path: ...) instead."
    )


def summarise_deviation(deviation: Mapping[str, Optional[float]]) -> Sequence[str]:
    """Human-readable one-liners for a ``deviation_vs_declared`` block (report helper)."""
    labels = {
        "mean_ws_pct": "mean wind speed",
        "capacity_factor_pct": "capacity factor",
        "aep_pct": "AEP",
    }
    lines: list[str] = []
    for key, label in labels.items():
        val = deviation.get(key)
        if val is None:
            lines.append(f"{label}: n/a (no declared baseline)")
        else:
            lines.append(f"{label}: {val:+.2f}% vs declared ERA5")
    return lines


__all__ = [
    "MERRA2",
    "LOCAL",
    "NEWA",
    "CROSSVAL_SOURCES",
    "FETCHABLE_SOURCES",
    "NASA_POWER_HOURLY_URL",
    "crossval_settings",
    "build_crossval_assessment",
    "fetch_merra2_series",
    "load_reference_series",
    "summarise_deviation",
]
