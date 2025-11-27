"""
Docstrings and help text for Sensitivity Analytics (v14+).

These strings are shared by multiple modules (batch, v14, dashboards)
to ensure consistent terminology and easier updates.
"""

SENSITIVITY_OVERVIEW = """
Sensitivity analysis evaluates how changes in key parameters
(capex, opex, tariff, debt terms, etc.) impact project KPIs
such as IRR, NPV, DSCR, LLCR, and covenants.

The v14 suite supports:
- One-way (tornado) sensitivity sweeps over any model parameter.
- Multi-parameter stress scenarios (e.g. low tariff + high capex).
- Tail-risk and downside analytics for lenders / DFIs / ICs.
"""


TORNADO_CHART_DOC = """
Tornado charts show the relative impact of each parameter on a
selected KPI (e.g. project IRR or minimum DSCR), holding all
other inputs constant at base-case values.

Bars are sorted from largest to smallest impact so decision-makers
can see which assumptions truly drive risk and value.
"""


LENDER_VIEW_DOC = """
Lender-focused sensitivity outputs emphasise DSCR, LLCR, PLCR,
covenant headroom, and downside protection metrics.

Typical views include:
- DSCR distribution across scenarios and tail events.
- Headroom to minimum DSCR / cash-sweep triggers.
- Scenario tables for credit committee / IC packs.
"""
