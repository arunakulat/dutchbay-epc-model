"""Global sensitivity (SALib Morris/Sobol) — analytics/sensitivity/global_sa.py.

- Closed-form: Sobol recovers the known Ishigami interaction structure (x3 has ~0 first-order
  but material total-order — a pure interaction the one-way tornado cannot see).
- Engine smoke: Morris screening runs through the canonical evaluate_with_overrides gateway
  on the lender case and ranks the known-dominant drivers (tariff / capex) at the top.
- build_problem contract: skips fx_calibrated drivers; requires >=2 sweepable drivers.

KPI-neutral: this is an additive, read-only analysis layer; the deterministic base case is
never touched (no canonical-KPI assertions belong here).
"""

from __future__ import annotations

import importlib.util
import logging
import math
import sys

import pytest

pytest.importorskip("SALib")  # optional dependency (CASPER); skip cleanly if absent

from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402

from analytics.sensitivity.global_sa import (  # noqa: E402
    GlobalSAProblem,
    build_problem,
    run_morris,
    run_pawn,
    run_sobol,
)

REPO = Path(__file__).resolve().parents[2]
LENDER = str(REPO / "scenarios" / "dutchbay_lendercase_2025Q4.yaml")


def _ishigami(overrides):
    """Standard SALib test function f(x1,x2,x3) = sin x1 + a sin^2 x2 + b x3^4 sin x1.

    Known Sobol (a=7, b=0.1): S1 ~= [0.314, 0.442, 0.0]; ST ~= [0.557, 0.442, 0.244].
    x3 is the diagnostic case: ~0 first-order, but ~0.24 total-order (pure interaction).
    """
    a, b = 7.0, 0.1
    x1, x2, x3 = overrides["x1"], overrides["x2"], overrides["x3"]
    return {"y": math.sin(x1) + a * math.sin(x2) ** 2 + b * (x3**4) * math.sin(x1)}


def test_sobol_recovers_ishigami_interaction_structure() -> None:
    prob = GlobalSAProblem(names=["x1", "x2", "x3"], bounds=[(-math.pi, math.pi)] * 3)
    res = run_sobol(problem=prob, evaluate_fn=_ishigami, metrics=("y",), n=512, seed=1)
    d = res["metrics"]["y"]["drivers"]
    # x1, x2 carry real first-order variance.
    assert d["x1"]["S1"] > 0.2
    assert d["x2"]["S1"] > 0.3
    # x3: ~0 first-order, but materially interactive (ST >> S1).
    assert abs(d["x3"]["S1"]) < 0.1
    assert d["x3"]["ST"] > 0.1
    assert d["x3"]["interactive"] is True
    assert res["metrics"]["y"]["interactions_present"] is True
    # Total-order dominates first-order for every driver (variance accounting).
    for name in prob.names:
        assert d[name]["ST"] >= d[name]["S1"] - 0.05


def test_run_sobol_rejects_non_power_of_two_n() -> None:
    """#586: SALib's base-2 Sobol' sampler only keeps its balance properties at
    powers of 2 — SALib merely warns and degrades, so run_sobol fails loud."""
    prob = GlobalSAProblem(names=["x1", "x2", "x3"], bounds=[(-math.pi, math.pi)] * 3)
    for bad in (100, 3, 511, 0, -256):
        with pytest.raises(ValueError, match="power of 2"):
            run_sobol(problem=prob, evaluate_fn=_ishigami, metrics=("y",), n=bad)
    # bool is a subclass of int; True == 1 == 2**0 must still be rejected.
    with pytest.raises(ValueError, match="power of 2"):
        run_sobol(problem=prob, evaluate_fn=_ishigami, metrics=("y",), n=True)
    # Non-int n is a caller bug, not something to coerce.
    with pytest.raises(ValueError, match="power of 2"):
        run_sobol(problem=prob, evaluate_fn=_ishigami, metrics=("y",), n=256.0)


def test_run_sobol_accepts_power_of_two_n() -> None:
    """A small power-of-2 n runs end-to-end (n_runs = n * (D + 2))."""
    prob = GlobalSAProblem(names=["x1", "x2", "x3"], bounds=[(-math.pi, math.pi)] * 3)
    res = run_sobol(problem=prob, evaluate_fn=_ishigami, metrics=("y",), n=16, seed=1)
    assert res["n"] == 16
    assert res["n_runs"] == 16 * (3 + 2)
    assert set(res["metrics"]["y"]["drivers"]) == {"x1", "x2", "x3"}


def test_run_sobol_default_n_is_a_valid_power_of_two() -> None:
    """The documented default (n=256) must itself satisfy the new gate."""
    import inspect

    default_n = inspect.signature(run_sobol).parameters["n"].default
    assert default_n == 256
    assert default_n > 0 and (default_n & (default_n - 1)) == 0


def test_build_problem_skips_fx_calibrated() -> None:
    params = [
        {"name": "project.capacity_factor", "low": 0.30, "high": 0.36},
        {"name": "fx.start_lkr_per_usd", "distribution": "fx_calibrated"},
        {"name": "capex.usd_total", "low": 1.0e8, "high": 1.2e8},
    ]
    prob = build_problem("ignored.yaml", params=params)
    assert prob.names == ["project.capacity_factor", "capex.usd_total"]
    assert prob.skipped == ["fx.start_lkr_per_usd"]


def test_build_problem_requires_two_drivers() -> None:
    with pytest.raises(ValueError, match=">=2 sweepable drivers"):
        build_problem("ignored.yaml", params=[{"name": "x", "low": 0.0, "high": 1.0}])


def test_build_problem_requires_both_bounds() -> None:
    """A parameter that omits a bound must fail with an actionable ValueError naming
    the field (CASPER), not the bare TypeError that float(None) used to raise."""
    with pytest.raises(ValueError, match="both a low/min and a high/max"):
        build_problem(
            "ignored.yaml",
            params=[
                {"name": "a", "low": 0.0, "high": 1.0},
                {"name": "b", "low": 0.0},  # missing high/max -> float(None) pre-fix
            ],
        )


def test_morris_smoke_lendercase_ranks_dominant_drivers() -> None:
    res = run_morris(LENDER, n_trajectories=4, metrics=("project_irr",), seed=1)
    assert res["n_runs"] == 4 * (res["problem"]["num_vars"] + 1)
    ranking = res["metrics"]["project_irr"]["ranking"]
    # tariff and capex are the model's known dominant project-IRR drivers; one should top it.
    assert ranking[0] in {"tariff.lkr_per_kwh", "capex.usd_total"}


def _ishigami_with_flat(overrides):
    """Ishigami for 'y' plus a covenant-pinned 'min_dscr' that never moves."""
    out = _ishigami(overrides)
    out["min_dscr"] = 1.30  # structurally invariant (debt sized to the DSCR target)
    return out


def test_sobol_flags_covenant_pinned_metric_as_flat() -> None:
    """A near-constant covenant metric is flagged, not decomposed into out-of-[0,1] indices.

    Audit D4 (#575): global SA had no analogue of the tornado's flat_metric guard, so a
    covenant-pinned min_dscr produced negative S1 / ST>1. The guard now zeroes and flags it.
    """
    prob = GlobalSAProblem(names=["x1", "x2", "x3"], bounds=[(-math.pi, math.pi)] * 3)
    res = run_sobol(
        problem=prob,
        evaluate_fn=_ishigami_with_flat,
        metrics=("y", "min_dscr"),
        n=256,
        seed=1,
    )
    # The real metric is decomposed as before.
    assert res["metrics"]["y"]["flat_metric"] is False
    # The covenant metric is flagged flat with zeroed, in-band indices (no negative S1 / ST>1).
    flat = res["metrics"]["min_dscr"]
    assert flat["flat_metric"] is True
    assert "covenant-pinned" in flat["flat_metric_reason"]
    # Indices are undefined on a flat output, so no interaction claim is computable:
    # None ("not computed"), not a definitive False (Fable review on #644).
    assert flat["interactions_present"] is None
    for d in flat["drivers"].values():
        assert d == {
            "S1": 0.0,
            "S1_conf": 0.0,
            "ST": 0.0,
            "ST_conf": 0.0,
            "interactive": False,
        }


def test_morris_flags_covenant_pinned_metric_as_flat() -> None:
    prob = GlobalSAProblem(names=["x1", "x2", "x3"], bounds=[(-math.pi, math.pi)] * 3)
    res = run_morris(
        problem=prob,
        evaluate_fn=_ishigami_with_flat,
        metrics=("y", "min_dscr"),
        n_trajectories=8,
        seed=1,
    )
    assert res["metrics"]["y"]["flat_metric"] is False
    flat = res["metrics"]["min_dscr"]
    assert flat["flat_metric"] is True
    for d in flat["drivers"].values():
        assert d == {"mu_star": 0.0, "sigma": 0.0}


def test_pawn_ranks_ishigami_influential_drivers_in_band() -> None:
    """PAWN median KS is in [0,1] and ranks a genuinely-influential Ishigami driver top (#591)."""
    prob = GlobalSAProblem(names=["x1", "x2", "x3"], bounds=[(-math.pi, math.pi)] * 3)
    res = run_pawn(problem=prob, evaluate_fn=_ishigami, metrics=("y",), n=512, seed=1)
    d = res["metrics"]["y"]["drivers"]
    # KS statistics are bounded in [0, 1] (unlike out-of-band variance indices).
    for name in prob.names:
        assert 0.0 <= d[name]["median"] <= 1.0
    # x1/x2 carry the first-order signal; one of them tops the ranking.
    assert res["metrics"]["y"]["ranking"][0] in {"x1", "x2"}
    assert res["metrics"]["y"]["flat_metric"] is False


def test_pawn_flags_covenant_pinned_metric_as_flat() -> None:
    """A near-constant covenant metric yields SPURIOUS PAWN indices on FP jitter, so PAWN
    flags+zeroes it via the same guard as Sobol/Morris (#591)."""
    prob = GlobalSAProblem(names=["x1", "x2", "x3"], bounds=[(-math.pi, math.pi)] * 3)
    res = run_pawn(
        problem=prob,
        evaluate_fn=_ishigami_with_flat,
        metrics=("y", "min_dscr"),
        n=256,
        seed=1,
    )
    assert res["metrics"]["y"]["flat_metric"] is False
    flat = res["metrics"]["min_dscr"]
    assert flat["flat_metric"] is True
    for d in flat["drivers"].values():
        assert d == {"median": 0.0, "mean": 0.0, "cv": 0.0}


# ---------------------------------------------------------------------------
# #644 — shared finite-mask: a partial-NaN metric column must not poison indices
# ---------------------------------------------------------------------------

_PROB3 = GlobalSAProblem(names=["x1", "x2", "x3"], bounds=[(-math.pi, math.pi)] * 3)


class _NanInjector:
    """Ishigami evaluator whose 'y_nan' copy returns None on a deterministic subset of calls.

    ``_evaluate_rows`` walks the sample rows in order, so "every ``keep_period``-th call"
    is a pure function of row order (MRM-01: deterministic masking). 'y' stays fully
    finite — the sibling-metric-isolation control.
    """

    def __init__(self, nan_period: int) -> None:
        self.nan_period = nan_period
        self.calls = 0

    def __call__(self, overrides):
        out = dict(_ishigami(overrides))
        self.calls += 1
        out["y_nan"] = None if self.calls % self.nan_period == 0 else out["y"]
        return out


class _MostlyNoneInjector:
    """Ishigami evaluator whose 'y_nan' copy is None on 2 of every 3 calls (share > 50%)."""

    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, overrides):
        out = dict(_ishigami(overrides))
        self.calls += 1
        out["y_nan"] = out["y"] if self.calls % 3 == 0 else None
        return out


def test_sobol_partial_nan_masks_whole_saltelli_blocks() -> None:
    """A partially-NaN column yields FINITE Sobol indices computed on the finite subset,
    masked by WHOLE Saltelli blocks (D+2 rows — row masking would corrupt the A/B/AB
    pairing), with a loud disclosure; the sibling clean metric is untouched (#644)."""
    res = run_sobol(
        problem=_PROB3,
        evaluate_fn=_NanInjector(97),
        metrics=("y", "y_nan"),
        n=512,
        seed=1,
    )
    clean, poisoned = res["metrics"]["y"], res["metrics"]["y_nan"]
    # Sibling metric: fully finite column -> analyzed on the FULL sample, no disclosure.
    assert clean["flat_metric"] is False
    assert clean["nan_poisoned"] is False
    assert "masked" not in clean
    # Masked metric: finite indices, Ishigami structure still recovered.
    assert poisoned["flat_metric"] is False
    assert poisoned["nan_poisoned"] is False
    d = poisoned["drivers"]
    for name in _PROB3.names:
        for k in ("S1", "S1_conf", "ST", "ST_conf"):
            assert math.isfinite(d[name][k])
    assert d["x1"]["S1"] > 0.2
    assert d["x2"]["S1"] > 0.3
    assert d["x3"]["ST"] > 0.1
    # Disclosure: whole (D+2)-row blocks dropped, share disclosed and sub-threshold.
    m = poisoned["masked"]
    assert m["unit"] == "saltelli_block"
    assert m["block_size"] == len(_PROB3.names) + 2
    assert 0 < m["n_units_dropped"] < m["n_units"]
    assert m["n_rows_dropped"] == m["n_units_dropped"] * m["block_size"]
    assert 0.0 < m["dropped_share"] < 0.5
    assert m["nan_poisoned"] is False


def test_morris_partial_nan_drops_whole_trajectories() -> None:
    """A partially-NaN column yields FINITE Morris mu_star/sigma with whole (D+1)-row
    trajectories dropped, and a ranking derived from the actual values — not the
    pre-#644 fabricated insertion-order sort over NaN keys."""
    res = run_morris(
        problem=_PROB3,
        evaluate_fn=_NanInjector(29),
        metrics=("y", "y_nan"),
        n_trajectories=32,
        seed=1,
    )
    clean, poisoned = res["metrics"]["y"], res["metrics"]["y_nan"]
    assert clean["nan_poisoned"] is False
    assert "masked" not in clean
    d = poisoned["drivers"]
    for name in _PROB3.names:
        assert math.isfinite(d[name]["mu_star"])
        assert math.isfinite(d[name]["sigma"])
    assert any(d[name]["mu_star"] > 0.0 for name in _PROB3.names)
    # Ranking follows the reported mu_star values (pre-fix: all-NaN -> fabricated order).
    assert poisoned["ranking"] == sorted(d, key=lambda k: d[k]["mu_star"], reverse=True)
    m = poisoned["masked"]
    assert m["unit"] == "trajectory"
    assert m["block_size"] == len(_PROB3.names) + 1
    assert 0 < m["n_units_dropped"] < m["n_units"]
    assert m["nan_poisoned"] is False


def test_pawn_partial_nan_masks_rows() -> None:
    """PAWN is given-data, so the mask is row-wise: finite, in-band KS indices on the
    finite subset, with the dropped-row disclosure (#644)."""
    res = run_pawn(
        problem=_PROB3,
        evaluate_fn=_NanInjector(37),
        metrics=("y", "y_nan"),
        n=256,
        seed=1,
    )
    clean, poisoned = res["metrics"]["y"], res["metrics"]["y_nan"]
    assert clean["nan_poisoned"] is False
    assert "masked" not in clean
    d = poisoned["drivers"]
    for name in _PROB3.names:
        assert 0.0 <= d[name]["median"] <= 1.0
        assert math.isfinite(d[name]["mean"])
    assert poisoned["ranking"] == sorted(d, key=lambda k: d[k]["median"], reverse=True)
    m = poisoned["masked"]
    assert m["unit"] == "row"
    assert m["block_size"] == 1
    assert m["n_rows_dropped"] == m["n_units_dropped"] > 0
    assert m["nan_poisoned"] is False


def test_sobol_clean_data_indices_identical_to_direct_salib() -> None:
    """The finite-mask is a strict no-op on clean data: run_sobol's indices are IDENTICAL
    to a hand-rolled SALib sample->analyze on the same seed, proving the Saltelli
    pairing is untouched by the #644 guard."""
    from SALib.analyze import sobol as sobol_analyze
    from SALib.sample import sobol as sobol_sample

    res = run_sobol(
        problem=_PROB3, evaluate_fn=_ishigami, metrics=("y",), n=128, seed=3
    )
    X = sobol_sample.sample(_PROB3.as_salib(), 128, calc_second_order=False, seed=3)
    Y = np.asarray(
        [_ishigami(dict(zip(_PROB3.names, row)))["y"] for row in X], dtype=float
    )
    Si = sobol_analyze.analyze(
        _PROB3.as_salib(), Y, calc_second_order=False, seed=3, print_to_console=False
    )
    entry = res["metrics"]["y"]
    assert entry["nan_poisoned"] is False
    assert "masked" not in entry
    for i, name in enumerate(_PROB3.names):
        assert entry["drivers"][name]["S1"] == float(Si["S1"][i])
        assert entry["drivers"][name]["S1_conf"] == float(Si["S1_conf"][i])
        assert entry["drivers"][name]["ST"] == float(Si["ST"][i])
        assert entry["drivers"][name]["ST_conf"] == float(Si["ST_conf"][i])


@pytest.mark.parametrize(
    "runner, kwargs, zeroed",
    [
        (
            run_sobol,
            {"n": 128},
            {
                "S1": 0.0,
                "S1_conf": 0.0,
                "ST": 0.0,
                "ST_conf": 0.0,
                "interactive": False,
            },
        ),
        (run_morris, {"n_trajectories": 16}, {"mu_star": 0.0, "sigma": 0.0}),
        (run_pawn, {"n": 128}, {"median": 0.0, "mean": 0.0, "cv": 0.0}),
    ],
)
def test_nan_poisoned_threshold_flags_metric(runner, kwargs, zeroed) -> None:
    """Above the 50% masked-share guard the metric is flagged nan_poisoned (the NaN
    analogue of flat_metric): zeroed indices + reason + disclosure, no exception, and the
    sibling clean metric's decomposition is unaffected (#644)."""
    res = runner(
        problem=_PROB3,
        evaluate_fn=_MostlyNoneInjector(),
        metrics=("y", "y_nan"),
        seed=1,
        **kwargs,
    )
    poisoned = res["metrics"]["y_nan"]
    assert poisoned["nan_poisoned"] is True
    assert poisoned["flat_metric"] is False
    assert "guard" in poisoned["nan_poisoned_reason"]
    assert poisoned["masked"]["nan_poisoned"] is True
    assert poisoned["masked"]["dropped_share"] > 0.5
    for d in poisoned["drivers"].values():
        assert d == zeroed
    if runner is run_sobol:
        # Nothing was analyzed, so no interaction claim is computable: None ("not
        # computed"), not a definitive False (Fable review on #644).
        assert poisoned["interactions_present"] is None
    if runner is run_morris:
        # The reason string pluralizes its sample unit correctly (not 'trajectorys').
        assert "trajectories" in poisoned["nan_poisoned_reason"]
    # The clean sibling metric is still genuinely decomposed.
    clean = res["metrics"]["y"]
    assert clean["flat_metric"] is False
    assert clean["nan_poisoned"] is False
    assert "masked" not in clean


def test_all_nan_column_still_resolves_via_flat_guard() -> None:
    """An ALL-NaN column keeps resolving through _is_flat_output (flat_metric=True), not
    through the #644 mask (#644 acceptance: the pre-existing path is preserved)."""

    def _fn(overrides):
        out = dict(_ishigami(overrides))
        out["y_nan"] = None
        return out

    res = run_sobol(
        problem=_PROB3, evaluate_fn=_fn, metrics=("y", "y_nan"), n=64, seed=1
    )
    entry = res["metrics"]["y_nan"]
    assert entry["flat_metric"] is True
    assert entry["nan_poisoned"] is False
    assert "masked" not in entry


def test_masking_emits_warning_with_count_and_metric(caplog) -> None:
    """Any masking is disclosed loudly (CESSPIT): a WARNING naming the metric and carrying
    the dropped count — never a silent truncation (#644)."""
    with caplog.at_level(logging.WARNING, logger="analytics.sensitivity.global_sa"):
        res = run_pawn(
            problem=_PROB3,
            evaluate_fn=_NanInjector(37),
            metrics=("y_nan",),
            n=128,
            seed=1,
        )
    m = res["metrics"]["y_nan"]["masked"]
    assert m["n_units_dropped"] > 0
    msgs = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
    matching = [msg for msg in msgs if "y_nan" in msg and "dropping" in msg]
    assert matching, f"no masking warning found in: {msgs}"
    assert any(
        f"dropping {m['n_units_dropped']} of {m['n_units']}" in msg for msg in matching
    )


def test_masking_warning_pluralizes_trajectory(caplog) -> None:
    """The Morris masking disclosure pluralizes its sample unit as 'trajectories' —
    the naive '+s' rendered 'trajectorys' (Fable review on #644)."""
    with caplog.at_level(logging.WARNING, logger="analytics.sensitivity.global_sa"):
        run_morris(
            problem=_PROB3,
            evaluate_fn=_NanInjector(29),
            metrics=("y_nan",),
            n_trajectories=32,
            seed=1,
        )
    msgs = [r.getMessage() for r in caplog.records]
    assert any("trajectories" in msg for msg in msgs), msgs
    assert not any("trajectorys" in msg for msg in msgs), msgs


# ---------------------------------------------------------------------------
# #658 — CLI dispatch: `run_global_sensitivity.py --method pawn` (SOLE owner of
# the --method pawn CLI wiring). The module-level importorskip("SALib") already
# gates this whole file, so the PAWN path is exercised only when SALib is present.
# ---------------------------------------------------------------------------


def _load_global_sa_cli():
    """Import scripts/run_global_sensitivity.py as a module (it lives in scripts/)."""
    if str(REPO) not in sys.path:
        sys.path.insert(0, str(REPO))
    spec = importlib.util.spec_from_file_location(
        "run_global_sensitivity", REPO / "scripts" / "run_global_sensitivity.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.skipif(not Path(LENDER).exists(), reason="lendercase scenario not present")
def test_cli_method_pawn_dispatches_and_tags_rows(capsys) -> None:
    """`--method pawn` runs run_pawn, prints a CSV whose method column is 'pawn'."""
    cli = _load_global_sa_cli()
    rc = cli.main(
        [
            "--config",
            LENDER,
            "--method",
            "pawn",
            "--metric",
            "project_irr",
            "--n",
            "16",
            "--s",
            "3",
        ]
    )
    assert rc == 0
    out = capsys.readouterr()
    # The stdout table (to_string) carries a 'pawn' method column and PAWN's
    # driver stat columns (median / mean / cv), NOT the Sobol/Morris columns.
    assert "pawn" in out.out
    assert "median" in out.out and "cv" in out.out
    # Lender headline on stderr uses the PAWN wording (median-KS ranking).
    assert "PAWN median-KS ranking" in out.err


@pytest.mark.skipif(not Path(LENDER).exists(), reason="lendercase scenario not present")
def test_cli_method_pawn_covenant_metric_is_flagged_flat(capsys) -> None:
    """The covenant-pinned min_dscr KPI must be disclosed FLAT in the PAWN headline,
    not presented as an influence ranking (CESSPIT fail-loud; #644 mask + #658 CLI)."""
    cli = _load_global_sa_cli()
    rc = cli.main(
        ["--config", LENDER, "--method", "pawn", "--metric", "min_dscr", "--n", "16"]
    )
    assert rc == 0
    err = capsys.readouterr().err
    assert "[min_dscr] PAWN median-KS ranking" in err
    assert "FLAT" in err


def test_cli_method_choices_include_pawn_and_default_morris() -> None:
    """--method still DEFAULTS to morris (opt-in), and now offers pawn (#658)."""
    cli = _load_global_sa_cli()
    args = cli._parse_args(["--config", LENDER])
    assert args.method == "morris"  # default unchanged
    args_pawn = cli._parse_args(["--config", LENDER, "--method", "pawn"])
    assert args_pawn.method == "pawn"
    # sobol still rejects a non-power-of-two n path unchanged; pawn is a distinct choice.
    with pytest.raises(SystemExit):
        cli._parse_args(["--config", LENDER, "--method", "bogus"])
