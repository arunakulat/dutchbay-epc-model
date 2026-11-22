"""Typed site-analysis report sections (#1824).

The models :class:`app.reports.report_model.ReportContext` carries. They live apart from the
builder (:mod:`app.reports.site_analysis_sections`) so that the report model does not import
the analyses: only a caller that builds the sections runs them.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field

STATUS_COMPLETED = "completed"
STATUS_STALE = "stale"
STATUS_NOT_RUN = "not_run"
STATUS_FAILED = "failed"
STATUS_NOT_APPLICABLE = "not_applicable"


class SiteAnalysisTable(BaseModel):
    """A small table of pre-formatted cells."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    caption: str
    columns: List[str]
    rows: List[List[str]] = Field(default_factory=list)


class SiteAnalysisSection(BaseModel):
    """One analysis's section: its status, labels, figures and where they came from."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str
    title: str
    status: str
    reason: Optional[str] = None
    stale_reasons: List[str] = Field(default_factory=list)
    labels: List[str] = Field(default_factory=list)
    hold: Optional[str] = None
    notes: Optional[str] = None
    site: Optional[str] = None
    figures: List[Tuple[str, str]] = Field(default_factory=list)
    tables: List[SiteAnalysisTable] = Field(default_factory=list)
    source: Optional[str] = None
    provenance: Optional[str] = None


class SiteAnalysesBlock(BaseModel):
    """Every site-analysis section of one report."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    intro: str
    sections: List[SiteAnalysisSection]

    @property
    def shown(self) -> List[SiteAnalysisSection]:
        """The sections that apply to the scenario."""
        return [s for s in self.sections if s.status != STATUS_NOT_APPLICABLE]

    @property
    def not_applicable(self) -> List[SiteAnalysisSection]:
        """The sections whose block the scenario does not declare."""
        return [s for s in self.sections if s.status == STATUS_NOT_APPLICABLE]


__all__ = [
    "STATUS_COMPLETED",
    "STATUS_FAILED",
    "STATUS_NOT_APPLICABLE",
    "STATUS_NOT_RUN",
    "STATUS_STALE",
    "SiteAnalysesBlock",
    "SiteAnalysisSection",
    "SiteAnalysisTable",
]
