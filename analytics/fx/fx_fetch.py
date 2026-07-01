"""Config-driven USD/LKR FX-rate resolution — fetch, pin, and VALIDATE-drift.

This is the FX analogue of the ERA5/ARCO wind-resource routine
(:mod:`wind_resource.era5_retrieval`, :mod:`wind_resource.arco_assessment`,
:mod:`wind_resource.weibull_fit`). It exists to collapse the *many* divergent
hardcoded LKR/USD rates that had accreted across the codebase (300, 305, 320,
375, 396) into a single, config-sourced, provenance-bearing source of truth.

Design (mirrors the wind routine one-for-one):

* **FIXED vintage (default, reproducible).** ``mode: "fixed"`` resolves the rate
  from a committed, pinned vintage (config ``fx.source.pinned_rate`` /
  ``pinned_as_of``, optionally materialised as a JSON artifact under
  ``tests/fixtures/fx/``). No network is ever touched — exactly how
  ``analytics.loader.aep_loader`` reads its committed AEP mock. Lender runs and
  CI use this path, so they are deterministic and offline.

* **LATEST (exploratory).** ``mode: "latest"`` fetches the live rate from a
  reputable programmatic provider and *freezes* the resolved rate + timestamp
  into a vintage — mirroring how ``era5_retrieval`` freezes its rolling window.

* **VALIDATE drift.** :func:`validate_fx` loads the pinned rate AND fetches live,
  reports the drift, and **never mutates config** — the FX analogue of
  ``arco_assessment.build_arco_assessment`` returning ``mode: "validate"`` and
  leaving the declared Weibull untouched. Re-baselining the pinned rate is a
  deliberate, dated config edit, never an automatic side effect.

The authoritative reference is the Central Bank of Sri Lanka (CBSL) daily
indicative USD/LKR spot rate; it is JS-rendered and therefore documented as a
``reference_url`` for audit, never a fetch target (just as the CDS docs are
referenced but not embedded in the ERA5 routine). The programmatic provider is
``open.er-api.com`` (no API key, ships ``provider`` + ``time_last_update_utc``
for provenance).

No magic FX constant lives here or anywhere downstream: every resolution path
either reads a config-pinned rate or fetches one with recorded provenance, and
raises when the rate cannot be resolved (CESSPIT / ARCH-01).
"""

from __future__ import annotations

import json
import logging
import urllib.request
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

logger = logging.getLogger(__name__)

_DEFAULTS_PATH = Path(__file__).resolve().parents[2] / "config" / "defaults.yaml"


@lru_cache(maxsize=1)
def default_fx_lkr_per_usd() -> float:
    """Canonical fallback USD/LKR rate, sourced from ``config/defaults.yaml``.

    This is the SINGLE source of truth for the handful of legacy code paths that
    lack an explicit scenario ``fx`` block (lightweight / hand-authored configs).
    It replaces the divergent stale literals (300 / 305 / 320 / 375 / 396) that
    were scattered across the codebase — no Python module may hardcode an FX rate
    (CESSPIT / ARCH-01). Production scenarios always declare their own
    ``fx.start_lkr_per_usd`` + pinned ``fx.source`` vintage and never hit this.
    """
    import yaml  # project core dep; imported here to keep module import light

    data = yaml.safe_load(_DEFAULTS_PATH.read_text())
    try:
        return float(data["defaults"]["fx_reference"]["start_lkr_per_usd"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(
            f"config/defaults.yaml missing defaults.fx_reference.start_lkr_per_usd "
            f"({_DEFAULTS_PATH})"
        ) from exc


DEFAULT_PROVIDER = "open_er_api"
DEFAULT_ENDPOINT = "https://open.er-api.com/v6/latest/USD"
# CBSL authoritative indicative rate — documented for audit, NEVER fetched (JS-rendered).
CBSL_REFERENCE_URL = (
    "https://www.cbsl.gov.lk/en/rates-and-indicators/exchange-rates/"
    "daily-indicative-usd-spot-exchange-rates"
)
_VALID_MODES = ("fixed", "latest")


# ---------------------------------------------------------------------------
# Value objects
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FXRate:
    """A resolved USD/LKR rate with full provenance.

    ``lkr_per_usd`` is the quote (LKR per 1 USD). ``as_of_utc`` is the provider's
    own observation timestamp (or the pinned vintage's ``pinned_as_of``).
    """

    lkr_per_usd: float
    as_of_utc: str
    provider: str
    source_url: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "lkr_per_usd": round(self.lkr_per_usd, 6),
            "as_of_utc": self.as_of_utc,
            "provider": self.provider,
            "source_url": self.source_url,
        }

    @classmethod
    def from_vintage_file(cls, path: str | Path) -> "FXRate":
        """Load a pinned vintage FXRate from a committed JSON artifact (no network)."""
        data = json.loads(Path(path).read_text())
        try:
            return cls(
                lkr_per_usd=float(data["lkr_per_usd"]),
                as_of_utc=str(data["as_of_utc"]),
                provider=str(data["provider"]),
                source_url=str(data.get("source_url", DEFAULT_ENDPOINT)),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(
                f"Malformed FX vintage artifact at {path}; "
                "expected keys lkr_per_usd, as_of_utc, provider"
            ) from exc


@dataclass(frozen=True)
class FXDrift:
    """Relative drift of a live rate vs the pinned vintage (VALIDATE-mode signal).

    Mirrors :class:`wind_resource.weibull_fit.WeibullDrift`. Never mutates config.
    """

    pinned_rate: float
    live_rate: float
    drift_pct: float
    tolerance_pct: float
    within_tolerance: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "pinned_rate": round(self.pinned_rate, 6),
            "live_rate": round(self.live_rate, 6),
            "drift_pct": round(self.drift_pct, 3),
            "tolerance_pct": self.tolerance_pct,
            "within_tolerance": self.within_tolerance,
        }


@dataclass(frozen=True)
class FXRequestConfig:
    """Resolved FX request parameters, sourced entirely from a scenario ``fx`` block.

    No field carries a magic rate default: ``mode: "fixed"`` *requires*
    ``pinned_rate`` + ``pinned_as_of``; resolution raises if they are absent.
    """

    base_currency: str
    quote_currency: str
    reference_mode: str
    provider: str
    endpoint: str
    reference_url: str
    pinned_rate: float | None
    pinned_as_of: str | None
    drift_tolerance_pct: float
    timeout_s: float = 10.0

    def __post_init__(self) -> None:
        if self.reference_mode not in _VALID_MODES:
            raise ValueError(
                f"fx.source.mode must be one of {_VALID_MODES}; got {self.reference_mode!r}"
            )
        if self.reference_mode == "fixed" and (
            self.pinned_rate is None or self.pinned_as_of is None
        ):
            raise ValueError(
                "fx.source.mode 'fixed' requires both 'pinned_rate' and 'pinned_as_of' "
                "(no magic default rate — pin a dated vintage)"
            )

    @classmethod
    def from_scenario(cls, scenario: Mapping[str, Any]) -> "FXRequestConfig":
        """Build an :class:`FXRequestConfig` from a scenario ``fx`` mapping.

        Reads the optional ``fx.source`` sub-block. When ``mode: "fixed"`` is used
        the pinned rate is cross-asserted against ``fx.start_lkr_per_usd`` so the
        two never silently diverge (mirrors the ARCO hub-height cross-assert).
        """
        fx_cfg = scenario.get("fx")
        if not isinstance(fx_cfg, Mapping):
            raise ValueError(
                "FX configuration missing; expected an 'fx' mapping with a 'source' block"
            )
        source = fx_cfg.get("source")
        if not isinstance(source, Mapping):
            raise ValueError(
                "fx.source block missing; expected mode/provider/pinned_rate/pinned_as_of "
                "(config-first FX, no hardcoded rate)"
            )

        mode = str(source.get("mode", "fixed"))
        pinned_rate = source.get("pinned_rate")
        pinned_as_of = source.get("pinned_as_of")

        if mode == "fixed" and pinned_rate is not None:
            start = fx_cfg.get("start_lkr_per_usd")
            if start is not None and abs(float(start) - float(pinned_rate)) > 1e-6:
                raise ValueError(
                    "fx.start_lkr_per_usd "
                    f"({start}) must equal fx.source.pinned_rate ({pinned_rate}) "
                    "when mode is 'fixed' — single source of truth"
                )

        return cls(
            base_currency=str(fx_cfg.get("base_currency", "USD")),
            quote_currency=str(fx_cfg.get("quote_currency", "LKR")),
            reference_mode=mode,
            provider=str(source.get("provider", DEFAULT_PROVIDER)),
            endpoint=str(source.get("endpoint", DEFAULT_ENDPOINT)),
            reference_url=str(source.get("reference_url", CBSL_REFERENCE_URL)),
            pinned_rate=None if pinned_rate is None else float(pinned_rate),
            pinned_as_of=None if pinned_as_of is None else str(pinned_as_of),
            drift_tolerance_pct=float(source.get("drift_tolerance_pct", 5.0)),
            timeout_s=float(source.get("timeout_s", 10.0)),
        )


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------


def load_pinned_fx(cfg: FXRequestConfig) -> FXRate:
    """Return the pinned vintage rate from config — NO network call.

    This is the default lender/CI path: deterministic and offline.
    """
    if cfg.pinned_rate is None or cfg.pinned_as_of is None:
        raise ValueError(
            "Cannot load a pinned FX rate: fx.source.pinned_rate / pinned_as_of absent"
        )
    return FXRate(
        lkr_per_usd=cfg.pinned_rate,
        as_of_utc=cfg.pinned_as_of,
        provider=cfg.provider,
        source_url=cfg.reference_url,
    )


def fetch_live_fx(cfg: FXRequestConfig) -> FXRate:
    """Fetch the live USD/LKR rate from the configured provider (network).

    Uses the stdlib only (``urllib``) — no third-party dependency, so the package
    always imports cleanly and CI (which never calls this) needs nothing extra.
    """
    if not cfg.endpoint.lower().startswith("https://"):
        raise ValueError(
            f"FX endpoint must use https (refusing file:/ or plaintext): {cfg.endpoint!r}"
        )
    req = urllib.request.Request(
        cfg.endpoint, headers={"User-Agent": "dutchbay-fx/1.0"}
    )
    with urllib.request.urlopen(
        req, timeout=cfg.timeout_s
    ) as resp:  # nosec B310 - https scheme enforced above
        payload = json.loads(resp.read().decode("utf-8"))

    rates = payload.get("rates") or {}
    if cfg.quote_currency not in rates:
        raise ValueError(
            f"Provider {cfg.provider} returned no {cfg.quote_currency} rate "
            f"(keys: {sorted(rates)[:5]}...)"
        )
    return FXRate(
        lkr_per_usd=float(rates[cfg.quote_currency]),
        as_of_utc=str(payload.get("time_last_update_utc", "")),
        provider=str(payload.get("provider", cfg.provider)),
        source_url=cfg.endpoint,
    )


def fx_drift(pinned: FXRate, live: FXRate, tolerance_pct: float) -> FXDrift:
    """Relative drift of ``live`` vs ``pinned`` — a VALIDATE-mode signal only.

    ``drift_pct = 100 * (live - pinned) / pinned``; ``within_tolerance`` when the
    absolute drift is ``<= tolerance_pct``. Never mutates config (mirrors
    :func:`wind_resource.weibull_fit.weibull_drift`).
    """
    drift = 100.0 * (live.lkr_per_usd - pinned.lkr_per_usd) / pinned.lkr_per_usd
    return FXDrift(
        pinned_rate=pinned.lkr_per_usd,
        live_rate=live.lkr_per_usd,
        drift_pct=drift,
        tolerance_pct=tolerance_pct,
        within_tolerance=abs(drift) <= tolerance_pct,
    )


def resolve_fx(cfg: FXRequestConfig) -> FXRate:
    """Resolve the operative FX rate per ``cfg.reference_mode``.

    * ``fixed``  -> the pinned vintage (no network; reproducible).
    * ``latest`` -> a freshly fetched rate, frozen into a vintage by the caller.
    """
    if cfg.reference_mode == "fixed":
        return load_pinned_fx(cfg)
    return fetch_live_fx(cfg)


def validate_fx(scenario: Mapping[str, Any]) -> dict[str, Any]:
    """VALIDATE the pinned FX vintage against the live rate without mutating config.

    Returns ``{mode, pinned, live, drift, vintage}``. If the live fetch fails
    (offline / rate-limited) the live + drift fields report ``unavailable`` rather
    than crashing the pipeline — mirroring the wind routine's non-fatal VALIDATE.
    When the drift breaches tolerance it logs a loud warning; the declared/pinned
    rate is left UNCHANGED (re-baselining is a deliberate dated edit).
    """
    cfg = FXRequestConfig.from_scenario(scenario)
    pinned = load_pinned_fx(cfg)
    out: dict[str, Any] = {
        "mode": "validate",
        "pinned": pinned.as_dict(),
        "vintage": {
            "pinned_as_of": cfg.pinned_as_of,
            "reference_url": cfg.reference_url,
        },
    }
    try:
        live = fetch_live_fx(cfg)
    except (OSError, ValueError) as exc:  # network / parse failure — non-fatal
        logger.warning(
            "FX VALIDATE: live fetch unavailable (%s); pinned rate UNCHANGED", exc
        )
        out["live"] = "unavailable"
        out["drift"] = None
        return out

    drift = fx_drift(pinned, live, cfg.drift_tolerance_pct)
    out["live"] = live.as_dict()
    out["drift"] = drift.as_dict()
    if not drift.within_tolerance:
        logger.warning(
            "FX VALIDATE: live %.3f LKR/USD drifts %+.2f%% from pinned %.3f "
            "(tolerance %.1f%%); pinned rate UNCHANGED — adopt only via a deliberate "
            "dated re-baseline.",
            live.lkr_per_usd,
            drift.drift_pct,
            pinned.lkr_per_usd,
            cfg.drift_tolerance_pct,
        )
    return out


__all__ = [
    "FXRate",
    "FXDrift",
    "FXRequestConfig",
    "default_fx_lkr_per_usd",
    "load_pinned_fx",
    "fetch_live_fx",
    "fx_drift",
    "resolve_fx",
    "validate_fx",
    "DEFAULT_PROVIDER",
    "DEFAULT_ENDPOINT",
    "CBSL_REFERENCE_URL",
]
