"""GIS-MCDM suitability-surface tests (#834): normalisation, AHP+CR, WLC, exclusion veto.

The pure-numpy math (normalisation, AHP priority vector + consistency ratio, WLC, veto) is
tested without any GIS toolchain. The GeoTIFF export path is exercised only when ``rasterio``
(the optional ``[gis]`` extra) is installed -- CASPER-skipped otherwise.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from analytics.gis.mcdm_suitability import (
    BENEFIT,
    COST,
    CR_ACCEPTANCE_THRESHOLD,
    SAATY_RANDOM_INDEX,
    ahp_priority_vector,
    apply_exclusion_veto,
    build_suitability_surface,
    normalise_criterion,
    weighted_linear_combination,
)

# --------------------------------------------------------------------------------------
# Normalisation: direction of preference + breakpoint clipping
# --------------------------------------------------------------------------------------


def test_normalise_benefit_direction_higher_is_better():
    # wind speed: ramp 5 -> 10 m/s; below 5 -> 0, above 10 -> 1, midpoint -> 0.5
    raster = np.array([[5.0, 7.5, 10.0], [4.0, 12.0, 6.0]], dtype="float64")
    out = normalise_criterion(raster, BENEFIT, low=5.0, high=10.0)
    expected = np.array([[0.0, 0.5, 1.0], [0.0, 1.0, 0.2]], dtype="float32")
    np.testing.assert_allclose(out, expected, rtol=0, atol=1e-6)


def test_normalise_cost_direction_higher_is_worse():
    # slope: ramp 0 -> 20 deg; flat (0) fully suitable (1), steep (>=20) unsuitable (0)
    raster = np.array([[0.0, 10.0, 20.0], [5.0, 25.0, -3.0]], dtype="float64")
    out = normalise_criterion(raster, COST, low=0.0, high=20.0)
    # cost = 1 - clip((x-0)/20): 0->1, 10->0.5, 20->0, 5->0.75, 25->0(clip), -3->1(clip)
    expected = np.array([[1.0, 0.5, 0.0], [0.75, 0.0, 1.0]], dtype="float32")
    np.testing.assert_allclose(out, expected, rtol=0, atol=1e-6)


def test_normalise_benefit_and_cost_are_complementary_within_ramp():
    raster = np.array([[6.0, 8.0]], dtype="float64")
    ben = normalise_criterion(raster, BENEFIT, 5.0, 10.0)
    cost = normalise_criterion(raster, COST, 5.0, 10.0)
    np.testing.assert_allclose(ben + cost, np.ones_like(ben), atol=1e-6)


def test_normalise_rejects_equal_breakpoints():
    with pytest.raises(ValueError):
        normalise_criterion(np.zeros((2, 2)), BENEFIT, low=3.0, high=3.0)


def test_normalise_rejects_bad_direction():
    with pytest.raises(ValueError):
        normalise_criterion(np.zeros((2, 2)), "sideways", low=0.0, high=1.0)


def test_normalise_preserves_nan():
    raster = np.array([[np.nan, 7.5]], dtype="float64")
    out = normalise_criterion(raster, BENEFIT, 5.0, 10.0)
    assert np.isnan(out[0, 0])
    assert out[0, 1] == pytest.approx(0.5)


# --------------------------------------------------------------------------------------
# AHP: priority vector + consistency ratio (known consistent & inconsistent matrices)
# --------------------------------------------------------------------------------------


def test_ahp_perfectly_consistent_matrix_cr_zero():
    # A perfectly consistent matrix has a_ij = w_i / w_j for some weight vector.
    # Choose w = [0.6, 0.3, 0.1] -> lambda_max == n, CI == 0, CR == 0.
    w = np.array([0.6, 0.3, 0.1])
    a = w[:, None] / w[None, :]  # 3x3, a_ij = w_i/w_j, reciprocal & consistent
    weights, cr, ci, lam = ahp_priority_vector(a)
    np.testing.assert_allclose(weights, w, atol=1e-9)
    assert weights.sum() == pytest.approx(1.0)
    assert lam == pytest.approx(3.0, abs=1e-9)
    assert ci == pytest.approx(0.0, abs=1e-9)
    assert cr == pytest.approx(0.0, abs=1e-9)
    assert cr <= CR_ACCEPTANCE_THRESHOLD


def test_ahp_known_inconsistent_matrix_cr_exceeds_threshold():
    # Classic cyclic/intransitive judgement: A >> B, B >> C, but C >> A (should be A >> C).
    # This 3x3 is strongly inconsistent -> CR well above 0.10.
    a = np.array(
        [
            [1.0, 5.0, 1.0 / 5.0],
            [1.0 / 5.0, 1.0, 5.0],
            [5.0, 1.0 / 5.0, 1.0],
        ]
    )
    weights, cr, ci, lam = ahp_priority_vector(a)
    assert weights.sum() == pytest.approx(1.0)
    # cyclic symmetry -> equal weights ~ 1/3 each
    np.testing.assert_allclose(weights, [1 / 3, 1 / 3, 1 / 3], atol=1e-6)
    assert lam > 3.0  # inconsistency inflates lambda_max above n
    assert cr > CR_ACCEPTANCE_THRESHOLD
    # Independent recomputation of CR from the returned CI and Saaty RI(3).
    expected_cr = ci / SAATY_RANDOM_INDEX[3]
    assert cr == pytest.approx(expected_cr, rel=1e-9)


def test_ahp_mildly_inconsistent_matrix_within_threshold():
    # A textbook near-consistent 3x3 (Saaty): expected CR ~ 0.05 (< 0.10).
    a = np.array(
        [
            [1.0, 2.0, 4.0],
            [1.0 / 2.0, 1.0, 3.0],
            [1.0 / 4.0, 1.0 / 3.0, 1.0],
        ]
    )
    weights, cr, ci, lam = ahp_priority_vector(a)
    assert weights.sum() == pytest.approx(1.0)
    # weights strictly ordered w1 > w2 > w3 (matrix says crit-1 dominates)
    assert weights[0] > weights[1] > weights[2]
    assert lam == pytest.approx(3.0183, abs=1e-3)
    assert 0.0 < cr < CR_ACCEPTANCE_THRESHOLD


def test_ahp_size_two_is_always_consistent():
    a = np.array([[1.0, 3.0], [1.0 / 3.0, 1.0]])
    weights, cr, ci, lam = ahp_priority_vector(a)
    np.testing.assert_allclose(weights, [0.75, 0.25], atol=1e-9)
    assert cr == 0.0
    assert ci == 0.0


def test_ahp_rejects_non_square():
    with pytest.raises(ValueError):
        ahp_priority_vector(np.ones((2, 3)))


def test_ahp_rejects_non_positive_entries():
    with pytest.raises(ValueError):
        ahp_priority_vector(np.array([[1.0, 0.0], [0.0, 1.0]]))


# --------------------------------------------------------------------------------------
# WLC: weighted-sum math on a known small case
# --------------------------------------------------------------------------------------


def test_wlc_weighted_sum_known_case():
    r1 = np.array([[1.0, 0.0], [0.5, 0.2]])  # weight 0.5
    r2 = np.array([[0.0, 1.0], [0.5, 0.8]])  # weight 0.3
    r3 = np.array([[1.0, 1.0], [0.0, 1.0]])  # weight 0.2
    out = weighted_linear_combination([r1, r2, r3], [0.5, 0.3, 0.2])
    # cell (0,0): 0.5*1 + 0.3*0 + 0.2*1 = 0.7
    # cell (0,1): 0.5*0 + 0.3*1 + 0.2*1 = 0.5
    # cell (1,0): 0.5*0.5 + 0.3*0.5 + 0.2*0 = 0.40
    # cell (1,1): 0.5*0.2 + 0.3*0.8 + 0.2*1 = 0.54
    expected = np.array([[0.7, 0.5], [0.40, 0.54]], dtype="float32")
    np.testing.assert_allclose(out, expected, atol=1e-6)


def test_wlc_output_stays_in_unit_interval():
    rng = np.random.default_rng(0)
    rasters = [rng.random((5, 5)) for _ in range(3)]
    weights = [0.5, 0.3, 0.2]  # sum 1
    out = weighted_linear_combination(rasters, weights)
    assert out.min() >= 0.0
    assert out.max() <= 1.0


def test_wlc_rejects_length_mismatch():
    with pytest.raises(ValueError):
        weighted_linear_combination([np.zeros((2, 2))], [0.5, 0.5])


def test_wlc_rejects_shape_mismatch():
    with pytest.raises(ValueError):
        weighted_linear_combination([np.zeros((2, 2)), np.zeros((3, 3))], [0.5, 0.5])


# --------------------------------------------------------------------------------------
# Exclusion veto: zero out non-buildable cells
# --------------------------------------------------------------------------------------


def test_exclusion_veto_zeroes_excluded_cells():
    suit = np.array([[0.9, 0.8], [0.7, 0.6]], dtype="float64")
    mask = np.array([[True, False], [False, True]])  # exclude (0,0) and (1,1)
    out = apply_exclusion_veto(suit, mask, excluded_value=True)
    expected = np.array([[0.0, 0.8], [0.7, 0.0]], dtype="float32")
    np.testing.assert_allclose(out, expected, atol=1e-6)


def test_exclusion_veto_supports_inclusion_mask_semantics():
    suit = np.array([[0.9, 0.8]], dtype="float64")
    buildable = np.array([[True, False]])  # True == buildable
    out = apply_exclusion_veto(suit, buildable, excluded_value=False)
    # excluded_value=False -> cells equal to False are vetoed -> (0,1) zeroed
    np.testing.assert_allclose(out, np.array([[0.9, 0.0]], dtype="float32"), atol=1e-6)


def test_exclusion_veto_rejects_shape_mismatch():
    with pytest.raises(ValueError):
        apply_exclusion_veto(np.zeros((2, 2)), np.zeros((3, 3), dtype=bool))


# --------------------------------------------------------------------------------------
# End-to-end pure-numpy pipeline (no I/O)
# --------------------------------------------------------------------------------------


def test_build_suitability_surface_end_to_end():
    wind = np.array([[10.0, 5.0], [7.5, 4.0]])  # benefit, ramp 5..10
    slope = np.array([[0.0, 20.0], [10.0, 5.0]])  # cost, ramp 0..20
    mask = np.array([[False, False], [True, False]])  # exclude (1,0)
    # perfectly consistent 2x2 with wind twice as important as slope -> weights [2/3, 1/3]
    matrix = np.array([[1.0, 2.0], [0.5, 1.0]])
    res = build_suitability_surface(
        criteria={"wind": wind, "slope": slope},
        directions={"wind": BENEFIT, "slope": COST},
        breakpoints={"wind": (5.0, 10.0), "slope": (0.0, 20.0)},
        pairwise_matrix=matrix,
        criterion_order=["wind", "slope"],
        exclusion_mask=mask,
    )
    assert res["weights"]["wind"] == pytest.approx(2 / 3, abs=1e-9)
    assert res["weights"]["slope"] == pytest.approx(1 / 3, abs=1e-9)
    assert res["consistency_ratio"] == 0.0
    assert res["consistency_ok"] is True

    # normalised wind: 10->1, 5->0, 7.5->0.5, 4->0 ; slope cost: 0->1, 20->0, 10->0.5, 5->0.75
    # suitability = (2/3)*wind_n + (1/3)*slope_n
    # (0,0): 2/3*1 + 1/3*1 = 1.0
    # (0,1): 2/3*0 + 1/3*0 = 0.0
    # (1,0): vetoed -> 0.0
    # (1,1): 2/3*0 + 1/3*0.75 = 0.25
    expected = np.array([[1.0, 0.0], [0.0, 0.25]], dtype="float32")
    np.testing.assert_allclose(res["suitability"], expected, atol=1e-6)


def test_build_suitability_flags_inconsistent_weights():
    r = np.zeros((2, 2))
    a = np.array(
        [
            [1.0, 5.0, 1.0 / 5.0],
            [1.0 / 5.0, 1.0, 5.0],
            [5.0, 1.0 / 5.0, 1.0],
        ]
    )
    res = build_suitability_surface(
        criteria={"a": r, "b": r, "c": r},
        directions={"a": BENEFIT, "b": BENEFIT, "c": COST},
        breakpoints={"a": (0.0, 1.0), "b": (0.0, 1.0), "c": (0.0, 1.0)},
        pairwise_matrix=a,
        criterion_order=["a", "b", "c"],
    )
    assert res["consistency_ratio"] > CR_ACCEPTANCE_THRESHOLD
    assert res["consistency_ok"] is False


def test_build_suitability_rejects_order_size_mismatch():
    r = np.zeros((2, 2))
    with pytest.raises(ValueError):
        build_suitability_surface(
            criteria={"a": r, "b": r},
            directions={"a": BENEFIT, "b": COST},
            breakpoints={"a": (0.0, 1.0), "b": (0.0, 1.0)},
            pairwise_matrix=np.array([[1.0]]),  # 1x1, but order has 2
            criterion_order=["a", "b"],
        )


# --------------------------------------------------------------------------------------
# GeoTIFF export (CASPER-skipped without rasterio)
# --------------------------------------------------------------------------------------

BBOX = (79.375, 7.895, 80.125, 8.645)  # ~0.75 deg box centred on Kalpitiya


def test_export_suitability_geotiff_and_manifest(tmp_path):
    rasterio = pytest.importorskip("rasterio")
    from analytics.gis.mcdm_suitability import export_suitability_surface

    wind = np.array([[10.0, 5.0], [7.5, 4.0]])
    slope = np.array([[0.0, 20.0], [10.0, 5.0]])
    mask = np.array([[False, False], [True, False]])
    matrix = np.array([[1.0, 2.0], [0.5, 1.0]])
    out = tmp_path / "suitability.tif"
    manifest = tmp_path / "DataLake_Manifest_All.json"

    res = export_suitability_surface(
        criteria={"wind": wind, "slope": slope},
        directions={"wind": BENEFIT, "slope": COST},
        breakpoints={"wind": (5.0, 10.0), "slope": (0.0, 20.0)},
        pairwise_matrix=matrix,
        criterion_order=["wind", "slope"],
        bbox=BBOX,
        out_path=out,
        exclusion_mask=mask,
        manifest_path=manifest,
    )

    assert res["consistency_warning"] is None
    with rasterio.open(out) as src:
        assert src.shape == (2, 2)
        assert src.dtypes[0] == "float32"
        band = src.read(1)
    np.testing.assert_allclose(
        band, np.array([[1.0, 0.0], [0.0, 0.25]], dtype="float32"), atol=1e-6
    )

    prov = json.loads(Path(f"{out}.prov.json").read_text())
    assert prov["method"] == "gis_mcdm_ahp_weighted_linear_combination"
    assert prov["ahp_priority_method"] == "normalised_column_mean"
    assert prov["exclusion_applied"] == "True"

    doc = json.loads(manifest.read_text())
    matching = [d for d in doc["datasets"] if d["name"] == "DutchBay/GIS/suitability"]
    assert len(matching) == 1
    assert matching[0]["variables"] == ["suitability"]


def test_export_suitability_records_consistency_warning(tmp_path):
    pytest.importorskip("rasterio")
    from analytics.gis.mcdm_suitability import export_suitability_surface

    r = np.zeros((2, 2))
    a = np.array(
        [
            [1.0, 5.0, 1.0 / 5.0],
            [1.0 / 5.0, 1.0, 5.0],
            [5.0, 1.0 / 5.0, 1.0],
        ]
    )
    res = export_suitability_surface(
        criteria={"a": r, "b": r, "c": r},
        directions={"a": BENEFIT, "b": BENEFIT, "c": COST},
        breakpoints={"a": (0.0, 1.0), "b": (0.0, 1.0), "c": (0.0, 1.0)},
        pairwise_matrix=a,
        criterion_order=["a", "b", "c"],
        bbox=BBOX,
        out_path=tmp_path / "s.tif",
    )
    assert res["consistency_warning"] is not None
    assert "exceeds Saaty" in res["consistency_warning"]
    prov = json.loads(Path(f"{tmp_path / 's.tif'}.prov.json").read_text())
    assert "ahp_consistency_warning" in prov
