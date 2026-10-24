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
import shlex
import subprocess
from pathlib import Path

import pytest
from packaging.requirements import InvalidRequirement, Requirement
from packaging.version import InvalidVersion, Version

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
ADVISORY_ID = re.compile(r"^[A-Za-z][-A-Za-z0-9_.]*$")
ASSIGNMENT = re.compile(
    rf"(?P<modifiers>(?:(?:override|export|private)\s+)*)"
    rf"{VARIABLE}\s*(?P<operator>:::=|::=|:=|\?=|\+=|!=|=)\s*(?P<value>.*)$"
)
DEFINE_ASSIGNMENT = re.compile(rf"^\s*(?:override\s+)?define\s+{VARIABLE}(?:\s|$)")
VERSION = re.compile(r"\d+(?:\.\d+)+")
# A cap with no published fix says so in these words rather than being left blank.
NO_FIX = "no-fix-published"
PLACEHOLDERS = frozenset({"", "-", "?", "n/a", "na", "none", "tbd", "todo", "unknown"})
# The exact contiguous contract the Makefile must carry in the comment block directly
# above the assignment. Token-presence checks are too weak: scattered words are not an
# instruction and were the P-10 failure mode.
CONTRACT_LINES = (
    "# SECDEP-01 canonical grammar (the fence rejects every other assignment shape):",
    "# Keep exactly one literal `PIP_AUDIT_IGNORES :=` assignment; do not use Make expansion or `+=`.",
    "# Each suppression has one physical declaration line in this comment block:",
    "# ignore-vuln: <ADVISORY-ID> | package: <name>==<version> | cap: <name><specifier> | lifted-by: <name> <version>|unknown | reason: <why the suppression is defensible>",
)


def _assignments(lines: list[str]) -> list[tuple[int, int, str, str, str]]:
    """Return every logical assignment, including append/override variants."""
    assignments: list[tuple[int, int, str, str, str]] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if line.lstrip().startswith("#"):
            index += 1
            continue
        if DEFINE_ASSIGNMENT.match(line):
            assignments.append((index, index, "define", "define", ""))
            index += 1
            continue
        match = ASSIGNMENT.search(line)
        if match is None:
            index += 1
            continue

        start = index
        prefix = line[: match.start()].strip()
        parts = [match.group("value")]
        while parts[-1].rstrip().endswith("\\") and index + 1 < len(lines):
            parts[-1] = parts[-1].rstrip()[:-1]
            index += 1
            parts.append(lines[index].strip())
        assignments.append(
            (
                start,
                index,
                " ".join(
                    part for part in (prefix, match.group("modifiers").strip()) if part
                ),
                match.group("operator"),
                " ".join(part.strip() for part in parts),
            )
        )
        index += 1
    return assignments


def _preceding_comment_block(lines: list[str], start: int) -> list[str]:
    """Return the maximal run of comment lines directly above ``start``."""
    first = start
    while first - 1 >= 0 and lines[first - 1].lstrip().startswith("#"):
        first -= 1
    return lines[first:start]


def _has_contiguous_contract(comment_block: list[str]) -> bool:
    """Return whether the exact SECDEP-01 authoring contract is contiguous."""
    width = len(CONTRACT_LINES)
    return any(
        tuple(comment_block[index : index + width]) == CONTRACT_LINES
        for index in range(len(comment_block) - width + 1)
    )


def _valid_exact_pin(value: str) -> bool:
    """Require one valid PEP 440 exact pin on one ordinary package name."""
    try:
        requirement = Requirement(value)
    except InvalidRequirement:
        return False
    if (
        requirement.extras
        or requirement.marker is not None
        or requirement.url is not None
    ):
        return False
    specifiers = list(requirement.specifier)
    if len(specifiers) != 1 or specifiers[0].operator != "==":
        return False
    version = specifiers[0].version
    if "*" in version:
        return False
    try:
        Version(version)
    except InvalidVersion:
        return False
    return True


def _valid_named_cap(value: str) -> bool:
    """Require a valid named requirement carrying a non-empty version specifier."""
    try:
        requirement = Requirement(value)
    except InvalidRequirement:
        return False
    return (
        not requirement.extras
        and requirement.marker is None
        and requirement.url is None
        and bool(requirement.specifier)
    )


def _suppressed_ids(
    assignments: list[tuple[int, int, str, str, str]],
    violations: list[str],
) -> list[str]:
    """Parse effective literal ignore flags and fail closed on unsupported Make syntax."""
    suppressed: list[str] = []
    for start, _end, _modifiers, operator, value in assignments:
        if operator == "define":
            violations.append(
                f"{VARIABLE}: `define` assignments are unsupported; use one literal `:=`"
            )
            continue
        if "$" in value:
            violations.append(
                f"{VARIABLE} line {start + 1}: Make/shell expansion is not auditable; "
                "use literal advisory IDs"
            )
            continue
        try:
            tokens = shlex.split(value, comments=True, posix=True)
        except ValueError as exc:
            violations.append(
                f"{VARIABLE} line {start + 1}: invalid quoting in assignment: {exc}"
            )
            continue

        index = 0
        while index < len(tokens):
            token = tokens[index]
            advisory: str | None = None
            if token == "--ignore-vuln":
                if index + 1 >= len(tokens):
                    violations.append(
                        f"{VARIABLE} line {start + 1}: `--ignore-vuln` has no advisory ID"
                    )
                    index += 1
                    continue
                advisory = tokens[index + 1]
                index += 2
            elif token.startswith("--ignore-vuln="):
                advisory = token.partition("=")[2]
                index += 1
            elif "--ignore-vuln" in token:
                violations.append(
                    f"{VARIABLE} line {start + 1}: malformed ignore flag {token!r}"
                )
                index += 1
                continue
            else:
                index += 1
                continue

            if ADVISORY_ID.fullmatch(advisory) is None:
                violations.append(
                    f"{VARIABLE} line {start + 1}: invalid advisory ID {advisory!r}"
                )
                continue
            if advisory in suppressed:
                violations.append(f"{advisory}: suppressed more than once")
            suppressed.append(advisory)
    return suppressed


def audit(makefile_text: str) -> list[str]:
    """Return one message per SECDEP-01 violation; an empty list means compliant."""
    lines = makefile_text.splitlines()
    assignments = _assignments(lines)
    if not assignments:
        return [f"{VARIABLE} assignment not found in the Makefile"]

    violations: list[str] = []
    if len(assignments) != 1:
        violations.append(
            f"{VARIABLE} must have exactly one assignment, got {len(assignments)}"
        )
    start, _end, modifiers, operator, _value = assignments[0]
    if modifiers or operator != ":=":
        shape = " ".join(part for part in (modifiers, operator) if part)
        violations.append(
            f"{VARIABLE} must use one unmodified literal `:=` assignment, got {shape!r}"
        )

    comment_block = _preceding_comment_block(lines, start)
    if not _has_contiguous_contract(comment_block):
        violations.append(
            f"{VARIABLE}: contiguous SECDEP-01 authoring contract is missing or displaced"
        )

    suppressed = _suppressed_ids(assignments, violations)
    annotated: dict[str, re.Match[str]] = {}
    for line in comment_block:
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

        if not _valid_exact_pin(package):
            violations.append(
                f"{advisory}: package must be a valid exact pin as `name==version`, "
                f"got {package!r}"
            )
        if cap.casefold() in PLACEHOLDERS:
            violations.append(f"{advisory}: cap is empty or a placeholder, got {cap!r}")
        elif cap != NO_FIX and not _valid_named_cap(cap):
            violations.append(
                f"{advisory}: cap must be a valid named requirement with a non-empty "
                f"version specifier, or `{NO_FIX}` where upstream has published no "
                f"fix, got {cap!r}"
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


CONTRACT_TEXT = "\n".join(CONTRACT_LINES)
COMPLIANT = f"""\
{CONTRACT_TEXT}
# ignore-vuln: PYSEC-2026-4320 | package: certifi==2026.7.22 | cap: requests<2.33 | \
lifted-by: certifi 2026.10.19 | reason: no installable certifi clears it under the cap
PIP_AUDIT_IGNORES := --ignore-vuln PYSEC-2026-4320
"""
EMPTY = f"{CONTRACT_TEXT}\nPIP_AUDIT_IGNORES :=\n"


def _mutate(field: str, value: str) -> str:
    """Rewrite one field of the compliant fixture, leaving the entry otherwise intact."""
    return re.sub(
        rf"(^# ignore-vuln: PYSEC-2026-4320 .*\| {field}: )[^|\n]*",
        rf"\g<1>{value} ",
        COMPLIANT,
        count=1,
        flags=re.MULTILINE,
    )


def _replace_empty_assignment(replacement: str) -> str:
    """Replace the real assignment without touching its mention in the contract."""
    prefix, suffix = EMPTY.rsplit("PIP_AUDIT_IGNORES :=", 1)
    return prefix + replacement + suffix


def test_the_live_allowlist_satisfies_secdep_01() -> None:
    """The real Makefile must carry a lift condition for every suppressed advisory."""
    assert audit(MAKEFILE.read_text(encoding="utf-8")) == []


def test_the_makefile_documents_the_declaration_shape() -> None:
    """Keep the exact contiguous contract next to the switch."""
    assert audit(MAKEFILE.read_text(encoding="utf-8")) == []


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
            "valid named requirement",
            id="cap names no specifier",
        ),
        pytest.param(_mutate("cap", "<"), "valid named requirement", id="cap invalid"),
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
        pytest.param(
            _mutate("package", "demo==???"),
            "valid exact pin",
            id="package version invalid",
        ),
        pytest.param(_mutate("reason", "capped"), "reason must say", id="reason thin"),
        pytest.param(
            _replace_empty_assignment(
                "# ignore-vuln: PYSEC-2026-4320 | package: certifi==2026.7.22 | "
                "cap: requests<2.33 | lifted-by: certifi 2026.10.19 | reason: "
                "left behind when the entry went\nPIP_AUDIT_IGNORES :=",
            ),
            "no longer suppressed",
            id="declaration outlives its entry",
        ),
        pytest.param(
            COMPLIANT.replace("PIP_AUDIT_IGNORES := ", "OTHER := "),
            "assignment not found",
            id="variable renamed away",
        ),
        pytest.param(
            _replace_empty_assignment(
                "PIP_AUDIT_IGNORES := --ignore-vuln='CVE-2026-999999'",
            ),
            "suppressed with no",
            id="quoted effective id is still discovered",
        ),
        pytest.param(
            _replace_empty_assignment(
                "ADVISORY := CVE-2026-999999\n"
                "PIP_AUDIT_IGNORES := --ignore-vuln $(ADVISORY)",
            ),
            "expansion is not auditable",
            id="make indirection rejected",
        ),
        pytest.param(
            EMPTY + "PIP_AUDIT_IGNORES += --ignore-vuln CVE-2026-999999\n",
            "exactly one assignment",
            id="later append rejected",
        ),
        pytest.param(
            EMPTY + "audit: PIP_AUDIT_IGNORES += --ignore-vuln CVE-2026-999999\n",
            "exactly one assignment",
            id="target-specific append rejected",
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


def test_make_oracle_confirms_rejected_indirection_and_append_are_effective(
    tmp_path: Path,
) -> None:
    """Make proves the rejected spellings would really suppress advisories."""
    makefile_text = """\
ADVISORY := CVE-2026-999999
PIP_AUDIT_IGNORES := --ignore-vuln $(ADVISORY)
PIP_AUDIT_IGNORES += --ignore-vuln=GHSA-abcd-1234-zzzz
print:
\t@printf '%s\\n' "$(PIP_AUDIT_IGNORES)"
"""
    makefile = tmp_path / "Makefile"
    makefile.write_text(makefile_text, encoding="utf-8")
    completed = subprocess.run(
        ["make", "--no-print-directory", "-f", str(makefile), "print"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert completed.stdout.strip() == (
        "--ignore-vuln CVE-2026-999999 --ignore-vuln=GHSA-abcd-1234-zzzz"
    )
    violations = audit(makefile_text)
    assert any("exactly one assignment" in item for item in violations)
    assert any("expansion is not auditable" in item for item in violations)


@pytest.mark.parametrize("removed_line", CONTRACT_LINES)
def test_contract_guard_rejects_control_loss(removed_line: str) -> None:
    """Every line of the authoring contract is load-bearing."""
    mutated = EMPTY.replace(removed_line, "# REMOVED CONTRACT CONTROL", 1)
    assert any("contract is missing or displaced" in item for item in audit(mutated))


def test_contract_guard_rejects_reordering() -> None:
    """The contract is one contiguous instruction, not a bag of tokens."""
    first, second, *rest = CONTRACT_LINES
    reordered = "\n".join((second, first, *rest))
    mutated = EMPTY.replace(CONTRACT_TEXT, reordered, 1)
    assert any("contract is missing or displaced" in item for item in audit(mutated))


def test_contract_guard_rejects_displacement_from_the_switch() -> None:
    """A blank line separating the contract from the switch fails closed."""
    mutated = EMPTY.replace("\nPIP_AUDIT_IGNORES :=", "\n\nPIP_AUDIT_IGNORES :=", 1)
    assert any("contract is missing or displaced" in item for item in audit(mutated))
