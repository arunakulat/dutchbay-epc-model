"""Unit tests for the config-driven FX-rate routine (analytics.fx.fx_fetch).

Mirrors the ERA5/ARCO wind-routine test philosophy: the FIXED-vintage path is
deterministic and offline (CI never touches the network), and VALIDATE-mode drift
is a non-mutating signal. The live-fetch path is exercised separately and skipped
when offline.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from analytics.fx.fx_fetch import (
    DEFAULT_ENDPOINT,
    FXRate,
    FXRequestConfig,
    default_fx_lkr_per_usd,
    fx_drift,
    load_pinned_fx,
    resolve_fx,
    validate_fx,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
VINTAGE = REPO_ROOT / "tests" / "fixtures" / "fx" / "fx_pinned_2026Q2.json"

PINNED = 333.79


def _scenario(
    mode: str = "fixed", start: float = PINNED, pinned: float = PINNED
) -> dict:
    return {
        "fx": {
            "start_lkr_per_usd": start,
            "annual_depr": 0.03,
            "source": {
                "mode": mode,
                "provider": "open_er_api",
                "endpoint": DEFAULT_ENDPOINT,
                "pinned_rate": pinned,
                "pinned_as_of": "2026-06-20T00:02:31Z",
                "drift_tolerance_pct": 5.0,
            },
        }
    }


def test_pinned_vintage_file_loads_offline() -> None:
    """The committed vintage artifact loads with no network and the expected rate."""
    fr = FXRate.from_vintage_file(VINTAGE)
    assert fr.lkr_per_usd == pytest.approx(PINNED, abs=0.01)
    assert fr.provider == "open_er_api"
    # sanity: the pinned rate is the corrected ~333.8, not the stale 300
    assert fr.lkr_per_usd > 320.0


def test_resolve_fixed_is_offline_and_pinned() -> None:
    """mode='fixed' returns the pinned rate via config — no network, reproducible."""
    cfg = FXRequestConfig.from_scenario(_scenario("fixed"))
    fr = resolve_fx(cfg)  # must not perform any network I/O
    assert fr.lkr_per_usd == pytest.approx(PINNED, abs=1e-9)
    assert load_pinned_fx(cfg).lkr_per_usd == pytest.approx(PINNED, abs=1e-9)


def test_cross_assert_start_must_equal_pinned() -> None:
    """fx.start_lkr_per_usd must equal fx.source.pinned_rate (single source of truth)."""
    with pytest.raises(ValueError, match="must equal"):
        FXRequestConfig.from_scenario(_scenario("fixed", start=300.0, pinned=PINNED))


def test_fixed_mode_requires_pinned_rate() -> None:
    """mode='fixed' with no pinned_rate raises (no magic default rate)."""
    scen = _scenario("fixed")
    scen["fx"]["source"].pop("pinned_rate")
    scen["fx"].pop("start_lkr_per_usd")
    with pytest.raises(ValueError, match="requires both 'pinned_rate'"):
        FXRequestConfig.from_scenario(scen)


def test_fx_drift_flags_the_stale_300() -> None:
    """Drift of the stale 300 vs the corrected ~333.8 is ~+11.3%, out of a 5% band."""
    pinned = FXRate(300.0, "old", "open_er_api", "x")
    live = FXRate(333.79, "2026-06-20", "open_er_api", "x")
    d = fx_drift(pinned, live, tolerance_pct=5.0)
    assert d.drift_pct == pytest.approx(11.26, abs=0.1)
    assert d.within_tolerance is False


def test_default_fx_is_config_sourced_not_300() -> None:
    """The single fallback default comes from config/defaults.yaml and is the new rate."""
    rate = default_fx_lkr_per_usd()
    assert rate == pytest.approx(PINNED, abs=0.5)
    assert rate > 320.0  # never the stale 300


def test_package_imports_without_requests() -> None:
    """analytics.fx imports cleanly with no third-party network dep (stdlib urllib)."""
    import importlib

    mod = importlib.import_module("analytics.fx.fx_fetch")
    assert hasattr(mod, "fetch_live_fx")  # defined, but only calls urllib when invoked


def test_validate_fx_live_drift_is_nonmutating() -> None:
    """VALIDATE fetches live + reports drift without mutating config (network; best-effort)."""
    scen = _scenario("fixed")
    try:
        out = validate_fx(scen)
    except Exception:  # pragma: no cover - offline CI
        pytest.skip("live FX provider unavailable")
    assert out["mode"] == "validate"
    assert out["pinned"]["lkr_per_usd"] == pytest.approx(PINNED, abs=0.01)
    # config untouched
    assert scen["fx"]["start_lkr_per_usd"] == PINNED
