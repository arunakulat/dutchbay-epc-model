"""Config-first output-path resolution for the v14 entrypoints (#735).

The v14 CLIs each build their artifact directory from a per-config Hydra default, so the default
output roots are scattered (``_out/run_full_pipeline_v14``, ``_out/monte_carlo``,
``_out/sensitivity``, …) with no shared resolver. This module is the single home for those
default roots plus one resolver so a run's artifacts can optionally be grouped under a
reproducible, run-scoped subdirectory.

Slice 1 (#735): the constants + :func:`resolve_output_dir` (with a unit-tested run-scoping mode),
consumed by ``run_full_pipeline_v14.py`` at its default (``run_scoped=False`` → the root
unchanged, so committed runs write to the same paths — byte-identical).

Slice 2 (#735): the remaining artifact/report/export writers route their DEFAULT paths through
this resolver too, so every artifact of a run co-scopes. The single-scenario pipeline's four
report/workbook emitters derive their defaults from the resolver; the Monte-Carlo and sensitivity
Hydra CLIs, and the batch scenario-analytics entrypoint (whose engine writes a sibling
``*_charts/`` directory), route their output directories through it as well. Opt-in run-scoping is
default-off everywhere, so committed runs stay byte-identical.

GWTF: CCCDIR (one source for the default roots; no hardcoded literals scattered across
entrypoints). The run-scope id reuses :mod:`analytics.run_manifest` (engine version + git SHA), so
a run-scoped directory carries the same reproducibility provenance the manifest stamps (MRM-02).
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from analytics.run_manifest import engine_version, git_sha

__all__ = [
    "DEFAULT_PIPELINE_OUTPUT_ROOT",
    "DEFAULT_MC_OUTPUT_ROOT",
    "DEFAULT_SENSITIVITY_OUTPUT_ROOT",
    "default_run_id",
    "resolve_output_dir",
]

#: Default artifact root for the single-scenario finance pipeline (``run_full_pipeline_v14.py``).
#: Slice 1 single-sourced this one; slice 2 (#735) converges the Monte-Carlo and sensitivity roots
#: onto this module too and routes their entrypoints through :func:`resolve_output_dir`.
DEFAULT_PIPELINE_OUTPUT_ROOT = "_out/run_full_pipeline_v14"

#: Default artifact root for the Monte-Carlo Hydra CLI
#: (``analytics/cli/cli_monte_carlo_hydra.py``). Single-sourced here (CCCDIR) so the literal no
#: longer lives only in that CLI's ``cfg.get("output_dir", ...)`` default.
DEFAULT_MC_OUTPUT_ROOT = "_out/monte_carlo"

#: Default artifact root for the sensitivity Hydra CLI
#: (``analytics/cli/cli_sensitivity_hydra.py``). Single-sourced here (CCCDIR) so the literal no
#: longer lives only in that CLI's ``cfg.get("output_dir", ...)`` default.
DEFAULT_SENSITIVITY_OUTPUT_ROOT = "_out/sensitivity"


def default_run_id() -> str:
    """A reproducible, auditable run-scope id: ``v<engine_version>_<git_sha12>`` (MRM-02).

    Reuses :func:`analytics.run_manifest.engine_version` and :func:`analytics.run_manifest.git_sha`
    so a run-scoped output directory carries the same provenance the run manifest stamps. Falls
    back to ``unknown`` for the SHA when git is unavailable (same contract as ``git_sha``).
    """
    return f"v{engine_version()}_{git_sha()[:12]}"


def resolve_output_dir(
    output_root: str | Path,
    *,
    run_scoped: bool = False,
    run_id: Optional[str] = None,
) -> Path:
    """Resolve the artifact directory for a run (config-first, #735).

    Args:
        output_root: The configured artifact root (e.g. ``export_dir``).
        run_scoped: When ``False`` (default) the root is returned unchanged, so existing runs write
            to exactly the same paths (byte-identical). When ``True`` the artifacts are grouped
            under a per-run subdirectory so concurrent/successive runs do not overwrite each other.
        run_id: The run-scope subdirectory name; defaults to :func:`default_run_id` when omitted and
            ``run_scoped`` is set. Ignored when ``run_scoped`` is ``False``.

    Returns:
        The resolved directory as a :class:`~pathlib.Path` (not created here — the caller mkdirs).
    """
    root = Path(output_root)
    if not run_scoped:
        return root
    return root / (run_id if run_id is not None else default_run_id())
