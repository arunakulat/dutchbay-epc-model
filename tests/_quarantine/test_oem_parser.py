#!/usr/bin/env python
"""Comprehensive test suite for OEM power curve parser.

Tests Envision EN-171-6.5 MW power curve processing, interpolation,
AEP calculations, and IEC 61400-12-1:2022 compliance validation.

Run:
    pytest tests/analytics/test_oem_parser.py -v --cov=analytics.power_curves.oem_parser

Coverage Target: >90%
Test Count: 15 test cases

Context:
    Sprint 17 - Issue #16: OEM Power Curve Parser
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from analytics.power_curves.oem_parser import (
    ENVISION_EN171_65_POWER_CURVE,
    ENVISION_EN171_65_SPECS,
    compute_aep_from_curve,
    interpolate_power_curve,
    parse_envision_en171_curve,
    validate_power_curve_iec_compliance,
)


# ══════════════════════════════════════════════════════════════════════════════
# FIXTURES
# ══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def reference_curve():
    """Load power curve at reference air density."""
    return parse_envision_en171_curve(air_density_kgm3=None)


@pytest.fixture
def site_curve():
    """Load power curve at site air density (1.15 kg/m³)."""
    return parse_envision_en171_curve(air_density_kgm3=1.15)


@pytest.fixture
def weibull_wind_8760():
    """Generate 8760-hour wind speed timeseries from Weibull distribution."""
    np.random.seed(42)  # Reproducible
    # Weibull: k=2.0, A=7.5 m/s (typical for good wind site)
    wind_speeds = np.random.weibull(2.0, 8760) * 7.5
    return wind_speeds


@pytest.fixture
def constant_wind_8760():
    """Generate 8760-hour constant wind speed timeseries."""
    return np.full(8760, 8.0)  # 8 m/s constant


@pytest.fixture
def low_wind_8760():
    """Generate 8760-hour low wind speed timeseries."""
    np.random.seed(43)
    return np.random.weibull(1.5, 8760) * 4.5  # Mean ~4 m/s


@pytest.fixture
def turbine_config():
    """Standard turbine configuration for testing."""
    return {
        "n_turbines": 23,
        "capacity_mw": 6.5,
        "hub_height_m": 150,
    }


# Test implementations would continue here...
# (Truncated for brevity - original test code continues)
