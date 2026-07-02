"""AEP source-provenance guard for the financed run (#18 — lender-grade).

The bankable AEP that backs a financed run derives from a turbine power curve, and a
lender requires that curve to come from an **approved, traceable source** — a certified
OEM curve or a vetted community reference — never an un-vetted or placeholder curve when
a certified one exists. ``analytics.loader.aep_loader`` already encodes that control
(``validate_config_aep_provenance`` + the ``APPROVED_SOURCES`` manifest, IEC-standard
tracking, placeholder detection), but it was **enforced only in tests** — no live
entrypoint called it, so a real run trusted whatever ``resource.power_curve.source_id``
the scenario declared. This module is the thin LIVE wrapper that folds that dormant
control into the financed path.

It mirrors :mod:`analytics.aep_reconciliation` deliberately:

- **Config-first policy** (CESSPIT / CCCDIR — never a Python literal). Resolution order::

      scenario ``aep_provenance.{enforce,require_source_id,allow_placeholder}``  →  else
      ``config/defaults.yaml`` ``defaults.aep_provenance.*``

- **Runs at AUTHORED-scenario LOAD time** (``analytics.scenario_loader``) and on authored
  configs **at the API boundary** (``api.pipeline_api``), NOT on every derived run — so
  deliberate sensitivity / Monte-Carlo perturbations (in-memory dicts, never re-loaded)
  are unaffected.

- **Pure detector**: it raises or it is a no-op; it changes no computed number, so it
  preserves byte-identical economics.

Graceful by design: a scenario that declares no ``resource.power_curve.source_id`` (a
simplified base case, a test fixture, an inline API config) is **skipped**, not rejected —
unless the policy sets ``require_source_id``. When a ``source_id`` IS present the dormant
guard fires for real: an unapproved source raises, and a placeholder source raises while a
certified OEM curve is available (the #18 lender control), unless ``allow_placeholder``.

Why a separate module and not folded into ``aep_reconciliation``: provenance (where did the
curve come from?) and reconciliation (does capacity×CF match the bankable AEP?) are
orthogonal controls with independent config knobs; keeping them apart keeps each guard's
contract and failure message single-purpose (CCCDIR).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

from analytics.loader.aep_loader import (
    APPROVED_SOURCES,
    register_approved_source,
    validate_config_aep_provenance,
)

logger = logging.getLogger(__name__)

_DEFAULTS_PATH = Path(__file__).resolve().parents[1] / "config" / "defaults.yaml"


class AepProvenanceError(ValueError):
    """Raised when a financed scenario's AEP source provenance is not lender-grade."""


@dataclass(frozen=True)
class ProvenancePolicy:
    """Resolved provenance-enforcement policy for a scenario.

    Attributes:
        enforce: Run the provenance guard at all (default True — it is a no-op when the
            scenario declares no source, so disabling is rarely needed).
        require_source_id: When True, a scenario that declares no
            ``resource.power_curve.source_id`` is rejected rather than skipped.
        allow_placeholder: When True, a placeholder / un-certified source is permitted even
            when a certified OEM curve exists (escape hatch for early-stage scenarios).
    """

    enforce: bool
    require_source_id: bool
    allow_placeholder: bool


@lru_cache(maxsize=1)
def default_provenance_policy() -> ProvenancePolicy:
    """The single config-sourced provenance policy (``config/defaults.yaml``)."""
    import yaml  # project core dep

    data = yaml.safe_load(_DEFAULTS_PATH.read_text())
    try:
        block = data["defaults"]["aep_provenance"]
        return ProvenancePolicy(
            enforce=bool(block["enforce"]),
            require_source_id=bool(block["require_source_id"]),
            allow_placeholder=bool(block["allow_placeholder"]),
        )
    except (KeyError, TypeError) as exc:
        raise ValueError(
            "config/defaults.yaml missing defaults.aep_provenance "
            "{enforce, require_source_id, allow_placeholder} "
            f"({_DEFAULTS_PATH})"
        ) from exc


def _resolve_bool(block: Mapping[str, Any], key: str, fallback: bool) -> bool:
    """Read a strictly-boolean override from a scenario block, else the fallback."""
    if key not in block:
        return fallback
    value = block[key]
    if not isinstance(value, bool):
        raise ValueError(f"aep_provenance.{key} must be a boolean; got {value!r}")
    return value


def resolve_provenance_policy(config: Mapping[str, Any]) -> ProvenancePolicy:
    """Resolve the provenance policy for a scenario.

    Prefers the scenario's explicit ``aep_provenance.{enforce,require_source_id,
    allow_placeholder}`` keys (each individually); falls back per-key to the single
    config-sourced default. Raises if an explicit value is not a boolean.
    """
    default = default_provenance_policy()
    block = config.get("aep_provenance")
    if not isinstance(block, Mapping):
        return default
    return ProvenancePolicy(
        enforce=_resolve_bool(block, "enforce", default.enforce),
        require_source_id=_resolve_bool(
            block, "require_source_id", default.require_source_id
        ),
        allow_placeholder=_resolve_bool(
            block, "allow_placeholder", default.allow_placeholder
        ),
    )


def _declared_source_id(config: Mapping[str, Any]) -> Any:
    """Return the raw ``resource.power_curve.source_id`` (or None if not declared).

    Returns the value verbatim — the caller validates it is a usable string — so a
    malformed non-scalar source_id (a list/dict) becomes a clean guard error rather
    than an unhashable-type ``TypeError`` inside the manifest membership test.
    """
    resource = config.get("resource")
    if not isinstance(resource, Mapping):
        return None
    power_curve = resource.get("power_curve")
    if not isinstance(power_curve, Mapping):
        return None
    source_id = power_curve.get("source_id")
    if source_id is None or source_id == "":
        return None
    return source_id


def _declared_approved_sources_yaml(config: Mapping[str, Any]) -> Any:
    """Return the raw ``resource.power_curve.approved_sources_yaml`` (or None).

    Returns the value verbatim so a malformed non-string declaration becomes a clean
    guard error in :func:`register_scenario_approved_sources` rather than a downstream
    ``TypeError`` — mirroring :func:`_declared_source_id`.
    """
    resource = config.get("resource")
    if not isinstance(resource, Mapping):
        return None
    power_curve = resource.get("power_curve")
    if not isinstance(power_curve, Mapping):
        return None
    value = power_curve.get("approved_sources_yaml")
    if value is None or value == "":
        return None
    return value


def _resolve_approved_sources_path(raw_path: str, config_path: str | None) -> Path:
    """Resolve the approved-sources YAML path relative to the SCENARIO file.

    An absolute ``raw_path`` is used as-is. A relative ``raw_path`` resolves against the
    directory of the scenario file (``config_path``) so a project can ship its
    approved-sources manifest alongside its scenario (e.g.
    ``resource.power_curve.approved_sources_yaml: approved_sources.yaml``). When
    ``config_path`` is absent or not a real on-disk file (an INLINE config submitted over
    the API / gateway, where ``config_path`` is ``"<inline>"`` or None), a relative path
    resolves against the current working directory as a documented fallback — committed
    scenarios never declare this key, so this path is inert for byte-identical economics.
    """
    candidate = Path(raw_path)
    if candidate.is_absolute():
        return candidate
    if config_path:
        base = Path(config_path)
        if base.is_file():
            return base.parent / candidate
    return candidate


def register_scenario_approved_sources(
    config: dict[str, Any], config_path: str | None = None
) -> list[str]:
    """Register a scenario's per-project approved AEP sources before the provenance guard.

    Config-first provenance widening (ARCH-01 / CESSPIT): when a scenario declares the
    optional ``resource.power_curve.approved_sources_yaml``, load that YAML manifest and
    register each ``{source_id: {type, description, iec_standard, ...}}`` entry into the
    process-global ``APPROVED_SOURCES`` — so a project can vet + admit its own turbine /
    source provenance from config instead of editing the code registry. Each entry is
    schema-validated by ``aep_loader.register_approved_source`` (required
    type/description/known IEC standard) and, with the default ``overwrite=False``, cannot
    silently replace a built-in entry (a duplicate ``source_id`` with DIFFERING metadata
    raises) — so config-driven widening admits new sources but cannot weaken the placeholder
    / curve-key cross-check controls on the existing ones. Re-registering an EXACT-duplicate
    entry (identical metadata) is idempotent — a no-op — so this seam is safe to run twice
    on the same config (the path-based API request registers once at load and once at the
    api boundary).

    Runs at AUTHORED-scenario LOAD time and at the inline-config boundaries, immediately
    BEFORE :func:`enforce_aep_provenance`, so the widened manifest is in force for every
    live provenance guard (``enforce_aep_provenance``, ``validate_curve_selection``,
    ``validate_config_aep_provenance``). No-op when the key is absent (the common case —
    committed scenarios do not declare it, preserving byte-identical economics).

    Args:
        config: Parsed scenario config mapping.
        config_path: The scenario file path, used to resolve a relative YAML path and to
            annotate errors. ``"<inline>"`` / None for inline configs.

    Returns:
        The list of ``source_id`` values registered (empty when the key is absent).

    Raises:
        AepProvenanceError: If the key is declared but is not a string, or the resolved
            YAML is missing / unreadable / malformed, or an entry fails schema validation
            (CESSPIT — a declared manifest must load; no silent skip).
    """
    where = f" in '{config_path}'" if config_path else ""
    raw_path = _declared_approved_sources_yaml(config)
    if raw_path is None:
        return []

    if not isinstance(raw_path, str):
        raise AepProvenanceError(
            "resource.power_curve.approved_sources_yaml must be a string path"
            + where
            + f"; got {type(raw_path).__name__}."
        )

    resolved = _resolve_approved_sources_path(raw_path, config_path)
    if not resolved.is_file():
        raise AepProvenanceError(
            f"resource.power_curve.approved_sources_yaml {raw_path!r} is declared"
            + where
            + f" but does not resolve to a readable file ({resolved}). A declared "
            "approved-sources manifest must load — refusing to silently skip it (CESSPIT)."
        )

    import yaml  # project core dep

    try:
        data = yaml.safe_load(resolved.read_text()) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise AepProvenanceError(
            f"resource.power_curve.approved_sources_yaml {raw_path!r} could not be "
            f"read/parsed as YAML{where}: {exc}"
        ) from exc
    if not isinstance(data, dict):
        raise AepProvenanceError(
            f"resource.power_curve.approved_sources_yaml {raw_path!r} must be a mapping "
            f"of source_id -> metadata{where}; got {type(data).__name__}."
        )

    registered: list[str] = []
    for raw_id, meta in data.items():
        source_id = str(raw_id)
        # Idempotent re-registration: this seam can run twice for a path-based API request
        # (once inside load_scenario_config, once at the api.pipeline_api boundary on the
        # same cfg). An EXACT-duplicate entry (identical metadata to what is already in the
        # manifest) is a no-op, so the second pass does not spuriously raise. A DIFFERING
        # entry for an existing source_id still raises via register_approved_source's
        # duplicate refusal below — a project cannot silently overwrite a built-in control.
        existing = APPROVED_SOURCES.get(source_id)
        if (
            existing is not None
            and isinstance(meta, Mapping)
            and dict(meta) == existing
        ):
            registered.append(source_id)
            continue
        try:
            register_approved_source(source_id, meta)
        except (TypeError, ValueError) as exc:
            # ValueError covers every per-entry schema failure (missing field, unknown IEC
            # standard, differing-duplicate id); TypeError covers a non-mapping meta value.
            # Re-raise as this module's error type with the offending config for a single,
            # actionable message.
            raise AepProvenanceError(
                f"resource.power_curve.approved_sources_yaml {raw_path!r} could not be "
                f"loaded{where}: {exc}"
            ) from exc
        registered.append(source_id)

    logger.debug(
        "AEP provenance: registered %d project source(s) from %s%s: %s",
        len(registered),
        raw_path,
        where,
        registered,
    )
    return registered


def enforce_aep_provenance(
    config: dict[str, Any], config_path: str | None = None
) -> None:
    """Fail loud if a financed scenario's AEP source is not lender-grade.

    Folds the dormant ``aep_loader.validate_config_aep_provenance`` control into the live
    path. No-op when provenance enforcement is disabled by policy, or when the scenario
    declares no ``resource.power_curve.source_id`` and the policy does not require one.
    Otherwise asserts the declared source is in the approved manifest and (unless
    ``allow_placeholder``) is not a placeholder while a certified OEM curve exists.

    Raises:
        AepProvenanceError: If a required source is missing, unapproved, or a refused
            placeholder. (Wraps the loader's ``KeyError`` / ``ValueError`` with the
            offending ``config_path`` for a single, actionable failure.)
    """
    policy = resolve_provenance_policy(config)
    where = f" in '{config_path}'" if config_path else ""

    if not policy.enforce:
        logger.debug("AEP provenance enforcement disabled by policy%s", where)
        return

    source_id = _declared_source_id(config)
    if source_id is None:
        if policy.require_source_id:
            raise AepProvenanceError(
                "Scenario declares no resource.power_curve.source_id"
                + where
                + ", but aep_provenance.require_source_id is set — a lender-grade run "
                "must name an approved AEP source (see analytics.loader.aep_loader."
                "APPROVED_SOURCES)."
            )
        logger.debug(
            "AEP provenance: no resource.power_curve.source_id%s; skipped (not required).",
            where,
        )
        return

    if not isinstance(source_id, str):
        # A non-scalar source_id would crash the manifest membership test with an
        # unhashable-type TypeError that escapes the except below; reject it cleanly.
        raise AepProvenanceError(
            "resource.power_curve.source_id must be a string"
            + where
            + f"; got {type(source_id).__name__} — a malformed AEP source cannot be "
            "provenance-checked."
        )

    try:
        block = validate_config_aep_provenance(
            config, allow_placeholder=policy.allow_placeholder
        )
    except (KeyError, ValueError) as exc:
        # KeyError/ValueError carry the manifest/placeholder detail; re-raise as the
        # module's own error type with the offending config for an actionable message.
        raise AepProvenanceError(
            f"AEP source provenance is not lender-grade{where}: {exc}"
        ) from exc

    logger.debug(
        "AEP provenance OK%s: source=%s type=%s placeholder=%s",
        where,
        block.get("aep_source_id"),
        block.get("source_type"),
        block.get("is_placeholder"),
    )


__all__ = [
    "AepProvenanceError",
    "ProvenancePolicy",
    "default_provenance_policy",
    "resolve_provenance_policy",
    "register_scenario_approved_sources",
    "enforce_aep_provenance",
]
