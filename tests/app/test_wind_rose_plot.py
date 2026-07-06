"""Tests for the polar wind-rose renderer (issue #853.2) — display-only.

The renderer re-projects a :func:`analytics.wind.wind_rose.build_wind_rose` block into a
self-contained base64 ``data:image/png`` URI, carrying its own CASPER call-time matplotlib
guard. It moves no KPI and feeds no AEP/wake path.
"""

from __future__ import annotations

import base64
import sys

from analytics.wind.wind_rose import build_wind_rose
from app.reports.wind_rose_plot import render_wind_rose_polar_data_uri


def _decode_png_header(data_uri: str) -> bytes:
    assert data_uri.startswith("data:image/png;base64,")
    return base64.b64decode(data_uri.split(",", 1)[1])[:8]


_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def test_renders_direction_only_rose_to_png_data_uri() -> None:
    # A pre-binned direction-only rose (no speed enrichment) still plots.
    rose = build_wind_rose([0.0, 0.0, 90.0, 180.0, 270.0], n_sectors=8)
    uri = render_wind_rose_polar_data_uri(rose)
    assert uri is not None
    # It is a genuine PNG payload, not a placeholder / empty string.
    assert _decode_png_header(uri) == _PNG_MAGIC


def test_renders_energy_enriched_rose_overlay() -> None:
    # A speed-enriched rose carries energy_frequency; the overlay path is exercised.
    directions = [10.0] * 20 + [200.0] * 20 + [90.0] * 5
    speeds = [12.0] * 20 + [6.0] * 20 + [3.0] * 5
    rose = build_wind_rose(directions, n_sectors=12, ws_series=speeds)
    assert "energy_frequency" in rose
    uri = render_wind_rose_polar_data_uri(rose)
    assert uri is not None
    assert _decode_png_header(uri) == _PNG_MAGIC


def test_returns_none_on_missing_vectors() -> None:
    # No sector_deg / frequency => nothing to plot; fail soft to None (not a crash).
    assert render_wind_rose_polar_data_uri({}) is None
    assert render_wind_rose_polar_data_uri({"sector_deg": [0.0, 90.0]}) is None
    assert render_wind_rose_polar_data_uri({"frequency": [0.5, 0.5]}) is None


def test_returns_none_on_length_mismatch() -> None:
    # Length mismatch between sector_deg and frequency => degrade to None.
    rose = {"sector_deg": [0.0, 90.0, 180.0], "frequency": [0.5, 0.5]}
    assert render_wind_rose_polar_data_uri(rose) is None


def test_energy_length_mismatch_is_ignored_not_fatal() -> None:
    # A malformed energy vector (wrong length) is dropped; the frequency rose still renders.
    rose = {
        "sector_deg": [0.0, 90.0, 180.0, 270.0],
        "frequency": [0.4, 0.3, 0.2, 0.1],
        "energy_frequency": [0.5, 0.5],  # wrong length -> ignored
    }
    uri = render_wind_rose_polar_data_uri(rose)
    assert uri is not None
    assert _decode_png_header(uri) == _PNG_MAGIC


def test_degrades_to_none_when_matplotlib_absent(monkeypatch) -> None:
    # CASPER: the optional plotting lib is guarded at call-time. Simulate its absence by
    # making `import matplotlib` raise, and confirm the renderer returns None (no crash).
    real_import = (
        __builtins__["__import__"]
        if isinstance(__builtins__, dict)
        else __builtins__.__import__
    )

    def _blocked_import(name, *args, **kwargs):
        if name == "matplotlib" or name.startswith("matplotlib."):
            raise ImportError("simulated: matplotlib not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", _blocked_import)
    # Drop any cached module so the guarded import path re-triggers the blocked import.
    monkeypatch.delitem(sys.modules, "matplotlib", raising=False)
    monkeypatch.delitem(sys.modules, "matplotlib.pyplot", raising=False)

    rose = build_wind_rose([0.0, 90.0, 180.0, 270.0], n_sectors=8)
    assert render_wind_rose_polar_data_uri(rose) is None
