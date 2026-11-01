"""The gearing solve's trial configs share unchanged objects, and that changes no number.

``_solve_gearing_for_dscr`` and ``_resize_for_amortization`` run ``apply_debt_layer`` once
per trial gearing. Each trial used to deep-copy the whole scenario to change one number, and
once #1451 made debt sizing a fixed point over several passes that copy became about 70% of
a lender-case run (the Oct 27 CI slowdown). ``_config_at_debt_ratio`` now copies only the
top-level mapping and the ``Financing_Terms`` section.

That is equivalent to the deep copy only if ``apply_debt_layer`` never mutates its
``params``. These tests pin both halves on the committed lender case, through every
sizing pass of the levered-tax fixed point, the P90 bind and the amortize bisection:

* ``apply_debt_layer`` leaves its params exactly as it found them; and
* every solve and every bisection returns exactly, not approximately, what the old
  deep-copy recipe returns from the same arguments.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Callable

import pytest

from analytics.evaluation_v14 import evaluate_with_overrides
from finance import debt_v14

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER_CONFIG = str(REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml")


def _deepcopy_config_at(config: dict[str, Any], ratio: float) -> dict[str, Any]:
    """The pre-change trial config recipe, kept verbatim as the oracle."""
    cfg = copy.deepcopy(config)
    fin = debt_v14._section_case_insensitive(cfg, "Financing_Terms")
    if isinstance(fin, dict):
        fin["debt_ratio"] = ratio
    else:
        cfg["debt_ratio"] = ratio
    return cfg


def _reference_solve(
    config: dict[str, Any],
    annual_rows: list[dict[str, Any]],
    target_dscr: float,
    max_ratio: float,
    *,
    step: float = 0.0025,
    fp_eps: float = 1e-6,
) -> float:
    """``_solve_gearing_for_dscr`` as it stood before the change (deep copy per trial)."""
    ratio = max_ratio
    while ratio > 0.0:
        core = debt_v14.apply_debt_layer(
            params=_deepcopy_config_at(config, ratio), annual_rows=annual_rows
        )
        public = debt_v14._clean_public_dscr_series(core.get("dscr_series", []) or [])
        achieved = min(public) if public else float(core.get("dscr_min", 0.0))
        if achieved >= target_dscr - fp_eps:
            return round(ratio, 6)
        ratio -= step
    return round(step, 6)


def _reference_resize(
    config: dict[str, Any], rows: list[dict[str, Any]], core: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """``_resize_for_amortization`` as it stood before the change."""
    if debt_v14._as_float(core.get("balloon_remaining"), 0.0) <= debt_v14._BALLOON_TOL:
        return config, core
    fin = debt_v14._section_case_insensitive(config, "Financing_Terms") or {}
    lo, hi = 0.0, debt_v14._as_float(fin.get("debt_ratio"), 0.70)
    for _ in range(40):
        mid = (lo + hi) / 2.0
        trial = debt_v14.apply_debt_layer(
            params=_deepcopy_config_at(config, mid), annual_rows=rows
        )
        if (
            debt_v14._as_float(trial.get("balloon_remaining"), 0.0)
            > debt_v14._BALLOON_TOL
        ):
            hi = mid
        else:
            lo = mid
    resized = _deepcopy_config_at(config, lo)
    return resized, debt_v14.apply_debt_layer(params=resized, annual_rows=rows)


@pytest.fixture
def recorded(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[Any]]:
    """Wrap the engine seams so one lender-case run records every call through them."""
    record: dict[str, list[Any]] = {
        "mutations": [],
        "layer_calls": [],
        "solves": [],
        "resizes": [],
    }

    real_layer: Callable[..., dict[str, Any]] = debt_v14.apply_debt_layer
    real_solve = debt_v14._solve_gearing_for_dscr
    real_resize = debt_v14._resize_for_amortization

    def checked_layer(
        *, params: dict[str, Any], annual_rows: list[dict[str, Any]]
    ) -> Any:
        before = copy.deepcopy(params)
        rows_before = copy.deepcopy(annual_rows)
        out = real_layer(params=params, annual_rows=annual_rows)
        record["layer_calls"].append(1)
        if params != before or annual_rows != rows_before:
            record["mutations"].append(len(record["layer_calls"]))
        return out

    def recording_solve(config, annual_rows, target_dscr, max_ratio, **kw):  # type: ignore[no-untyped-def]
        args = (
            copy.deepcopy(config),
            copy.deepcopy(annual_rows),
            target_dscr,
            max_ratio,
            kw,
        )
        solved = real_solve(config, annual_rows, target_dscr, max_ratio, **kw)
        record["solves"].append((args, solved))
        return solved

    def recording_resize(config, rows, core):  # type: ignore[no-untyped-def]
        args = (copy.deepcopy(config), copy.deepcopy(rows), copy.deepcopy(core))
        out = real_resize(config, rows, core)
        record["resizes"].append((args, out))
        return out

    monkeypatch.setattr(debt_v14, "apply_debt_layer", checked_layer)
    monkeypatch.setattr(debt_v14, "_solve_gearing_for_dscr", recording_solve)
    monkeypatch.setattr(debt_v14, "_resize_for_amortization", recording_resize)
    return record


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({}, id="lender-case"),
        pytest.param({"Financing_Terms.bind_downside": True}, id="p90-bind"),
        pytest.param({"Financing_Terms.balloon_treatment": "amortize"}, id="amortize"),
    ],
)
def test_trial_configs_match_the_deep_copy_recipe_exactly(
    recorded: dict[str, list[Any]], overrides: dict[str, Any]
) -> None:
    evaluate_with_overrides(LENDER_CONFIG, overrides=overrides, return_full_result=True)

    # The run went through the engine: several fixed-point passes, each a stepped solve.
    assert recorded["solves"], "the lender case no longer reaches the gearing solve"
    assert len(recorded["layer_calls"]) > 100
    # apply_debt_layer reads its params and rows and never writes them. If this fails,
    # _config_at_debt_ratio's sharing is unsafe and must go back to a deep copy.
    assert recorded["mutations"] == []

    for (config, rows, target, max_ratio, kw), solved in recorded["solves"]:
        assert solved == _reference_solve(config, rows, target, max_ratio, **kw)

    if overrides.get("Financing_Terms.balloon_treatment") == "amortize":
        assert recorded["resizes"], "amortize no longer reaches the bisection"
    for (config, rows, core), (out_cfg, out_core) in recorded["resizes"]:
        ref_cfg, ref_core = _reference_resize(config, rows, core)
        assert out_cfg == ref_cfg
        assert out_core == ref_core


def test_config_at_debt_ratio_writes_where_the_deep_copy_did() -> None:
    nested = {"rates": {"usd_nominal": 0.08}}
    config: dict[str, Any] = {
        "financing_terms": {"debt_ratio": 0.7, "x": nested},
        "k": [1],
    }
    out = debt_v14._config_at_debt_ratio(config, 0.5)
    assert out == _deepcopy_config_at(config, 0.5)
    # The caller's config is untouched, and only the changed mappings were copied.
    assert config["financing_terms"]["debt_ratio"] == 0.7
    assert out["financing_terms"] is not config["financing_terms"]
    assert out["financing_terms"]["x"] is nested
    assert out["k"] is config["k"]

    # No Financing_Terms dict: the gearing goes on the top level, as before.
    flat: dict[str, Any] = {"debt_ratio": 0.7, "Financing_Terms": None}
    assert debt_v14._config_at_debt_ratio(flat, 0.25) == _deepcopy_config_at(flat, 0.25)
    assert flat["debt_ratio"] == 0.7
