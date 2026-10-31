"""Required YAML BESS ratings fail at v14 preflight, before finance (#1401)."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
import yaml

from analytics.schema_guard import ConfigValidationError, validate_config_for_v14
from finance.bess_revenue import resolve_bess_specs

SCENARIOS = Path(__file__).resolve().parents[2] / "scenarios"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("power_mw", None),
        ("power_mw", 0),
        ("power_mw", True),
        ("power_mw", float("nan")),
        ("duration_h", None),
        ("duration_h", -4),
        ("duration_h", "4"),
        ("energy_mwh", 400),
        ("energy_mwh", None),
    ],
)
def test_bad_bess_rating_is_refused_before_finance(field: str, value: Any) -> None:
    config = yaml.safe_load(
        (SCENARIOS / "dutchbay_hybrid_bess_2025Q4.yaml").read_text()
    )
    config["generation"]["technologies"]["bess_1"][field] = value
    with pytest.raises(ConfigValidationError, match=field):
        validate_config_for_v14(config, "hostile-bess.yaml", [])


@pytest.mark.parametrize("field", ["power_mw", "duration_h"])
def test_missing_authored_rating_has_no_engine_default(field: str) -> None:
    config = yaml.safe_load(
        (SCENARIOS / "dutchbay_hybrid_bess_2025Q4.yaml").read_text()
    )
    del config["generation"]["technologies"]["bess_1"][field]
    with pytest.raises(ConfigValidationError, match=field):
        validate_config_for_v14(config, "missing-bess.yaml", [])


def test_energy_tariff_derives_energy_from_the_same_authored_ratings() -> None:
    config = yaml.safe_load(
        (SCENARIOS / "ceb_solar_bess_nightpeak_10mw.yaml").read_text()
    )
    original = deepcopy(config)
    block = config["generation"]["technologies"]["bess_unit"]
    del block["energy_mwh"]
    validate_config_for_v14(config, "derived-energy.yaml", [])
    specs = resolve_bess_specs(config)
    assert specs is not None
    assert specs[0]["energy_mwh"] == 40.0
    assert specs[0]["duration_h"] == 4.0
    assert "energy_mwh" not in block
    assert original["generation"]["technologies"]["bess_unit"]["energy_mwh"] == 40.0
