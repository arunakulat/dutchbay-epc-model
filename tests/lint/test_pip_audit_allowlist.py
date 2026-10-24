"""SECDEP-01 fence: a suppressed advisory must declare what would lift it.

#1369 accepted eight ``pillow 12.3.0`` advisories on a finding that was true when it
was written: every published ``streamlit`` capped ``pillow<13``. ``streamlit 1.66.1``
lifted that cap twelve minutes after the merge, and the same unchanged pin carried
eight advisories that evening and twenty-four by morning. Neither event needed a
commit in this repository. An accepted advisory is a dated claim about the world, so
it expires on its own, and #1372 had to clear the gate on merit because nothing here
recorded what the suppression was waiting for.

This fence reads the SHAPE of each entry's declaration, not the index. It cannot know
that a cap has lifted - only that an entry failed to say what would lift it. Checking
the claim itself is ``RELEASING.md`` step 2 and the reviewer's job.

The live allowlist is EMPTY (#1372 emptied it), so the test against the real
``Makefile`` is vacuous today and will stay vacuous until someone adds an entry. A
guard that cannot fail is worth nothing - that is the defect recorded as P-9 on
dutchbay-epc-model#1353 - so the fence is exercised here against crafted allowlists
instead: one well-formed entry that must audit clean, and one negative control per
field that must not.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MAKEFILE = REPO_ROOT / "Makefile"
VARIABLE = "PIP_AUDIT_IGNORES"

# The declaration SECDEP-01 requires, one line per suppressed advisory, in the comment
# block directly above the assignment. Every field is captured separately so a blank or
# placeholder value fails on its own rather than passing because the line matched.
ANNOTATION = re.compile(
    r"^#\s*ignore-vuln:\s*(?P<advisory>[A-Za-z][-A-Za-z0-9_.]*)"
    r"\s*\|\s*package:\s*(?P<package>[^|]*)"
    r"\|\s*cap:\s*(?P<cap>[^|]*)"
    r"\|\s*lifted-by:\s*(?P<lifted_by>[^|]*)"
    r"\|\s*reason:\s*(?P<reason>.*)$"
)
SUPPRESSION = re.compile(r"--ignore-vuln[=\s]+([A-Za-z][-A-Za-z0-9_.]*)")
ASSIGNMENT = re.compile(rf"^{VARIABLE}\s*[:?+]?=")
PACKAGE_PIN = re.compile(r"^[A-Za-z0-9][-A-Za-z0-9_.]*==\S+$")
VERSION = re.compile(r"\d+(?:\.\d+)+")
SPECIFIER = re.compile(r"[<>=!~]")
# A cap with no published fix says so in these words rather than being left blank.
NO_FIX = "no-fix-published"
PLACEHOLDERS = frozenset({"", "-", "?", "n/a", "na", "none", "tbd", "todo", "unknown"})
# The contract text the Makefile must carry where an entry would be added, so the next
# author reads the shape at the switch rather than only in this test.
CONTRACT = (
    "SECDEP-01",
    "ignore-vuln:",
    "lifted-by:",
    NO_FIX,
    "tests/lint/test_pip_audit_allowlist.py",
)


def _assignment_span(lines: list[str]) -> tuple[int, int] | None:
    """Return the inclusive line span of the assignment, following continuations."""
    for index, line in enumerate(lines):
        if ASSIGNMENT.match(line):
            end = index
            while end + 1 < len(lines) and lines[end].rstrip().endswith("\\"):
                end += 1
            return index, end
    return None


def _preceding_comment_block(lines: list[str], start: int) -> list[str]:
    """Return the maximal run of comment lines directly above ``start``."""
    first = start
    while first - 1 >= 0 and lines[first - 1].lstrip().startswith("#"):
        first -= 1
    return lines[first:start]


def audit(makefile_text: str) -> list[str]:
    """Return one message per SECDEP-01 violation; an empty list means compliant."""
    lines = makefile_text.splitlines()
    span = _assignment_span(lines)
    if span is None:
        return [f"{VARIABLE} assignment not found in the Makefile"]

    start, end = span
    suppressed: list[str] = []
    for line in lines[start : end + 1]:
        suppressed.extend(SUPPRESSION.findall(line))

    annotated: dict[str, re.Match[str]] = {}
    violations: list[str] = []
    for line in _preceding_comment_block(lines, start):
        match = ANNOTATION.match(line.strip())
        if match is None:
            continue
        advisory = match.group("advisory")
        if advisory in annotated:
            violations.append(f"{advisory}: declared more than once")
            continue
        annotated[advisory] = match

    for advisory in suppressed:
        if advisory not in annotated:
            violations.append(
                f"{advisory}: suppressed with no `# ignore-vuln:` declaration above "
                f"{VARIABLE}"
            )
    for advisory in annotated:
        if advisory not in suppressed:
            violations.append(
                f"{advisory}: declared but no longer suppressed - remove the "
                "declaration with the entry"
            )

    for advisory, match in annotated.items():
        if advisory not in suppressed:
            continue
        package = match.group("package").strip()
        cap = match.group("cap").strip()
        lifted_by = match.group("lifted_by").strip()
        reason = match.group("reason").strip()

        if not PACKAGE_PIN.match(package):
            violations.append(
                f"{advisory}: package must name the pinned version as `name==version`, "
                f"got {package!r}"
            )
        if cap.casefold() in PLACEHOLDERS:
            violations.append(f"{advisory}: cap is empty or a placeholder, got {cap!r}")
        elif cap != NO_FIX and not SPECIFIER.search(cap):
            violations.append(
                f"{advisory}: cap must give the forcing constraint as a version "
                f"specifier, or `{NO_FIX}` where upstream has published no fix, got "
                f"{cap!r}"
            )
        if lifted_by.casefold() in PLACEHOLDERS - {"unknown"}:
            violations.append(
                f"{advisory}: lifted-by is empty or a placeholder - name the release "
                f"that would lift the cap, or `unknown`, got {lifted_by!r}"
            )
        elif lifted_by.casefold() != "unknown" and not VERSION.search(lifted_by):
            violations.append(
                f"{advisory}: lifted-by must name a release version, or `unknown`, got "
                f"{lifted_by!r}"
            )
        if reason.casefold() in PLACEHOLDERS or len(reason) < 12:
            violations.append(
                f"{advisory}: reason must say why the suppression is defensible, got "
                f"{reason!r}"
            )

    return violations


COMPLIANT = """\
# pip-audit allowlist.
# ignore-vuln: PYSEC-2026-4320 | package: certifi==2026.7.22 | cap: requests<2.33 | \
lifted-by: certifi 2026.10.19 | reason: no installable certifi clears it under the cap
PIP_AUDIT_IGNORES := --ignore-vuln PYSEC-2026-4320
"""
EMPTY = "# pip-audit allowlist - EMPTY.\nPIP_AUDIT_IGNORES :=\n"


def _mutate(field: str, value: str) -> str:
    """Rewrite one field of the compliant fixture, leaving the entry otherwise intact."""
    return re.sub(rf"(\| {field}: )[^|\n]*", rf"\g<1>{value} ", COMPLIANT, count=1)


def test_the_live_allowlist_satisfies_secdep_01() -> None:
    """The real Makefile must carry a lift condition for every suppressed advisory."""
    assert audit(MAKEFILE.read_text(encoding="utf-8")) == []


def test_the_makefile_documents_the_declaration_shape() -> None:
    """Keep the contract next to the switch, not only in this module."""
    makefile = MAKEFILE.read_text(encoding="utf-8")
    for control in CONTRACT:
        assert control in makefile


def test_an_empty_allowlist_is_compliant() -> None:
    """#1372 emptied the variable; that state must stay green, not merely silent."""
    assert audit(EMPTY) == []


def test_a_well_formed_entry_is_compliant() -> None:
    """Positive control: the fence must be able to PASS with a populated allowlist."""
    assert audit(COMPLIANT) == []


@pytest.mark.parametrize(
    ("makefile_text", "expected"),
    [
        pytest.param(
            COMPLIANT.replace(
                "# ignore-vuln: PYSEC-2026-4320 | package: certifi==2026.7.22 | "
                "cap: requests<2.33 | lifted-by: certifi 2026.10.19 | reason: no "
                "installable certifi clears it under the cap\n",
                "",
            ),
            "no `# ignore-vuln:` declaration",
            id="entry with no declaration at all",
        ),
        pytest.param(_mutate("cap", ""), "cap is empty", id="cap blank"),
        pytest.param(_mutate("cap", "TBD"), "cap is empty", id="cap placeholder"),
        pytest.param(
            _mutate("cap", "waiting on requests"),
            "forcing constraint as a version specifier",
            id="cap names no specifier",
        ),
        pytest.param(
            _mutate("lifted-by", ""), "lifted-by is empty", id="lifted-by blank"
        ),
        pytest.param(
            _mutate("lifted-by", "a future release"),
            "lifted-by must name a release version",
            id="lifted-by names no version",
        ),
        pytest.param(
            _mutate("package", "certifi"), "name==version", id="package not pinned"
        ),
        pytest.param(_mutate("reason", "capped"), "reason must say", id="reason thin"),
        pytest.param(
            EMPTY.replace(
                "# pip-audit allowlist - EMPTY.",
                "# ignore-vuln: PYSEC-2026-4320 | package: certifi==2026.7.22 | cap: "
                "requests<2.33 | lifted-by: certifi 2026.10.19 | reason: left behind "
                "when the entry went",
            ),
            "no longer suppressed",
            id="declaration outlives its entry",
        ),
        pytest.param(
            COMPLIANT.replace("PIP_AUDIT_IGNORES := ", "OTHER := "),
            "assignment not found",
            id="variable renamed away",
        ),
    ],
)
def test_the_fence_rejects_an_undeclared_suppression(
    makefile_text: str, expected: str
) -> None:
    """Negative controls: one per field, observed failing rather than assumed to."""
    violations = audit(makefile_text)
    assert violations, "the fence passed a non-compliant allowlist"
    assert any(expected in violation for violation in violations), violations
