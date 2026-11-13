"""Resource assurance contracts, evidence requests, and labelled fixture guards.

Defines the five challengeable resource assessment strands and evidence tracking
for Milestone P1.2 (Issue #1425):

1. Strand 1: Measurement & Site Identity (mast coordinates, sensor calibrations, QA)
2. Strand 2: Long-Term Reference Selection & MCP Correlation
3. Strand 3: Equipment, Loss Accounting & Yield Bridge
4. Strand 4: Statistical Uncertainty Build-up & Exceedance Probabilities (IEC 61400-15)
5. Strand 5: Frozen-Export-to-Finance Reconciliation & Invariant Guards

Also enforces the Labelled Fixtures Protocol: unverified or reanalysis-only data
must remain explicitly flagged as LABELLED_FIXTURE and cannot be silently promoted
to bankable status without satisfying the evidence register.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Sequence


class ResourceEvidenceStatus(str, Enum):
    """Evidence status classification for resource data fixtures."""

    LABELLED_FIXTURE = "LABELLED_FIXTURE"
    PROVISIONAL_CALIBRATED = "PROVISIONAL_CALIBRATED"
    CERTIFIED_BANKABLE = "CERTIFIED_BANKABLE"


class EnergyYieldStrand(str, Enum):
    """The five independently challengeable resource assessment strands."""

    STRAND_1_MEASUREMENT_SITE_IDENTITY = "STRAND_1_MEASUREMENT_SITE_IDENTITY"
    STRAND_2_LONG_TERM_MCP_CORRELATION = "STRAND_2_LONG_TERM_MCP_CORRELATION"
    STRAND_3_EQUIPMENT_LOSS_ACCOUNTING = "STRAND_3_EQUIPMENT_LOSS_ACCOUNTING"
    STRAND_4_UNCERTAINTY_EXCEEDANCE = "STRAND_4_UNCERTAINTY_EXCEEDANCE"
    STRAND_5_FINANCE_RECONCILIATION = "STRAND_5_FINANCE_RECONCILIATION"


@dataclass(frozen=True)
class StrandSpec:
    """Specification and standards adherence for a challengeable resource strand."""

    strand_id: EnergyYieldStrand
    title: str
    primary_standards: Sequence[str]
    description: str
    required_artifacts: Sequence[str]
    done_when: str


@dataclass(frozen=True)
class EvidenceRequest:
    """Formal technical due diligence evidence request item."""

    request_id: str
    title: str
    description: str
    required_verification: str
    strand: EnergyYieldStrand
    status: str = "PENDING_FIELD_DATA"


STRAND_SPECS: Mapping[EnergyYieldStrand, StrandSpec] = {
    EnergyYieldStrand.STRAND_1_MEASUREMENT_SITE_IDENTITY: StrandSpec(
        strand_id=EnergyYieldStrand.STRAND_1_MEASUREMENT_SITE_IDENTITY,
        title="Measurement & Site Identity",
        primary_standards=("IEC 61400-12-1:2017", "MEASNET Site Assessment"),
        description="On-site mast station metadata, anemometer calibrations, and raw QA.",
        required_artifacts=(
            "mast_station_metadata.json",
            "anemometer_calibration_certificates.pdf",
            "raw_10min_timeseries_manifest.sha256",
        ),
        done_when="Sensors and calibration parameters are cryptographically pinned.",
    ),
    EnergyYieldStrand.STRAND_2_LONG_TERM_MCP_CORRELATION: StrandSpec(
        strand_id=EnergyYieldStrand.STRAND_2_LONG_TERM_MCP_CORRELATION,
        title="Long-Term Reference Selection & MCP Correlation",
        primary_standards=("IEC 61400-15",),
        description="Concurrent period correlation between on-site mast and long-term reanalysis.",
        required_artifacts=(
            "reanalysis_provenance_spec.json",
            "concurrent_mcp_correlation_report.json",
            "long_term_weibull_fit.json",
        ),
        done_when="Directional R2 >= 0.85 and 20+ year long-term Weibull derived.",
    ),
    EnergyYieldStrand.STRAND_3_EQUIPMENT_LOSS_ACCOUNTING: StrandSpec(
        strand_id=EnergyYieldStrand.STRAND_3_EQUIPMENT_LOSS_ACCOUNTING,
        title="Equipment, Loss Accounting & Yield Bridge",
        primary_standards=("IEC 61400-12-1", "DTU PyWake"),
        description="OEM power curve normalization, layout wake model, and loss waterfall.",
        required_artifacts=(
            "oem_power_curve_density_matrix.json",
            "pywake_bastankhah_wake_loss.json",
            "loss_waterfall_bridge.json",
        ),
        done_when="All loss categories explicitly tracked in reconciling waterfall ledger.",
    ),
    EnergyYieldStrand.STRAND_4_UNCERTAINTY_EXCEEDANCE: StrandSpec(
        strand_id=EnergyYieldStrand.STRAND_4_UNCERTAINTY_EXCEEDANCE,
        title="Statistical Uncertainty Build-up & Exceedance Probabilities",
        primary_standards=("IEC 61400-15-2",),
        description="Quadrature combination of systematic and random uncertainties to derive P50/P75/P90.",
        required_artifacts=(
            "uncertainty_budget_iec61400_15.json",
            "exceedance_probabilities_p50_p75_p90.json",
        ),
        done_when="P75/P90 derived from statistical quadrature budget rather than flat scalars.",
    ),
    EnergyYieldStrand.STRAND_5_FINANCE_RECONCILIATION: StrandSpec(
        strand_id=EnergyYieldStrand.STRAND_5_FINANCE_RECONCILIATION,
        title="Frozen-Export-to-Finance Reconciliation & Invariant Guards",
        primary_standards=("GWTF CCCDIR (FRAMEWORK-03)",),
        description="Boundary adapter validation and cryptographic scenario integrity.",
        required_artifacts=(
            "wind_cashflow_export.json",
            "scenario_patch_validation_receipt.json",
        ),
        done_when="Capacity factor, generation, and CFADS reconcile with zero silent drift.",
    ),
}

EVIDENCE_REQUEST_REGISTER: Mapping[str, EvidenceRequest] = {
    "EV-REQ-01": EvidenceRequest(
        request_id="EV-REQ-01",
        title="Met-Mast Anemometer Calibration & Geometry",
        description="ISO 17025 calibration certificates for DutchBay met mast 617725 sensors.",
        required_verification="Slope/offset verification within 12 months of campaign start.",
        strand=EnergyYieldStrand.STRAND_1_MEASUREMENT_SITE_IDENTITY,
    ),
    "EV-REQ-02": EvidenceRequest(
        request_id="EV-REQ-02",
        title="Raw 10-Minute Concurrent Mast Time-Series",
        description="12 consecutive months of raw 10-minute on-site mast observations.",
        required_verification="SHA-256 sidecar, <10% missing timestamps, range QA.",
        strand=EnergyYieldStrand.STRAND_2_LONG_TERM_MCP_CORRELATION,
    ),
    "EV-REQ-03": EvidenceRequest(
        request_id="EV-REQ-03",
        title="OEM-Certified Turbine Power & Thrust Curves",
        description="Manufacturer IEC 61400-12-1 measured power and Ct curve matrices.",
        required_verification="Third-party accredited test report (DNV/UL/TÜV).",
        strand=EnergyYieldStrand.STRAND_3_EQUIPMENT_LOSS_ACCOUNTING,
    ),
    "EV-REQ-04": EvidenceRequest(
        request_id="EV-REQ-04",
        title="Solar GHI/DNI Ground Calibration Series",
        description="Co-located thermopile pyranometer measurements for solar cross-validation.",
        required_verification="ISO 9060 Class A calibration certificate.",
        strand=EnergyYieldStrand.STRAND_2_LONG_TERM_MCP_CORRELATION,
    ),
}


def assert_labelled_fixture_only(metadata: Mapping[str, Any]) -> None:
    """Enforce the Labelled Fixtures Protocol on uncertified resource fixtures.

    Raises:
        ValueError: If an uncertified fixture attempts to declare bankable status.
    """
    status = metadata.get("evidence_status", ResourceEvidenceStatus.LABELLED_FIXTURE)
    if isinstance(status, str):
        try:
            status = ResourceEvidenceStatus(status)
        except ValueError as exc:
            raise ValueError(f"Invalid resource evidence status: {status!r}") from exc

    if status == ResourceEvidenceStatus.CERTIFIED_BANKABLE:
        evidence_keys = metadata.get("satisfied_evidence_requests", [])
        required = {"EV-REQ-01", "EV-REQ-02", "EV-REQ-03"}
        missing = required - set(evidence_keys)
        if missing:
            raise ValueError(
                f"Cannot declare CERTIFIED_BANKABLE without fulfilling required evidence: {sorted(missing)}"
            )


def get_strand_specification(strand: EnergyYieldStrand) -> StrandSpec:
    """Retrieve the authoritative specification for a challengeable strand."""
    return STRAND_SPECS[strand]


def list_pending_evidence_requests() -> Sequence[EvidenceRequest]:
    """List all open evidence requests for lender technical due diligence."""
    return list(EVIDENCE_REQUEST_REGISTER.values())
