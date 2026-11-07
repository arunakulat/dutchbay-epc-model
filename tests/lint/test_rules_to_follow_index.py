"""Keep the rule IDs and titles in ``Rules to follow.md`` equal to the canonical CSV.

``Rules to follow.md`` summarises the GWTF ruleset for agents, which cite rule IDs from it.
#1549 shipped it with meanings filed under the wrong IDs (JSON-first output under ``CLI-02``,
the VERSION bump under ``FIN-01``, the coverage gate under ``TEST-05``) and a category count
the CSV does not have. These guards pin what can be checked mechanically: the §3.0 index
must list every CSV rule with its exact category and title in CSV order, the rule and
category counts must match, every bold heading that pairs a rule ID with a title must carry
that ID's exact CSV title, and every backticked rule ID must exist. The prose after a
heading is a summary, and review checks it; the CSV text governs.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CANONICAL_RULESET = REPO_ROOT / "go_with_the_flow_rules_v3_0_clean.csv"
RULES_TO_FOLLOW = REPO_ROOT / "Rules to follow.md"

_INDEX_ROW = re.compile(r"^\| `([^`|]+)` \| ([^|]+?) \| ([^|]+?) \|$", re.MULTILINE)
_TITLED_HEADING = re.compile(r"\*\*`([A-Za-z0-9_-]+)`: ([^*]+)\*\*")
_RULE_ID_TOKEN = re.compile(
    r"`((?:[A-Z]+-\d{2})|(?:R\d{1,2})|(?:SPRINT[A-Z0-9_]*_R1))`"
)
_COUNT_CLAIM = re.compile(r"(\d+) active rules across (\d+) categories")


def _rows() -> list[dict[str, str]]:
    """Load the canonical ruleset rows in file order."""
    with CANONICAL_RULESET.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _problems(text: str, rows: list[dict[str, str]]) -> list[str]:
    """Return every mismatch between the document's rule references and the CSV."""
    problems: list[str] = []
    by_id = {row["rule_id"]: row for row in rows}

    expected = [(r["rule_id"], r["category"], r["title"]) for r in rows]
    found = [tuple(match.groups()) for match in _INDEX_ROW.finditer(text)]
    if found != expected:
        missing = [row for row in expected if row not in found]
        extra = [row for row in found if row not in expected]
        problems.append(
            f"rule index differs from the CSV: missing={missing[:5]} extra={extra[:5]}"
            + ("" if missing or extra else " (order differs)")
        )

    active = sum(1 for row in rows if row["status"] == "active")
    categories = len({row["category"] for row in rows})
    claims = _COUNT_CLAIM.findall(text)
    if not claims:
        problems.append("no 'N active rules across M categories' statement")
    for rules_claimed, categories_claimed in claims:
        if (int(rules_claimed), int(categories_claimed)) != (active, categories):
            problems.append(
                f"count claim {rules_claimed}/{categories_claimed} != CSV {active}/{categories}"
            )

    for rule_id, title in _TITLED_HEADING.findall(text):
        if rule_id not in by_id:
            problems.append(f"heading names unknown rule {rule_id}")
        elif title.strip() != by_id[rule_id]["title"]:
            problems.append(
                f"heading {rule_id} title {title.strip()!r} != CSV {by_id[rule_id]['title']!r}"
            )

    for rule_id in sorted(set(_RULE_ID_TOKEN.findall(text))):
        if rule_id not in by_id:
            problems.append(f"unknown rule ID `{rule_id}`")
    return problems


def _document() -> str:
    """Read the committed document."""
    return RULES_TO_FOLLOW.read_text(encoding="utf-8")


def test_rules_to_follow_matches_the_canonical_ruleset() -> None:
    """The index, counts, titled headings and rule IDs all agree with the CSV."""
    assert _problems(_document(), _rows()) == []


def test_rules_to_follow_titles_its_headings() -> None:
    """The guard has something to check: most rules carry a titled heading."""
    titled = {rule_id for rule_id, _ in _TITLED_HEADING.findall(_document())}
    assert len(titled) >= 40


def _swap_first(text: str, old: str, new: str) -> str:
    assert old in text, old
    return text.replace(old, new, 1)


@pytest.mark.parametrize(
    "mutate",
    [
        pytest.param(
            lambda t, rows: _swap_first(
                t,
                f"| `CLI-02` | {rows['CLI-02']['category']} | {rows['CLI-02']['title']} |",
                f"| `CLI-02` | {rows['CLI-02']['category']} | JSON-first outputs for automation |",
            ),
            id="index-title-swapped",
        ),
        pytest.param(
            lambda t, rows: _swap_first(
                t,
                f"| `R19` | {rows['R19']['category']} | {rows['R19']['title']} |\n",
                "",
            ),
            id="index-row-dropped",
        ),
        pytest.param(
            lambda t, rows: _swap_first(
                t, "across 41 categories", "across 19 categories"
            ),
            id="category-count-wrong",
        ),
        pytest.param(
            lambda t, rows: _swap_first(
                t,
                "**`CLI-03`: JSON-first outputs for automation**",
                "**`CLI-03`: No argparse anywhere in repo**",
            ),
            id="heading-title-misattributed",
        ),
        pytest.param(
            lambda t, rows: _swap_first(
                t,
                "**`FIN-01`: Numeric robustness and IRR/NPV safety**",
                "**`FIN-03`: Numeric robustness and IRR/NPV safety**",
            ),
            id="heading-unknown-rule",
        ),
        pytest.param(
            lambda t, rows: t + "\nSee `TEST-09`.\n",
            id="unknown-rule-token",
        ),
    ],
)
def test_rules_to_follow_guard_rejects_drift(mutate) -> None:  # type: ignore[no-untyped-def]
    """Observe each check fire on a document that drifts from the CSV."""
    rows = _rows()
    by_id = {row["rule_id"]: row for row in rows}
    mutated = mutate(_document(), by_id)
    assert _problems(mutated, rows) != []
