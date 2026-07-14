"""Provenance-bearing historical USD/LKR series loader for FX calibration.

This is the *historical-series* analogue of :mod:`analytics.fx.fx_fetch` (which
resolves a single pinned SPOT vintage). Where ``fx_fetch`` anchors today's rate,
this module loads the long daily history used to CALIBRATE the Monte-Carlo FX
driver (drift + volatility + crisis regimes), replacing the previously hand-set
uniform bound ``fx.start_lkr_per_usd ∈ [300, 367]`` that carried zero empirical
provenance.

Design (mirrors the ERA5 / ``fx_fetch`` vintage pattern):

* **FIXED vintage (default, reproducible, offline).** :func:`load_pinned_history`
  reads a committed CSV + a JSON provenance sidecar from ``inputs/fxdata/`` and
  verifies the CSV's SHA-256 against the sidecar. No network is touched, so lender
  runs and CI are deterministic. The provenance ``provider`` must be an APPROVED
  source (CESSPIT / ARCH-01) — the FX analogue of the wind-AEP APPROVED_SOURCES
  guard, closing the asymmetry where the wind resource had a provenance gate but
  the FX assumption did not.

* **LATEST (exploratory refresh).** :func:`fetch_live_history_bis` /
  :func:`fetch_live_history_fred` pull the live series from a keyless provider and
  return it for re-pinning (a deliberate, dated edit), never an automatic mutation.

* **VALIDATE drift.** :func:`validate_history_drift` compares the pinned series'
  latest level to a freshly fetched one and reports the drift — never mutates.

The pinned backbone is **BIS XRU** (keyless SDMX REST, daily ``D.LK.LKR.A`` from
1973), chosen because it is reachable and reproducible; **FRED DEXSLUS** is the
research-preferred backbone (Fed H.10 noon-NYC) and is supported as an alternate
live provider. Both are independent of CBSL's official daily indicative spot
(CBSL is the authoritative *reference*, documented but JS-rendered), so recent
levels should be reconciled to CBSL where exactness matters.
"""

from __future__ import annotations

import csv
import datetime as _dt
import hashlib
import json
import logging
import math
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

logger = logging.getLogger(__name__)

# Repo root: analytics/fx/fx_history.py -> analytics/fx -> analytics -> root
_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_VINTAGE_CSV = _REPO_ROOT / "inputs" / "fxdata" / "usdlkr_daily_bis_vintage.csv"
DEFAULT_VINTAGE_PROVENANCE = (
    _REPO_ROOT / "inputs" / "fxdata" / "usdlkr_daily_bis_vintage.provenance.json"
)

#: Sources whose provenance is acceptable for FX calibration (CESSPIT / ARCH-01).
#: Mirrors the wind-AEP APPROVED_SOURCES gate. A pinned vintage whose declared
#: provider is not in this set is REJECTED rather than silently calibrated on.
APPROVED_FX_SOURCES = frozenset({"BIS", "FRED", "CBSL", "IMF"})

# Keyless live endpoints (used only by the LATEST refresh path; never by CI).
BIS_DAILY_ENDPOINT = "https://stats.bis.org/api/v2/data/dataflow/BIS/WS_XRU/1.0/D.LK.LKR.A?format=jsondata"
FRED_DEXSLUS_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DEXSLUS"

#: Default trailing window (years) for a periodic refresh. The user asked for "20
#: years past data as of TODAY"; a 10-year window is accepted as a more
#: crisis-weighted alternative (it spans the 2022 float but drops the calm
#: 2005–2014 stretch, so it reports higher drift/vol).
DEFAULT_WINDOW_YEARS = 20

#: Provider-stable descriptor fields — the single source for the sidecar's
#: DESCRIPTOR fields (series/dataset/sdmx_key/collection/endpoint/
#: authoritative_reference/preferred_live_backbone). The per-vintage fields
#: (provider/frequency/unit/rows/date_range/latest_value/fetched_as_of/sha256/
#: window_years/notes) are filled per refresh from the fetched series. These
#: descriptors reproduce the committed BIS sidecar exactly (CCCDIR; guarded by
#: tests/analytics/test_fx_calibration.py::test_generator_reproduces_committed_descriptors).
#: ``endpoint`` is the stable dataset URL WITHOUT the volatile response-format
#: query (``fetch_live_history_bis`` appends ``?format=jsondata`` at request time).
_PROVIDER_METADATA: dict[str, dict[str, Any]] = {
    "BIS": {
        "series": "USD/LKR daily spot exchange rate",
        "dataset": "WS_XRU",
        "sdmx_key": "D.LK.LKR.A",
        "endpoint": "https://stats.bis.org/api/v2/data/dataflow/BIS/WS_XRU/1.0/D.LK.LKR.A",
        "collection": "A — average of observations through period",
        "authoritative_reference": (
            "CBSL daily indicative USD/LKR spot "
            "(https://www.cbsl.gov.lk/en/rates-and-indicators/exchange-rates/daily-indicative-usd-spot-exchange-rates) "
            "— BIS is an aggregator one step removed; reconcile recent levels to CBSL where exactness matters."
        ),
        "preferred_live_backbone": (
            "FRED DEXSLUS (https://fred.stlouisfed.org/graph/fredgraph.csv?id=DEXSLUS) — daily Fed H.10 "
            "noon-NYC quote; preferred per research but network-restricted from the build environment, so "
            "BIS (keyless, reachable, full-window) is the pinned backbone. fx_history supports FRED as an "
            "alternate live provider."
        ),
    },
    "FRED": {
        "series": "USD/LKR daily noon-NYC exchange rate (Fed H.10 DEXSLUS)",
        "dataset": "H.10",
        "sdmx_key": "DEXSLUS",
        "endpoint": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DEXSLUS",
        "collection": "Noon buying rate, New York",
        "authoritative_reference": (
            "CBSL daily indicative USD/LKR spot "
            "(https://www.cbsl.gov.lk/en/rates-and-indicators/exchange-rates/daily-indicative-usd-spot-exchange-rates) "
            "— reconcile recent levels to CBSL where exactness matters."
        ),
    },
}


@dataclass(frozen=True)
class FXHistorySeries:
    """A provenance-bearing historical USD/LKR series (LKR per 1 USD)."""

    provider: str
    frequency: str
    unit: str
    dates: tuple[str, ...]
    rates: tuple[float, ...]
    fetched_as_of: str
    source_endpoint: str
    sha256: str | None = None
    notes: str = ""
    provenance: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if len(self.dates) != len(self.rates):
            raise ValueError(
                f"FX history dates ({len(self.dates)}) and rates ({len(self.rates)}) "
                "must be equal length"
            )
        if not self.rates:
            raise ValueError("FX history series is empty")
        # Reject non-finite too: NaN passes a naive ``r <= 0`` check (NaN comparisons
        # are False), so guard explicitly (BIS carries US-holiday dates as NaN).
        if any((not math.isfinite(r)) or r <= 0 for r in self.rates):
            raise ValueError(
                "FX history contains a non-finite or non-positive rate "
                "(LKR per USD must be a finite value > 0)"
            )

    @property
    def latest(self) -> float:
        return self.rates[-1]

    @property
    def date_range(self) -> tuple[str, str]:
        return (self.dates[0], self.dates[-1])


def _coerce_rate(val: Any) -> float | None:
    """Parse a rate; return ``None`` for null/blank/non-numeric/non-finite/non-positive.

    The single definition of a "valid LKR/USD observation", shared by the CSV
    loader and the live fetchers. BIS carries US-holiday placeholders as ``NaN``
    and FRED as ``"."`` — both must be dropped, not fed to
    :class:`FXHistorySeries` (whose constructor rejects non-finite values).
    """
    if val is None:
        return None
    s = str(val).strip()
    if not s or s == ".":
        return None
    try:
        f = float(s)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(f) or f <= 0:
        return None
    return f


def _parse_csv_series(csv_path: Path) -> tuple[tuple[str, ...], tuple[float, ...]]:
    """Read a two-column ``date,lkr_per_usd`` CSV (header required), sorted by date."""
    rows: list[tuple[str, float]] = []
    with csv_path.open(newline="") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None or "date" not in reader.fieldnames:
            raise ValueError(
                f"FX vintage CSV {csv_path} must have a 'date' column header"
            )
        rate_col = (
            "lkr_per_usd"
            if "lkr_per_usd" in reader.fieldnames
            else reader.fieldnames[1]
        )
        for r in reader:
            d = (r.get("date") or "").strip()
            rate = _coerce_rate(r.get(rate_col))  # drops NaN/holiday placeholders
            if not d or rate is None:
                continue
            rows.append((d, rate))
    if not rows:
        raise ValueError(f"FX vintage CSV {csv_path} contained no data rows")
    rows.sort(key=lambda t: t[0])
    dates, rates = zip(*rows, strict=True)
    return tuple(dates), tuple(rates)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_pinned_history(
    csv_path: str | Path = DEFAULT_VINTAGE_CSV,
    provenance_path: str | Path = DEFAULT_VINTAGE_PROVENANCE,
    *,
    verify_sha256: bool = True,
) -> FXHistorySeries:
    """Load the committed FX history vintage with provenance + integrity checks.

    Raises:
        FileNotFoundError: the CSV or provenance sidecar is missing.
        ValueError: the provider is not in :data:`APPROVED_FX_SOURCES`, or the
            CSV's SHA-256 does not match the sidecar (tamper / stale-provenance).
    """
    csv_path = Path(csv_path)
    provenance_path = Path(provenance_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"FX vintage CSV not found: {csv_path}")
    if not provenance_path.exists():
        raise FileNotFoundError(
            f"FX vintage provenance sidecar not found: {provenance_path}"
        )

    prov: dict[str, Any] = json.loads(provenance_path.read_text())
    provider = str(prov.get("provider", "")).strip().upper()
    if provider not in APPROVED_FX_SOURCES:
        raise ValueError(
            f"FX vintage provider {provider!r} is not in APPROVED_FX_SOURCES "
            f"{sorted(APPROVED_FX_SOURCES)} — refuse to calibrate on an unprovenanced series "
            "(CESSPIT / ARCH-01)."
        )

    actual_sha = _sha256(csv_path)
    declared_sha = prov.get("sha256")
    if verify_sha256 and declared_sha and actual_sha != declared_sha:
        raise ValueError(
            f"FX vintage integrity check FAILED for {csv_path.name}: CSV sha256 {actual_sha[:16]}… "
            f"!= provenance sha256 {str(declared_sha)[:16]}…. Re-pin the vintage (deliberate dated "
            "edit) rather than editing the CSV in place."
        )

    dates, rates = _parse_csv_series(csv_path)
    return FXHistorySeries(
        provider=provider,
        frequency=str(prov.get("frequency", "daily")),
        unit=str(prov.get("unit", "LKR per 1 USD")),
        dates=dates,
        rates=rates,
        fetched_as_of=str(prov.get("fetched_as_of", "")),
        source_endpoint=str(prov.get("endpoint", "")),
        sha256=actual_sha,
        notes=str(prov.get("notes", "")),
        provenance=prov,
    )


def resolve_fx_history(config: Mapping[str, Any]) -> FXHistorySeries:
    """Resolve the FX history vintage for a scenario.

    Reads ``monte_carlo.fx_calibration.{vintage_csv, provenance_json}`` when present
    (paths relative to the repo root), else the committed default BIS vintage.
    """
    mc = config.get("monte_carlo") if isinstance(config, Mapping) else None
    fxc = mc.get("fx_calibration") if isinstance(mc, Mapping) else None
    csv_path: str | Path = DEFAULT_VINTAGE_CSV
    prov_path: str | Path = DEFAULT_VINTAGE_PROVENANCE
    if isinstance(fxc, Mapping):
        if fxc.get("vintage_csv"):
            csv_path = _REPO_ROOT / str(fxc["vintage_csv"])
        if fxc.get("provenance_json"):
            prov_path = _REPO_ROOT / str(fxc["provenance_json"])
    return load_pinned_history(csv_path, prov_path)


# ---------------------------------------------------------------------------
# LATEST refresh (network) — never used by CI; for deliberate re-pinning only
# ---------------------------------------------------------------------------


def fetch_live_history_bis(timeout_s: float = 60.0) -> FXHistorySeries:
    """Fetch the live BIS daily USD/LKR series (keyless SDMX REST)."""
    req = urllib.request.Request(
        BIS_DAILY_ENDPOINT,
        headers={
            "User-Agent": "dutchbay-fx/1.0",
            "Accept": "application/vnd.sdmx.data+json",
        },
    )
    with urllib.request.urlopen(
        req, timeout=timeout_s
    ) as resp:  # nosec B310 - fixed https BIS literal, not user input
        payload = json.loads(resp.read().decode("utf-8"))
    data = payload["data"]
    series_obj = next(iter(data["dataSets"][0]["series"].values()))
    observations = series_obj["observations"]
    dim_dates = [
        v["id"] for v in data["structure"]["dimensions"]["observation"][0]["values"]
    ]
    parsed: list[tuple[str, float]] = []
    for k, v in observations.items():
        if not v:
            continue
        rate = _coerce_rate(v[0])  # drop holiday/NaN placeholders (BIS carries NaN)
        if rate is None:
            continue
        parsed.append((dim_dates[int(k)], rate))
    if not parsed:
        raise ValueError("Live BIS fetch returned no finite observations")
    parsed.sort(key=lambda t: t[0])
    dates, rates = zip(*parsed, strict=True)
    return FXHistorySeries(
        provider="BIS",
        frequency="daily",
        unit="LKR per 1 USD",
        dates=tuple(dates),
        rates=tuple(rates),
        fetched_as_of=str(payload.get("meta", {}).get("prepared", "")),
        source_endpoint=BIS_DAILY_ENDPOINT,
        notes="Live BIS XRU D.LK.LKR.A fetch (re-pin deliberately).",
    )


def fetch_live_history_fred(timeout_s: float = 30.0) -> FXHistorySeries:
    """Fetch the live FRED DEXSLUS daily series (keyless CSV).

    Research-preferred backbone (Fed H.10 noon-NYC); may be network-restricted in
    some environments — :func:`fetch_live_history_bis` is the reachable fallback.
    """
    req = urllib.request.Request(
        FRED_DEXSLUS_CSV, headers={"User-Agent": "dutchbay-fx/1.0"}
    )
    with urllib.request.urlopen(
        req, timeout=timeout_s
    ) as resp:  # nosec B310 - fixed https FRED literal, not user input
        text = resp.read().decode("utf-8")
    pairs: list[tuple[str, float]] = []
    for line in text.splitlines()[1:]:
        if not line.strip():
            continue
        date_str, _, val = line.partition(",")
        rate = _coerce_rate(val)  # FRED marks holidays with '.'
        if rate is None:
            continue
        pairs.append((date_str.strip(), rate))
    if not pairs:
        raise ValueError("Live FRED fetch returned no finite observations")
    pairs.sort(key=lambda t: t[0])
    dates, rates = zip(*pairs, strict=True)
    return FXHistorySeries(
        provider="FRED",
        frequency="daily",
        unit="LKR per 1 USD",
        dates=tuple(dates),
        rates=tuple(rates),
        fetched_as_of=dates[-1],
        source_endpoint=FRED_DEXSLUS_CSV,
        notes="Live FRED DEXSLUS fetch (re-pin deliberately).",
    )


def validate_history_drift(
    pinned: FXHistorySeries, live: FXHistorySeries, tolerance_pct: float = 5.0
) -> dict[str, Any]:
    """Report drift of ``live`` latest vs ``pinned`` latest. Never mutates config."""
    drift_pct = 100.0 * (live.latest - pinned.latest) / pinned.latest
    within = abs(drift_pct) <= tolerance_pct
    if not within:
        logger.warning(
            "FX history VALIDATE: live %.3f LKR/USD drifts %+.2f%% from pinned %.3f "
            "(tolerance %.1f%%); pinned vintage UNCHANGED — re-pin only via a deliberate dated edit.",
            live.latest,
            drift_pct,
            pinned.latest,
            tolerance_pct,
        )
    return {
        "pinned_latest": round(pinned.latest, 4),
        "live_latest": round(live.latest, 4),
        "drift_pct": round(drift_pct, 3),
        "tolerance_pct": tolerance_pct,
        "within_tolerance": within,
    }


# ---------------------------------------------------------------------------
# PERIODIC REFRESH — re-pin a trailing-window vintage as-of TODAY (opt-in/manual)
# ---------------------------------------------------------------------------
#
# The user asked for "a periodical re-update of the FX rate sampling from BIS,
# based on 20 years past data as of TODAY (taking the date from a current-date
# module); 10 years acceptable if realistic. Give the user the OPTION to run this."
#
# This is a DELIBERATE, dated re-pin — never automatic, never touched by CI. It
# refreshes the calibration *vintage* (→ keeps the Monte-Carlo ``fx_calibrated``
# driver and the calibration report current). It does NOT mutate the deterministic
# scenario ``fx.annual_depr`` scalars; re-adopting a refreshed drift into scenarios
# is a separate, explicit step (a documented KPI re-baseline).


def _today() -> _dt.date:
    """Current date seam (the 'current-date module').

    Mirrors the established repo idiom (``wind_resource.arco_assessment`` /
    ``era5_retrieval`` both do ``datetime.date.today()`` for trailing windows).
    Factored out so the refresh is injectable/deterministic in offline tests.
    """
    return _dt.date.today()


def _window_start(as_of: _dt.date, window_years: int) -> _dt.date:
    """First day of the trailing ``window_years`` window ending at ``as_of``.

    Handles the Feb-29 corner (a non-leap start year) by clamping to Feb-28.
    """
    if window_years <= 0:
        raise ValueError(f"window_years must be a positive int, got {window_years!r}")
    try:
        return as_of.replace(year=as_of.year - window_years)
    except ValueError:
        return as_of.replace(year=as_of.year - window_years, day=28)


def filter_series_to_window(
    series: FXHistorySeries, start: _dt.date, end: _dt.date
) -> FXHistorySeries:
    """Return a new series restricted to the inclusive ``[start, end]`` date window.

    Dates are ISO ``YYYY-MM-DD`` (zero-padded) so lexicographic compare == chronological.
    """
    lo, hi = start.isoformat(), end.isoformat()
    kept = [
        (d, r) for d, r in zip(series.dates, series.rates, strict=True) if lo <= d <= hi
    ]
    if not kept:
        raise ValueError(
            f"No observations fall in the window [{lo}, {hi}] — refusing to write an "
            "empty vintage (check the window and the live series coverage)."
        )
    dates, rates = zip(*kept, strict=True)
    return FXHistorySeries(
        provider=series.provider,
        frequency=series.frequency,
        unit=series.unit,
        dates=tuple(dates),
        rates=tuple(rates),
        fetched_as_of=series.fetched_as_of,
        source_endpoint=series.source_endpoint,
        notes=series.notes,
    )


def _format_rate(rate: float) -> str:
    """Stable CSV rendering of a rate (4 dp, trailing zeros trimmed)."""
    return f"{rate:.4f}".rstrip("0").rstrip(".")


def _build_refresh_provenance(
    series: FXHistorySeries,
    *,
    window_years: int,
    as_of: _dt.date,
    sha256: str,
) -> dict[str, Any]:
    """Provenance sidecar for a refreshed vintage (provider descriptors + window)."""
    prov: dict[str, Any] = dict(_PROVIDER_METADATA.get(series.provider, {}))
    prov.update(
        {
            "provider": series.provider,
            # Stable dataset URL from the descriptor (no volatile ?format=); fall
            # back to the live request endpoint only for providers we don't pin.
            "endpoint": prov.get("endpoint") or series.source_endpoint,
            "frequency": series.frequency,
            "unit": series.unit,
            "rows": len(series.rates),
            "date_range": list(series.date_range),
            "latest_value": series.latest,
            "fetched_as_of": as_of.isoformat(),
            "window_years": window_years,
            "sha256": sha256,
            "notes": (
                f"Periodic trailing-{window_years}y refresh as of {as_of.isoformat()} "
                f"(re-pinned from live {series.provider}). Deliberate dated re-pin — never "
                "automatic, never touched by CI. The deterministic scenario fx.annual_depr "
                "scalars are NOT auto-updated by this refresh; re-adopting a refreshed drift "
                "into scenarios is a separate, explicit KPI re-baseline."
            ),
        }
    )
    return prov


def write_vintage(
    series: FXHistorySeries,
    csv_path: str | Path,
    provenance_path: str | Path,
    *,
    window_years: int,
    as_of: _dt.date,
) -> dict[str, Any]:
    """Write a vintage CSV + provenance sidecar and return a summary.

    The CSV is written with ``\\n`` newlines so the recomputed SHA-256 is stable
    cross-platform and matches what :func:`load_pinned_history` verifies on read.
    The provider must be in :data:`APPROVED_FX_SOURCES` (CESSPIT / ARCH-01).
    """
    if series.provider not in APPROVED_FX_SOURCES:
        raise ValueError(
            f"Refresh provider {series.provider!r} is not in APPROVED_FX_SOURCES "
            f"{sorted(APPROVED_FX_SOURCES)} — refuse to pin an unprovenanced series."
        )
    csv_path = Path(csv_path)
    provenance_path = Path(provenance_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    lines = ["date,lkr_per_usd"]
    lines.extend(
        f"{d},{_format_rate(r)}"
        for d, r in zip(series.dates, series.rates, strict=True)
    )
    csv_path.write_text("\n".join(lines) + "\n", newline="\n")

    # Re-read what actually landed on disk so the provenance describes the
    # ARTIFACT, not the in-memory series (the CSV rounds to 4dp). Building the
    # sidecar from the persisted rows keeps latest_value/rows/date_range exactly
    # consistent with the file the SHA-256 hashes.
    persisted_dates, persisted_rates = _parse_csv_series(csv_path)
    if len(persisted_rates) != len(series.rates):
        # Fail loud: rounding/parse must never silently drop or merge rows. This
        # is unreachable for real USD/LKR levels (~90-400 never round to "0"), but
        # the guard makes any future precision change a hard error, not a silent
        # data loss (CESSPIT).
        raise ValueError(
            f"write_vintage round-trip dropped rows: wrote {len(series.rates)} but "
            f"{len(persisted_rates)} persisted in {csv_path.name} — refusing to pin a "
            "vintage whose CSV disagrees with the source series."
        )
    persisted = FXHistorySeries(
        provider=series.provider,
        frequency=series.frequency,
        unit=series.unit,
        dates=persisted_dates,
        rates=persisted_rates,
        fetched_as_of=series.fetched_as_of,
        source_endpoint=series.source_endpoint,
        notes=series.notes,
    )

    sha = _sha256(csv_path)  # authoritative: hash the bytes on disk
    prov = _build_refresh_provenance(
        persisted, window_years=window_years, as_of=as_of, sha256=sha
    )
    provenance_path.write_text(json.dumps(prov, indent=2, ensure_ascii=False) + "\n")

    # Round-trip self-check: the file we just wrote must load + pass the guards.
    reloaded = load_pinned_history(csv_path, provenance_path)
    return {
        "written": True,
        "csv_path": str(csv_path),
        "provenance_path": str(provenance_path),
        "provider": persisted.provider,
        "rows": len(persisted.rates),
        "date_range": list(persisted.date_range),
        "latest_value": persisted.latest,
        "fetched_as_of": as_of.isoformat(),
        "window_years": window_years,
        "sha256": sha,
        "reloaded_latest": reloaded.latest,
    }


#: Provider -> default live fetcher for the refresh path.
_LIVE_FETCHERS: dict[str, Callable[[], FXHistorySeries]] = {
    "BIS": fetch_live_history_bis,
    "FRED": fetch_live_history_fred,
}


def refresh_pinned_vintage(
    *,
    window_years: int = DEFAULT_WINDOW_YEARS,
    provider: str = "BIS",
    as_of: _dt.date | None = None,
    csv_path: str | Path = DEFAULT_VINTAGE_CSV,
    provenance_path: str | Path = DEFAULT_VINTAGE_PROVENANCE,
    fetcher: Callable[[], FXHistorySeries] | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Re-pin the FX vintage to the trailing ``window_years`` window ending TODAY.

    This is the user-runnable periodic refresh. It fetches the live series from a
    keyless provider, restricts it to ``[today - window_years, today]``, and (unless
    ``dry_run``) overwrites the committed vintage CSV + provenance sidecar with a
    fresh SHA-256 and ``fetched_as_of``/``window_years`` stamps.

    Args:
        window_years: trailing window length (default 20; 10 accepted — more
            crisis-weighted). Must be a positive int.
        provider: ``"BIS"`` (default, keyless/reachable) or ``"FRED"``.
        as_of: the "current date" anchor; defaults to :func:`_today`.
        csv_path / provenance_path: targets (default = the committed vintage).
        fetcher: live-series source; defaults to the provider's keyless fetcher.
            Injectable so offline tests never touch the network.
        dry_run: fetch + window + report only; do NOT write the files.

    Returns:
        A summary dict (rows, date_range, sha256, fetched_as_of, ...). For a
        dry run, ``written`` is ``False`` and no files are touched.

    Note:
        Refreshing the vintage does NOT change the deterministic scenario
        ``fx.annual_depr`` scalars — those are a deliberate KPI baseline.
    """
    provider = provider.strip().upper()
    if window_years <= 0:
        raise ValueError(f"window_years must be a positive int, got {window_years!r}")
    if fetcher is None:
        fetcher = _LIVE_FETCHERS.get(provider)
        if fetcher is None:
            raise ValueError(
                f"No default live fetcher for provider {provider!r}; "
                f"choose one of {sorted(_LIVE_FETCHERS)} or pass an explicit fetcher."
            )

    anchor = as_of if as_of is not None else _today()
    start = _window_start(anchor, window_years)

    live = fetcher()
    windowed = filter_series_to_window(live, start, anchor)

    if dry_run:
        return {
            "written": False,
            "provider": windowed.provider,
            "rows": len(windowed.rates),
            "date_range": list(windowed.date_range),
            "latest_value": windowed.latest,
            "fetched_as_of": anchor.isoformat(),
            "window_years": window_years,
            "window_start": start.isoformat(),
        }

    return write_vintage(
        windowed,
        csv_path,
        provenance_path,
        window_years=window_years,
        as_of=anchor,
    )


def _annualization_factor(
    frequency: str, observations_per_year: int | None = None
) -> int:
    """Observations per year for annualising returns (daily≈252, weekly=52, monthly=12)."""
    if observations_per_year:
        return int(observations_per_year)
    return {"daily": 252, "weekly": 52, "monthly": 12}.get(frequency.lower(), 252)


def to_periodic(
    series: FXHistorySeries, frequency: str = "weekly"
) -> tuple[Sequence[str], Sequence[float]]:
    """Resample a daily series to the weekly/monthly last observation.

    Returns ``(dates, rates)`` where each ``date`` is the ACTUAL ``YYYY-MM-DD`` of the
    last observation in its period (NOT an ISO-week label) so the dates still
    compare correctly against ``YYYY-MM-DD`` regime windows. ``weekly`` groups by
    ISO week, ``monthly`` by calendar month, ``daily`` returns the series unchanged.
    """
    freq = frequency.lower()
    if freq == "daily":
        return list(series.dates), list(series.rates)

    def period_key(date_str: str) -> str:
        y, m, d = date_str.split("-")
        if freq == "monthly":
            return f"{y}-{m}"
        import datetime as _dt

        iso = _dt.date(int(y), int(m), int(d)).isocalendar()
        return f"{iso[0]}-W{iso[1]:02d}"

    last: dict[str, tuple[str, float]] = {}
    for dt, rate in zip(series.dates, series.rates, strict=True):
        k = period_key(dt)
        prev = last.get(k)
        if prev is None or dt >= prev[0]:
            last[k] = (dt, rate)
    # Sort by the real observation date and return real dates (not period labels).
    items = sorted(last.values(), key=lambda dv: dv[0])
    dates = [dv[0] for dv in items]
    vals = [dv[1] for dv in items]
    return dates, vals


__all__ = [
    "FXHistorySeries",
    "APPROVED_FX_SOURCES",
    "DEFAULT_VINTAGE_CSV",
    "DEFAULT_VINTAGE_PROVENANCE",
    "DEFAULT_WINDOW_YEARS",
    "BIS_DAILY_ENDPOINT",
    "FRED_DEXSLUS_CSV",
    "load_pinned_history",
    "resolve_fx_history",
    "fetch_live_history_bis",
    "fetch_live_history_fred",
    "validate_history_drift",
    "filter_series_to_window",
    "write_vintage",
    "refresh_pinned_vintage",
    "to_periodic",
    "_annualization_factor",
]
