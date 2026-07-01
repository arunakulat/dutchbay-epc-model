"""Lender-report layer: project a ``CaseResult`` into an HTML / PDF report.

Pure presentation over the canonical pipeline output (Dolphin — no finance
logic). Branding, covenant thresholds, and the KPI display table are config-
driven (``config/report_defaults.yaml``, CCCDIR). The PDF backend (WeasyPrint)
is an optional extra; the HTML report needs only Jinja2.
"""

from __future__ import annotations

from app.reports.renderer import (
    ReportDependencyError,
    render_report_html,
    render_report_pdf,
)
from app.reports.report_config import ReportConfig, load_report_config
from app.reports.report_model import ReportContext, build_report_context

__all__ = [
    "ReportConfig",
    "load_report_config",
    "ReportContext",
    "build_report_context",
    "ReportDependencyError",
    "render_report_html",
    "render_report_pdf",
]
