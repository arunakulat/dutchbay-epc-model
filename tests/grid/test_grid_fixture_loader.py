"""Loader test for the redacted Envision ENPCS01 grid-code fixture (D0, #871).

This test intentionally imports NO grid libraries (pandapower/andes/opendssdirect
arrive in D1) — it only proves the committed reference fixture parses as YAML and
carries the mandated provenance string plus the parsed grid-code CONstants. The OEM
binaries (.dyr/.dll/.pfd) are proprietary and are never committed or executed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

_REPO = Path(__file__).resolve().parents[2]
_FIXTURE = _REPO / "tests" / "fixtures" / "grid" / "envision_enpcs01_gridcode.yaml"

_EXPECTED_PROVENANCE = (
    "Envision ENPCS01 GFL PCS — PSS/E UDM V2 (2025-03-17) + "
    "DigSILENT V1.2a (2025-05-06); grid-code CONs parsed 2026-07-06; "
    "OEM .dyr/.dll/.pfd proprietary, referenced-not-executed."
)


def _load() -> dict[str, Any]:
    data: dict[str, Any] = yaml.safe_load(_FIXTURE.read_text())
    return data


def test_fixture_exists() -> None:
    assert _FIXTURE.is_file(), f"missing grid-code fixture: {_FIXTURE}"


def test_fixture_parses_and_carries_provenance() -> None:
    data = _load()
    assert isinstance(data, dict)
    assert data["provenance"] == _EXPECTED_PROVENANCE


def test_grid_code_constants() -> None:
    pcs = _load()["pcs"]
    assert pcs["model"] == "Envision ENPCS01"
    assert pcs["topology"] == "GFL"
    assert pcs["rating_kw"] == 2750
    assert pcs["pf_range"] == [-0.95, 0.95]
    assert pcs["q_range_pu"] == [-0.5, 0.5]
    assert pcs["lvrt_enter_pu"] == 0.89
    assert pcs["hvrt_enter_pu"] == 1.10
    assert pcs["lvrt_k_factor"] == 2.0
    assert pcs["hvrt_k_factor"] == 1.9

    freq = pcs["freq_trip_hz"]
    assert freq["underfrequency"] == [[47.5, 1800.0], [47.0, 0.1]]
    assert freq["overfrequency"] == [[51.5, 1800.0], [52.0, 0.1]]

    volt = pcs["volt_trip_pu"]
    assert volt["undervoltage"] == [[0.85, 21.0], [0.50, 11.0]]
    assert volt["overvoltage"] == [[1.1, 20.0], [1.2, 1.0], [1.3, 0.1]]
