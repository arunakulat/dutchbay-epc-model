"""Coverage tests for ``analytics.scenario_loader``.

Exercises the scenario YAML/JSON loader and the strict FX resolver against the
LIVE module: path-suffix inference, the JSON branch, the documented ``raise``
paths (empty / non-mapping / unsupported extension / bad ``meta`` / scalar FX /
missing or malformed FX), and the ``fx.source`` cross-assert that routes through
``analytics.fx.fx_fetch``. Every repo path is resolved RELATIVE to this test file
so the suite is portable to CI's checkout; outputs are written only under
``tmp_path``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from analytics.fx.fx_fetch import FXRequestConfig
from analytics.scenario_loader import (
    ScenarioConfigError,
    _assert_fx_spot_consistency,
    _ensure_meta_source,
    _load_raw_config,
    _resolve_fx,
    _try_config_paths,
    load_scenario_config,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
CANONICAL = REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"


# ---------------------------------------------------------------------------
# _try_config_paths — suffix inference
# ---------------------------------------------------------------------------


def test_try_config_paths_returns_existing_path_as_is(tmp_path: Path) -> None:
    """A path that exists as-is is returned untouched (no inference)."""
    target = tmp_path / "scenario.yaml"
    target.write_text("project: {}\n")
    assert _try_config_paths(target) == target


def test_try_config_paths_with_suffix_missing_raises(tmp_path: Path) -> None:
    """A missing path that already carries a suffix raises immediately."""
    missing = tmp_path / "nope.yaml"
    with pytest.raises(FileNotFoundError, match="Scenario config not found"):
        _try_config_paths(missing)


def test_try_config_paths_infers_yaml(tmp_path: Path) -> None:
    """Suffix-less base resolves to the ``.yaml`` candidate first."""
    (tmp_path / "scn.yaml").write_text("a: 1\n")
    assert _try_config_paths(tmp_path / "scn") == tmp_path / "scn.yaml"


def test_try_config_paths_infers_yml(tmp_path: Path) -> None:
    """When only ``.yml`` exists it is inferred."""
    (tmp_path / "scn.yml").write_text("a: 1\n")
    assert _try_config_paths(tmp_path / "scn") == tmp_path / "scn.yml"


def test_try_config_paths_infers_json(tmp_path: Path) -> None:
    """When only ``.json`` exists it is inferred (last candidate tried)."""
    (tmp_path / "scn.json").write_text("{}\n")
    assert _try_config_paths(tmp_path / "scn") == tmp_path / "scn.json"


def test_try_config_paths_no_candidate_raises_with_tried_list(tmp_path: Path) -> None:
    """No matching candidate raises and reports every suffix it tried."""
    with pytest.raises(FileNotFoundError, match="tried:") as exc:
        _try_config_paths(tmp_path / "ghost")
    msg = str(exc.value)
    assert ".yaml" in msg and ".yml" in msg and ".json" in msg


# ---------------------------------------------------------------------------
# _load_raw_config — format branches and structural raises
# ---------------------------------------------------------------------------


def test_load_raw_config_json_branch(tmp_path: Path) -> None:
    """A ``.json`` file is parsed through the JSON branch."""
    target = tmp_path / "scn.json"
    target.write_text(json.dumps({"project": {"name": "x"}}))
    data = _load_raw_config(target)
    assert data == {"project": {"name": "x"}}


def test_load_raw_config_unsupported_extension_raises(tmp_path: Path) -> None:
    """An existing file with an unsupported extension raises ScenarioConfigError."""
    target = tmp_path / "scn.txt"
    target.write_text("project: {}\n")
    with pytest.raises(ScenarioConfigError, match="Unsupported scenario config extension"):
        _load_raw_config(target)


def test_load_raw_config_empty_file_raises(tmp_path: Path) -> None:
    """A YAML file that parses to ``None`` is rejected as empty."""
    target = tmp_path / "empty.yaml"
    target.write_text("")
    with pytest.raises(ScenarioConfigError, match="Empty configuration"):
        _load_raw_config(target)


def test_load_raw_config_non_mapping_top_level_raises(tmp_path: Path) -> None:
    """A top-level sequence (not a mapping) is rejected."""
    target = tmp_path / "list.yaml"
    target.write_text("- 1\n- 2\n")
    with pytest.raises(ScenarioConfigError, match="Expected a mapping at top level"):
        _load_raw_config(target)


# ---------------------------------------------------------------------------
# _ensure_meta_source
# ---------------------------------------------------------------------------


def test_ensure_meta_source_creates_breadcrumb() -> None:
    """A missing ``meta`` block gets a source_path breadcrumb."""
    cfg: dict[str, Any] = {}
    _ensure_meta_source(cfg, Path("scenarios/x.yaml"))
    assert cfg["meta"]["source_path"] == str(Path("scenarios/x.yaml"))


def test_ensure_meta_source_preserves_existing_source_path() -> None:
    """An existing ``meta.source_path`` is not overwritten (setdefault)."""
    cfg: dict[str, Any] = {"meta": {"source_path": "already/set.yaml"}}
    _ensure_meta_source(cfg, Path("scenarios/x.yaml"))
    assert cfg["meta"]["source_path"] == "already/set.yaml"


def test_ensure_meta_source_non_mapping_meta_raises() -> None:
    """A non-mapping ``meta`` block is rejected."""
    with pytest.raises(ScenarioConfigError, match="'meta' to be a mapping"):
        _ensure_meta_source({"meta": ["not", "a", "map"]}, Path("x.yaml"))


# ---------------------------------------------------------------------------
# _resolve_fx — the strict FX resolver contract
# ---------------------------------------------------------------------------


def test_resolve_fx_missing_raises() -> None:
    """Missing ``fx`` raises ValueError per the documented contract."""
    with pytest.raises(ValueError, match="FX configuration missing"):
        _resolve_fx({})


def test_resolve_fx_scalar_raises() -> None:
    """A scalar ``fx`` is rejected (no-scalar-FX policy)."""
    with pytest.raises(ValueError, match="Scalar 'fx' not supported"):
        _resolve_fx({"fx": 333.79})


def test_resolve_fx_non_mapping_non_scalar_raises() -> None:
    """A list ``fx`` (neither scalar nor mapping) raises the mapping error."""
    with pytest.raises(ValueError, match="must be a mapping"):
        _resolve_fx({"fx": [333.79]})


def test_resolve_fx_missing_start_rate_raises() -> None:
    """A mapping ``fx`` without ``start_lkr_per_usd`` raises."""
    with pytest.raises(ValueError, match="FX configuration missing"):
        _resolve_fx({"fx": {"annual_depr": 0.03}})


def test_resolve_fx_non_numeric_start_rate_raises() -> None:
    """A non-numeric ``start_lkr_per_usd`` is reported clearly."""
    with pytest.raises(ValueError, match="start_lkr_per_usd must be a valid number"):
        _resolve_fx({"fx": {"start_lkr_per_usd": "abc"}})


def test_resolve_fx_non_numeric_annual_depr_raises() -> None:
    """A non-numeric ``annual_depr`` is reported clearly."""
    with pytest.raises(ValueError, match="annual_depr must be a valid number"):
        _resolve_fx({"fx": {"start_lkr_per_usd": 333.79, "annual_depr": "fast"}})


def test_resolve_fx_minimal_defaults_annual_depr_to_zero() -> None:
    """A minimal mapping resolves and defaults ``annual_depr`` to 0.0."""
    result = _resolve_fx({"fx": {"start_lkr_per_usd": 333.79}})
    assert result == {"start_lkr_per_usd": 333.79, "annual_depr": 0.0}


def test_resolve_fx_passes_through_explicit_annual_depr() -> None:
    """An explicit ``annual_depr`` is coerced to float and preserved."""
    result = _resolve_fx({"fx": {"start_lkr_per_usd": "333.79", "annual_depr": "0.03"}})
    assert result["start_lkr_per_usd"] == pytest.approx(333.79)
    assert result["annual_depr"] == pytest.approx(0.03)


def test_resolve_fx_with_valid_source_block_cross_asserts() -> None:
    """A valid ``fx.source`` block routes through FXRequestConfig.from_scenario.

    The canonical scenario pins ``start_lkr_per_usd == source.pinned_rate``, so the
    cross-assert passes and the resolver returns the normalized mapping.
    """
    cfg = load_scenario_config(str(CANONICAL))
    result = _resolve_fx(cfg)
    # Cross-check against the LIVE FX routine that the resolver delegates to.
    fx_req = FXRequestConfig.from_scenario(cfg)
    assert result["start_lkr_per_usd"] == pytest.approx(fx_req.pinned_rate)
    assert result["start_lkr_per_usd"] > 0.0
    assert result["annual_depr"] >= 0.0


def test_resolve_fx_source_block_drift_raises() -> None:
    """A ``fx.source`` whose pinned_rate diverges from start_lkr_per_usd is rejected."""
    cfg = {
        "fx": {
            "start_lkr_per_usd": 333.79,
            "source": {
                "mode": "fixed",
                "pinned_rate": 300.0,
                "pinned_as_of": "2026-06-20T00:00:00Z",
            },
        }
    }
    with pytest.raises(ValueError, match="must equal fx.source.pinned_rate"):
        _resolve_fx(cfg)


# ---------------------------------------------------------------------------
# load_scenario_config — public loader
# ---------------------------------------------------------------------------


def test_load_scenario_config_canonical_round_trips() -> None:
    """The canonical lender-case loads, gets a meta breadcrumb, and reconciles."""
    cfg = load_scenario_config(str(CANONICAL))
    assert isinstance(cfg, dict)
    assert cfg["meta"]["source_path"] == str(CANONICAL)
    # Invariant: the canonical scenario carries the engine's revenue basis.
    assert cfg["project"]["capacity_mw"] > 0.0
    assert 0.0 < cfg["project"]["capacity_factor"] < 1.0


def test_load_scenario_config_accepts_path_object() -> None:
    """The loader accepts a ``Path`` as well as a ``str``."""
    cfg = load_scenario_config(CANONICAL)
    assert cfg["meta"]["source_path"] == str(CANONICAL)


def test_load_scenario_config_scalar_fx_raises(tmp_path: Path) -> None:
    """A scalar ``fx`` at load time is rejected (line-195 guard)."""
    target = tmp_path / "scalar_fx.yaml"
    target.write_text(yaml.safe_dump({"project": {"name": "x"}, "fx": 333.79}))
    with pytest.raises(ValueError, match="scalar 'fx' not supported"):
        load_scenario_config(target)


def test_load_scenario_config_minimal_no_fx_no_aep(tmp_path: Path) -> None:
    """A minimal config without FX or bankable AEP loads cleanly (no enforcement)."""
    target = tmp_path / "minimal.yaml"
    target.write_text(yaml.safe_dump({"project": {"name": "minimal"}}))
    cfg = load_scenario_config(target)
    assert cfg["project"]["name"] == "minimal"
    assert cfg["meta"]["source_path"] == str(target)


# ---------------------------------------------------------------------------
# Wave-2 re-audit #6: FX spot cross-assertion (two-sources-of-truth guard)
# ---------------------------------------------------------------------------
def test_fx_spot_consistency_passes_when_keys_agree() -> None:
    """All three FX spot keys equal -> no error (the canonical pinned-vintage case)."""
    cfg = {
        "fx": {
            "rates": {"lkr_per_usd": 333.79},
            "start_lkr_per_usd": 333.79,
            "source": {"pinned_rate": 333.79},
        }
    }
    _assert_fx_spot_consistency(cfg, "test")  # must not raise


def test_fx_spot_consistency_raises_when_keys_diverge() -> None:
    """A stale fx.start vs an edited fx.rates.lkr_per_usd is the #236 class -> fail loud."""
    cfg = {
        "fx": {
            "rates": {"lkr_per_usd": 350.0},   # author edited this
            "start_lkr_per_usd": 333.79,        # forgot to update this
        }
    }
    with pytest.raises(ValueError, match="inconsistent LKR/USD spot"):
        _assert_fx_spot_consistency(cfg, "diverging-scenario")


def test_fx_spot_consistency_noop_with_single_key() -> None:
    """Fewer than two pinned keys -> nothing to cross-assert."""
    _assert_fx_spot_consistency({"fx": {"start_lkr_per_usd": 333.79}}, "test")
    _assert_fx_spot_consistency({"fx": {}}, "test")
    _assert_fx_spot_consistency({}, "test")
