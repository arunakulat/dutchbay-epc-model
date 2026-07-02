"""Tests for the AEP uncertainty knobs: P50 bankability haircut + correlation-aware sigma.

Two config-driven options on the IEC 61400-15-2 exceedance build-up:
- ``resource.uncertainty.p50_haircut_pct`` — a haircut on the modelled P50 (empirical
  pre-construction over-prediction), applied before the P-value build-up. At the CONFIG layer
  (aep_summary_builder) a scenario that is SILENT on it now defaults to the recommended
  ``RECOMMENDED_P50_HAIRCUT_PCT`` (5%, WES 2026; #587), not 0 — a no-EYA scenario is corrected
  for the documented P50 optimism. The ``exceedance_levels`` KERNEL keeps a 0.0 identity default.
- ``resource.uncertainty.correlation`` — uniform inter-category correlation rho in [0,1]
  for combining the systematic sigmas (rho=0 = the IEC root-sum-of-squares baseline;
  rho=1 = fully correlated / linear sum). RSS empirically understates total uncertainty. Defaults
  to 0.

Every COMMITTED scenario now sets p50_haircut_pct explicitly (has-EYA DutchBay scenarios — lender,
5usc, hybrid, both capex variants — at 2.0%; the two no-EYA fixtures kalpitiya_160m/mullikulam at 0.0%),
so the recommended default governs only future NEW no-EYA scenarios — all committed KPIs are unchanged.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from analytics.scenario_loader import load_scenario_config
from analytics.wind.aep_summary_builder import build_aep_summary_from_config
from wind_resource.bankable_aep import (
    RECOMMENDED_P50_HAIRCUT_PCT,
    UncertaintyBudget,
    exceedance_levels,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER = str(REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml")


# --- engine: UncertaintyBudget correlation -------------------------------------
def test_systematic_sigma_rss_at_zero_correlation() -> None:
    b = UncertaintyBudget()
    rss = (4.5**2 + 4.0**2 + 3.0**2 + 2.5**2 + 5.0**2 + 3.0**2) ** 0.5
    assert b.systematic_sigma_pct(0.0) == pytest.approx(rss, abs=1e-9)  # ~9.25


def test_systematic_sigma_linear_at_full_correlation() -> None:
    b = UncertaintyBudget()
    linear = 4.5 + 4.0 + 3.0 + 2.5 + 5.0 + 3.0  # 22.0
    assert b.systematic_sigma_pct(1.0) == pytest.approx(linear, abs=1e-9)


def test_systematic_sigma_monotonic_in_correlation() -> None:
    b = UncertaintyBudget()
    s0, s5, s1 = (
        b.systematic_sigma_pct(0.0),
        b.systematic_sigma_pct(0.5),
        b.systematic_sigma_pct(1.0),
    )
    assert s0 < s5 < s1  # correlation widens uncertainty


def test_combined_sigma_reproduces_canonical_10pct() -> None:
    """The default budget's 1-yr sigma is ~10.07% (matches the canonical mock)."""
    assert UncertaintyBudget().combined_sigma_pct(1.0, 0.0) == pytest.approx(
        10.07, abs=0.02
    )


# --- engine: exceedance haircut + correlation ----------------------------------
def test_exceedance_haircut_scales_p50() -> None:
    b = UncertaintyBudget()
    base = exceedance_levels(100.0, b)
    cut = exceedance_levels(100.0, b, p50_haircut_pct=10.0)
    assert cut.p50_gwh == pytest.approx(90.0, abs=1e-9)  # 100 x (1 - 0.10)
    # all P-values shift down proportionally with the haircut P50
    assert cut.p90_1yr_gwh == pytest.approx(base.p90_1yr_gwh * 0.90, rel=1e-9)


def test_exceedance_correlation_widens_lowers_p90_only() -> None:
    b = UncertaintyBudget()
    base = exceedance_levels(100.0, b, correlation=0.0)
    corr = exceedance_levels(100.0, b, correlation=0.7)
    assert corr.p50_gwh == pytest.approx(base.p50_gwh)  # P50 unaffected by uncertainty
    assert corr.sigma_1yr_pct > base.sigma_1yr_pct
    assert corr.p90_1yr_gwh < base.p90_1yr_gwh  # wider band -> lower P90


# --- builder: config-driven (haircut defaults to recommended; correlation default-off) --------
def test_builder_default_reproduces_canonical_exceedance() -> None:
    """LENDER YAML carries the 2% pre-construction P50 haircut -> canonical post-haircut exceedance."""
    summary = build_aep_summary_from_config(load_scenario_config(LENDER))
    assert summary["net_site_aep_gwh"] == pytest.approx(
        464.3, abs=0.5
    )  # 464.36 post 2% haircut
    exc = summary["exceedance"]
    assert exc["sigma_1yr_pct"] == pytest.approx(10.07, abs=0.05)
    assert exc["net_aep_p90_1yr_gwh"] == pytest.approx(
        404.4, abs=1.0
    )  # 412.7 -> 404.4 post 2% haircut
    assert (
        summary["uncertainty"]["p50_haircut_pct"] == 2.0
    )  # 2% pre-construction P50 haircut now in LENDER YAML
    assert summary["uncertainty"]["correlation"] == 0.0


def test_builder_haircut_reduces_bankable_p50() -> None:
    cfg = copy.deepcopy(dict(load_scenario_config(LENDER)))
    cfg["resource"]["uncertainty"] = {"p50_haircut_pct": 5.0}
    summary = build_aep_summary_from_config(cfg)
    assert summary["net_site_aep_gwh"] == pytest.approx(473.8 * 0.95, abs=0.5)  # 450.1
    # the modelled (pre-haircut) P50 is preserved for provenance
    assert summary["uncertainty"]["modelled_p50_gwh"] == pytest.approx(473.8, abs=0.5)
    assert summary["exceedance"]["net_aep_p50_gwh"] == pytest.approx(450.1, abs=0.5)


def test_builder_defaults_to_recommended_haircut_when_silent() -> None:
    """A scenario SILENT on p50_haircut_pct now picks up the recommended WES-2026 default (#587):
    a no-EYA scenario is corrected for pre-construction P50 optimism rather than assuming 0%. The
    committed DutchBay scenarios all set it explicitly, so this governs only no-EYA regenerations.
    """
    cfg = copy.deepcopy(dict(load_scenario_config(LENDER)))
    cfg["resource"]["uncertainty"] = {}  # silent -> recommended default applies
    summary = build_aep_summary_from_config(cfg)
    assert summary["uncertainty"]["p50_haircut_pct"] == RECOMMENDED_P50_HAIRCUT_PCT
    assert summary["net_site_aep_gwh"] == pytest.approx(
        473.8 * (1.0 - RECOMMENDED_P50_HAIRCUT_PCT / 100.0), abs=0.5
    )
    # provenance: the modelled (pre-haircut) P50 is still preserved
    assert summary["uncertainty"]["modelled_p50_gwh"] == pytest.approx(473.8, abs=0.5)


def test_builder_correlation_widens_uncertainty() -> None:
    cfg = copy.deepcopy(dict(load_scenario_config(LENDER)))
    # Pin the haircut to 0.0 so this isolates the correlation knob: post-#587 an uncertainty
    # block that omits p50_haircut_pct picks up the recommended 5% default, which would confound
    # the "P50 unchanged by correlation" assertion.
    cfg["resource"]["uncertainty"] = {"correlation": 0.5, "p50_haircut_pct": 0.0}
    summary = build_aep_summary_from_config(cfg)
    assert summary["net_site_aep_gwh"] == pytest.approx(473.8, abs=0.5)  # P50 unchanged
    assert summary["exceedance"]["sigma_1yr_pct"] > 10.07  # wider than RSS baseline
    assert summary["exceedance"]["net_aep_p90_1yr_gwh"] < 412.7
