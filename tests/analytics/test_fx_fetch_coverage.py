"""Coverage tests for analytics.fx.fx_fetch — raises and mode branches.

Complements ``test_fx_fetch.py`` by exercising the defensive ``raise`` paths and
the ``latest`` / VALIDATE branches that the happy-path suite leaves uncovered.
Every network touch is mocked: no test here performs real I/O. The FIXED-vintage
philosophy (offline, deterministic) holds throughout — live fetches are stubbed
with deterministic payloads so drift assertions are exact.
"""

from __future__ import annotations

import io
import json
import logging
from pathlib import Path
from typing import Any

import pytest

import analytics.fx.fx_fetch as fx_fetch
from analytics.fx.fx_fetch import (
    CBSL_REFERENCE_URL,
    DEFAULT_ENDPOINT,
    DEFAULT_PROVIDER,
    FXDrift,
    FXRate,
    FXRequestConfig,
    default_fx_lkr_per_usd,
    fetch_live_fx,
    fx_drift,
    load_pinned_fx,
    resolve_fx,
    validate_fx,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

PINNED = 333.79
PINNED_AS_OF = "2026-06-20T00:02:31Z"


def _scenario(
    mode: str = "fixed",
    *,
    start: float | None = PINNED,
    pinned: float | None = PINNED,
    with_source: bool = True,
    drift_tolerance_pct: float = 5.0,
) -> dict[str, Any]:
    source: dict[str, Any] = {
        "mode": mode,
        "provider": "open_er_api",
        "endpoint": DEFAULT_ENDPOINT,
        "pinned_as_of": PINNED_AS_OF,
        "drift_tolerance_pct": drift_tolerance_pct,
    }
    if pinned is not None:
        source["pinned_rate"] = pinned
    fx: dict[str, Any] = {}
    if start is not None:
        fx["start_lkr_per_usd"] = start
    if with_source:
        fx["source"] = source
    return {"fx": fx}


def _live_response(lkr_per_usd: float) -> io.BytesIO:
    payload = {
        "rates": {"LKR": lkr_per_usd, "USD": 1.0},
        "time_last_update_utc": "Fri, 20 Jun 2026 00:02:31 +0000",
        "provider": "open_er_api",
    }
    return io.BytesIO(json.dumps(payload).encode("utf-8"))


class _FakeURLOpen:
    """Context-manager replacement for urllib.request.urlopen returning a fixed body."""

    def __init__(self, body: io.BytesIO) -> None:
        self._body = body

    def __enter__(self) -> io.BytesIO:
        return self._body

    def __exit__(self, *exc: object) -> bool:
        return False


# ---------------------------------------------------------------------------
# default_fx_lkr_per_usd — config-missing raise (lines 71-72)
# ---------------------------------------------------------------------------


def test_default_fx_raises_when_defaults_key_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A defaults.yaml lacking start_lkr_per_usd raises a descriptive ValueError."""
    bad = tmp_path / "defaults.yaml"
    bad.write_text("defaults:\n  fx_reference: {}\n")
    monkeypatch.setattr(fx_fetch, "_DEFAULTS_PATH", bad)
    default_fx_lkr_per_usd.cache_clear()
    try:
        with pytest.raises(ValueError, match="missing defaults.fx_reference"):
            default_fx_lkr_per_usd()
    finally:
        default_fx_lkr_per_usd.cache_clear()


# ---------------------------------------------------------------------------
# FXRate.from_vintage_file — malformed artifact raise (lines 124-125)
# ---------------------------------------------------------------------------


def test_from_vintage_file_malformed_raises(tmp_path: Path) -> None:
    """A vintage JSON missing required keys raises with the artifact path quoted."""
    bad = tmp_path / "vintage.json"
    bad.write_text(json.dumps({"provider": "open_er_api"}))  # no lkr_per_usd / as_of_utc
    with pytest.raises(ValueError, match="Malformed FX vintage artifact"):
        FXRate.from_vintage_file(bad)


def test_from_vintage_file_defaults_source_url(tmp_path: Path) -> None:
    """source_url falls back to DEFAULT_ENDPOINT when absent in the artifact."""
    good = tmp_path / "vintage.json"
    good.write_text(
        json.dumps(
            {
                "lkr_per_usd": PINNED,
                "as_of_utc": PINNED_AS_OF,
                "provider": "open_er_api",
            }
        )
    )
    fr = FXRate.from_vintage_file(good)
    assert fr.source_url == DEFAULT_ENDPOINT
    assert fr.lkr_per_usd == pytest.approx(PINNED)


# ---------------------------------------------------------------------------
# FXRequestConfig.__post_init__ — invalid mode (line 175)
# ---------------------------------------------------------------------------


def test_invalid_mode_raises() -> None:
    """A reference_mode outside the valid set raises in __post_init__."""
    with pytest.raises(ValueError, match="fx.source.mode must be one of"):
        FXRequestConfig(
            base_currency="USD",
            quote_currency="LKR",
            reference_mode="bogus",
            provider=DEFAULT_PROVIDER,
            endpoint=DEFAULT_ENDPOINT,
            reference_url=CBSL_REFERENCE_URL,
            pinned_rate=PINNED,
            pinned_as_of=PINNED_AS_OF,
            drift_tolerance_pct=5.0,
        )


# ---------------------------------------------------------------------------
# FXRequestConfig.from_scenario — missing fx / source raises (lines 196, 201)
# ---------------------------------------------------------------------------


def test_from_scenario_missing_fx_raises() -> None:
    """No 'fx' mapping at all raises."""
    with pytest.raises(ValueError, match="FX configuration missing"):
        FXRequestConfig.from_scenario({})


def test_from_scenario_fx_not_mapping_raises() -> None:
    """An 'fx' value that is not a mapping also raises the same guard."""
    with pytest.raises(ValueError, match="FX configuration missing"):
        FXRequestConfig.from_scenario({"fx": "nope"})


def test_from_scenario_missing_source_raises() -> None:
    """An 'fx' block with no 'source' sub-block raises."""
    with pytest.raises(ValueError, match="fx.source block missing"):
        FXRequestConfig.from_scenario({"fx": {"start_lkr_per_usd": PINNED}})


def test_from_scenario_latest_mode_builds() -> None:
    """mode='latest' needs no pinned rate and resolves the documented defaults."""
    cfg = FXRequestConfig.from_scenario(
        {"fx": {"source": {"mode": "latest"}}}
    )
    assert cfg.reference_mode == "latest"
    assert cfg.provider == DEFAULT_PROVIDER
    assert cfg.endpoint == DEFAULT_ENDPOINT
    assert cfg.reference_url == CBSL_REFERENCE_URL
    assert cfg.pinned_rate is None
    assert cfg.drift_tolerance_pct == pytest.approx(5.0)
    assert cfg.timeout_s == pytest.approx(10.0)


# ---------------------------------------------------------------------------
# load_pinned_fx — missing pinned raises (line 244)
# ---------------------------------------------------------------------------


def test_load_pinned_fx_missing_raises() -> None:
    """load_pinned_fx on a latest-mode cfg (no pinned vintage) raises."""
    cfg = FXRequestConfig.from_scenario({"fx": {"source": {"mode": "latest"}}})
    with pytest.raises(ValueError, match="Cannot load a pinned FX rate"):
        load_pinned_fx(cfg)


# ---------------------------------------------------------------------------
# fetch_live_fx — quote missing + success (lines 267, 304 via resolve_fx)
# ---------------------------------------------------------------------------


def test_fetch_live_fx_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """A well-formed provider payload yields an FXRate with full provenance."""
    monkeypatch.setattr(
        fx_fetch.urllib.request,
        "urlopen",
        lambda req, timeout=None: _FakeURLOpen(_live_response(340.0)),
    )
    cfg = FXRequestConfig.from_scenario(_scenario("latest", start=None, pinned=None))
    fr = fetch_live_fx(cfg)
    assert fr.lkr_per_usd == pytest.approx(340.0)
    assert fr.provider == "open_er_api"
    assert fr.source_url == DEFAULT_ENDPOINT
    assert "2026" in fr.as_of_utc


def test_fetch_live_fx_missing_quote_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """A payload with no LKR key raises a descriptive ValueError."""
    body = io.BytesIO(json.dumps({"rates": {"USD": 1.0, "EUR": 0.9}}).encode("utf-8"))
    monkeypatch.setattr(
        fx_fetch.urllib.request,
        "urlopen",
        lambda req, timeout=None: _FakeURLOpen(body),
    )
    cfg = FXRequestConfig.from_scenario(_scenario("latest", start=None, pinned=None))
    with pytest.raises(ValueError, match="returned no LKR rate"):
        fetch_live_fx(cfg)


# ---------------------------------------------------------------------------
# resolve_fx — latest dispatches to fetch_live_fx (line 304)
# ---------------------------------------------------------------------------


def test_resolve_fx_latest_dispatches_to_live(monkeypatch: pytest.MonkeyPatch) -> None:
    """mode='latest' routes resolve_fx through the (mocked) live fetch."""
    monkeypatch.setattr(
        fx_fetch.urllib.request,
        "urlopen",
        lambda req, timeout=None: _FakeURLOpen(_live_response(335.0)),
    )
    cfg = FXRequestConfig.from_scenario(_scenario("latest", start=None, pinned=None))
    fr = resolve_fx(cfg)
    assert fr.lkr_per_usd == pytest.approx(335.0)


def test_resolve_fx_fixed_is_pinned() -> None:
    """mode='fixed' resolves to the pinned vintage with no network."""
    cfg = FXRequestConfig.from_scenario(_scenario("fixed"))
    fr = resolve_fx(cfg)
    assert fr.lkr_per_usd == pytest.approx(PINNED)
    assert fr.as_of_utc == PINNED_AS_OF


# ---------------------------------------------------------------------------
# validate_fx — unavailable branch (lines 325-329) and drift-breach warn (335)
# ---------------------------------------------------------------------------


def test_validate_fx_live_unavailable_is_nonfatal(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A failing live fetch yields live='unavailable', drift=None, and a warning."""

    def _boom(req: Any, timeout: Any = None) -> None:
        raise OSError("network down")

    monkeypatch.setattr(fx_fetch.urllib.request, "urlopen", _boom)
    scen = _scenario("fixed")
    with caplog.at_level(logging.WARNING, logger="analytics.fx.fx_fetch"):
        out = validate_fx(scen)
    assert out["mode"] == "validate"
    assert out["live"] == "unavailable"
    assert out["drift"] is None
    assert out["pinned"]["lkr_per_usd"] == pytest.approx(PINNED)
    assert "live fetch unavailable" in caplog.text
    # config untouched
    assert scen["fx"]["start_lkr_per_usd"] == PINNED


def test_validate_fx_within_tolerance_no_warning(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A live rate close to pinned reports drift, within tolerance, and warns nothing."""
    monkeypatch.setattr(
        fx_fetch.urllib.request,
        "urlopen",
        lambda req, timeout=None: _FakeURLOpen(_live_response(PINNED * 1.01)),
    )
    scen = _scenario("fixed", drift_tolerance_pct=5.0)
    with caplog.at_level(logging.WARNING, logger="analytics.fx.fx_fetch"):
        out = validate_fx(scen)
    assert out["live"] != "unavailable"
    assert out["drift"]["within_tolerance"] is True
    assert out["drift"]["drift_pct"] == pytest.approx(1.0, abs=0.01)
    assert "drifts" not in caplog.text


def test_validate_fx_drift_breach_warns(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A live rate far from pinned breaches tolerance and logs the loud warning."""
    monkeypatch.setattr(
        fx_fetch.urllib.request,
        "urlopen",
        lambda req, timeout=None: _FakeURLOpen(_live_response(PINNED * 1.20)),
    )
    scen = _scenario("fixed", drift_tolerance_pct=5.0)
    with caplog.at_level(logging.WARNING, logger="analytics.fx.fx_fetch"):
        out = validate_fx(scen)
    assert out["drift"]["within_tolerance"] is False
    assert out["drift"]["drift_pct"] == pytest.approx(20.0, abs=0.01)
    assert "drifts" in caplog.text
    assert "UNCHANGED" in caplog.text
    # pinned rate is left untouched
    assert out["pinned"]["lkr_per_usd"] == pytest.approx(PINNED)


# ---------------------------------------------------------------------------
# Value-object as_dict round-trips (rounding + provenance)
# ---------------------------------------------------------------------------


def test_fxrate_as_dict_rounds() -> None:
    """FXRate.as_dict rounds the quote to 6 dp and carries provenance fields."""
    fr = FXRate(333.7912345678, PINNED_AS_OF, "open_er_api", DEFAULT_ENDPOINT)
    d = fr.as_dict()
    assert d["lkr_per_usd"] == pytest.approx(333.791235, abs=1e-9)
    assert d["provider"] == "open_er_api"
    assert d["source_url"] == DEFAULT_ENDPOINT


def test_fxdrift_as_dict_and_fx_drift_signs() -> None:
    """fx_drift computes signed percent and as_dict rounds drift to 3 dp."""
    pinned = FXRate(300.0, "old", DEFAULT_PROVIDER, "x")
    live = FXRate(333.79, "new", DEFAULT_PROVIDER, "x")
    d: FXDrift = fx_drift(pinned, live, tolerance_pct=5.0)
    assert d.drift_pct == pytest.approx(11.263, abs=0.01)
    assert d.within_tolerance is False
    dd = d.as_dict()
    assert dd["pinned_rate"] == pytest.approx(300.0)
    assert dd["drift_pct"] == pytest.approx(11.263, abs=0.001)
    assert dd["within_tolerance"] is False
