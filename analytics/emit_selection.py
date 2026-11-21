"""Which optional emitters a ``run_full_pipeline_v14`` run writes (#1756).

Each emitter has its own ``emit_*`` switch in ``conf/run_full_pipeline_v14.yaml``. ``emit_all``
turns them all on at once. The rules:

- A switch set explicitly (``true`` or ``false``) wins over ``emit_all``. So
  ``emit_all=true emit_grid_screen=false`` runs everything except grid screening.
- A switch left unset (``null``) follows ``emit_all``, which is on by default (owner ruling,
  2026-11-16: the analyses run for every scenario unless switched off). ``emit_all=false``
  with every switch unset runs no emitter, as before this module.
- Under ``emit_all``, an emitter whose inputs the run does not have is not run, and the plan
  records why: no ``monte_carlo.parameters`` the Monte Carlo engine can read, no
  ``interaction_grid`` block, no well-formed ``tech_comparison`` block (a mapping whose
  ``scenarios`` list holds ``{label, config}`` entries naming files that exist), or no grid
  block with ``study_enabled: true``.
- The CLI writes the run's figures before any emitter runs. An emitter that ran under
  ``emit_all`` and raised is recorded as ``failed`` with its error under
  ``result['emitters']`` and logged as an error; the run still completes.
- An emitter switched on explicitly is always attempted, and its failure stops the run
  (``FRAMEWORK-02``), as it did before this module.

The Monte Carlo parameters are read with the engine's own parser, and the ``tech_comparison``
block is checked by the emitter's own rules. The other applicability checks look only for the
presence of an emitter's inputs; a declared but malformed block is the emitter's to refuse. The lender guards in
the emitters themselves (the capital-risk report's trial floor and forced fail-loud Monte Carlo)
are untouched.

``EMIT_FLAGS`` lists every ``emit_*`` switch. A lint test ties it to the switches the CLI reads
and the conf declares, so a new emitter cannot be left out of ``emit_all``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional, Tuple

#: Every optional emitter switch, in the order the CLI runs them.
EMIT_FLAGS: Tuple[str, ...] = (
    "emit_executive_workbook",
    "emit_capital_risk_report",
    "emit_lender_report",
    "emit_interaction_grid",
    "emit_tech_comparison",
    "emit_grid_screen",
)

#: Plan statuses. ``failed`` is set by the CLI, not the plan: an emitter that ran under
#: ``emit_all`` and raised.
STATUS_RUN = "run"
STATUS_NOT_RUN = "not_run"
STATUS_OFF = "off"
STATUS_FAILED = "failed"


@dataclass(frozen=True)
class EmitterDecision:
    """One emitter's decision: whether it runs, and why."""

    flag: str
    run: bool
    status: str
    source: str
    reason: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        """Return the decision as a JSON-ready mapping."""
        out: Dict[str, Any] = {"status": self.status, "source": self.source}
        if self.reason is not None:
            out["reason"] = self.reason
        return out


def _get(cfg: Any, key: str) -> Any:
    getter = getattr(cfg, "get", None)
    if getter is None:
        raise TypeError(f"run config must be a mapping; got {type(cfg).__name__}")
    return getter(key, None)


def _switch(cfg: Any, key: str) -> Optional[bool]:
    """Return an explicit switch value, or ``None`` when the switch is unset."""
    value = _get(cfg, key)
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    raise ValueError(f"{key} must be true, false or null; got {value!r}")


#: ``emit_all`` when the run config leaves it unset. On, by the owner's ruling of 2026-11-16.
EMIT_ALL_DEFAULT = True


def emit_all_requested(cfg: Any) -> bool:
    """Return the ``emit_all`` switch (:data:`EMIT_ALL_DEFAULT` when unset)."""
    value = _switch(cfg, "emit_all")
    return EMIT_ALL_DEFAULT if value is None else value


def _needs_monte_carlo_parameters(
    scenario: Mapping[str, Any], cfg: Any
) -> Optional[str]:
    mc = scenario.get("monte_carlo")
    if not (isinstance(mc, Mapping) and mc.get("parameters")):
        return "the scenario declares no monte_carlo.parameters to sample"
    # Read the parameters with the Monte Carlo engine's own parser before the run, so a block
    # the engine would refuse is listed with the engine's reason instead of failing the run
    # after the figures (FRAMEWORK-02 pre-flight). Imported here to keep the engine off the
    # CLI's import path when no Monte Carlo is planned.
    from analytics.mc.engine import MonteCarloEngine

    # Any parser error is listed, not only MonteCarloConfigError: a non-numeric bound such as
    # ``low: null`` reaches ``float(...)`` and raises TypeError or ValueError, and a default run
    # must still complete (owner ruling 2026-11-16 07:15Z).
    try:
        names, _, kinds, _, _ = MonteCarloEngine._extract_param_definitions(scenario)
        MonteCarloEngine._refuse_native_capex_conflicts(scenario, names, kinds)
    except Exception as exc:  # noqa: BLE001 - listed with its reason, never silent
        return (
            "the Monte Carlo engine cannot read monte_carlo.parameters: "
            f"{type(exc).__name__}: {exc}"
        )
    return None


def _needs_interaction_grid(scenario: Mapping[str, Any], cfg: Any) -> Optional[str]:
    if isinstance(scenario.get("interaction_grid"), Mapping):
        return None
    return "the scenario declares no interaction_grid block"


def _needs_tech_comparison_scenarios(
    scenario: Mapping[str, Any], cfg: Any
) -> Optional[str]:
    """Check the whole ``tech_comparison`` block's shape, as the emitter would.

    Every malformed shape is listed with its reason rather than raised: this check also runs
    before the finance run, and a default run must still write its figures (owner ruling
    2026-11-16 07:15Z). The rules are those of
    :func:`app.reports.tech_comparison_emit.resolve_tech_comparison_scenarios`, which is not
    imported here so that the report stack stays off the CLI's import path; a test holds the
    two to the same verdicts.
    """
    block = _get(cfg, "tech_comparison")
    if block is None:
        return "the run config lists no tech_comparison.scenarios"
    # OmegaConf's DictConfig is a Mapping; its ListConfig is not, and ListConfig.get takes an
    # index, so a list-shaped block must be refused before any .get (#1760 domain D-1).
    if not isinstance(block, Mapping):
        return (
            "tech_comparison must be a mapping with a scenarios list; "
            f"got {type(block).__name__}"
        )
    entries = block.get("scenarios", None)
    if entries is None:
        return "the run config lists no tech_comparison.scenarios"
    if isinstance(entries, (str, bytes, Mapping)) or not isinstance(entries, Sequence):
        return (
            "tech_comparison.scenarios must be a list of {label, config} entries; "
            f"got {type(entries).__name__}"
        )
    if not len(entries):
        return "the run config lists no tech_comparison.scenarios"
    for i, entry in enumerate(entries):
        if not isinstance(entry, Mapping):
            return (
                f"tech_comparison.scenarios[{i}] must be a mapping with 'label' and "
                f"'config'; got {type(entry).__name__}"
            )
        label = entry.get("label", None)
        if not isinstance(label, str) or not label:
            return f"tech_comparison.scenarios[{i}] must declare a non-empty 'label'"
        config = entry.get("config", None)
        if not isinstance(config, str) or not config:
            return f"tech_comparison.scenarios[{i}] ('{label}') must declare a 'config' path"
        if not Path(config).exists():
            return (
                f"tech_comparison.scenarios[{i}] ('{label}') config path does not exist: "
                f"{config}"
            )
    return None


def _needs_enabled_grid_study(scenario: Mapping[str, Any], cfg: Any) -> Optional[str]:
    grid = scenario.get("grid")
    if isinstance(grid, Mapping) and grid.get("study_enabled") is True:
        return None
    return "the scenario declares no grid block with study_enabled: true"


def _always(scenario: Mapping[str, Any], cfg: Any) -> Optional[str]:
    return None


#: For each switch, a check that returns ``None`` when the run has the emitter's inputs, or the
#: reason it does not.
APPLICABILITY: Dict[str, Callable[[Mapping[str, Any], Any], Optional[str]]] = {
    "emit_executive_workbook": _always,
    "emit_capital_risk_report": _needs_monte_carlo_parameters,
    # The combined lender report (#1752) lists any section it cannot build, with its reason,
    # so it applies to every run with figures.
    "emit_lender_report": _always,
    "emit_interaction_grid": _needs_interaction_grid,
    "emit_tech_comparison": _needs_tech_comparison_scenarios,
    "emit_grid_screen": _needs_enabled_grid_study,
}


WRITE_ARTIFACTS_OFF_REASON = (
    "write_artifacts is false, so emit_all writes no files; switch an emitter on by name"
    " to write it"
)


def plan_emitters(
    cfg: Any,
    scenario: Optional[Mapping[str, Any]] = None,
    *,
    write_artifacts: bool = True,
) -> Dict[str, EmitterDecision]:
    """Decide which emitters run.

    Args:
        cfg: The run config (``DictConfig`` or mapping).
        scenario: The effective scenario mapping. Required when ``emit_all`` is on, any
            switch is unset and ``write_artifacts`` is true, because applicability is read
            from it; ignored otherwise.
        write_artifacts: Whether the run writes files (#1760 assurance L-1). When false,
            ``emit_all`` switches nothing on: every unset switch is listed as not run with
            :data:`WRITE_ARTIFACTS_OFF_REASON`, so a run that writes no figures writes no
            report either. A switch set by name still runs, as before #1756.

    Returns:
        One :class:`EmitterDecision` per entry in :data:`EMIT_FLAGS`, in that order.
    """
    emit_all = emit_all_requested(cfg)
    plan: Dict[str, EmitterDecision] = {}
    for flag in EMIT_FLAGS:
        explicit = _switch(cfg, flag)
        if explicit is not None:
            plan[flag] = EmitterDecision(
                flag=flag,
                run=explicit,
                status=STATUS_RUN if explicit else STATUS_OFF,
                source="explicit",
            )
            continue
        if not emit_all:
            plan[flag] = EmitterDecision(
                flag=flag, run=False, status=STATUS_OFF, source="default"
            )
            continue
        if not write_artifacts:
            plan[flag] = EmitterDecision(
                flag=flag,
                run=False,
                status=STATUS_NOT_RUN,
                source="emit_all",
                reason=WRITE_ARTIFACTS_OFF_REASON,
            )
            continue
        if scenario is None:
            raise ValueError(
                "emit_all needs the effective scenario to decide which emitters apply"
            )
        # Any error from an applicability check is listed with its reason, not raised: the
        # plan is read before the finance run, and a default run must still write its figures
        # (owner ruling 2026-11-16 07:15Z). An OmegaConf interpolation that cannot resolve, for
        # example, raises on first read (#1760 domain D-2 at 7c595118).
        try:
            reason = APPLICABILITY[flag](scenario, cfg)
        except Exception as exc:  # noqa: BLE001 - listed with its reason, never silent
            reason = (
                f"the run config's inputs for {flag} cannot be read: "
                f"{type(exc).__name__}: {exc}"
            )
        plan[flag] = EmitterDecision(
            flag=flag,
            run=reason is None,
            status=STATUS_RUN if reason is None else STATUS_NOT_RUN,
            source="emit_all",
            reason=reason,
        )
    return plan


def plan_report(plan: Mapping[str, EmitterDecision]) -> Dict[str, Dict[str, Any]]:
    """Return the plan as the JSON block a run records under ``result['emitters']``."""
    return {flag: decision.as_dict() for flag, decision in plan.items()}
