"""One runner for every site analysis, with the digests it ran with (#1824).

The site analyses (#1754) each have their own runner for any scenario. This module puts them
behind one call, :func:`run_site_analysis`, and records with each result the code and the
configuration it ran with, so a summary written earlier can be checked against the tree:

- ``code``: the SHA-256 of each source file of the analysis's own modules
  (:data:`SITE_ANALYSIS_RUNS`), and of their sorted listing (``tree``);
- ``config``: the SHA-256 of the scenario file, the method config the block names (or the
  analysis's default) and every repository file the block names.

A summary is stale when either digest no longer matches the tree (:func:`stale_reasons`).
The engine the analyses call is not in the code digest: every pull request that changes it
would otherwise stale every summary. The model version the summary was written under is
recorded beside the digests and shown with it.

Two analyses are cheap and read nothing outside the repository (FX and tenor screening,
equipment cost parity), so a report runs them live. The other two take minutes, and the wind
battery options read a public reference held outside the repository, so a report reads their
committed summary instead: ``docs/site_analyses/<scenario file stem>/<block>.json``, written by
``scripts/run_site_analysis_v14.py``. Nothing here names a site, a path inside a site's inputs
or a figure (``ARCH-01``): the scenario supplies all of them.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import math
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]

#: Where committed summaries live, one folder per scenario file stem.
SUMMARY_DIR = Path("docs") / "site_analyses"

#: How a report obtains an analysis's result.
MODE_LIVE = "live"
MODE_SUMMARY = "summary"

#: Provenance schema stamped on every result this module returns.
PROVENANCE_SCHEMA = "dutchbay.site_analysis_provenance.v1"

_REPO_FILE_SUFFIXES = (".yaml", ".yml", ".json", ".csv", ".geojson")


@dataclass(frozen=True)
class SiteAnalysisRun:
    """How one site analysis runs and what its code digest covers."""

    block: str
    mode: str
    default_method_config: str
    code_files: Tuple[str, ...]


#: Every site analysis, in the order of :data:`analytics.site_analysis_blocks.SITE_ANALYSIS_BLOCKS`.
SITE_ANALYSIS_RUNS: Dict[str, SiteAnalysisRun] = {
    "storage_options": SiteAnalysisRun(
        block="storage_options",
        mode=MODE_SUMMARY,
        default_method_config="conf/wind_bess_options.yaml",
        code_files=(
            "analytics/wind/wind_bess_options.py",
            "analytics/wind/wind_bess_options_runner.py",
        ),
    ),
    "solar_storage_sizing": SiteAnalysisRun(
        block="solar_storage_sizing",
        mode=MODE_SUMMARY,
        default_method_config="conf/solar_bess_sizing.yaml",
        code_files=(
            "solar_resource/pv_bess_sizing.py",
            "solar_resource/pv_bess_sizing_runner.py",
        ),
    ),
    "financing_screening": SiteAnalysisRun(
        block="financing_screening",
        mode=MODE_LIVE,
        default_method_config="conf/fx_tenor_screening.yaml",
        code_files=("analytics/finance/fx_tenor_screening.py",),
    ),
    "equipment_cost_parity": SiteAnalysisRun(
        block="equipment_cost_parity",
        mode=MODE_LIVE,
        default_method_config="conf/equipment_parity.yaml",
        code_files=("analytics/wind/equipment_parity.py",),
    ),
}


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _listing_digest(files: Mapping[str, str]) -> str:
    listing = "".join(f"{files[r]}  {r}\n" for r in sorted(files))
    return hashlib.sha256(listing.encode("utf-8")).hexdigest()


def _repo_rel(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _named_repo_files(value: Any, root: Path) -> List[str]:
    """Every string in ``value`` that names an existing input file in the repository."""
    out: List[str] = []
    if isinstance(value, Mapping):
        for item in value.values():
            out.extend(_named_repo_files(item, root))
    elif isinstance(value, (list, tuple)):
        for item in value:
            out.extend(_named_repo_files(item, root))
    elif isinstance(value, str) and value.endswith(_REPO_FILE_SUFFIXES):
        rel = Path(value)
        if not rel.is_absolute() and ".." not in rel.parts and (root / rel).is_file():
            out.append(rel.as_posix())
    return out


def method_config_path(block: str, block_value: Mapping[str, Any]) -> str:
    """The method config the block names, or the analysis's default."""
    named = block_value.get("method_config")
    if isinstance(named, str) and named:
        return named
    return SITE_ANALYSIS_RUNS[block].default_method_config


def provenance(
    block: str,
    block_value: Mapping[str, Any],
    scenario_path: Path,
    *,
    root: Path = REPO_ROOT,
) -> Dict[str, Any]:
    """Return the code and config digests an analysis of ``block`` runs with now."""
    spec = SITE_ANALYSIS_RUNS[block]
    code = {rel: _sha256_file(root / rel) for rel in spec.code_files}
    config_rels = {
        _repo_rel(scenario_path, root),
        method_config_path(block, block_value),
        *_named_repo_files(block_value, root),
    }
    config = {rel: _sha256_file(root / rel) for rel in sorted(config_rels)}
    return {
        "schema": PROVENANCE_SCHEMA,
        "block": block,
        "code": {"tree": _listing_digest(code), "files": code},
        "config": {"tree": _listing_digest(config), "files": config},
        "model_version": (root / "VERSION").read_text(encoding="utf-8").strip(),
    }


def stale_reasons(recorded: Any, current: Mapping[str, Any]) -> List[str]:
    """Why a recorded provenance no longer matches ``current``; empty when it does.

    Each reason names the file that changed, appeared or disappeared, so a reader can see
    what to re-run for.
    """
    if not isinstance(recorded, Mapping) or recorded.get("schema") != PROVENANCE_SCHEMA:
        return ["the summary records no provenance this report can check"]
    reasons: List[str] = []
    for part in ("code", "config"):
        was = recorded.get(part)
        now = current[part]
        if not isinstance(was, Mapping) or not isinstance(was.get("files"), Mapping):
            reasons.append(f"the summary records no {part} digest")
            continue
        if was.get("tree") == now["tree"] and dict(was["files"]) == now["files"]:
            continue
        before: Mapping[str, Any] = was["files"]
        for rel in sorted(set(before) | set(now["files"])):
            if rel not in now["files"]:
                reasons.append(f"{part} file no longer read: {rel}")
            elif rel not in before:
                reasons.append(f"{part} file not in the summary: {rel}")
            elif before[rel] != now["files"][rel]:
                reasons.append(f"{part} file changed since the summary: {rel}")
        if not reasons:
            reasons.append(f"the summary's {part} tree digest does not match its files")
    return reasons


def summary_path(scenario_path: Path, block: str, *, root: Path = REPO_ROOT) -> Path:
    """Where the committed summary of ``block`` for ``scenario_path`` lives."""
    return root / SUMMARY_DIR / Path(scenario_path).stem / f"{block}.json"


def _load_method(rel: str, root: Path) -> Dict[str, Any]:
    raw = yaml.safe_load((root / rel).read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not isinstance(raw.get("method"), dict):
        raise ValueError(f"{rel} must be a mapping with a 'method' mapping")
    return raw


def _runner(block: str) -> Callable[..., Dict[str, Any]]:
    # Imported on use, so a report that runs one analysis loads only that analysis's stack.
    if block == "storage_options":
        from analytics.wind.wind_bess_options_runner import (
            run_wind_bess_options_for_scenario,
        )

        return run_wind_bess_options_for_scenario
    if block == "solar_storage_sizing":
        from solar_resource.pv_bess_sizing_runner import (
            run_solar_bess_sizing_for_scenario,
        )

        def run_sizing(
            scenario: Mapping[str, Any],
            method: Mapping[str, Any],
            *,
            scenario_label: str,
            root: Path,
        ) -> Dict[str, Any]:
            return run_solar_bess_sizing_for_scenario(
                scenario,
                method,
                scenario_label=scenario_label,
                script=root / "scripts" / "run_site_analysis_v14.py",
            )

        return run_sizing
    if block == "financing_screening":
        from analytics.finance.fx_tenor_screening import (
            run_fx_tenor_screening_for_scenario,
        )

        return run_fx_tenor_screening_for_scenario
    if block == "equipment_cost_parity":
        from analytics.wind.equipment_parity import run_equipment_parity_for_scenario

        def run_parity(
            scenario: Mapping[str, Any],
            method: Mapping[str, Any],
            *,
            scenario_label: str,
            root: Path,
        ) -> Dict[str, Any]:
            return run_equipment_parity_for_scenario(
                scenario, method, root, scenario_label=scenario_label
            )

        return run_parity
    raise KeyError(f"unknown site analysis block {block!r}")


def run_site_analysis(
    block: str,
    scenario: Mapping[str, Any],
    scenario_path: Path,
    *,
    root: Path = REPO_ROOT,
) -> Dict[str, Any]:
    """Run one site analysis for a scenario and stamp the result with its provenance.

    ``scenario_path`` is the scenario's file (absolute, or relative to ``root``); it labels
    the result and enters the config digest. A scenario without the block returns the
    runner's own ``not_applicable`` result, unstamped.

    Raises:
        KeyError: ``block`` is not a site analysis.
        ValueError: The block or the method config is malformed (the runner's message).
    """
    from analytics.site_analysis_blocks import (
        STATUS_NOT_APPLICABLE,
        resolve_site_analysis_block,
    )

    if block not in SITE_ANALYSIS_RUNS:
        raise KeyError(f"unknown site analysis block {block!r}")
    path = Path(scenario_path)
    if not path.is_absolute():
        path = root / path
    label = _repo_rel(path, root)
    block_value = resolve_site_analysis_block(scenario, block)
    if block_value is None:
        return {
            "status": STATUS_NOT_APPLICABLE,
            "reason": f"the scenario declares no {block} block",
        }
    raw = _load_method(method_config_path(block, block_value), root)
    run = _runner(block)
    if block in ("solar_storage_sizing", "equipment_cost_parity"):
        result = run(scenario, raw["method"], scenario_label=label, root=root)
    else:
        result = run(scenario, raw["method"], scenario_label=label)
    result = dict(result)
    result["provenance"] = provenance(block, block_value, path, root=root)
    return result


def write_summary(result: Mapping[str, Any], target: Path) -> None:
    """Write a stamped result as a committed summary (sorted keys, no NaN)."""
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(json_ready(result), indent=2, sort_keys=True, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )


def json_ready(value: Any) -> Any:
    """Strict JSON: NaN and infinities become ``None``, numpy scalars become Python, dates
    become ISO text and exact decimals keep their full text."""
    if isinstance(value, Mapping):
        return {str(k): json_ready(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(v) for v in value]
    if isinstance(value, bool) or value is None or isinstance(value, (str, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, (_dt.date, _dt.datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    item = getattr(value, "item", None)
    if callable(item):
        return json_ready(item())
    raise TypeError(f"cannot write {type(value).__name__} to a summary")


def load_summary(path: Path) -> Optional[Dict[str, Any]]:
    """Return a committed summary, or ``None`` when there is none."""
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must hold a JSON object")
    return data


__all__ = [
    "MODE_LIVE",
    "MODE_SUMMARY",
    "PROVENANCE_SCHEMA",
    "SITE_ANALYSIS_RUNS",
    "SUMMARY_DIR",
    "SiteAnalysisRun",
    "json_ready",
    "load_summary",
    "method_config_path",
    "provenance",
    "run_site_analysis",
    "stale_reasons",
    "summary_path",
    "write_summary",
]
