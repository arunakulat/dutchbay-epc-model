import pytest
from dutchbay_v13 import scenario_runner as sr


def test_validate_params_with_schema(monkeypatch):
    schema = {"tariff_usd_per_kwh": {"min": 0.0, "max": 1.0}}
    monkeypatch.setattr(sr, "SCHEMA", schema, raising=False)
    ok = sr._validate_params_dict({"tariff_usd_per_kwh": 0.5}, where="test")
    assert ok["tariff_usd_per_kwh"] == 0.5
    with pytest.raises(ValueError):
        sr._validate_params_dict({"tariff_usd_per_kwh": 2.0}, where="test")


def test_validate_debt_with_schema(monkeypatch):
    ds = {"debt_ratio": {"min": 0.0, "max": 1.0}}
    monkeypatch.setattr(sr, "DEBT_SCHEMA", ds, raising=False)
    ok = sr._validate_debt_dict({"debt_ratio": 0.7}, where="test")
    assert ok["debt_ratio"] == 0.7
    with pytest.raises(ValueError):
        sr._validate_debt_dict({"debt_ratio": 2.0}, where="test")
