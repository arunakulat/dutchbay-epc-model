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
import hashlib
import json
import logging
import math
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

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
            v = (r.get(rate_col) or "").strip()
            if not d or not v:
                continue
            try:
                rate = float(v)
            except ValueError:
                continue  # skip non-numeric placeholders
            if not math.isfinite(rate) or rate <= 0:
                continue  # skip NaN/holiday placeholders (BIS carries them as NaN)
            rows.append((d, rate))
    if not rows:
        raise ValueError(f"FX vintage CSV {csv_path} contained no data rows")
    rows.sort(key=lambda t: t[0])
    dates, rates = zip(*rows)
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
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:  # noqa: S310 (https only)
        payload = json.loads(resp.read().decode("utf-8"))
    data = payload["data"]
    series_obj = next(iter(data["dataSets"][0]["series"].values()))
    observations = series_obj["observations"]
    dim_dates = [
        v["id"] for v in data["structure"]["dimensions"]["observation"][0]["values"]
    ]
    pairs = sorted(
        (dim_dates[int(k)], float(v[0]))
        for k, v in observations.items()
        if v and v[0] is not None
    )
    dates, rates = zip(*pairs)
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
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:  # noqa: S310 (https only)
        text = resp.read().decode("utf-8")
    pairs: list[tuple[str, float]] = []
    for line in text.splitlines()[1:]:
        if not line.strip():
            continue
        date_str, _, val = line.partition(",")
        val = val.strip()
        if not val or val == ".":  # FRED marks holidays with '.'
            continue
        pairs.append((date_str.strip(), float(val)))
    pairs.sort(key=lambda t: t[0])
    dates, rates = zip(*pairs)
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
    for dt, rate in zip(series.dates, series.rates):
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
    "BIS_DAILY_ENDPOINT",
    "FRED_DEXSLUS_CSV",
    "load_pinned_history",
    "resolve_fx_history",
    "fetch_live_history_bis",
    "fetch_live_history_fred",
    "validate_history_drift",
    "to_periodic",
    "_annualization_factor",
]
