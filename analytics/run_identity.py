"""One run, one identity, on every output surface (#1815).

A pipeline run stamps its manifest once (``analytics.run_manifest.build_run_manifest``).
Three consumer surfaces carry it:

* the API response (``api.pipeline_api.RunPipelineResponse.manifest``);
* the report context (``app.reports.report_model.ReportContext.manifest``), which the HTML
  report and the DBPL print render;
* the executive workbook's "Manifest" sheet (``analytics.executive_workbook``).

:func:`require_same_run_identity` refuses outputs that do not carry the same identity, and
names every field that differs with each surface's value.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

#: The run-identity fields every output surface must carry with equal values.
#: ``generated_at`` is the run's own stamp, so it is equal across surfaces built from one
#: run, not across runs. ``validation_mode`` and ``seed`` may be null.
RUN_IDENTITY_FIELDS: tuple[str, ...] = (
    "config_sha256",
    "engine_version",
    "git_sha",
    "generated_at",
    "manifest_schema_version",
    "validation_mode",
    "seed",
)
_REQUIRED_FIELDS: tuple[str, ...] = RUN_IDENTITY_FIELDS[:5]


def run_identity(manifest: Optional[Mapping[str, Any]], surface: str) -> Dict[str, Any]:
    """Return the run-identity fields of one surface's manifest.

    Raises:
        ValueError: The surface carries no manifest, or omits one of
            ``config_sha256``, ``engine_version``, ``git_sha``, ``generated_at`` and
            ``manifest_schema_version``.
    """
    if not isinstance(manifest, Mapping):
        raise ValueError(f"{surface}: no run manifest")
    missing = [key for key in _REQUIRED_FIELDS if not manifest.get(key)]
    if missing:
        raise ValueError(f"{surface}: run manifest lacks {', '.join(missing)}")
    return {key: manifest.get(key) for key in RUN_IDENTITY_FIELDS}


def require_same_run_identity(
    manifests: Mapping[str, Optional[Mapping[str, Any]]],
) -> Dict[str, Any]:
    """Refuse outputs that do not carry one and the same run identity.

    Args:
        manifests: Each surface's manifest, keyed by surface name.

    Returns:
        The shared identity.

    Raises:
        ValueError: Fewer than two surfaces, a surface without its identity, or two
            surfaces that disagree. The message names every disagreeing field.
    """
    if len(manifests) < 2:
        raise ValueError("a run-identity comparison needs at least two surfaces")
    identities = {name: run_identity(m, name) for name, m in manifests.items()}
    names = list(identities)
    reference = identities[names[0]]
    problems = []
    for key in RUN_IDENTITY_FIELDS:
        values = {name: identities[name][key] for name in names}
        if any(value != reference[key] for value in values.values()):
            problems.append(
                f"{key}: "
                + ", ".join(f"{name}={value!r}" for name, value in values.items())
            )
    if problems:
        raise ValueError(
            "the outputs do not carry one run identity: " + "; ".join(problems)
        )
    return reference


__all__ = ["RUN_IDENTITY_FIELDS", "require_same_run_identity", "run_identity"]
