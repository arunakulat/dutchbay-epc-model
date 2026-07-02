"""Regression tests for the batch discount-rate default consolidation (#586).

Before #586 the batch default discount rate was stated three times with two
different values: a silent ``0.10`` code fallback in
``run_scenario_analytics_v14.py``, the authoritative ``0.12`` in
``conf/run_scenario_analytics_v14.yaml``, and a ``0.10`` constructor default in
``analytics/scenario_analytics.py``. These tests pin the consolidated contract:

- the packaged YAML remains the authoritative batch value (explicit ``0.12``);
- the CLI fails loudly if the key is missing (no silent code fallback,
  CESSPIT: config explicit);
- invalid values are still rejected with the pre-existing ``ValueError``;
- the direct-API constructor default is single-sourced from
  ``DEFAULT_GLOBAL_DISCOUNT_RATE`` and still resolves to ``0.10``
  (no resolved-value drift for any existing caller).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from analytics.scenario_analytics import DEFAULT_GLOBAL_DISCOUNT_RATE, ScenarioAnalytics
from run_scenario_analytics_v14 import _resolve_default_discount_rate

REPO_ROOT = Path(__file__).resolve().parents[2]
BATCH_CONFIG = REPO_ROOT / "conf" / "run_scenario_analytics_v14.yaml"


def test_missing_key_fails_loud() -> None:
    """A config without the key raises instead of silently defaulting."""
    with pytest.raises(ValueError, match="Missing 'default_discount_rate'"):
        _resolve_default_discount_rate({})


def test_none_value_still_rejected() -> None:
    """An explicit null keeps the pre-existing invalid-value ValueError."""
    with pytest.raises(ValueError, match="Invalid default_discount_rate"):
        _resolve_default_discount_rate({"default_discount_rate": None})


def test_non_numeric_value_rejected() -> None:
    with pytest.raises(ValueError, match="Invalid default_discount_rate"):
        _resolve_default_discount_rate({"default_discount_rate": "not-a-rate"})


def test_valid_values_coerced_to_float() -> None:
    resolved = _resolve_default_discount_rate({"default_discount_rate": 0.12})
    assert resolved == pytest.approx(0.12)
    resolved_str = _resolve_default_discount_rate({"default_discount_rate": "0.12"})
    assert resolved_str == pytest.approx(0.12)


def test_packaged_yaml_is_explicit_and_authoritative() -> None:
    """The committed batch config must carry the key explicitly, at 0.12.

    Deleting the key now fails loudly at runtime; MOVING the value would move
    every batch scenario's default-discounted NPV, i.e. a conscious KPI
    decision — this test pins the committed 0.12 so it cannot drift silently.
    """
    cfg = yaml.safe_load(BATCH_CONFIG.read_text())
    assert isinstance(cfg, dict)
    assert "default_discount_rate" in cfg
    assert cfg["default_discount_rate"] == pytest.approx(0.12)
    assert _resolve_default_discount_rate(cfg) == pytest.approx(0.12)


def test_constructor_default_is_single_sourced(tmp_path: Path) -> None:
    """Direct-API default comes from DEFAULT_GLOBAL_DISCOUNT_RATE (still 0.10)."""
    sa = ScenarioAnalytics(scenarios_dir=tmp_path)
    assert sa.global_default_discount_rate == pytest.approx(
        DEFAULT_GLOBAL_DISCOUNT_RATE
    )
    # Consolidation must not move the resolved default for existing callers.
    assert DEFAULT_GLOBAL_DISCOUNT_RATE == pytest.approx(0.10)
