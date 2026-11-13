"""Tests for P1.2 independently challengeable resource strands and evidence register.

Covers Issue #1425 and Milestone P1.2.
"""

from __future__ import annotations

import pytest

from wind_resource.resource_assurance import (
    EVIDENCE_REQUEST_REGISTER,
    STRAND_SPECS,
    EnergyYieldStrand,
    EvidenceRequest,
    ResourceEvidenceStatus,
    StrandSpec,
    assert_labelled_fixture_only,
    get_strand_specification,
    list_pending_evidence_requests,
)


def test_all_five_strands_registered() -> None:
    """Verify all five P1.2 challengeable strands are defined with authoritative specs."""
    assert len(EnergyYieldStrand) == 5
    assert len(STRAND_SPECS) == 5

    expected_strands = {
        EnergyYieldStrand.STRAND_1_MEASUREMENT_SITE_IDENTITY,
        EnergyYieldStrand.STRAND_2_LONG_TERM_MCP_CORRELATION,
        EnergyYieldStrand.STRAND_3_EQUIPMENT_LOSS_ACCOUNTING,
        EnergyYieldStrand.STRAND_4_UNCERTAINTY_EXCEEDANCE,
        EnergyYieldStrand.STRAND_5_FINANCE_RECONCILIATION,
    }
    assert set(STRAND_SPECS.keys()) == expected_strands

    for strand in EnergyYieldStrand:
        spec = get_strand_specification(strand)
        assert isinstance(spec, StrandSpec)
        assert spec.strand_id == strand
        assert len(spec.title) > 5
        assert len(spec.primary_standards) >= 1
        assert len(spec.required_artifacts) >= 2
        assert len(spec.done_when) > 10


def test_evidence_requests_registered() -> None:
    """Verify evidence request register covers on-site mast, time-series, power curve, and solar."""
    requests = list_pending_evidence_requests()
    assert len(requests) == 4
    assert set(EVIDENCE_REQUEST_REGISTER.keys()) == {
        "EV-REQ-01",
        "EV-REQ-02",
        "EV-REQ-03",
        "EV-REQ-04",
    }

    for req in requests:
        assert isinstance(req, EvidenceRequest)
        assert req.request_id.startswith("EV-REQ-")
        assert len(req.title) > 5
        assert len(req.description) > 15
        assert len(req.required_verification) > 10
        assert req.status == "PENDING_FIELD_DATA"
        assert isinstance(req.strand, EnergyYieldStrand)


def test_labelled_fixture_guard_permits_labelled_fixtures() -> None:
    """Fixtures declaring LABELLED_FIXTURE or omitting status default to allowed fixture mode."""
    # Default without explicit status
    assert_labelled_fixture_only({"site": "DutchBay", "hub_height_m": 120.0})

    # Explicit LABELLED_FIXTURE
    assert_labelled_fixture_only(
        {
            "site": "DutchBay",
            "evidence_status": ResourceEvidenceStatus.LABELLED_FIXTURE,
        }
    )
    assert_labelled_fixture_only(
        {
            "site": "DutchBay",
            "evidence_status": "LABELLED_FIXTURE",
        }
    )


def test_labelled_fixture_guard_rejects_unfulfilled_bankable_claim() -> None:
    """Negative control: declaring CERTIFIED_BANKABLE without required evidence is blocked."""
    with pytest.raises(
        ValueError,
        match="Cannot declare CERTIFIED_BANKABLE without fulfilling required evidence",
    ):
        assert_labelled_fixture_only(
            {
                "site": "DutchBay",
                "evidence_status": ResourceEvidenceStatus.CERTIFIED_BANKABLE,
            }
        )

    # Partial evidence still fails loud
    with pytest.raises(
        ValueError,
        match="Cannot declare CERTIFIED_BANKABLE without fulfilling required evidence",
    ):
        assert_labelled_fixture_only(
            {
                "site": "DutchBay",
                "evidence_status": "CERTIFIED_BANKABLE",
                "satisfied_evidence_requests": ["EV-REQ-01"],
            }
        )


def test_labelled_fixture_guard_accepts_verified_bankable() -> None:
    """When all mandatory evidence requests are fulfilled, CERTIFIED_BANKABLE is accepted."""
    assert_labelled_fixture_only(
        {
            "site": "DutchBay",
            "evidence_status": ResourceEvidenceStatus.CERTIFIED_BANKABLE,
            "satisfied_evidence_requests": ["EV-REQ-01", "EV-REQ-02", "EV-REQ-03"],
        }
    )


def test_invalid_status_raises_value_error() -> None:
    """Negative control: malformed status string fails loud."""
    with pytest.raises(
        ValueError, match="Invalid resource evidence status: 'UNAUDITED'"
    ):
        assert_labelled_fixture_only({"evidence_status": "UNAUDITED"})


def test_dataclasses_are_frozen() -> None:
    """Assurance: StrandSpec and EvidenceRequest instances are immutable."""
    spec = get_strand_specification(
        EnergyYieldStrand.STRAND_1_MEASUREMENT_SITE_IDENTITY
    )
    with pytest.raises(AttributeError):
        spec.title = "Mutated Title"  # type: ignore[misc]

    req = EVIDENCE_REQUEST_REGISTER["EV-REQ-01"]
    with pytest.raises(AttributeError):
        req.status = "MUTATED"  # type: ignore[misc]
