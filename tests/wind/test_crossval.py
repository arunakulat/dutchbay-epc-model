"""Tests for :mod:`wind_resource.crossval` — opt-in second-source cross-validation (#612).

Exercises the whole disclose-don't-mutate contract with ZERO network: the core
:func:`build_crossval_assessment` runs on synthetic injected series (exactly like
``tests/wind/test_arco_assessment_coverage.py`` exercises the ARCO path), the live NASA
POWER fetch is monkeypatched at the ``requests`` boundary, and the schema-guard
auto-enforcement is checked against the real lender scenario.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Dict

import numpy as np
import pandas as pd
import pytest

from analytics.scenario_loader import load_scenario_config
from wind_resource import crossval

# NB: analytics.schema_guard symbols are resolved LAZILY inside the schema-guard tests (via
# _live_schema_guard) rather than imported here, because an earlier suite test evicts and
# re-imports the whole analytics.* graph — see _live_schema_guard for the full rationale.

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER_CONFIG = REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"

WS_COL = "ws_150m"


@pytest.fixture(scope="module")
def scenario() -> Dict[str, Any]:
    return load_scenario_config(str(LENDER_CONFIG))


def _weibull_series(a: float, k: float, n: int = 40_000, seed: int = 7) -> pd.DataFrame:
    """A synthetic second-source hub-height series drawn from Weibull(scale=a, shape=k)."""
    rng = np.random.default_rng(seed)
    return pd.DataFrame({WS_COL: rng.weibull(k, n) * a})


# ── crossval_settings: the opt-in gate (default OFF -> None) ────────────────────


def test_settings_absent_block_returns_none() -> None:
    assert crossval.crossval_settings({"resource": {}}) is None
    assert crossval.crossval_settings({}) is None


def test_settings_disabled_returns_none() -> None:
    cfg = {"resource": {"crossval": {"enabled": False, "source_type": "merra2"}}}
    assert crossval.crossval_settings(cfg) is None


def test_settings_enabled_resolves() -> None:
    cfg = {
        "resource": {
            "crossval": {
                "enabled": True,
                "source_type": "MERRA2",  # case-insensitive
                "drift_tolerance_pct": 7.5,
                "series_path": "x.csv",
            }
        }
    }
    out = crossval.crossval_settings(cfg)
    assert out is not None
    assert out["source_type"] == "merra2"
    assert out["drift_tolerance_pct"] == 7.5
    assert out["series_path"] == "x.csv"


def test_settings_non_bool_enabled_raises() -> None:
    cfg = {"resource": {"crossval": {"enabled": "yes", "source_type": "merra2"}}}
    with pytest.raises(ValueError, match="enabled must be a boolean"):
        crossval.crossval_settings(cfg)


def test_settings_missing_source_type_raises() -> None:
    cfg = {"resource": {"crossval": {"enabled": True}}}
    with pytest.raises(KeyError, match="source_type"):
        crossval.crossval_settings(cfg)


def test_settings_bad_source_type_raises() -> None:
    cfg = {"resource": {"crossval": {"enabled": True, "source_type": "bogus"}}}
    with pytest.raises(ValueError, match="source_type"):
        crossval.crossval_settings(cfg)


@pytest.mark.parametrize("bad_tol", [0.0, -1.0, "abc"])
def test_settings_bad_tolerance_raises(bad_tol: Any) -> None:
    cfg = {
        "resource": {
            "crossval": {
                "enabled": True,
                "source_type": "merra2",
                "drift_tolerance_pct": bad_tol,
            }
        }
    }
    with pytest.raises(ValueError, match="drift_tolerance_pct"):
        crossval.crossval_settings(cfg)


# ── build_crossval_assessment: disclose, never mutate ──────────────────────────


def test_assessment_validate_mode_and_within_tolerance(
    scenario: Dict[str, Any],
) -> None:
    """A second source matching the declared Weibull discloses small in-tolerance drift."""
    series = _weibull_series(8.199, 2.665)  # == declared A/k
    res = crossval.build_crossval_assessment(
        series,
        scenario,
        WS_COL,
        source_type="merra2",
        source_id="NASA_POWER_WS50M",
        drift_tolerance_pct=5.0,
    )
    assert res["mode"] == "validate"
    assert res["source_type"] == "merra2"
    assert res["source_id"] == "NASA_POWER_WS50M"
    assert res["drift"]["within_tolerance"] is True
    # deviation vs the frozen resource.wind headline is disclosed (all three fields present)
    dev = res["deviation_vs_declared"]
    assert set(dev) == {"mean_ws_pct", "capacity_factor_pct", "aep_pct"}
    assert all(v is not None for v in dev.values())


def test_assessment_never_mutates_scenario(scenario: Dict[str, Any]) -> None:
    """The declared baseline (wind_resource + resource.wind) is byte-identical after a run."""
    before = copy.deepcopy(scenario)
    crossval.build_crossval_assessment(
        _weibull_series(9.5, 2.2), scenario, WS_COL, source_type="merra2"
    )
    assert scenario["wind_resource"] == before["wind_resource"]
    assert scenario["resource"]["wind"] == before["resource"]["wind"]


def test_assessment_out_of_tolerance_warns_not_mutates(
    scenario: Dict[str, Any], caplog: pytest.LogCaptureFixture
) -> None:
    """A materially different source flags drift (>tol) but still only discloses."""
    series = _weibull_series(6.0, 2.665)  # A ~27% below declared 8.199
    with caplog.at_level("WARNING"):
        res = crossval.build_crossval_assessment(
            series, scenario, WS_COL, source_type="merra2", drift_tolerance_pct=5.0
        )
    assert res["mode"] == "validate"
    assert res["drift"]["within_tolerance"] is False
    assert res["deviation_vs_declared"]["mean_ws_pct"] < 0  # lower resource disclosed
    assert "drift exceeds" in caplog.text
    # declared baseline unchanged
    assert scenario["wind_resource"]["weibull_a"] == 8.199


def test_assessment_bad_source_type_raises(scenario: Dict[str, Any]) -> None:
    with pytest.raises(ValueError, match="source_type"):
        crossval.build_crossval_assessment(
            _weibull_series(8.199, 2.665), scenario, WS_COL, source_type="bogus"
        )


def test_assessment_partial_baseline_yields_null_deviation(
    scenario: Dict[str, Any],
) -> None:
    """A slim resource.wind (no headline fields) yields null deviations, not a raise."""
    sc = copy.deepcopy(scenario)
    sc["resource"]["wind"] = {"source_id": "x", "source_type": "REFERENCE"}
    res = crossval.build_crossval_assessment(
        _weibull_series(8.199, 2.665), sc, WS_COL, source_type="local"
    )
    assert res["deviation_vs_declared"] == {
        "mean_ws_pct": None,
        "capacity_factor_pct": None,
        "aep_pct": None,
    }
    # the hard drift-vs-declared-Weibull baseline is still computed
    assert res["drift"]["within_tolerance"] is True


def test_assessment_tolerance_defaults_from_scenario_block(
    scenario: Dict[str, Any],
) -> None:
    """With no explicit tolerance, it reads resource.crossval.drift_tolerance_pct."""
    sc = copy.deepcopy(scenario)
    sc.setdefault("resource", {})["crossval"] = {
        "enabled": True,
        "source_type": "merra2",
        "drift_tolerance_pct": 1.0,  # very tight
    }
    res = crossval.build_crossval_assessment(
        _weibull_series(8.6, 2.665), sc, WS_COL, source_type="merra2"
    )
    assert res["drift"]["tolerance_pct"] == 1.0


# ── load_reference_series routing (local / merra2 / newa) ──────────────────────


def test_load_local_series(tmp_path: Path) -> None:
    csv = tmp_path / "merra2_local.csv"
    pd.DataFrame({WS_COL: [7.1, 8.2, 6.5]}).to_csv(csv, index=False)
    settings = {"source_type": "local", "series_path": str(csv)}
    frame = crossval.load_reference_series(settings, ws_column=WS_COL)
    assert list(frame[WS_COL]) == [7.1, 8.2, 6.5]


def test_load_local_missing_path_raises() -> None:
    with pytest.raises(ValueError, match="series_path is required"):
        crossval.load_reference_series({"source_type": "local"}, ws_column=WS_COL)


def test_load_local_missing_column_raises(tmp_path: Path) -> None:
    csv = tmp_path / "wrong.csv"
    pd.DataFrame({"speed": [1.0, 2.0]}).to_csv(csv, index=False)
    with pytest.raises(ValueError, match="no column"):
        crossval.load_reference_series(
            {"source_type": "local", "series_path": str(csv)}, ws_column=WS_COL
        )


def test_load_newa_is_not_fetched() -> None:
    """NEWA is EU-only and must NOT be fetched for the Sri Lanka site — it raises."""
    with pytest.raises(ValueError, match="NEWA covers Europe only"):
        crossval.load_reference_series({"source_type": "newa"}, ws_column=WS_COL)


def test_load_merra2_missing_site_args_raises() -> None:
    with pytest.raises(ValueError, match="site centroid"):
        crossval.load_reference_series({"source_type": "merra2"}, ws_column=WS_COL)


# ── fetch_merra2_series: requests boundary mocked (zero network) ───────────────


class _FakeResponse:
    def __init__(self, payload: Dict[str, Any]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:  # noqa: D401 - stub
        return None

    def json(self) -> Dict[str, Any]:
        return self._payload


def test_fetch_merra2_parses_power_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    """A well-formed NASA POWER payload is parsed into a wind-speed frame (no network)."""
    payload = {
        "properties": {
            "parameter": {
                "WS50M": {
                    "2020010100": 7.1,
                    "2020010101": 8.4,
                    "2020010102": -999.0,  # fill value -> dropped
                    "2020010103": 6.9,
                }
            }
        }
    }
    captured: Dict[str, Any] = {}

    def fake_get(url: str, params: Dict[str, Any], timeout: float) -> _FakeResponse:
        captured["url"] = url
        captured["params"] = params
        return _FakeResponse(payload)

    import requests

    monkeypatch.setattr(requests, "get", fake_get)
    frame = crossval.fetch_merra2_series(8.27, 79.75, 2020, 2020, ws_column=WS_COL)
    assert captured["url"] == crossval.NASA_POWER_HOURLY_URL
    assert captured["params"]["parameters"] == "WS50M"
    assert captured["params"]["start"] == "20200101"
    assert captured["params"]["end"] == "20201231"
    # -999 fill value dropped, three usable values remain
    assert list(frame[WS_COL]) == [7.1, 8.4, 6.9]


def test_fetch_merra2_no_wind_field_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    import requests

    monkeypatch.setattr(
        requests, "get", lambda url, params, timeout: _FakeResponse({"properties": {}})
    )
    with pytest.raises(RuntimeError, match="did not contain a WS50M"):
        crossval.fetch_merra2_series(8.27, 79.75, 2020, 2020, ws_column=WS_COL)


def test_fetch_merra2_all_fill_values_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    import requests

    payload = {"properties": {"parameter": {"WS50M": {"2020010100": -999.0}}}}
    monkeypatch.setattr(
        requests, "get", lambda url, params, timeout: _FakeResponse(payload)
    )
    with pytest.raises(RuntimeError, match="no usable WS50M"):
        crossval.fetch_merra2_series(8.27, 79.75, 2020, 2020, ws_column=WS_COL)


def test_load_merra2_routes_to_fetch(monkeypatch: pytest.MonkeyPatch) -> None:
    """load_reference_series('merra2', ...) delegates to fetch_merra2_series."""
    sentinel = pd.DataFrame({WS_COL: [5.0, 6.0]})

    def fake_fetch(
        lat: float, lon: float, sy: int, ey: int, *, ws_column: str
    ) -> pd.DataFrame:
        assert (lat, lon, sy, ey, ws_column) == (8.27, 79.75, 2005, 2024, WS_COL)
        return sentinel

    monkeypatch.setattr(crossval, "fetch_merra2_series", fake_fetch)
    out = crossval.load_reference_series(
        {"source_type": "merra2"},
        latitude=8.27,
        longitude=79.75,
        start_year=2005,
        end_year=2024,
        ws_column=WS_COL,
    )
    assert out is sentinel


# ── summarise_deviation (report helper) ────────────────────────────────────────


def test_summarise_deviation_formats() -> None:
    lines = crossval.summarise_deviation(
        {"mean_ws_pct": 1.23, "capacity_factor_pct": None, "aep_pct": -2.0}
    )
    joined = "\n".join(lines)
    assert "mean wind speed: +1.23% vs declared ERA5" in joined
    assert "capacity factor: n/a" in joined
    assert "AEP: -2.00% vs declared ERA5" in joined


# ── schema guard: opt-in, byte-identical when absent, enforced when present ────


def _live_schema_guard() -> tuple[Any, type]:
    """Resolve the CURRENT ``schema_guard`` symbols from ``sys.modules``.

    Earlier suite tests (``tests/lint/test_import_smoke.py::test_import_speed_baseline``)
    deliberately evict the whole ``analytics.*`` graph from ``sys.modules`` and re-import
    it, which forks a fresh ``config_schema`` (a NEW ``_REGISTRY``) away from the symbols a
    module-level ``from analytics.schema_guard import ...`` bound at collection time. Binding
    the guard here — after that eviction has run — guarantees the validator and the registry
    it reads are the SAME live objects the interface schema re-registers into, so the opt-in
    ``crossval`` specs are actually enforced regardless of suite ordering.
    """
    import importlib

    guard_mod = importlib.import_module("analytics.schema_guard")
    return guard_mod.validate_config_for_v14, guard_mod.ConfigValidationError


def test_schema_guard_absent_block_is_untouched(scenario: Dict[str, Any]) -> None:
    """No resource.crossval -> the guard adds no crossval enforcement (opt-in default OFF)."""
    guard, _ = _live_schema_guard()
    # the shipped lender scenario has no crossval block; it validates cleanly today
    guard(scenario, "lender", ["cashflow", "debt"])


def test_schema_guard_enforces_declared_block(scenario: Dict[str, Any]) -> None:
    """A declared-but-malformed crossval block fails the pre-flight gate (CESSPIT)."""
    guard, config_error = _live_schema_guard()
    sc = copy.deepcopy(scenario)
    sc["resource"]["crossval"] = {"enabled": True}  # missing source_type
    with pytest.raises(config_error, match="source_type"):
        guard(sc, "lender", ["cashflow", "debt"])


def test_schema_guard_accepts_valid_block(scenario: Dict[str, Any]) -> None:
    guard, _ = _live_schema_guard()
    sc = copy.deepcopy(scenario)
    sc["resource"]["crossval"] = {"enabled": True, "source_type": "merra2"}
    guard(sc, "lender", ["cashflow", "debt"])


def test_schema_guard_rejects_bad_source_type(scenario: Dict[str, Any]) -> None:
    guard, config_error = _live_schema_guard()
    sc = copy.deepcopy(scenario)
    sc["resource"]["crossval"] = {"enabled": True, "source_type": "gribble"}
    with pytest.raises(config_error, match="source_type"):
        guard(sc, "lender", ["cashflow", "debt"])
