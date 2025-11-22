# tests/api/test_bad_missing_tax_schema_guard.py
from pathlib import Path

import pytest

from analytics.scenario_loader import load_scenario_config
from analytics.schema_guard import ConfigValidationError, validate_config_for_v14


def test_bad_missing_tax_yaml_is_rejected_by_schema_guard():
    """
    Ensure that the known-bad scenario 'bad_missing_tax.yaml' is
    rejected by the v14 schema guard with a clear error about
    corporate_tax_rate.
    """
    cfg_path = Path("scenarios") / "bad_missing_tax.yaml"
    assert cfg_path.is_file(), "Expected scenarios/bad_missing_tax.yaml to exist"

    config = load_scenario_config(str(cfg_path))

    with pytest.raises(ConfigValidationError) as excinfo:
        validate_config_for_v14(
            raw_config=config,
            config_path=str(cfg_path),
            modules=["cashflow"],
        )

    msg = str(excinfo.value)
    # Defensive: make sure the error really is about corporate_tax_rate
    assert "corporate_tax_rate" in msg
    assert "bad_missing_tax.yaml" in msg

    