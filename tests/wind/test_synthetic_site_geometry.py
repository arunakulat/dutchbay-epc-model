"""Guard the SYNTHETIC micro-siting geometry derivation (feasibility_reproduce/lib).

The reproduce kit derives a site boundary and baseline layout from committed scenario
parameters because the real geometry was never committed (see
``feasibility_reproduce/cache/micrositing_synthetic_site.yaml``). That derivation is
pure geometry with real branching — a wrong projection or a silently-accepted "real"
provenance would produce authoritative-looking nonsense — so it is tested here even
though the kit itself sits outside the coverage denominator.

The kit is not an installed package; ``lib`` is added to ``sys.path`` the same way the
kit's own scripts import it.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any, Dict

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
KIT_LIB = REPO_ROOT / "feasibility_reproduce" / "lib"
SITE_CONFIG = (
    REPO_ROOT / "feasibility_reproduce" / "cache" / "micrositing_synthetic_site.yaml"
)

if str(KIT_LIB) not in sys.path:
    sys.path.insert(0, str(KIT_LIB))

from synthetic_site import (  # noqa: E402  (path shim above)
    SYNTHETIC_PROVENANCE,
    build_synthetic_site,
    load_synthetic_site,
    turbine_spec_from_power_curve,
)

pytestmark = pytest.mark.skipif(
    not SITE_CONFIG.is_file(), reason="synthetic site config absent"
)


def _config() -> Dict[str, Any]:
    with open(SITE_CONFIG, encoding="utf-8") as handle:
        return yaml.safe_load(handle)


# ─────────────────────────────────────────────────────────────────────────────
# Derivation — the geometry must match the committed scenario parameters
# ─────────────────────────────────────────────────────────────────────────────


def test_site_projects_into_the_declared_utm_zone() -> None:
    """utm_zone '44N' -> EPSG:32644 (WGS84 UTM north = 32600 + zone)."""
    assert load_synthetic_site(SITE_CONFIG).utm_epsg == 32644


def test_baseline_matches_committed_turbine_count_and_spacing() -> None:
    site = load_synthetic_site(SITE_CONFIG)
    assert site.n_turbines == 15
    # Linear north-south: constant easting, 650 m northing steps.
    assert len(set(round(x, 6) for x in site.baseline_x_m)) == 1
    steps = [
        site.baseline_y_m[i + 1] - site.baseline_y_m[i]
        for i in range(len(site.baseline_y_m) - 1)
    ]
    assert all(step == pytest.approx(650.0) for step in steps)
    assert site.array_span_m == pytest.approx(14 * 650.0)


def test_min_spacing_reproduces_the_committed_594m() -> None:
    """3.0 D against the committed 198 m rotor is the pinned 594 m."""
    site = load_synthetic_site(SITE_CONFIG)
    assert site.min_spacing_diameters * 198.0 == pytest.approx(594.0)


def test_boundary_is_a_closed_circle_containing_every_turbine() -> None:
    site = load_synthetic_site(SITE_CONFIG)
    cx = sum(p[0] for p in site.boundary_m) / len(site.boundary_m)
    cy = sum(p[1] for p in site.boundary_m) / len(site.boundary_m)
    radii = [math.hypot(p[0] - cx, p[1] - cy) for p in site.boundary_m]
    assert max(radii) - min(radii) < 1.0  # equidistant vertices => a circle
    radius = radii[0]
    for x, y in zip(site.baseline_x_m, site.baseline_y_m):
        assert math.hypot(x - cx, y - cy) < radius


def test_run_is_deterministic_per_mrm_01() -> None:
    """Same config in, same geometry out — no hidden RNG in the derivation."""
    first, second = load_synthetic_site(SITE_CONFIG), load_synthetic_site(SITE_CONFIG)
    assert first == second
    assert first.random_seed == 42
    assert first.use_smart_start is False


# ─────────────────────────────────────────────────────────────────────────────
# CESSPIT guards — fail loud, name the field, never silently accept
# ─────────────────────────────────────────────────────────────────────────────


def test_refuses_a_non_synthetic_provenance() -> None:
    """A real site boundary must not be laundered through the synthetic builder."""
    cfg = _config()
    cfg["micrositing_synthetic"]["provenance"] = "real"
    with pytest.raises(ValueError, match="provenance must be"):
        build_synthetic_site(cfg)


def test_refuses_a_config_without_the_block() -> None:
    with pytest.raises(ValueError, match="micrositing_synthetic"):
        build_synthetic_site({})


def test_refuses_a_boundary_too_small_for_the_array() -> None:
    """The 2 km radius first considered cannot hold a 9.1 km array — say so."""
    cfg = _config()
    cfg["micrositing_synthetic"]["boundary"]["radius_m"] = 2000
    with pytest.raises(ValueError, match="cannot fit"):
        build_synthetic_site(cfg)


@pytest.mark.parametrize("bad", [0, -1, "abc", None, float("nan")])
def test_rejects_non_positive_or_non_finite_radius(bad: Any) -> None:
    cfg = _config()
    cfg["micrositing_synthetic"]["boundary"]["radius_m"] = bad
    with pytest.raises(ValueError, match="radius_m"):
        build_synthetic_site(cfg)


@pytest.mark.parametrize("bad_zone", ["44", "", "zzN", "0N", "61N"])
def test_rejects_a_malformed_utm_zone(bad_zone: str) -> None:
    cfg = _config()
    cfg["micrositing_synthetic"]["derived_from"]["utm_zone"] = bad_zone
    with pytest.raises(ValueError, match="utm_zone"):
        build_synthetic_site(cfg)


def test_rejects_an_unsupported_boundary_shape() -> None:
    cfg = _config()
    cfg["micrositing_synthetic"]["boundary"]["shape"] = "hexagon"
    with pytest.raises(ValueError, match="only supports 'circle'"):
        build_synthetic_site(cfg)


# ─────────────────────────────────────────────────────────────────────────────
# Turbine spec — real physics from the COMMITTED curve, not invented numbers
# ─────────────────────────────────────────────────────────────────────────────


def test_turbine_spec_comes_from_the_committed_power_curve() -> None:
    spec = turbine_spec_from_power_curve(
        "iea_reference_10mw",
        rotor_diameter_m=198.0,
        hub_height_m=150.0,
        curves_path=REPO_ROOT / "wind_resource" / "config" / "power_curves.yaml",
    )
    assert spec.name == "IEA_Reference_10MW_198"
    assert len(spec.wind_speed_ms) == len(spec.power_kw) == len(spec.thrust_coefficient)
    assert max(spec.power_kw) == pytest.approx(10638.3)
    assert all(0.0 <= ct <= 1.2 for ct in spec.thrust_coefficient)


def test_turbine_spec_names_an_unknown_curve() -> None:
    with pytest.raises(ValueError, match="not found"):
        turbine_spec_from_power_curve(
            "no_such_turbine",
            rotor_diameter_m=198.0,
            hub_height_m=150.0,
            curves_path=REPO_ROOT / "wind_resource" / "config" / "power_curves.yaml",
        )


def test_committed_config_declares_itself_synthetic() -> None:
    """The shipped config must never drift to claiming it is a real site."""
    block = _config()["micrositing_synthetic"]
    assert block["provenance"] == SYNTHETIC_PROVENANCE
    assert block["not_site_representative"] is True
