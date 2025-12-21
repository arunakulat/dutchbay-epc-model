#!/usr/bin/env python
"""EPC AEP resource loader with cryptographic provenance tracking.

Provides unified interface for loading wind resource data from multiple sources
(OEM curves, NREL data, ECMWF reanalysis) with built-in validation, normalization,
and audit trail generation for lender-grade financial modeling.

Usage:
    from analytics.loader.aep_loader import load_aep_from_summary, validate_source_manifest
    
    # Load AEP from Data Lake
    aep_data = load_aep_from_summary(
        path='Curated/AEP/DutchBay/aep_summary_2020_2024.json',
        validate_manifest=True
    )
    
    print(f"Net AEP: {aep_data['net_site_aep_gwh']:.2f} GWh")
    print(f"Capacity Factor: {aep_data['capacity_factor']:.2%}")
    print(f"Source: {aep_data['source_type']} - {aep_data['source_id']}")
    
    # Validate provenance chain
    assert 'provenance' in aep_data
    assert aep_data['provenance']['iec_standard_version'] == '61400-12-1:2022'

References:
    - IEC 61400-12-1:2022 Wind turbines - Power performance measurements
    - IEC 61400-15-1:2025 Assessment of wind resource, energy yield and site suitability
    - DFI Working Group on Blended Concessional Finance (audit requirements)
    - NREL System Advisor Model (SAM) - Wind resource data formats

Context:
    Sprint 17 - Issues #17 + #18: EPC Resource Loader + Provenance Chain
    Part of wind-to-AEP pipeline for DutchBay 150 MW wind farm
    Required for lender-grade financial modeling with audit trails
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)

# ═════════════════════════════════════════════════════════════════════════════
# DATA LAKE MANIFEST REGISTRY
# ═════════════════════════════════════════════════════════════════════════════

# Approved AEP data sources (will be loaded from manifest in production)
APPROVED_SOURCES = {
    "OEM_ENVISION_EN171_65_PC": {
        "type": "OEM",
        "description": "Envision EN-171-6.5 MW Certified Power Curve",
        "iec_standard": "IEC 61400-21:2008",
        "certification_body": "Beijing CGC Certification Center",
        "test_date": "2024-04-12 to 2024-09-21",
        "test_location": "Huizhi Wind Farm, Jiangsu, China",
    },
    "ECMWF_ERA5_2020_2024_DUTCHBAY": {
        "type": "ECMWF",
        "description": "ERA5 Reanalysis 2020-2024 Dutch Bay Region",
        "iec_standard": "IEC 61400-15-1:2025",
        "data_source": "Copernicus Climate Data Store",
        "spatial_resolution": "0.25° x 0.25°",
        "temporal_resolution": "Hourly",
    },
    "NREL_WTK_SRI_LANKA_2020_2024": {
        "type": "NREL",
        "description": "NREL Wind Toolkit Sri Lanka 2020-2024",
        "iec_standard": "IEC 61400-15-1:2025",
        "data_source": "NREL Wind Integration National Dataset",
        "spatial_resolution": "2 km x 2 km",
        "temporal_resolution": "5-minute",
    },
}

# IEC standards mapping
IEC_STANDARDS = {
    "61400-12-1:2022": "Wind turbines - Part 12-1: Power performance measurements of electricity producing wind turbines",
    "61400-15-1:2025": "Wind turbines - Part 15-1: Assessment of wind resource, energy yield and site suitability - General requirements",
    "61400-21:2008": "Wind turbines - Part 21: Measurement and assessment of power quality characteristics",
}


def compute_checksum_sha256(data: Dict[str, Any]) -> str:
    """Compute SHA-256 checksum for data integrity verification.
    
    Args:
        data: Dictionary to compute checksum for
    
    Returns:
        SHA-256 hex digest (64 characters)
    
    Example:
        >>> data = {'aep_gwh': 485.32, 'capacity_factor': 0.375}
        >>> checksum = compute_checksum_sha256(data)
        >>> len(checksum)
        64
    """
    # Serialize to JSON with sorted keys for deterministic hashing
    json_str = json.dumps(data, sort_keys=True)
    sha256_hash = hashlib.sha256(json_str.encode('utf-8')).hexdigest()
    return sha256_hash


def validate_source_manifest(
    source_id: str,
    manifest: Optional[Dict[str, Any]] = None
) -> bool:
    """Validate that source_id exists in approved Data Lake manifest.
    
    Args:
        source_id: Source identifier (e.g., 'ECMWF_ERA5_2020_2024_DUTCHBAY')
        manifest: Custom manifest dict. If None, uses APPROVED_SOURCES.
    
    Returns:
        True if source_id is approved, False otherwise
    
    Raises:
        ValueError: If source_id not in manifest and validation required
    
    Example:
        >>> validate_source_manifest('OEM_ENVISION_EN171_65_PC')
        True
        >>> validate_source_manifest('UNKNOWN_SOURCE')
        False
    """
    registry = manifest if manifest is not None else APPROVED_SOURCES
    
    if source_id not in registry:
        logger.error(
            f"Source ID '{source_id}' not found in approved manifest. "
            f"Available sources: {list(registry.keys())}"
        )
        return False
    
    logger.info(f"Source '{source_id}' validated against manifest")
    return True


def load_aep_from_summary(
    path: str,
    validate_manifest: bool = True,
    manifest: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Load normalized AEP data from Data Lake summary file.
    
    Supports JSON and CSV formats with automatic format detection.
    Performs validation and enriches with provenance metadata.
    
    Args:
        path: Path to AEP summary file (JSON or CSV)
        validate_manifest: If True, validates source_id against manifest
        manifest: Custom manifest dict. If None, uses APPROVED_SOURCES.
    
    Returns:
        Dictionary with normalized AEP data:
            - capacity_factor: Net site capacity factor (0-1)
            - net_site_aep_gwh: Annual energy production (GWh)
            - n_turbines: Number of turbines
            - rated_power_kw: Rated power per turbine (kW)
            - hub_height_m: Hub height (m)
            - source_id: Data source identifier
            - source_type: Source type (OEM, NREL, ECMWF)
            - iec_standard: IEC standard version
            - provenance: Audit trail metadata
    
    Raises:
        FileNotFoundError: If path does not exist
        ValueError: If required fields missing or validation fails
        KeyError: If source_id not in manifest (when validate_manifest=True)
    
    Example:
        >>> aep_data = load_aep_from_summary(
        ...     'Curated/AEP/DutchBay/aep_summary_2020_2024.json'
        ... )
        >>> aep_data['net_site_aep_gwh']
        485.32
        >>> aep_data['provenance']['iec_standard_version']
        '61400-12-1:2022'
    """
    file_path = Path(path)
    
    if not file_path.exists():
        raise FileNotFoundError(f"AEP summary file not found: {path}")
    
    # Load data based on file extension
    if file_path.suffix == '.json':
        with open(file_path, 'r') as f:
            raw_data = json.load(f)
    elif file_path.suffix == '.csv':
        df = pd.read_csv(file_path)
        raw_data = df.to_dict('records')[0]  # Assume single-row summary
    else:
        raise ValueError(
            f"Unsupported file format: {file_path.suffix}. "
            "Use .json or .csv"
        )
    
    # Validate required fields
    required_fields = [
        'capacity_factor',
        'net_site_aep_gwh',
        'n_turbines',
        'rated_power_kw',
        'source_id',
        'source_type'
    ]
    
    missing = [f for f in required_fields if f not in raw_data]
    if missing:
        raise ValueError(
            f"Missing required fields in AEP summary: {missing}. "
            f"Available: {list(raw_data.keys())}"
        )
    
    # Validate source_id against manifest
    source_id = raw_data['source_id']
    if validate_manifest:
        if not validate_source_manifest(source_id, manifest):
            raise KeyError(
                f"Source ID '{source_id}' not in approved manifest. "
                "Set validate_manifest=False to bypass."
            )
    
    # Get source metadata from manifest
    registry = manifest if manifest is not None else APPROVED_SOURCES
    source_meta = registry.get(source_id, {})
    
    # Build provenance chain
    provenance = {
        'aep_source_id': source_id,
        'derived_from': raw_data.get('derived_from', []),
        'iec_standard_version': source_meta.get('iec_standard', 'Unknown'),
        'validation_date': datetime.utcnow().strftime('%Y-%m-%d'),
        'data_lake_path': str(file_path),
    }
    
    # Compute checksum for integrity
    checksum_data = {
        'capacity_factor': raw_data['capacity_factor'],
        'net_site_aep_gwh': raw_data['net_site_aep_gwh'],
        'n_turbines': raw_data['n_turbines'],
        'source_id': source_id,
    }
    provenance['checksum_sha256'] = compute_checksum_sha256(checksum_data)
    
    # Build normalized output
    aep_data = {
        'capacity_factor': float(raw_data['capacity_factor']),
        'net_site_aep_gwh': float(raw_data['net_site_aep_gwh']),
        'n_turbines': int(raw_data['n_turbines']),
        'rated_power_kw': float(raw_data['rated_power_kw']),
        'hub_height_m': float(raw_data.get('hub_height_m', 150.0)),
        'source_id': source_id,
        'source_type': raw_data['source_type'],
        'iec_standard': source_meta.get('iec_standard', 'Unknown'),
        'provenance': provenance,
    }
    
    # Optional fields
    if 'gross_aep_gwh' in raw_data:
        aep_data['gross_aep_gwh'] = float(raw_data['gross_aep_gwh'])
    
    if 'losses' in raw_data:
        aep_data['losses'] = raw_data['losses']
    
    logger.info(
        f"Loaded AEP data: {aep_data['net_site_aep_gwh']:.2f} GWh, "
        f"CF={aep_data['capacity_factor']:.2%}, "
        f"Source={source_id}"
    )
    
    return aep_data


def create_aep_summary_template() -> Dict[str, Any]:
    """Create template for AEP summary file.
    
    Returns:
        Dictionary template with required and optional fields
    
    Example:
        >>> template = create_aep_summary_template()
        >>> with open('aep_summary.json', 'w') as f:
        ...     json.dump(template, f, indent=2)
    """
    template = {
        # Required fields
        "capacity_factor": 0.0,  # Net capacity factor (0-1)
        "net_site_aep_gwh": 0.0,  # Net AEP (GWh)
        "n_turbines": 0,  # Number of turbines
        "rated_power_kw": 0.0,  # Rated power per turbine (kW)
        "source_id": "SOURCE_ID_HERE",  # Must match manifest
        "source_type": "OEM | NREL | ECMWF",  # Source type
        
        # Optional fields
        "hub_height_m": 150.0,  # Hub height (m)
        "gross_aep_gwh": 0.0,  # Gross AEP before losses
        "derived_from": [],  # List of upstream source IDs
        "losses": {
            "wake_loss_pct": 8.0,
            "availability_pct": 97.0,
            "electrical_loss_pct": 2.0,
        },
        
        # Metadata
        "created_date": datetime.utcnow().strftime('%Y-%m-%d'),
        "created_by": "analytics.loader.aep_loader",
        "version": "1.0",
    }
    
    return template


def export_provenance_report(
    aep_data: Dict[str, Any],
    output_path: str
) -> None:
    """Export provenance report for audit trail.
    
    Generates human-readable report with all AEP data sources,
    IEC standards, checksums, and validation status.
    
    Args:
        aep_data: AEP data from load_aep_from_summary()
        output_path: Path to save report (JSON or Markdown)
    
    Example:
        >>> aep_data = load_aep_from_summary('aep_summary.json')
        >>> export_provenance_report(
        ...     aep_data,
        ...     'reports/aep_provenance_2025_12_21.md'
        ... )
    """
    output_file = Path(output_path)
    provenance = aep_data.get('provenance', {})
    
    if output_file.suffix == '.json':
        # JSON format
        with open(output_file, 'w') as f:
            json.dump(provenance, f, indent=2)
    
    elif output_file.suffix == '.md':
        # Markdown format
        report_lines = [
            "# AEP Provenance Report",
            "",
            f"**Generated**: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}",
            "",
            "## AEP Summary",
            "",
            f"- **Net AEP**: {aep_data['net_site_aep_gwh']:.2f} GWh",
            f"- **Capacity Factor**: {aep_data['capacity_factor']:.2%}",
            f"- **Number of Turbines**: {aep_data['n_turbines']}",
            f"- **Rated Power**: {aep_data['rated_power_kw']:.0f} kW per turbine",
            f"- **Hub Height**: {aep_data.get('hub_height_m', 'N/A')} m",
            "",
            "## Data Provenance",
            "",
            f"- **Source ID**: {provenance['aep_source_id']}",
            f"- **Source Type**: {aep_data['source_type']}",
            f"- **IEC Standard**: {provenance['iec_standard_version']}",
            f"- **Validation Date**: {provenance['validation_date']}",
            f"- **Checksum (SHA-256)**: `{provenance['checksum_sha256']}`",
            "",
        ]
        
        if provenance.get('derived_from'):
            report_lines.extend([
                "## Derived From",
                "",
            ])
            for source in provenance['derived_from']:
                report_lines.append(f"- {source}")
            report_lines.append("")
        
        with open(output_file, 'w') as f:
            f.write('\n'.join(report_lines))
    
    else:
        raise ValueError(f"Unsupported output format: {output_file.suffix}")
    
    logger.info(f"Provenance report exported to {output_path}")


__all__ = [
    "APPROVED_SOURCES",
    "IEC_STANDARDS",
    "compute_checksum_sha256",
    "validate_source_manifest",
    "load_aep_from_summary",
    "create_aep_summary_template",
    "export_provenance_report",
]
