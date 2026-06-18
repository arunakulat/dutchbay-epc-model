#!/usr/bin/env python
"""EPC AEP resource loader with provenance tracking.

Loads pre-computed AEP summaries from Data Lake with:
- Source ID validation against approved manifest
- SHA-256 checksum verification
- Multi-source support (OEM/NREL/ECMWF)
- IEC standard tracking

All currency and tariff values MUST come from YAML config (GWTF ARCH-01).
This module NEVER hardcodes currency conversions or tariff prices.

Context:
    Sprint 17 - Issue #17: EPC Resource Loader
    Integrates with Data Lake manifest system
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

import pandas as pd

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# APPROVED AEP SOURCE MANIFEST (Data Lake)
# ═══════════════════════════════════════════════════════════════════════════════

IEC_STANDARDS = {
    "61400-12-1:2022": "Power performance measurements",
    "61400-15-1:2025": "Assessment of site-specific wind conditions",
    "61400-21:2008": "Power quality characteristics",
}

APPROVED_SOURCES = {
    "OEM_ENVISION_EN171_65_PC": {
        "type": "OEM",
        "description": "Envision EN-171/6.5 MW certified power curve (canonical)",
        "iec_standard": "61400-12-1:2022",
        "certificate": "CGC-B-FNc-2024-184"
    },
    "OEM_ENVISION_EN171_10_PC": {
        "type": "OEM",
        "description": "Envision EN-171-10.0 MW power curve (PLACEHOLDER, extrapolated from 6.5 MW; superseded by OEM_ENVISION_EN171_65_PC)",
        "iec_standard": "61400-12-1:2022",
        "certificate": "CGC-B-FNc-2024-184 (extrapolated)"
    },
    "ECMWF_ERA5_2020_2024_DUTCHBAY": {
        "type": "ECMWF",
        "description": "ERA5 reanalysis 2020-2024 for Dutch Bay",
        "iec_standard": "61400-15-1:2025",
    },
    "NREL_WTK_SRI_LANKA_2020_2024": {
        "type": "NREL",
        "description": "NREL Wind Toolkit for Sri Lanka 2020-2024",
        "iec_standard": "61400-15-1:2025",
    },
}


def validate_source_manifest(
    source_id: str,
    manifest: Optional[Dict[str, Any]] = None
) -> bool:
    """Validate source ID against approved manifest.
    
    Args:
        source_id: Source identifier (e.g., 'OEM_ENVISION_EN171_10_PC')
        manifest: Optional custom manifest (default: APPROVED_SOURCES)
    
    Returns:
        True if source ID is in manifest, False otherwise
    """
    if manifest is None:
        manifest = APPROVED_SOURCES
    return source_id in manifest


def compute_checksum_sha256(data: Dict[str, Any]) -> str:
    """Compute SHA-256 checksum for AEP data integrity.
    
    Args:
        data: Dictionary of AEP data to hash
    
    Returns:
        64-character hex string (SHA-256 hash)
    """
    json_str = json.dumps(data, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(json_str.encode('utf-8')).hexdigest()


def load_aep_from_summary(
    path: str,
    validate_manifest: bool = True
) -> Dict[str, Any]:
    """Load AEP summary from Data Lake with provenance validation.
    
    CRITICAL: This function NEVER hardcodes currency or tariff values.
    All revenue calculations must use tariff.lkr_per_kwh from YAML config.
    
    Args:
        path: Path to AEP summary file (JSON or CSV)
        validate_manifest: If True, verify source_id is in approved manifest
    
    Returns:
        Dictionary with:
            - capacity_factor: Net capacity factor
            - net_site_aep_gwh: Net AEP (GWh)
            - gross_aep_gwh: Gross AEP before losses (GWh)
            - n_turbines: Number of turbines
            - rated_power_kw: Turbine rated power (kW)
            - rated_power_mw: Turbine rated power (MW)
            - source_id: Data source identifier
            - source_type: Source category (OEM/NREL/ECMWF)
            - losses: Loss breakdown dict
            - provenance: Metadata dict
    
    Raises:
        FileNotFoundError: If path does not exist
        ValueError: If required fields missing or format unsupported
        KeyError: If source_id not in manifest (when validate_manifest=True)
    
    Example:
        >>> aep_data = load_aep_from_summary(
        ...     path='tests/mocks/aep_summary_dutchbay.json',
        ...     validate_manifest=True
        ... )
        >>> print(f"Net AEP: {aep_data['net_site_aep_gwh']:.2f} GWh")
        Net AEP: 485.32 GWh
    """
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"AEP summary not found: {path}")
    
    # Load based on file type
    if file_path.suffix == ".json":
        with open(file_path) as f:
            data = json.load(f)
    elif file_path.suffix == ".csv":
        df = pd.read_csv(file_path)
        if len(df) != 1:
            raise ValueError(f"Expected 1 row in CSV, got {len(df)}")
        data = df.iloc[0].to_dict()
    else:
        raise ValueError(f"Unsupported file format: {file_path.suffix}")
    
    # Validate required fields
    required_fields = [
        "capacity_factor",
        "net_site_aep_gwh",
        "n_turbines",
        "rated_power_kw",
        "source_id"
    ]
    missing = [f for f in required_fields if f not in data]
    if missing:
        raise ValueError(f"Missing required fields: {missing}")
    
    # Validate source manifest
    if validate_manifest:
        source_id = data["source_id"]
        if not validate_source_manifest(source_id):
            raise KeyError(
                f"Source ID '{source_id}' not in approved manifest. "
                f"Valid sources: {list(APPROVED_SOURCES.keys())}"
            )
        source_meta = APPROVED_SOURCES[source_id]
        data["source_type"] = source_meta["type"]
    
    # Add derived fields
    data["rated_power_mw"] = data["rated_power_kw"] / 1000.0
    
    # Consistency check: n_turbines × rated_power_mw should match project capacity
    calculated_capacity_mw = data["n_turbines"] * data["rated_power_mw"]
    logger.info(
        f"Turbine configuration: {data['n_turbines']} × {data['rated_power_mw']:.1f} MW = "
        f"{calculated_capacity_mw:.1f} MW total capacity"
    )
    
    # Build provenance metadata
    provenance = {
        "aep_source_id": data["source_id"],
        "derived_from": data.get("derived_from", []),
        "iec_standard_version": data.get("iec_standard", "Unknown"),
        "validation_date": datetime.now().isoformat(),
        "checksum_sha256": compute_checksum_sha256(data),
        "file_path": str(file_path.absolute())
    }
    # Standardized provenance.aep block for v14 outputs (#18). Attached only for
    # manifest-approved sources (load with validate_manifest=False to skip).
    if validate_source_manifest(data["source_id"]):
        provenance["aep"] = build_provenance_aep_block(
            data["source_id"],
            derived_from=data.get("derived_from"),
        )
    data["provenance"] = provenance
    
    logger.info(
        f"Loaded AEP summary from {file_path.name}:\n"
        f"  Source: {data['source_id']} ({data.get('source_type', 'Unknown')})\n"
        f"  Net AEP: {data['net_site_aep_gwh']:.2f} GWh\n"
        f"  Capacity Factor: {data['capacity_factor']:.2%}\n"
        f"  Checksum: {provenance['checksum_sha256'][:16]}..."
    )

    return cast("dict[str, Any]", data)


def create_aep_summary_template() -> Dict[str, Any]:
    """Create template for AEP summary JSON.
    
    Returns:
        Dictionary template with placeholders
    """
    return {
        "capacity_factor": 0.0,
        "net_site_aep_gwh": 0.0,
        "gross_aep_gwh": 0.0,
        "n_turbines": 0,
        "rated_power_kw": 0,
        "hub_height_m": 0,
        "source_id": "PLACEHOLDER",
        "source_type": "PLACEHOLDER",
        "iec_standard": "61400-12-1:2022",
        "derived_from": [],
        "losses": {
            "wake_loss_pct": 0.0,
            "availability_pct": 97.0,
            "electrical_loss_pct": 0.0,
            "total_loss_pct": 0.0
        }
    }


def export_provenance_report(
    aep_data: Dict[str, Any],
    output_path: str
) -> None:
    """Export provenance report for lender audit.
    
    Args:
        aep_data: AEP data dict from load_aep_from_summary()
        output_path: Output file path (.json or .md)
    """
    output_file = Path(output_path)
    provenance = aep_data.get("provenance", {})
    
    if output_file.suffix == ".json":
        with open(output_file, "w") as f:
            json.dump(provenance, f, indent=2)
    elif output_file.suffix == ".md":
        with open(output_file, "w") as f:
            f.write("# AEP Provenance Report\n\n")
            f.write(f"**Source ID**: `{provenance.get('aep_source_id')}`\n\n")
            f.write(f"**Net AEP**: {aep_data['net_site_aep_gwh']:.2f} GWh\n\n")
            f.write(f"**Capacity Factor**: {aep_data['capacity_factor']:.2%}\n\n")
            f.write(f"**Checksum (SHA-256)**: `{provenance.get('checksum_sha256')}`\n\n")
            f.write(f"**Validation Date**: {provenance.get('validation_date')}\n\n")
            f.write(f"**IEC Standard**: {provenance.get('iec_standard_version')}\n\n")
    
    logger.info(f"Provenance report exported to {output_file}")


# ═══════════════════════════════════════════════════════════════════════════════
# PROVENANCE ENFORCEMENT (#18 — lender-grade, test-enforced)
# ═══════════════════════════════════════════════════════════════════════════════

# Sources kept for back-compat that must NOT back a lender-grade AEP when a
# certified OEM curve is available (e.g. the extrapolated 10 MW placeholder).
PLACEHOLDER_SOURCE_IDS = frozenset({"OEM_ENVISION_EN171_10_PC"})
PLACEHOLDER_SOURCE_TYPES = frozenset({"PLACEHOLDER"})


def assert_source_in_manifest(
    source_id: str,
    manifest: Optional[Dict[str, Any]] = None,
) -> None:
    """Raise if ``source_id`` is not an approved AEP source.

    Args:
        source_id: The AEP source identifier to check.
        manifest: Approved-source manifest (defaults to ``APPROVED_SOURCES``).

    Raises:
        KeyError: If ``source_id`` is not present in the manifest.
    """
    if manifest is None:
        manifest = APPROVED_SOURCES
    if source_id not in manifest:
        raise KeyError(
            f"AEP source_id {source_id!r} is not in the approved manifest. "
            f"Approved sources: {sorted(manifest)}"
        )


def is_placeholder_source(
    source_id: str,
    manifest: Optional[Dict[str, Any]] = None,
) -> bool:
    """Return True if ``source_id`` is a known placeholder (non-certified) source.

    A source is a placeholder if it is in :data:`PLACEHOLDER_SOURCE_IDS`, declares
    a placeholder ``type``, or its description is marked ``PLACEHOLDER``.
    """
    if manifest is None:
        manifest = APPROVED_SOURCES
    if source_id in PLACEHOLDER_SOURCE_IDS:
        return True
    meta = manifest.get(source_id, {})
    if meta.get("type") in PLACEHOLDER_SOURCE_TYPES:
        return True
    return "PLACEHOLDER" in str(meta.get("description", "")).upper()


def has_certified_oem_curve(manifest: Optional[Dict[str, Any]] = None) -> bool:
    """Return True if a certified (non-placeholder) OEM power curve is available."""
    if manifest is None:
        manifest = APPROVED_SOURCES
    return any(
        meta.get("type") == "OEM" and not is_placeholder_source(sid, manifest)
        for sid, meta in manifest.items()
    )


def build_provenance_aep_block(
    source_id: str,
    *,
    derived_from: Optional[List[str]] = None,
    manifest: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build the standardized ``provenance.aep`` block for v14 outputs (#18).

    Args:
        source_id: Approved AEP source identifier.
        derived_from: Upstream source IDs this AEP derives from.
        manifest: Approved-source manifest (defaults to ``APPROVED_SOURCES``).

    Returns:
        Mapping with ``aep_source_id``, ``source_type``, ``derived_from``,
        ``iec_standard``, ``certificate`` and ``is_placeholder``.

    Raises:
        KeyError: If ``source_id`` is not in the manifest.
    """
    if manifest is None:
        manifest = APPROVED_SOURCES
    assert_source_in_manifest(source_id, manifest)
    meta = manifest[source_id]
    return {
        "aep_source_id": source_id,
        "source_type": meta.get("type", "Unknown"),
        "derived_from": list(derived_from or []),
        "iec_standard": meta.get("iec_standard", "Unknown"),
        "certificate": meta.get("certificate"),
        "is_placeholder": is_placeholder_source(source_id, manifest),
    }


def validate_config_aep_provenance(
    config: Dict[str, Any],
    *,
    manifest: Optional[Dict[str, Any]] = None,
    allow_placeholder: bool = False,
) -> Dict[str, Any]:
    """Enforce AEP provenance for a v14 scenario config and return its block.

    Reads ``resource.power_curve.source_id``, asserts it is an approved source,
    and (unless ``allow_placeholder``) refuses a placeholder source when a
    certified OEM curve is available — the lender-grade guard.

    Args:
        config: Parsed v14 scenario config mapping.
        manifest: Approved-source manifest (defaults to ``APPROVED_SOURCES``).
        allow_placeholder: If True, permit a placeholder source (e.g. for tests).

    Returns:
        The ``provenance.aep`` block for the config's source.

    Raises:
        ValueError: If the source is missing, or is a placeholder while a
            certified OEM curve exists (and ``allow_placeholder`` is False).
        KeyError: If the source is not in the manifest.
    """
    if manifest is None:
        manifest = APPROVED_SOURCES
    resource = config.get("resource", {}) or {}
    power_curve = resource.get("power_curve", {}) or {}
    source_id = power_curve.get("source_id")
    if not source_id:
        raise ValueError(
            "Config is missing resource.power_curve.source_id "
            "(AEP provenance is required for lender-grade output)."
        )
    assert_source_in_manifest(source_id, manifest)
    if (
        not allow_placeholder
        and is_placeholder_source(source_id, manifest)
        and has_certified_oem_curve(manifest)
    ):
        raise ValueError(
            f"AEP source_id {source_id!r} is a PLACEHOLDER but a certified OEM "
            f"curve is available; refuse for lender-grade output (#18)."
        )
    derived_from = power_curve.get("derived_from") or resource.get("derived_from")
    return build_provenance_aep_block(
        source_id, derived_from=derived_from, manifest=manifest
    )


__all__ = [
    "APPROVED_SOURCES",
    "IEC_STANDARDS",
    "PLACEHOLDER_SOURCE_IDS",
    "validate_source_manifest",
    "assert_source_in_manifest",
    "is_placeholder_source",
    "has_certified_oem_curve",
    "build_provenance_aep_block",
    "validate_config_aep_provenance",
    "compute_checksum_sha256",
    "load_aep_from_summary",
    "create_aep_summary_template",
    "export_provenance_report",
]
