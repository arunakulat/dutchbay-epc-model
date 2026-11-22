"""Lender-report layer: project a ``CaseResult`` into an HTML / PDF report.

Pure presentation over the canonical pipeline output (Dolphin — no finance
logic). Branding, covenant thresholds, and the KPI display table are config-
driven (``config/report_defaults.yaml``, CCCDIR). The PDF backend (WeasyPrint)
is an optional extra; the HTML report needs only Jinja2.

Uses PEP 562 lazy attribute loading so importing lightweight sub-modules such
as :mod:`app.reports.module_ledger` never triggers eager imports of
``report_model``, ``renderer``, ``analytics.*``, or ``finance.*``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
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


def __getattr__(name: str) -> Any:
    """Lazily resolve public report exports without eager submodule loading."""
    value: Any
    if name in ("ReportConfig", "load_report_config"):
        from app.reports.report_config import ReportConfig, load_report_config

        value = {
            "ReportConfig": ReportConfig,
            "load_report_config": load_report_config,
        }[name]
    elif name in ("ReportContext", "build_report_context"):
        from app.reports.report_model import ReportContext, build_report_context

        value = {
            "ReportContext": ReportContext,
            "build_report_context": build_report_context,
        }[name]
    elif name in ("ReportDependencyError", "render_report_html", "render_report_pdf"):
        from app.reports.renderer import (
            ReportDependencyError,
            render_report_html,
            render_report_pdf,
        )

        value = {
            "ReportDependencyError": ReportDependencyError,
            "render_report_html": render_report_html,
            "render_report_pdf": render_report_pdf,
        }[name]
    else:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """Expose lazy compatibility exports to interactive and inspection clients."""
    return sorted(set(globals()) | set(__all__))
