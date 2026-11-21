"""Seeded Monte Carlo sizing of a solar + BESS unit or project: the run and its summary.

Moved from the single-site sizing script (#1578 U3) so that any scenario can run the
sizing. The run reads the unit, pricing and (for a project) regulatory configs
and the scenario the sizing config names, sizes through
:mod:`solar_resource.pv_bess_sizing`, and returns one JSON-ready summary: the run spec with
its seed and its requested and effective evaluation counts (``MRM-01``, ``TEST-03``), every
grid point, the recommendation and the sensitivities. The spec names the code that ran by
content (``code_sha256``) as well as by commit (``git_sha``), because a squash merge leaves
the run's commit outside ``main`` (MRM-02). Nothing here names a site: the caller passes the
config label, the script and the stated limitations.
"""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence

import yaml

from solar_resource.pv_bess_sizing import (
    PROJECT_SIZING_SCHEMA,
    run_project_sizing,
    run_sizing,
    site_context,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def _repo_path(rel: str) -> Path:
    """Resolve a config path against the repository root."""
    p = Path(rel)
    return p if p.is_absolute() else REPO_ROOT / p


def _read(rel: str) -> Any:
    """Read a repository JSON or YAML file."""
    text = _repo_path(rel).read_text()
    return (
        json.loads(text)
        if rel.endswith((".json", ".geojson"))
        else yaml.safe_load(text)
    )


def _sha256(rel: str) -> str:
    return hashlib.sha256(_repo_path(rel).read_bytes()).hexdigest()


def _git_head() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def code_sha256(files: Iterable[Path], root: Path = REPO_ROOT) -> Dict[str, Any]:
    """Digest the repository code a run executed (MRM-02).

    ``git_sha`` names the commit a run started from, but a squash merge leaves that commit
    outside ``main`` (#1568's summaries cite f5b45904, held only by its pull-request ref). The
    file digests are checkable against any checkout: ``tree`` is the SHA-256 of the
    ``sha256sum`` listing (``"<sha256>  <path>"`` lines, sorted by path, newline-terminated),
    so ``sha256sum -c`` verifies each file and the listing reproduces ``tree``.
    ``uncommitted`` names the files that differed from ``git_sha`` when the run ended (empty
    for a clean run; ``None`` when git could not be asked).
    """
    rels = sorted({p.resolve().relative_to(root.resolve()).as_posix() for p in files})
    digests = {r: hashlib.sha256((root / r).read_bytes()).hexdigest() for r in rels}
    listing = "".join(f"{digests[r]}  {r}\n" for r in rels)
    try:
        dirty = subprocess.run(
            ["git", "status", "--porcelain", "--", *rels],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        uncommitted: list[str] | None = sorted(
            line[3:] for line in dirty.splitlines() if line.strip()
        )
    except (OSError, subprocess.CalledProcessError):
        uncommitted = None
    return {
        "tree": hashlib.sha256(listing.encode()).hexdigest(),
        "files": digests,
        "uncommitted": uncommitted,
    }


def inputs_digest(spec: Mapping[str, Any]) -> str:
    """One content digest of everything a sizing run was computed from.

    It covers the code that ran (``code_sha256.tree``), the config and scenario files the
    run read (``inputs_sha256``: unit, pricing, scenario and, for a project, regulatory)
    and the sizing config itself (``sizing_config_sha256``). It is the SHA-256 of their
    canonical JSON, so it can be recomputed from a committed summary's own spec fields.
    ``VERSION`` is deliberately not an input: a release number changes no figure, so a
    version bump does not make a summary stale.
    """
    record = {
        "code_tree": spec["code_sha256"]["tree"],
        "inputs_sha256": dict(spec["inputs_sha256"]),
        "sizing_config_sha256": spec["sizing_config_sha256"],
    }
    return hashlib.sha256(
        json.dumps(record, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def loaded_repo_modules(root: Path = REPO_ROOT) -> list[Path]:
    """The source files of every imported module that lives in this repository.

    Modules under a virtual environment or ``site-packages`` inside the checkout are third
    party and are left out (the lock file pins them). A module of one of this repository's
    top-level packages that was imported from outside ``root`` (another checkout reached
    through an editable install, say) is refused, not dropped: ``code_sha256`` would
    otherwise omit code that ran (#1691 assurance A-4).
    """
    base = root.resolve()
    packages = {p.name for p in base.iterdir() if (p / "__init__.py").is_file()}
    out: list[Path] = []
    for key, mod in list(sys.modules.items()):
        name = getattr(mod, "__file__", None)
        if not name:
            continue
        path = Path(name).resolve()
        if not path.is_relative_to(base):
            if key.split(".")[0] in packages:
                raise RuntimeError(
                    f"repository module {key} was imported from {path}, outside {base}"
                )
            continue
        if path.suffix != ".py":
            continue
        rel = path.relative_to(base).parts
        if rel[0].startswith(".") or "site-packages" in rel:
            continue
        out.append(path)
    return out


def _is_project_schema(value: Any) -> bool:
    """Whether ``value`` names the project sizing family, with or without a site prefix."""
    return isinstance(value, str) and (
        value == PROJECT_SIZING_SCHEMA or value.endswith("_" + PROJECT_SIZING_SCHEMA)
    )


def run(
    cfg: Mapping[str, Any],
    *,
    config_label: str,
    script: Path,
    limitations: Sequence[str],
    project_limitations: Sequence[str] = (),
    n_workers: Optional[int] = None,
) -> Dict[str, Any]:
    """Run the sizing and return the JSON-ready summary.

    A config whose ``schema_version`` is of the project family
    (:data:`~solar_resource.pv_bess_sizing.PROJECT_SIZING_SCHEMA`, with or without a site
    prefix) runs :func:`~solar_resource.pv_bess_sizing.run_project_sizing`; any other runs
    :func:`~solar_resource.pv_bess_sizing.run_sizing`.

    Args:
        cfg: The sizing config, as the caller composed it.
        config_label: What the summary's ``config`` names (the config file the run read).
        script: The command-line script that ran, digested with the code (MRM-02).
        limitations: The run's stated limitations, in the order the summary lists them.
        project_limitations: Further limitations listed for a project run only.
    """
    started = time.time()
    unit_cfg = _read(str(cfg["unit_config"]))
    pricing_cfg = _read(str(cfg["pricing_config"]))
    scenario = _read(str(cfg["scenario"]))
    workers = cfg.get("n_workers", 1) if n_workers is None else n_workers
    sizing_cfg = {k: v for k, v in cfg.items() if k not in ("hydra", "n_workers")}
    project = _is_project_schema(cfg.get("schema_version"))
    inputs = ["unit_config", "pricing_config", "scenario"]
    if project:
        inputs.append("regulatory_config")
        result = run_project_sizing(
            sizing_cfg,
            unit_cfg=unit_cfg,
            pricing_cfg=pricing_cfg,
            regulatory_cfg=_read(str(cfg["regulatory_config"])),
            scenario=scenario,
            site=site_context(unit_cfg, _read),
            n_workers=workers,
        )
    else:
        result = run_sizing(
            sizing_cfg,
            unit_cfg=unit_cfg,
            pricing_cfg=pricing_cfg,
            scenario=scenario,
            site=site_context(unit_cfg, _read),
            n_workers=workers,
        )
    spec = dict(result.spec)
    spec["inputs_sha256"] = {str(cfg[k]): _sha256(str(cfg[k])) for k in inputs}
    spec["sizing_config_sha256"] = hashlib.sha256(
        json.dumps(
            {
                k: v
                for k, v in sizing_cfg.items()
                if k not in ("output", "recommendation")
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()
    spec["git_sha"] = _git_head()
    spec["code_sha256"] = code_sha256([*loaded_repo_modules(), Path(script)])
    # The summary names what it was computed from by content, not by release number: a
    # VERSION bump that moves none of these inputs leaves a committed summary current.
    spec["inputs_digest"] = inputs_digest(spec)
    spec["limitations"] = list(limitations)
    if project:
        spec["limitations"] += list(project_limitations)
    sens_key = "sensitivities" if project else "curtailment_scenario"
    out: Dict[str, Any] = {
        "config": config_label,
        "statistics_convention": (
            "p50 median; p90 exceeded in 90% of trials (10th percentile); "
            "p10 exceeded in 10% (90th percentile)"
        ),
        "spec": spec,
        "recommendation": result.recommendation,
        "points": result.points,
        sens_key: result.curtailment,
    }
    text = json.dumps(out, sort_keys=True, allow_nan=False, indent=1)
    spec["result_sha256"] = hashlib.sha256(text.encode()).hexdigest()
    spec["runtime_s"] = round(time.time() - started, 1)
    target = cfg["output"]["summary_json"]
    if target:
        written = concise_project_summary(out) if project else out
        path = _repo_path(str(target))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(written, sort_keys=True, allow_nan=False, indent=1) + "\n"
        )
    return out


#: The grid table's columns: (column, path into a point). Statistics are P50 and P90 in the
#: exceedance convention, and ``n`` counts the trials whose metric is defined.
GRID_COLUMNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("pv_tables", ("pv_tables",)),
    ("pv_tables_is_land_max", ("pv_tables_is_land_max",)),
    ("dc_mwp", ("dc_mwp",)),
    ("pv_ac_mw", ("pv_ac_mw",)),
    ("dc_ac_ratio", ("dc_ac_ratio",)),
    ("bess_power_mw", ("bess_power_mw",)),
    ("bess_energy_mwh", ("bess_energy_mwh",)),
    ("fits", ("fits",)),
    ("meets_4h_rule", ("meets_4h_rule",)),
    ("eligible_A", ("eligible_by_reading", "A")),
    ("eligible_B", ("eligible_by_reading", "B")),
    ("tables_that_fit", ("land", "tables_that_fit")),
    ("bess_containers", ("land", "bess_containers")),
    ("inverter_count", ("inverter", "inverter_count")),
    ("pv_capex_usd_base", ("capex_usd_base", "pv")),
    ("bess_capex_usd_base", ("capex_usd_base", "bess")),
    ("discount_rate_used", ("discount_rate_used",)),
    ("base_unit_pretax_npv_usd", ("base", "unit_pretax_npv_usd")),
    ("base_project_npv", ("base", "project_npv")),
    ("unit_pretax_npv_usd_p50", ("metrics", "unit_pretax_npv_usd", "p50")),
    ("unit_pretax_npv_usd_p90", ("metrics", "unit_pretax_npv_usd", "p90")),
    ("unit_pretax_npv_usd_mean", ("metrics", "unit_pretax_npv_usd", "mean")),
    ("unit_pretax_irr_p50", ("metrics", "unit_pretax_irr", "p50")),
    ("unit_pretax_irr_p90", ("metrics", "unit_pretax_irr", "p90")),
    ("project_npv_p50", ("metrics", "project_npv", "p50")),
    ("project_npv_p90", ("metrics", "project_npv", "p90")),
    ("project_irr_p50", ("metrics", "project_irr", "p50")),
    ("project_irr_n", ("metrics", "project_irr", "n")),
    ("equity_irr_p50", ("metrics", "equity_irr", "p50")),
    ("equity_npv_p50", ("metrics", "equity_npv", "p50")),
    ("min_dscr_p50", ("metrics", "min_dscr", "p50")),
    ("year1_revenue_lkr_p50", ("year1_unit_revenue_lkr", "p50")),
    ("year1_priority_export_mwh_p50", ("year1_priority_export_mwh", "p50")),
    ("year1_unit_export_mwh_p50", ("year1_unit_export_mwh", "p50")),
)


def grid_columns(readings: Sequence[str]) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """The grid table's columns for a run with these readings, in the readings' order.

    :data:`GRID_COLUMNS` is this for readings ``A`` and ``B``: one ``eligible_<name>``
    column per reading, where those two stand.
    """
    eligible = tuple(
        (f"eligible_{name}", ("eligible_by_reading", name)) for name in readings
    )
    fixed = [c for c in GRID_COLUMNS if c[1][0] != "eligible_by_reading"]
    at = next(i for i, c in enumerate(GRID_COLUMNS) if c[0] == "meets_4h_rule") + 1
    return (*fixed[:at], *eligible, *fixed[at:])


_SIZE_KEYS = ("pv_tables", "pv_ac_mw", "bess_power_mw")


def _size(entry: Mapping[str, Any]) -> tuple[Any, ...]:
    return tuple(entry[k] for k in _SIZE_KEYS)


def _dig(entry: Mapping[str, Any], path: tuple[str, ...]) -> Any:
    node: Any = entry
    for key in path:
        if not isinstance(node, Mapping) or key not in node:
            return None
        node = node[key]
    return node


def concise_project_summary(out: Mapping[str, Any]) -> Dict[str, Any]:
    """The project run as a concise record (``TEST-03``).

    Every grid point is one row of ``grid`` (size, fit, eligibility, base case and the
    distribution summaries). The full point, with the base case's engine fields and year-1
    energy, is kept in ``named_points`` only for the sizes the recommendation names.
    ``spec.result_sha256`` still identifies the full output the CLI printed. It hashes
    the spec too (``git_sha``, ``code_sha256``, input digests), so two runs on different
    commits never share it even when their results agree: to show that a re-run
    reproduced, compare ``points``, ``grid`` and ``recommendation`` (#1691 assurance A-6).
    """
    rec = out["recommendation"]
    named = set()
    for r in rec["by_reading"].values():
        for key in ("size", "revenue_max", "largest_bess"):
            if r.get(key):
                named.add(_size(r[key]))
        for key in ("any_pv", "land_max_pv"):
            if r.get(key):
                named.add(_size(r[key]["size"]))
    if rec["revenue_max_any_reading"]["size"]:
        named.add(_size(rec["revenue_max_any_reading"]["size"]))
    named_points = [p for p in out["points"] if _size(p) in named and p["evaluated"]]
    readings = list(rec["by_reading"])
    columns = grid_columns(readings)
    grid = {
        "columns": [c for c, _ in columns],
        "rows": [[_dig(p, path) for _, path in columns] for p in out["points"]],
    }
    sens: Dict[str, Any] = {}
    sens_cols = (
        "pv_tables",
        "pv_ac_mw",
        "bess_power_mw",
        *(f"eligible_{name}" for name in readings),
        "unit_pretax_npv_usd",
        "project_npv",
        "year1_unit_revenue_lkr",
    )
    for name, block in out["sensitivities"].items():
        if not isinstance(block, Mapping) or "rows" not in block:
            # None, or a block that is already compact (one_at_a_time, break_even).
            sens[name] = block
            continue
        sens[name] = {k: v for k, v in block.items() if k != "rows"}
        sens[name]["columns"] = list(sens_cols)
        sens[name]["rows"] = [
            [
                r["size"]["pv_tables"],
                r["size"]["pv_ac_mw"],
                r["size"]["bess_power_mw"],
                *(r["eligible_by_reading"][name] for name in readings),
                r["unit_pretax_npv_usd"],
                r["project_npv"],
                r["year1_unit_revenue_lkr"],
            ]
            for r in block["rows"]
        ]
    spec = dict(out["spec"])
    spec["summary"] = (
        "concise: one grid row per point; the full point only for the named sizes"
    )
    return {
        "config": out["config"],
        "statistics_convention": out["statistics_convention"],
        "spec": spec,
        "recommendation": rec,
        "grid": grid,
        "named_points": named_points,
        "sensitivities": sens,
    }


# ---------------------------------------------------------------------------
# Scenario-driven entry point (#1578 U3)
# ---------------------------------------------------------------------------

#: The block this analysis reads (:mod:`analytics.site_analysis_blocks`).
BLOCK = "solar_storage_sizing"
SUMMARY_SCHEMA = "dutchbay.solar_bess_sizing.v1"
#: Keys the method config's ``method`` mapping must hold: the Monte Carlo settings and the
#: objective are the method's; every site input is the scenario block's.
METHOD_KEYS = ("monte_carlo", "objective")
#: Block keys that pass into the project sizing config unchanged.
BLOCK_SIZING_KEYS = (
    "unit_config",
    "pricing_config",
    "regulatory_config",
    "unit_overrides",
    "grid",
    "readings",
    "uncertainty",
    "battery_health",
    "plant",
    "curtailment_scenario",
    "sensitivities",
    "recommendation",
)


def config_from_block(
    block: Mapping[str, Any],
    method: Mapping[str, Any],
    *,
    scenario_label: str,
    summary_json: Optional[str] = None,
) -> Dict[str, Any]:
    """Build the project sizing config from a scenario's block and the method config.

    The site inputs come from the block, the Monte Carlo settings and the objective from the
    method config, and ``scenario`` is the scenario's own path, so the run evaluates the
    scenario that declares the block.

    Raises:
        ValueError: The method config lacks a key it must hold.
    """
    missing = [k for k in METHOD_KEYS if k not in method]
    if missing:
        raise ValueError(f"method config lacks {missing}")
    cfg: Dict[str, Any] = {
        "schema_version": PROJECT_SIZING_SCHEMA,
        "scenario": scenario_label,
    }
    for key in BLOCK_SIZING_KEYS:
        cfg[key] = copy.deepcopy(block[key])
    for key in METHOD_KEYS:
        cfg[key] = copy.deepcopy(method[key])
    cfg["output"] = {"summary_json": summary_json}
    return cfg


def _digest(value: Any) -> str:
    text = json.dumps(value, sort_keys=True, default=str, allow_nan=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def run_solar_bess_sizing_for_scenario(
    scenario: Mapping[str, Any],
    method: Mapping[str, Any],
    *,
    scenario_label: str,
    script: Path,
    summary_json: Optional[str] = None,
) -> Dict[str, Any]:
    """Size the solar + BESS project for one scenario, or report it as not applicable.

    A scenario with a ``solar_storage_sizing`` block gets ``"status": "completed"`` and the
    summary :func:`run` returns for the config :func:`config_from_block` builds; one without
    it gets ``"status": "not_applicable"`` and the reason, never an error.
    ``scenario_label`` must be the scenario's path (repository relative or absolute): the
    sizing re-reads the scenario from it. ``summary_json`` writes the concise summary.

    Raises:
        ValueError: The block is present but malformed (every problem is listed), or the
            method config is incomplete.
    """
    from analytics.site_analysis_blocks import (
        SITE_ANALYSIS_NAMES,
        STATUS_NOT_APPLICABLE,
        resolve_site_analysis_block,
    )

    common: Dict[str, Any] = {
        "schema": SUMMARY_SCHEMA,
        "analysis": SITE_ANALYSIS_NAMES[BLOCK],
        "scenario": scenario_label,
    }
    block = resolve_site_analysis_block(scenario, BLOCK)
    if block is None:
        return {
            **common,
            "status": STATUS_NOT_APPLICABLE,
            "reason": f"the scenario declares no {BLOCK} block",
        }
    cfg = config_from_block(
        block, method, scenario_label=scenario_label, summary_json=summary_json
    )
    out = run(
        cfg,
        config_label=f"{scenario_label}#{BLOCK}",
        script=script,
        limitations=list(block["limitations"]),
    )
    return {
        **common,
        "status": "completed",
        "site": dict(block["site"]),
        "notes": block.get("notes"),
        "block_sha256": _digest(block),
        "method_sha256": _digest(method),
        **out,
    }


__all__ = [
    "BLOCK",
    "GRID_COLUMNS",
    "METHOD_KEYS",
    "SUMMARY_SCHEMA",
    "config_from_block",
    "grid_columns",
    "run_solar_bess_sizing_for_scenario",
    "REPO_ROOT",
    "code_sha256",
    "concise_project_summary",
    "inputs_digest",
    "loaded_repo_modules",
    "run",
]
