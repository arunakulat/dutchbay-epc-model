"""Model code names no site (#1759).

The model is universal: a site's name, its scenario and config files, its equipment IDs and
its coordinates come from the scenario YAML or other configuration. This lint reads every
string and number literal in model code, skipping docstrings and the text of raised
exceptions and log calls, and refuses:

- ``site-name``: an unambiguous site or place name (Blue Whale, Kalpitiya, Mannar, Puttalam,
  Norochcholai, Mullikulam, or "Dutch Bay" spelled as two words);
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
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Dict, Iterator, List, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
MODEL_DIRS = ("analytics", "finance", "solar_resource", "wind_resource", "app", "api")
MODEL_FILES = ("run_full_pipeline_v14.py", "run_scenario_analytics_v14.py")

_SITE_NAME = re.compile(
    r"blue[ _-]?whale|kalpitiya|mannar|puttalam|norochcholai|mullikulam|dutch bay",
    re.IGNORECASE,
)
_SITE_YAML = re.compile(r"(dutchbay|kalpitiya|mannar|blue_whale)[\w.-]*\.ya?ml", re.I)
_SCENARIO_PATH = re.compile(r"(^|[\s'\"=/])scenarios/(?!example)[\w./-]+\.ya?ml")
_LAT_LON = re.compile(r"\b(?:[5-9]|10)\.\d{3,}\s*,\s*(?:79|8[01])\.\d{3,}")
_LOG_METHODS = {"debug", "info", "warning", "error", "exception", "critical"}

#: (repository-relative path, rule, the literal's opening text) -> why it stays.
ALLOWED: Dict[Tuple[str, str, str], str] = {
    # Site-named schema versions: renamed by U2 and U4 (#1578 universal ruling). #1725
    # already renamed the PV + BESS sizing ones.
    (
        "analytics/wind/wind_bess_options.py",
        "site-name",
        "blue_whale_wind_bess_options_v1",
    ): "U2",
    (
        "analytics/finance/blue_whale_fx_tenor_screening.py",
        "site-name",
        "blue_whale_fx_tenor_screening_v1",
    ): "U4, after #1730",
    (
        "analytics/finance/blue_whale_fx_tenor_screening.py",
        "site-path",
        "scenarios/dutchbay_basecase_2025Q4.yaml",
    ): "U4, after #1730 (which edits this file)",
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
}

#: Files whose site-named literals are all pending a named work item.
ALLOWED_FILES: Dict[str, str] = {
    "analytics/wind/blue_whale_equipment_parity.py": (
        "single-site adapter kept by #1755 for its byte-identical legacy output; its "
        "inputs move into the scenario with U2"
    ),
    "analytics/grid/synthetic_feeder_placeholder.py": (
        "labelled synthetic grid oracle, frozen under #1429 G04: its disclaimers name the "
        "real feeder it is not, and its frozen inputs cite their source files"
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
    files_with_hits = {rel for rel, *_ in findings}
    stale_files = sorted(f for f in ALLOWED_FILES if f not in files_with_hits)
    assert not stale_files, f"remove file allow-list entries: {stale_files}"


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
        [
            "site-name",
            "site-path",
            "site-location",
            "site-equipment",
            "coordinate",
            "coordinate",
        ]
    )
