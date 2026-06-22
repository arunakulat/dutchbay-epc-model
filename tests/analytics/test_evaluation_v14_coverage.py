"""Coverage-hardening tests for ``analytics.evaluation_v14``.

These exercise the error / edge branches of the canonical evaluation gateway
that the behavioural suites do not reach under the
``tests/analytics tests/api`` coverage command set:

    - the lazy Monte Carlo proxy body (``run_monte_carlo_analysis``);
    - the dotted-override expansion deep-merge collision branch;
    - the documented ``raise`` paths (bad pipeline payload, non-mapping KPIs,
      neither config_path nor raw_config, missing config file);
    - ``return_full_result=True`` vs the KPIs-only default;
    - the full ``evaluate_with_casper_tail_risk`` orchestrator, driven with the
      deterministic in-repo fakes (no network / cdsapi / matplotlib), including
      the Monte Carlo branch, the ``n_iterations`` config-key fallback, the
      seed-from-scenario fallback, the no-iterations guard, and the
      sensitivity-suite tail-risk enrichment block.

ECONOMICS-CRITICAL: no IRR/NPV/DSCR magic numbers are asserted here. Where a
real engine is exercised we assert only invariants (signs, ordering, structural
shape, documented raises) — the numeric KPI values flow from the fakes' own
fixtures or the live engine, never from a guessed constant.

Framework: TEST-01 (branch/edge pins), TYPE-01 (full hints).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import pytest

from analytics import evaluation_v14
from analytics.contracts_v14 import (
    MonteCarloResult,
    SensitivitySuite,
    ShockResult,
    TornadoResult,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER_SCENARIO = REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"


# ---------------------------------------------------------------------------
# Lazy Monte Carlo proxy (lines 57-59)
# ---------------------------------------------------------------------------
def test_run_monte_carlo_analysis_proxy_delegates_to_engine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The module-level ``run_monte_carlo_analysis`` is a thin lazy proxy that
    imports and forwards to ``analytics.mc.engine.run_monte_carlo_analysis``.

    Patch the *real* engine symbol (the one the proxy imports lazily) and assert
    args/kwargs are forwarded verbatim and the return value passed through.
    """
    captured: dict[str, Any] = {}
    sentinel = object()

    import analytics.mc.engine as mc_engine

    def _fake_engine(*args: Any, **kwargs: Any) -> Any:
        captured["args"] = args
        captured["kwargs"] = kwargs
        return sentinel

    monkeypatch.setattr(mc_engine, "run_monte_carlo_analysis", _fake_engine)

    out = evaluation_v14.run_monte_carlo_analysis(7, base_config={"a": 1}, seed=99)

    assert out is sentinel
    assert captured["args"] == (7,)
    assert captured["kwargs"] == {"base_config": {"a": 1}, "seed": 99}


# ---------------------------------------------------------------------------
# Dotted-override expansion: deep-merge collision branch (line 132)
# ---------------------------------------------------------------------------
def test_expand_dotted_overrides_merges_plain_mapping_into_expanded_branch() -> None:
    """A dotted key that materialises ``expanded["finance"] = {...}`` followed by
    a *plain* ``"finance"`` mapping must deep-merge (not clobber) — the line-132
    branch where ``existing`` is already a dict and ``value`` is a Mapping.
    """
    # Insertion order matters: the dotted key creates expanded["finance"] first,
    # then the plain "finance" mapping is merged into it.
    overrides = {
        "finance.capex_usd": 1100,
        "finance": {"opex_usd": 50},
    }

    out = evaluation_v14._expand_dotted_overrides(overrides)

    assert out == {"finance": {"capex_usd": 1100, "opex_usd": 50}}


def test_expand_dotted_overrides_passes_plain_keys_through() -> None:
    """Plain (non-dotted) scalar keys round-trip unchanged; nested mappings are
    expanded recursively."""
    out = evaluation_v14._expand_dotted_overrides(
        {"plain": 5, "nested": {"deep.key": 9}}
    )
    assert out == {"plain": 5, "nested": {"deep": {"key": 9}}}


# ---------------------------------------------------------------------------
# _run_pipeline_with_config: non-mapping payload raises (line 200)
# ---------------------------------------------------------------------------
def test_run_pipeline_with_config_rejects_non_mapping_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If ``run_v14_pipeline`` returns a non-mapping, the helper must raise
    TypeError naming the offending type (documented contract)."""
    monkeypatch.setattr(
        evaluation_v14, "run_v14_pipeline", lambda **_kw: ["not", "a", "mapping"]
    )
    with pytest.raises(TypeError, match="Expected pipeline result to be a mapping"):
        evaluation_v14._run_pipeline_with_config({"project": {"name": "x"}})


def test_run_pipeline_with_config_forwards_explicit_validation_modules(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Explicit ``validation_modules`` are forwarded to the pipeline verbatim
    (covers the non-default branch of the modules guard)."""
    seen: dict[str, Any] = {}

    def _fake_pipeline(
        *, config: Mapping[str, Any], validation_mode: str, validation_modules: Any
    ) -> Mapping[str, Any]:
        seen["modules"] = validation_modules
        seen["mode"] = validation_mode
        return {"kpis": {"project_irr": 0.1}}

    monkeypatch.setattr(evaluation_v14, "run_v14_pipeline", _fake_pipeline)

    out = evaluation_v14._run_pipeline_with_config(
        {"project": {"name": "x"}}, validation_modules=["cashflow"]
    )

    assert out == {"kpis": {"project_irr": 0.1}}
    assert seen["modules"] == ["cashflow"]
    assert seen["mode"] == "strict"


# ---------------------------------------------------------------------------
# evaluate_scenario_from_dict: non-mapping kpis raises (line 232)
# ---------------------------------------------------------------------------
def test_evaluate_scenario_from_dict_rejects_non_mapping_kpis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the pipeline returns ``kpis`` that is not a mapping,
    ``evaluate_scenario_from_dict`` must raise TypeError."""
    monkeypatch.setattr(
        evaluation_v14, "run_v14_pipeline", lambda **_kw: {"kpis": [1, 2, 3]}
    )
    with pytest.raises(TypeError, match="Expected 'kpis' to be a mapping"):
        evaluation_v14.evaluate_scenario_from_dict({"project": {"name": "x"}})


def test_evaluate_scenario_from_dict_normalizes_kpis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Happy path: dotted overrides applied, kpis normalized to floats and
    non-numeric entries dropped."""
    captured: dict[str, Any] = {}

    def _fake_pipeline(*, config: Mapping[str, Any], **_kw: Any) -> Mapping[str, Any]:
        captured["config"] = config
        return {"kpis": {"project_irr": 0.12, "label": "skip-me", "min_dscr": "1.4"}}

    monkeypatch.setattr(evaluation_v14, "run_v14_pipeline", _fake_pipeline)

    out = evaluation_v14.evaluate_scenario_from_dict(
        {"project": {"name": "x"}, "finance": {"capex_usd": 100}},
        overrides={"finance.capex_usd": 200},
    )

    assert out == {"project_irr": 0.12, "min_dscr": 1.4}
    # dotted override was expanded + deep-merged before the pipeline ran.
    assert captured["config"]["finance"]["capex_usd"] == 200


# ---------------------------------------------------------------------------
# evaluate_with_overrides: input validation + return modes (lines 289/314/319)
# ---------------------------------------------------------------------------
def test_evaluate_with_overrides_requires_a_config_source() -> None:
    """Neither ``config_path`` nor ``raw_config`` -> ValueError (line 289)."""
    with pytest.raises(ValueError, match="config_path or raw_config must be provided"):
        evaluation_v14.evaluate_with_overrides()


def test_evaluate_with_overrides_missing_file_raises() -> None:
    """A non-existent ``config_path`` -> FileNotFoundError."""
    with pytest.raises(FileNotFoundError, match="Scenario config not found"):
        evaluation_v14.evaluate_with_overrides(config_path="no/such/scenario.yaml")


def test_evaluate_with_overrides_full_result_passthrough(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``return_full_result=True`` returns the full pipeline mapping verbatim
    (line 314), not just the KPI subset."""
    full = {
        "kpis": {"project_irr": 0.1},
        "debt_result": {"min_dscr": 1.45},
        "annual_rows": [],
    }
    monkeypatch.setattr(evaluation_v14, "run_v14_pipeline", lambda **_kw: full)

    out = evaluation_v14.evaluate_with_overrides(
        raw_config={"project": {"name": "x"}}, return_full_result=True
    )

    assert out == full
    assert out["debt_result"]["min_dscr"] == 1.45


def test_evaluate_with_overrides_raw_config_kpis_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Default (``return_full_result=False``) returns normalized KPIs from an
    in-memory ``raw_config`` (the raw_config load branch)."""
    monkeypatch.setattr(
        evaluation_v14,
        "run_v14_pipeline",
        lambda **_kw: {"kpis": {"project_irr": 0.1, "min_dscr": 1.4}},
    )
    out = evaluation_v14.evaluate_with_overrides(raw_config={"project": {"name": "x"}})
    assert out == {"project_irr": 0.1, "min_dscr": 1.4}


def test_evaluate_with_overrides_full_result_non_mapping_kpis_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """KPIs-only branch with a non-mapping ``kpis`` -> TypeError (line 319)."""
    monkeypatch.setattr(
        evaluation_v14, "run_v14_pipeline", lambda **_kw: {"kpis": 123}
    )
    with pytest.raises(TypeError, match="Expected 'kpis' to be a mapping"):
        evaluation_v14.evaluate_with_overrides(raw_config={"project": {"name": "x"}})


def test_evaluate_scenario_alias_is_evaluate_with_overrides() -> None:
    """The public ``evaluate_scenario`` alias is the same object as
    ``evaluate_with_overrides`` (documented backward-compat surface)."""
    assert evaluation_v14.evaluate_scenario is evaluation_v14.evaluate_with_overrides


# ---------------------------------------------------------------------------
# evaluate_with_casper_tail_risk (lines 367-491)
# ---------------------------------------------------------------------------
def _write_toy_configs(tmp_path: Path) -> Path:
    """Write a toy scenario YAML and return its path."""
    cfg = tmp_path / "toy.yaml"
    cfg.write_text("project:\n  name: Toy Scenario\n", encoding="utf-8")
    return cfg


def _toy_suite(cfg_path: Path) -> SensitivitySuite:
    """A minimal SensitivitySuite whose single tornado/shock feeds the live
    tail-risk enrichment (no MC arrays required)."""
    return SensitivitySuite(
        base_config_path=str(cfg_path),
        metric="project_irr",
        tornado_results=[
            TornadoResult(
                metric_name="project_irr",
                base_metric=0.12,
                shock_results=[
                    ShockResult(
                        variable_name="project.capex_usd_per_kw",
                        label="capex",
                        low_case=0.10,
                        high_case=0.14,
                        base_case=0.12,
                        impact=0.04,
                        impact_abs=0.04,
                        metric_name="project_irr",
                    ),
                ],
                label="capex",
                impact_abs=0.04,
            ),
        ],
    )


def _patch_fakes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch pipeline + MC orchestrators inside evaluation_v14 with the
    deterministic in-repo fakes."""
    from tests.analytics_layer._casper_fakes import (
        fake_run_monte_carlo_analysis,
        fake_run_v14_pipeline,
    )

    monkeypatch.setattr(evaluation_v14, "run_v14_pipeline", fake_run_v14_pipeline)
    monkeypatch.setattr(
        evaluation_v14, "run_monte_carlo_analysis", fake_run_monte_carlo_analysis
    )


def test_casper_missing_config_raises() -> None:
    """A non-existent base config path -> FileNotFoundError (line 368-369)."""
    with pytest.raises(FileNotFoundError, match="Scenario config not found"):
        evaluation_v14.evaluate_with_casper_tail_risk(
            config_path="no/such/file.yaml"
        )


def test_casper_full_path_with_fakes_and_enrichment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Full CASPER orchestration via fakes: MC branch (iterations key),
    sensitivity tail-risk enrichment, and assembled CasperResult metadata.

    Covers the MC-config 'iterations' key path, the seed extraction, the MC
    guard, and the sensitivity-suite enrichment block in one end-to-end run.
    """
    _patch_fakes(monkeypatch)
    cfg = _write_toy_configs(tmp_path)
    mc_cfg = tmp_path / "mc.yaml"
    mc_cfg.write_text("monte_carlo:\n  iterations: 10\n  seed: 7\n", encoding="utf-8")

    result = evaluation_v14.evaluate_with_casper_tail_risk(
        config_path=str(cfg),
        monte_carlo_config_path=str(mc_cfg),
        sensitivity_suite=_toy_suite(cfg),
        metric="project_irr",
        confidence=0.9,
        validation_modules=("cashflow", "debt"),
    )

    # Scenario + baseline KPIs hydrated from the fake pipeline.
    assert result.scenario is not None
    assert result.baseline_kpis["project_irr"] == pytest.approx(0.12)
    # MC dataclass surfaced with iterations from the config 'iterations' key.
    assert result.monte_carlo is not None
    assert result.monte_carlo.iterations == 10
    assert result.sensitivities is not None
    # Tail-risk enrichment populated metadata, alpha derived from confidence.
    assert "tail_risk" in result.metadata
    assert "tail_risk_summary" in result.metadata
    snap = result.metadata["tail_risk_summary"]["project_irr"]
    assert snap["cvar_alpha"] == pytest.approx(1.0 - 0.9)


def test_casper_uses_n_iterations_key_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """MC config exposing ``n_iterations`` (not ``iterations``) is honoured via
    the elif fallback branch."""
    _patch_fakes(monkeypatch)
    cfg = _write_toy_configs(tmp_path)
    mc_cfg = tmp_path / "mc.yaml"
    mc_cfg.write_text("monte_carlo:\n  n_iterations: 4\n", encoding="utf-8")

    result = evaluation_v14.evaluate_with_casper_tail_risk(
        config_path=str(cfg),
        monte_carlo_config_path=str(mc_cfg),
        confidence=0.9,
    )
    assert result.monte_carlo is not None
    assert result.monte_carlo.iterations == 4


def test_casper_mc_config_without_iterations_uses_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """MC config with a ``monte_carlo`` block but no iterations key falls back to
    the 1000 default (the warning branch). Seed falls back to the scenario
    ``monte_carlo.seed`` block (base_config branch of the seed lookup)."""
    cfg = tmp_path / "toy.yaml"
    cfg.write_text(
        "project:\n  name: Toy\nmonte_carlo:\n  seed: 13\n", encoding="utf-8"
    )
    mc_cfg = tmp_path / "mc.yaml"
    mc_cfg.write_text("monte_carlo:\n  something_else: 1\n", encoding="utf-8")

    seen: dict[str, Any] = {}

    def _capture_mc(
        *, base_config: Mapping[str, Any], n_trials: int, seed: int, **_kw: Any
    ) -> MonteCarloResult:
        seen["n_trials"] = n_trials
        seen["seed"] = seed
        return MonteCarloResult(scenario_name="Toy", iterations=n_trials)

    from tests.analytics_layer._casper_fakes import fake_run_v14_pipeline

    monkeypatch.setattr(evaluation_v14, "run_v14_pipeline", fake_run_v14_pipeline)
    monkeypatch.setattr(evaluation_v14, "run_monte_carlo_analysis", _capture_mc)

    result = evaluation_v14.evaluate_with_casper_tail_risk(
        config_path=str(cfg),
        monte_carlo_config_path=str(mc_cfg),
        confidence=0.9,
    )
    assert result.monte_carlo is not None
    assert seen["n_trials"] == 1000  # default used
    assert seen["seed"] == 13  # from scenario monte_carlo.seed block


def test_casper_malformed_mc_iterations_and_seed_fall_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Non-numeric ``iterations`` and ``seed`` in the MC config trigger the
    defensive ``except (AttributeError, TypeError, ValueError)`` handlers, which
    fall back to the 1000 / 42 defaults rather than crashing (lines 427-428,
    442-443)."""
    cfg = _write_toy_configs(tmp_path)
    mc_cfg = tmp_path / "mc.yaml"
    # int("not-a-number") raises ValueError inside both extraction try-blocks.
    mc_cfg.write_text(
        "monte_carlo:\n  iterations: not-a-number\n  seed: also-bad\n",
        encoding="utf-8",
    )

    seen: dict[str, Any] = {}

    def _capture_mc(
        *, base_config: Mapping[str, Any], n_trials: int, seed: int, **_kw: Any
    ) -> MonteCarloResult:
        seen["n_trials"] = n_trials
        seen["seed"] = seed
        return MonteCarloResult(scenario_name="Toy", iterations=n_trials)

    from tests.analytics_layer._casper_fakes import fake_run_v14_pipeline

    monkeypatch.setattr(evaluation_v14, "run_v14_pipeline", fake_run_v14_pipeline)
    monkeypatch.setattr(evaluation_v14, "run_monte_carlo_analysis", _capture_mc)

    result = evaluation_v14.evaluate_with_casper_tail_risk(
        config_path=str(cfg),
        monte_carlo_config_path=str(mc_cfg),
        confidence=0.9,
    )
    assert result.monte_carlo is not None
    assert seen["n_trials"] == 1000  # iterations extraction fell back to default
    assert seen["seed"] == 42  # seed extraction fell back to default


def test_casper_zero_iteration_mc_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An MC engine that yields zero iterations -> ValueError guard (line 456)."""
    cfg = _write_toy_configs(tmp_path)
    mc_cfg = tmp_path / "mc.yaml"
    mc_cfg.write_text("monte_carlo:\n  iterations: 5\n", encoding="utf-8")

    from tests.analytics_layer._casper_fakes import fake_run_v14_pipeline

    def _zero_mc(**_kw: Any) -> MonteCarloResult:
        return MonteCarloResult(scenario_name="Toy", iterations=0)

    monkeypatch.setattr(evaluation_v14, "run_v14_pipeline", fake_run_v14_pipeline)
    monkeypatch.setattr(evaluation_v14, "run_monte_carlo_analysis", _zero_mc)

    with pytest.raises(ValueError, match="Monte Carlo produced no iterations"):
        evaluation_v14.evaluate_with_casper_tail_risk(
            config_path=str(cfg),
            monte_carlo_config_path=str(mc_cfg),
            confidence=0.9,
        )


def test_casper_bad_scenario_result_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pipeline missing a mapping ``scenario_result`` -> ValueError (line 387)."""
    cfg = _write_toy_configs(tmp_path)

    def _bad_pipeline(
        *, config: Mapping[str, Any], validation_mode: str, validation_modules: Any
    ) -> Mapping[str, Any]:
        return {"kpis": {"project_irr": 0.1}, "scenario_result": "not-a-mapping"}

    monkeypatch.setattr(evaluation_v14, "run_v14_pipeline", _bad_pipeline)

    with pytest.raises(ValueError, match="did not return a 'scenario_result' mapping"):
        evaluation_v14.evaluate_with_casper_tail_risk(config_path=str(cfg))


def test_casper_no_mc_no_suite_minimal_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No MC config + no sensitivity suite: the orchestrator still assembles a
    CasperResult with empty metadata (skips both the MC and enrichment blocks)."""
    cfg = _write_toy_configs(tmp_path)

    from tests.analytics_layer._casper_fakes import fake_run_v14_pipeline

    monkeypatch.setattr(evaluation_v14, "run_v14_pipeline", fake_run_v14_pipeline)

    result = evaluation_v14.evaluate_with_casper_tail_risk(
        config_path=str(cfg),
        validation_modules=["cashflow", "debt"],
    )
    assert result.monte_carlo is None
    assert result.sensitivities is None
    assert result.metadata == {}
    assert result.baseline_kpis["project_irr"] == pytest.approx(0.12)


def test_casper_seed_from_mc_config_block(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Seed is taken from the MC config's own ``monte_carlo.seed`` when present
    (preferred over the scenario block)."""
    cfg = tmp_path / "toy.yaml"
    cfg.write_text(
        "project:\n  name: Toy\nmonte_carlo:\n  seed: 99\n", encoding="utf-8"
    )
    mc_cfg = tmp_path / "mc.yaml"
    mc_cfg.write_text("monte_carlo:\n  iterations: 3\n  seed: 21\n", encoding="utf-8")

    seen: dict[str, Any] = {}

    def _capture_mc(
        *, base_config: Mapping[str, Any], n_trials: int, seed: int, **_kw: Any
    ) -> MonteCarloResult:
        seen["seed"] = seed
        return MonteCarloResult(scenario_name="Toy", iterations=n_trials)

    from tests.analytics_layer._casper_fakes import fake_run_v14_pipeline

    monkeypatch.setattr(evaluation_v14, "run_v14_pipeline", fake_run_v14_pipeline)
    monkeypatch.setattr(evaluation_v14, "run_monte_carlo_analysis", _capture_mc)

    evaluation_v14.evaluate_with_casper_tail_risk(
        config_path=str(cfg),
        monte_carlo_config_path=str(mc_cfg),
        confidence=0.9,
    )
    assert seen["seed"] == 21  # MC config seed preferred over scenario's 99


def test_casper_real_engine_on_lender_scenario(tmp_path: Path) -> None:
    """End-to-end with NO fakes on the canonical lender scenario: the live
    pipeline + live MC engine must drive a populated, ordered MonteCarloResult.

    Invariant-only (no magic numbers): p10 <= p50 <= p90, 100% success.
    """
    if not LENDER_SCENARIO.is_file():
        pytest.skip(f"Canonical lender scenario not found: {LENDER_SCENARIO}")

    mc_cfg = tmp_path / "mc_small.yaml"
    mc_cfg.write_text("monte_carlo:\n  iterations: 4\n  seed: 42\n", encoding="utf-8")

    result = evaluation_v14.evaluate_with_casper_tail_risk(
        config_path=str(LENDER_SCENARIO),
        monte_carlo_config_path=str(mc_cfg),
        metric="project_irr",
        confidence=0.9,
    )

    assert result.monte_carlo is not None
    assert result.monte_carlo.iterations == 4
    assert result.monte_carlo.failed_iterations == 0
    assert result.monte_carlo.success_rate() == 100.0
    p10 = result.monte_carlo.project_irr_p10
    p50 = result.monte_carlo.project_irr_p50
    p90 = result.monte_carlo.project_irr_p90
    assert isinstance(p10, float) and isinstance(p50, float) and isinstance(p90, float)
    assert p10 <= p50 <= p90
