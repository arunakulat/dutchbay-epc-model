"""DutchBay Presentation Layer (DBPL).

The house style for every DutchBay document, and the enforced print core behind any DBPL PDF.

Per GWTF DBPL-01, a document described as a DBPL / dbpl PDF must be produced through
:func:`app.reports.dbpl.print_core.render_dbpl_pdf`, which requires the COMPLETE ``[report]``
optional extra (weasyprint, reportlab, geopandas, contextily), applies the house style, and
surfaces the font provenance behind the render.

Style tokens live in :mod:`app.reports.dbpl.style` and were measured from the reference
document, not invented; see that module for provenance.
"""

from app.reports.dbpl.print_core import (
    DBPL_EXTRA,
    DbplDependencyError,
    DbplRenderResult,
    FontResolution,
    probe_fonts,
    render_dbpl_pdf,
    require_dbpl_stack,
)
from app.reports.dbpl.style import (
    DBPL_FONT_STACKS,
    DBPL_PALETTE,
    DBPL_REFERENCE_DOCUMENT,
    DBPL_STRUCTURAL_FURNITURE,
    DBPL_TYPE_SCALE,
)

__all__ = [
    "DBPL_EXTRA",
    "DBPL_FONT_STACKS",
    "DBPL_PALETTE",
    "DBPL_REFERENCE_DOCUMENT",
    "DBPL_STRUCTURAL_FURNITURE",
    "DBPL_TYPE_SCALE",
    "DbplDependencyError",
    "DbplRenderResult",
    "FontResolution",
    "probe_fonts",
    "render_dbpl_pdf",
    "require_dbpl_stack",
]
