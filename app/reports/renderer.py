"""Render a :class:`ReportContext` to HTML (Jinja2) and PDF (WeasyPrint).

The HTML path uses Jinja2 (a core dependency) and is fully unit-testable. The PDF
path lazily imports WeasyPrint — an **optional** extra (``pip install -e
'.[report]'``) that also needs system libraries (pango/cairo). When WeasyPrint is
absent the renderer raises :class:`ReportDependencyError` (CESSPIT — fail loud, no
silent stub), so a caller can map it to an HTTP 503 cleanly.
"""

from __future__ import annotations

from pathlib import Path
from typing import cast

from jinja2 import Environment, FileSystemLoader

from app.reports.report_model import ReportContext

#: Template directory shipped alongside this module.
_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
_TEMPLATE_NAME = "report.html.j2"


class ReportDependencyError(RuntimeError):
    """Raised when the optional PDF backend (WeasyPrint) is not installed."""


def _environment() -> Environment:
    """Build the Jinja2 environment.

    Autoescaping is forced on (this environment renders one HTML template, whose
    ``.j2`` extension would otherwise defeat ``select_autoescape``) so any
    user-supplied value — e.g. a site name — is HTML-escaped (no injection).
    """
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render_report_html(context: ReportContext) -> str:
    """Render the report context to a standalone HTML document string."""
    template = _environment().get_template(_TEMPLATE_NAME)
    return template.render(ctx=context)


def render_report_pdf(context: ReportContext) -> bytes:
    """Render the report context to PDF bytes via WeasyPrint.

    Args:
        context: The assembled report context.

    Returns:
        The PDF document as bytes.

    Raises:
        ReportDependencyError: WeasyPrint (the optional ``[report]`` extra) is
            not installed.
    """
    html = render_report_html(context)
    try:
        from weasyprint import HTML
    except ImportError as exc:  # CESSPIT: fail loud, never a silent stub
        raise ReportDependencyError(
            "PDF rendering requires WeasyPrint. Install the optional extra: "
            "pip install -e '.[report]' (also needs the pango/cairo system "
            "libraries). The HTML report is available without it."
        ) from exc
    # write_pdf() returns Any (WeasyPrint is untyped); narrow to bytes.
    return cast(bytes, HTML(string=html).write_pdf())  # pragma: no cover (optional dep)
