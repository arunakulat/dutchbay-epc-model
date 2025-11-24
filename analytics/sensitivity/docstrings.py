"""
docstrings.py – Narrative Lookups for Sensitivity Outputs (v14+)

PURPOSE:
    Links driver variable names to human text explanations (e.g., for tooltips, reports, or dashboards).
    Makes exported tornado tables, charts, and dashboards more understandable—critical for stakeholders.

USAGE:
    from analytics.sensitivity.docstrings import param_narrative_lookup
    narrative = param_narrative_lookup("project.capex_usd_per_kw", doc_map)

TYPICAL doc_map (usually load from YAML/JSON):
    {
        "project.capex_usd_per_kw": "Total EPC capex per kW in USD before VAT, incl. contingency.",
        "generation.capacity_factor_pct": "Expected long-term annual net capacity factor (%)"
    }

RETURNS:
    Explanatory string, or "" if not mapped.
"""

def param_narrative_lookup(variable_name: str, doc_yaml: dict) -> str:
    """Look up a doc/explanation string for a variable (for use in table/tooltip/export)."""
    return doc_yaml.get(variable_name, "")
