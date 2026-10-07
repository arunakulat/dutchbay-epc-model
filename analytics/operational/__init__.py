"""Post-COD operational-assessment contracts.

The package starts with a dependency-free evidence envelope.  Parsers, estimators,
OpenOA adapters, report rendering, and finance wiring belong to later dolphins.
"""

from analytics.operational.contracts import (
    OPERATIONAL_EVIDENCE_SCHEMA,
    OPERATIONAL_REQUIRED_DATASET_KINDS,
    OPERATIONAL_REQUIRED_ROLES,
    OperationalAssessmentInput,
    OperationalColumnBinding,
    OperationalDatasetEvidence,
    OperationalEvidenceError,
)

__all__ = [
    "OPERATIONAL_EVIDENCE_SCHEMA",
    "OPERATIONAL_REQUIRED_DATASET_KINDS",
    "OPERATIONAL_REQUIRED_ROLES",
    "OperationalAssessmentInput",
    "OperationalColumnBinding",
    "OperationalDatasetEvidence",
    "OperationalEvidenceError",
]
