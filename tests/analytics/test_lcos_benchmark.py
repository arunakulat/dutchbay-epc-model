"""LCOS advisory sanity band vs PNNL ESGC 2024 / Lazard LCOS v10.0 non-ITC (#605).

analytics.cost.benchmark.lcos_benchmark is a report-only external plausibility check on
the computed BESS LCOS (finance.bess_lcos): the USD 115-254/MWh NON-ITC comparator band
(DutchBay has no US ITC), config-sourced from defaults.cost_reference (CCCDIR). An
out-of-band LCOS logs a WARNING citing the sources; an undefined LCOS (None) is
explicitly not-comparable; nothing ever raises and no computed value changes. The model's
LCOS is a fixed-dispatch basis (the #596 limitation notes on each LcosResult), so the
band is a review prompt, not a gate.
"""

from __future__ import annotations

import json

import pytest

from analytics.cost.benchmark import lcos_band_usd_per_mwh, lcos_benchmark


def test_lcos_band_is_config_sourced() -> None:
    """The band, sources, and vintage come from defaults.cost_reference, not literals."""
    low, high, sources, year = lcos_band_usd_per_mwh()
    assert low == pytest.approx(115.0)  # config/defaults.yaml, non-ITC low
    assert high == pytest.approx(254.0)  # config/defaults.yaml, non-ITC high
    assert year == 2025  # Lazard LCOS v10.0 publication vintage
    joined = " ".join(sources)
    assert "PNNL ESGC 2024" in joined
    assert "Lazard LCOS v10.0" in joined
    assert "non-ITC" in joined


def test_in_band_lcos_passes_quietly(caplog: pytest.LogCaptureFixture) -> None:
    """An in-band LCOS is disclosed with the sources cited and logs no warning."""
    with caplog.at_level("WARNING", logger="analytics.cost.benchmark"):
        b = lcos_benchmark(180.0)
    assert b["within_band"] is True
    assert b["band_low_usd_per_mwh"] == pytest.approx(115.0)
    assert b["band_high_usd_per_mwh"] == pytest.approx(254.0)
    assert "PNNL ESGC 2024" in b["note"] and "Lazard LCOS v10.0" in b["note"]
    assert "OUTSIDE" not in b["note"]
    assert caplog.records == []


def test_band_edges_are_within_band() -> None:
    """The band is inclusive at both edges."""
    low, high, _sources, _year = lcos_band_usd_per_mwh()
    assert lcos_benchmark(low)["within_band"] is True
    assert lcos_benchmark(high)["within_band"] is True


def test_below_band_lcos_flags_and_warns(caplog: pytest.LogCaptureFixture) -> None:
    """A below-band LCOS is flagged OUTSIDE/BELOW and logs a WARNING citing the sources."""
    with caplog.at_level("WARNING", logger="analytics.cost.benchmark"):
        b = lcos_benchmark(89.0)
    assert b["within_band"] is False
    assert "BELOW" in b["note"] and "OUTSIDE" in b["note"]
    warnings = [r for r in caplog.records if r.levelname == "WARNING"]
    assert len(warnings) == 1
    assert "PNNL ESGC 2024" in warnings[0].getMessage()
    assert "Lazard LCOS v10.0" in warnings[0].getMessage()


def test_above_band_lcos_flags_and_warns(caplog: pytest.LogCaptureFixture) -> None:
    """An above-band LCOS is flagged OUTSIDE/ABOVE and logs a WARNING."""
    with caplog.at_level("WARNING", logger="analytics.cost.benchmark"):
        b = lcos_benchmark(400.0)
    assert b["within_band"] is False
    assert "ABOVE" in b["note"] and "OUTSIDE" in b["note"]
    assert any(r.levelname == "WARNING" for r in caplog.records)


def test_none_lcos_is_not_comparable_never_raises(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An undefined LCOS (None, e.g. zero DoD) yields an explicit not-comparable note —
    within_band is None (tri-state), never a crash or a silent zero (CESSPIT)."""
    with caplog.at_level("WARNING", logger="analytics.cost.benchmark"):
        b = lcos_benchmark(None)
    assert b["within_band"] is None
    assert "not comparable" in b["note"]
    assert "PNNL ESGC 2024" in b["note"]  # sources still cited for the disclosure
    assert caplog.records == []  # undefined is a note, not an out-of-band warning


def test_non_finite_lcos_is_not_comparable() -> None:
    """A non-finite LCOS (defensive) is treated like undefined, not compared."""
    assert lcos_benchmark(float("nan"))["within_band"] is None
    assert lcos_benchmark(float("inf"))["within_band"] is None


def test_advisory_is_json_serialisable() -> None:
    """The advisory dict round-trips through JSON for the report-pack surfaces."""
    for value in (180.0, 89.0, None):
        json.dumps(lcos_benchmark(value))  # raises if any field is non-serialisable
