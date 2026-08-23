"""Fail a pull request whose verification receipts are missing or silent (`VERIFY-01`).

A claimed check without a receipt is not a check. The pull-request template collects the
command and its result for each check, and requires a check that was *not* run to be
declared as ``not run - <reason>`` rather than left blank. This script is what makes that
template load-bearing instead of decorative: it reads the pull-request body and fails when
the receipts table is absent, empty, or carries a row whose Result cell is silent.

Silence is the target. An empty cell and a leftover placeholder are indistinguishable from
"I did not run this and would rather not say", which is exactly the state `VERIFY-01`
exists to make impossible. A declared ``not run - <reason>`` passes: declaring a gap is the
point, and the reviewer can then judge it.

The script never inspects *which* checks were run or whether their results were green -- CI
itself remains the merge authority for that. It only enforces that the record is complete
and explicit.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from typing import Final, Sequence

#: Bot authors do not use the human template; holding them to it would fail every
#: dependency bump for a reason no human could act on.
EXEMPT_AUTHORS: Final[frozenset[str]] = frozenset(
    {"dependabot[bot]", "github-actions[bot]", "copilot[bot]", "renovate[bot]"}
)

#: Cell contents that say nothing. ``n/a`` is deliberately included: the template asks for
#: a reason, and "n/a" is a refusal to give one.
_SILENT_CELLS: Final[frozenset[str]] = frozenset(
    {"", "...", "…", "-", "--", "—", "n/a", "na", "none", "tbd", "todo", "?", "x"}
)

_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_SEPARATOR_CELL = re.compile(r"^:?-{2,}:?$")


def _strip_markup(cell: str) -> str:
    """Return the cell's text with HTML comments and inline emphasis removed."""
    text = _COMMENT.sub("", cell)
    for token in ("`", "*", "_"):
        text = text.replace(token, "")
    return text.strip()


def _is_silent(cell: str) -> bool:
    """Return True when a Result cell records nothing a reviewer could act on."""
    text = _strip_markup(cell).lower()
    if text in _SILENT_CELLS:
        return True
    # The template's own worked example, left in place unedited.
    return text.startswith("e.g.")


def _split_row(line: str) -> list[str] | None:
    """Split one markdown table row into cells, or return None if it is not a row."""
    stripped = line.strip()
    if not stripped.startswith("|"):
        return None
    return [cell.strip() for cell in stripped.strip("|").split("|")]


def _is_separator(cells: Sequence[str]) -> bool:
    """Return True for a markdown header-separator row (``|---|---|``)."""
    return bool(cells) and all(_SEPARATOR_CELL.match(cell.strip()) for cell in cells)


def find_receipts_table(body: str) -> tuple[list[list[str]], int] | None:
    """Locate the receipts table and the index of its Result column.

    Args:
        body: The pull-request description.

    Returns:
        ``(data_rows, result_index)``, or None when no such table is present.
    """
    lines = body.splitlines()
    for index, line in enumerate(lines):
        header = _split_row(line)
        if header is None:
            continue
        lowered = [_strip_markup(cell).lower() for cell in header]
        if not any(cell.startswith("check") for cell in lowered):
            continue
        result_index = next(
            (i for i, cell in enumerate(lowered) if cell.startswith("result")), None
        )
        if result_index is None:
            continue
        rows: list[list[str]] = []
        for following in lines[index + 1 :]:
            cells = _split_row(following)
            if cells is None:
                break
            if _is_separator(cells):
                continue
            rows.append(cells)
        return rows, result_index
    return None


def evaluate(body: str, author: str = "") -> tuple[int, str]:
    """Judge one pull-request body against `VERIFY-01`.

    Args:
        body: The pull-request description.
        author: The pull-request author's login, for the bot exemption.

    Returns:
        ``(exit_code, message)`` where 0 means the receipts are complete.
    """
    if author in EXEMPT_AUTHORS:
        return 0, f"VERIFY-01: {author} is exempt (bot-authored pull request)."

    found = find_receipts_table(body)
    if found is None:
        return 1, (
            "VERIFY-01: no verification receipts table found in the pull-request body.\n"
            "Restore the 'Verification - receipts, not claims' table from "
            ".github/pull_request_template.md and record, for each check, the command you "
            "ran and its result. A check you did not run is declared as "
            "'not run - <reason>', never left blank."
        )

    rows, result_index = found
    if not rows:
        return 1, (
            "VERIFY-01: the receipts table has no rows. At least one check must be "
            "recorded, even if every row declares 'not run - <reason>'."
        )

    silent: list[str] = []
    for cells in rows:
        result = cells[result_index] if result_index < len(cells) else ""
        if _is_silent(result):
            label = _strip_markup(cells[0]) if cells else "(unnamed row)"
            silent.append(f"  - {label or '(unnamed row)'}: Result cell is empty")

    if silent:
        return 1, (
            "VERIFY-01: the receipts table has silent Result cells.\n"
            + "\n".join(silent)
            + "\n\nRecord the result of each check, or declare it explicitly as "
            "'not run - <reason>'. A blank cell is indistinguishable from an "
            "undisclosed gap, which is the failure this rule exists to prevent."
        )

    return 0, f"VERIFY-01: {len(rows)} receipt row(s) recorded, none silent."


def main(argv: Sequence[str] | None = None) -> int:
    """Read the pull-request body from the environment or a file and judge it."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--body-file",
        help="Read the pull-request body from this file instead of $PR_BODY.",
    )
    parser.add_argument(
        "--author",
        default=os.environ.get("PR_AUTHOR", ""),
        help="Pull-request author login (defaults to $PR_AUTHOR).",
    )
    args = parser.parse_args(argv)

    if args.body_file:
        with open(args.body_file, encoding="utf-8") as handle:
            body = handle.read()
    else:
        body = os.environ.get("PR_BODY", "")

    code, message = evaluate(body, args.author)
    print(message)
    return code


if __name__ == "__main__":
    sys.exit(main())
