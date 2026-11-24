"""Model code and its scripts name no site (#1759, #1775).

The model is universal: a site's name, its scenario and config files, its equipment IDs and
its coordinates come from the scenario YAML or other configuration. The owner ruled on
2026-11-16 that all code must be available to any scenario, so the scripts, the feasibility
reproduction kit and the analysis tools are held to the same rule as the model (#1775). This
lint reads every string and number literal in that code, skipping docstrings and the text of
raised exceptions and log calls, and refuses:

- ``site-name``: an unambiguous site or place name (Blue Whale, Kalpitiya, Mannar, Puttalam,
  Norochcholai, Mullikulam, Kolonnawa, Sri Jayewardenepura Kotte, Battaramulla, Colombo, or
  "Dutch Bay" spelled as two words);
- ``site-path``: a path to a scenario file, other than the ``scenarios/example`` placeholder
  used in usage strings, or any YAML file named for a site;
- ``site-location``: the bare location value ``"dutchbay"``;
- ``site-equipment``: the met-mast ID ``617725``;
- ``coordinate``: a float that looks like a coordinate in the region (a longitude between
  79.5 and 82.0 with three or more decimals, or a latitude between 5.8 and 10.0 with four or
  more), or a "lat, lon" pair in a string.

The product's own name is not a site: ``dutchbay.*`` schema IDs, ``DUTCHBAY_*`` environment
variables, ``dutchbay_*`` file prefixes and "DutchBay" titles stay. ``ALLOWED`` lists the
literals that remain, each with the work item that removes it or the reason it stays. An
entry that no longer matches anything fails the test, so the list only shrinks.
``ALLOWED_FILES`` waives a file whole, with its exact count of site literals pinned, so a
new literal in a waived file fails as well.
"""

from __future__ import annotations

import ast
import re
from collections import Counter
from pathlib import Path
from typing import Dict, Iterator, List, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
MODEL_DIRS = (
    "analytics",
    "finance",
    "solar_resource",
    "wind_resource",
    "app",
    "api",
    # #1775: the code that runs the model is held to the same rule.
    "monte_carlo",
    "scripts",
    "analysis_tools",
    "feasibility_reproduce",
)
MODEL_FILES = ("run_full_pipeline_v14.py", "run_scenario_analytics_v14.py")

_SITE_NAME = re.compile(
    r"blue[ _-]?whale|kalpitiya|mannar|puttalam|norochcholai|mullikulam|dutch bay"
    r"|kolonnawa|kotte|jayewardenepura|battaramulla|colombo",
    re.IGNORECASE,
)
_SITE_YAML = re.compile(r"(dutchbay|kalpitiya|mannar|blue_whale)[\w.-]*\.ya?ml", re.I)
_SCENARIO_PATH = re.compile(r"(^|[\s'\"=/])scenarios/(?!example)[\w./-]+\.ya?ml")
_LAT_LON = re.compile(r"\b(?:[5-9]|10)\.\d{3,}\s*,\s*(?:79|8[01])\.\d{3,}")
_LOG_METHODS = {"debug", "info", "warning", "error", "exception", "critical"}

#: (repository-relative path, rule, the literal's opening text) -> why it stays.
ALLOWED: Dict[Tuple[str, str, str], str] = {
    (
        "analytics/grid/curtailment_qsts.py",
        "site-name",
        "Not the CEB Kalpitiya/Puttalam feeder and not site-representative.",
    ): "synthetic QSTS disclaimer",
    (
        "app/reports/grid_screening_emit.py",
        "site-name",
        "SYNTHETIC COUNTERFACTUAL — NOT SITE-REPRESENTATIVE EVIDENCE.",
    ): "synthetic QSTS disclaimer naming the real feeder it is not",
    # #1775: the scripts and tools.
    (
        "scripts/01_github_repo_scanner.py",
        "site-location",
        "dutchbay",
    ): "the product's own package name in an import classifier, not a site",
    (
        "scripts/dutchbay_cleanup_analyzer.py",
        "site-path",
        "dutchbay_lendercase_2025Q3.yaml",
    ): "repository-maintenance list of retired file names it looks for",
    (
        "scripts/validate_f5_02_lender_return.py",
        "site-path",
        "DUTCHBAY_F5_02_LENDER_CONFIRMATION_TEMPLATE_v1.yaml",
    ): "the product's lender-confirmation template file, not a site",
    (
        "analysis_tools/f5_02_lender_return.py",
        "site-path",
        "DUTCHBAY_F5_02_LENDER_CONFIRMATION_TEMPLATE_v1.yaml",
    ): "the product's lender-confirmation template file, not a site",
    (
        "feasibility_reproduce/lib/mc_run.py",
        "site-path",
        "scenarios/dutchbay_lendercase_2025Q4.yaml",
    ): "the reproduction kit re-runs one published study, on that study's own case",
    (
        "feasibility_reproduce/lib/run_global_sa.py",
        "site-path",
        "scenarios/dutchbay_lendercase_2025Q4.yaml",
    ): "the reproduction kit re-runs one published study, on that study's own case",
    (
        "feasibility_reproduce/lib/wind_provenance.py",
        "site-path",
        "dutchbay_lendercase_2025Q4.yaml",
    ): "the reproduction kit re-runs one published study, on that study's own case",
}

_BLUE_WHALE_RUNNER = (
    "Blue Whale runner (#1775): its config, scenario and schema names move to the scenario "
    "blocks and generic names with U2 to U6 of the #1754 plan"
)

#: Files waived whole, each with its pinned count of site literals and the reason they stay.
#: The count is exact, so a new site literal in a waived file fails and a removed one must
#: lower the pin: the waiver only shrinks.
ALLOWED_FILES: Dict[str, Tuple[int, str]] = {
    "scripts/run_blue_whale_capex_solar_resource_v14.py": (13, _BLUE_WHALE_RUNNER),
    "scripts/run_blue_whale_met_mast_transfer_v14.py": (14, _BLUE_WHALE_RUNNER),
    "scripts/run_blue_whale_solar_bess_v14.py": (7, _BLUE_WHALE_RUNNER),
    "scripts/run_blue_whale_wind_siting_v14.py": (5, _BLUE_WHALE_RUNNER),
    "analytics/grid/synthetic_feeder_placeholder.py": (
        8,
        "labelled synthetic grid oracle, frozen under #1429 G04: its disclaimers name the "
        "real feeder it is not, and its frozen inputs cite their source files",
    ),
}


def _allowed(rel: str, rule: str, literal: str) -> bool:
    return any(
        rel == a_rel and rule == a_rule and literal.startswith(a_text)
        for a_rel, a_rule, a_text in ALLOWED
    )


def _model_files() -> List[Path]:
    files = [p for d in MODEL_DIRS for p in sorted((REPO_ROOT / d).rglob("*.py"))]
    files += [REPO_ROOT / f for f in MODEL_FILES]
    return [p for p in files if "tests" not in p.relative_to(REPO_ROOT).parts]


def _skipped_nodes(tree: ast.AST) -> Set[int]:
    skipped: Set[int] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            skipped.add(id(node.value))  # a docstring or a bare string comment
        body = getattr(node, "body", None)
        if isinstance(
            node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ) and isinstance(body, list):
            first = body[0] if body else None
            if (
                isinstance(first, ast.Expr)
                and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)
            ):
                skipped.add(id(first.value))
        if isinstance(node, ast.Raise) and node.exc is not None:
            skipped.update(id(sub) for sub in ast.walk(node.exc))
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in _LOG_METHODS
        ):
            skipped.update(id(sub) for sub in ast.walk(node))
    return skipped


def _string_rules(value: str) -> Iterator[str]:
    if _SITE_NAME.search(value):
        yield "site-name"
    if _SITE_YAML.search(value) or _SCENARIO_PATH.search(value):
        yield "site-path"
    if value.strip().lower() == "dutchbay":
        yield "site-location"
    if "617725" in value:
        yield "site-equipment"
    if _LAT_LON.search(value):
        yield "coordinate"


def _float_is_coordinate(source: str, value: float) -> bool:
    decimals = len(source.split(".", 1)[1]) if "." in source else 0
    if 79.5 <= value <= 82.0 and decimals >= 3:
        return True
    return 5.8 <= value <= 10.0 and decimals >= 4


def find_site_literals(path: Path) -> List[Tuple[str, str, str, int]]:
    """Return ``(relative path, rule, literal, line)`` for each site literal in ``path``."""
    rel = path.relative_to(REPO_ROOT).as_posix()
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text)
    skipped = _skipped_nodes(tree)
    found: List[Tuple[str, str, str, int]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or id(node) in skipped:
            continue
        if isinstance(node.value, str):
            for rule in _string_rules(node.value):
                found.append((rel, rule, node.value, node.lineno))
        elif isinstance(node.value, float):
            source = ast.get_source_segment(text, node) or ""
            if _float_is_coordinate(source, node.value):
                found.append((rel, "coordinate", source, node.lineno))
    return found


def _all_findings() -> List[Tuple[str, str, str, int]]:
    return [hit for path in _model_files() for hit in find_site_literals(path)]


def test_model_code_holds_no_site_literal() -> None:
    offenders = [
        f"{rel}:{line} [{rule}] {literal[:80]!r}"
        for rel, rule, literal, line in _all_findings()
        if rel not in ALLOWED_FILES and not _allowed(rel, rule, literal)
    ]
    assert not offenders, (
        "site-specific literals in model code (take them from the scenario or "
        "configuration, #1759):\n" + "\n".join(offenders)
    )


def test_allow_list_has_no_stale_entry() -> None:
    findings = _all_findings()
    stale = sorted(
        str(key)
        for key in ALLOWED
        if not any(
            rel == key[0] and rule == key[1] and literal.startswith(key[2])
            for rel, rule, literal, _ in findings
        )
    )
    assert not stale, "remove allow-list entries that no longer match:\n" + "\n".join(
        stale
    )


def test_waived_files_hold_exactly_their_pinned_count() -> None:
    counts = Counter(rel for rel, *_ in _all_findings())
    drift = sorted(
        f"{rel}: pinned {pinned}, found {counts[rel]}"
        for rel, (pinned, _) in ALLOWED_FILES.items()
        if counts[rel] != pinned
    )
    assert not drift, (
        "a waived file's site literals changed: a new one must come from configuration, "
        "and a removed one lowers the pin (remove the entry at 0):\n" + "\n".join(drift)
    )


def test_rules_catch_each_kind_of_site_literal(tmp_path: Path) -> None:
    """Negative control: each rule fires on a planted literal and spares the product."""
    probe = REPO_ROOT / "analytics" / "_site_literal_probe_1759.py"
    probe.write_text(
        "\n".join(
            [
                '"""Docstring naming Kalpitiya is fine."""',
                'A = "Kalpitiya"',
                'B = "scenarios/some_site_case.yaml"',
                'C = "dutchbay"',
                'D = "mast 617725"',
                "E = 79.8312",
                'F = "8.0612, 79.8312"',
                'G = "dutchbay.feasibility_report_package.v1"',
                'H = "DUTCHBAY_JWT_SECRET"',
                'I = "scenarios/example.yaml"',
                'J = "Colombo"',
                'K = "kolonnawa"',
                'L = "Kotte"',
                'M = "Jayewardenepura"',
                'N = "Battaramulla"',
                "def f() -> None:",
                '    raise ValueError("Mannar in a message is fine")',
                "",
            ]
        ),
        encoding="utf-8",
    )
    try:
        rules = sorted(rule for _, rule, _, _ in find_site_literals(probe))
    finally:
        probe.unlink()
    assert rules == sorted(
        ["site-name"] * 6
        + [
            "site-path",
            "site-location",
            "site-equipment",
            "coordinate",
            "coordinate",
        ]
    )
