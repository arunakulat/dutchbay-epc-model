"""Pin the `VERIFY-01` receipts checker, its workflow, and the template contract."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CHECKER = REPO_ROOT / "scripts" / "ci" / "check_pr_receipts.py"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "pr-receipts.yml"
TEMPLATE = REPO_ROOT / ".github" / "pull_request_template.md"


def _load() -> Any:
    """Import the checker by path (scripts/ is not an importable package)."""
    spec = importlib.util.spec_from_file_location("check_pr_receipts", CHECKER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


check = _load()

_TABLE_HEADER = "| Check | Command run | Result |\n|---|---|---|\n"


def _body(*rows: str) -> str:
    return "## Verification\n\n" + _TABLE_HEADER + "".join(rows)


def test_complete_receipts_pass() -> None:
    code, message = check.evaluate(
        _body("| Focused tests | `pytest -q` | `30 passed in 1.26s` |\n")
    )
    assert code == 0, message


def test_declared_not_run_passes() -> None:
    """Declaring a gap is the point of the rule, so it must not fail."""
    code, message = check.evaluate(
        _body(
            "| Grid Study | n/a | not run - docs-only change, no grid surface touched |\n"
        )
    )
    assert code == 0, message


@pytest.mark.parametrize(
    "cell", ["", " ", "`  `", "TBD", "n/a", "-", "*e.g.* `12 passed`"]
)
def test_silent_result_cells_fail(cell: str) -> None:
    """An empty cell or a leftover placeholder is indistinguishable from a hidden gap."""
    code, message = check.evaluate(_body(f"| Focused tests | `pytest -q` | {cell} |\n"))
    assert code == 1
    assert "silent Result cells" in message


def test_missing_table_fails() -> None:
    code, message = check.evaluate("## Summary\n\nI ran the tests and they passed.\n")
    assert code == 1
    assert "no verification receipts table" in message


def test_empty_table_fails() -> None:
    code, message = check.evaluate(_body())
    assert code == 1
    assert "no rows" in message


def test_bot_authors_are_exempt() -> None:
    code, _ = check.evaluate("no table at all", author="dependabot[bot]")
    assert code == 0


def test_result_column_is_located_by_name_not_position() -> None:
    """The table must survive a reordered or extended header."""
    body = (
        "| Result | Check | Command run |\n|---|---|---|\n"
        "| `30 passed` | Focused tests | `pytest -q` |\n"
    )
    assert check.evaluate(body)[0] == 0


def test_the_template_ships_a_parsable_receipts_table() -> None:
    """The shipped template must itself be readable by the checker.

    Guards the contract between the two files: a template edit that renames the columns
    would silently disable the gate for every future pull request.
    """
    found = check.find_receipts_table(TEMPLATE.read_text(encoding="utf-8"))
    assert found is not None, "PR template has no parsable Check/Result table"
    rows, _ = found
    assert rows, "the PR template's receipts table has no rows"


def test_workflow_passes_the_body_through_the_environment() -> None:
    """Script-injection guard: the body must never be interpolated into `run:`."""
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "run: python scripts/ci/check_pr_receipts.py" in workflow
    assert "types: [opened, edited, synchronize, reopened]" in workflow

    # Every reference to the author-controlled body must be an `env:` assignment. If one
    # ever appears anywhere else -- a `run:` line above all -- this fails.
    references = [
        line.strip()
        for line in workflow.splitlines()
        if "github.event.pull_request.body" in line
    ]
    assert references == ["PR_BODY: ${{ github.event.pull_request.body }}"], references
