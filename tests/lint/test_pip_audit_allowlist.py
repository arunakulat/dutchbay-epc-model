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

import argparse
import importlib
import os
import re
import shlex
import subprocess
import warnings
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
GENERIC_ASSIGNMENT = re.compile(r"^(?P<lhs>.*?)(?P<operator>:::=|::=|:=|\?=|\+=|!=|=)")
DYNAMIC_DEFINE = re.compile(r"^\s*(?:override\s+)?define\s+(?P<name>\S+)")
INCLUDE_DIRECTIVE = re.compile(r"^\s*(?:-include|sinclude|include)\b")
EVAL_FUNCTION = re.compile(r"\$(?:\(\s*eval(?:\s|,)|\{\s*eval(?:\s|,))")
ONESHELL_DIRECTIVE = re.compile(r"^\s*\.ONESHELL\s*:")
# GNU Make discards a recipe's exit status under `.IGNORE` - globally when it has no
# prerequisites, or for the targets it names - and under the `-i`/`--ignore-errors`
# flag, which a Makefile can set for itself through any of its flag variables. None of
# that changes a command, its arguments or the dry-run output, so it is invisible to
# every other control here; it is rejected outright instead.
#
# GNUMAKEFLAGS is in the alternation because Make reads `-i` from it exactly as from
# MAKEFLAGS, and an in-file assignment takes effect in the current invocation: the
# domain lane demonstrated `GNUMAKEFLAGS := -i` swallowing a forced audit failure at
# rc=0 while this scan stayed silent. The runtime sentinels caught that form anyway,
# because they measure the exit status rather than the spelling, which is the point of
# having both controls; what was wrong was the author-facing diagnosis.
IGNORE_ERROR_DIRECTIVE = re.compile(r"^\s*\.IGNORE\s*:")
MAKEFLAGS_ASSIGNMENT = re.compile(
    r"(?<![-A-Za-z0-9_.])(?:MAKEFLAGS|GNUMAKEFLAGS|MFLAGS)\s*"
    r"(?::::=|::=|:=|\?=|\+=|!=|=)"
)
SHELL_ASSIGNMENT = re.compile(
    r"(?<![-A-Za-z0-9_.])(?:SHELL|\.SHELLFLAGS)\s*" r"(?::::=|::=|:=|\?=|\+=|!=|=)"
)
# Any long option, so each one can be judged against pip-audit's own grammar below.
LONG_OPTION = re.compile(r"(?<![-A-Za-z0-9_])--[A-Za-z0-9][-A-Za-z0-9]*")
# pip-audit's suppression options, read from its own parser. F-1A got in because this
# control keyed on the literal text ``--ignore``: argparse accepts any unambiguous
# PREFIX of a long option, so ``--ig`` and ``--ign`` suppress exactly as
# ``--ignore-vuln`` does while never containing the word the scan looked for.
IGNORE_OPTION_DESTS = frozenset({"ignore_vulns"})
CANONICAL_IGNORE_OPTIONS = frozenset({"--ignore-vuln"})


def _ignore_option_names() -> frozenset[str]:
    """Return pip-audit's own suppression option spellings.

    Derived from the installed parser rather than hard-coded, so a renamed or added
    suppression option is covered without editing this file. The canonical spelling is
    unioned in so an import failure cannot leave the fence with nothing to match.
    """
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            pip_audit_cli = importlib.import_module("pip_audit._cli")
        actions = pip_audit_cli._parser()._actions
    except Exception:  # pragma: no cover - the fence must never fail open
        return CANONICAL_IGNORE_OPTIONS
    return frozenset(
        {
            option
            for action in actions
            if action.dest in IGNORE_OPTION_DESTS
            for option in action.option_strings
            if option.startswith("--")
        }
        | set(CANONICAL_IGNORE_OPTIONS)
    )


IGNORE_OPTION_NAMES = _ignore_option_names()


def _is_ignore_option(token: str) -> bool:
    """Return True for any token pip-audit would read as a suppression option.

    Every prefix of a suppression option is rejected, ambiguous ones included: an
    ambiguous prefix such as ``--i`` makes pip-audit exit 2 instead of suppressing, so
    rejecting it costs nothing and keeps the rule the shape of argparse's own matching
    rather than a list of spellings someone has to remember to extend.
    """
    name = token.split("=", 1)[0]
    if not name.startswith("--") or name == "--":
        return False
    if any(option.startswith(name) for option in IGNORE_OPTION_NAMES):
        return True
    # An unknown ``--ignore-*`` spelling is not a pip-audit option at all, so it would
    # fail the audit rather than suppress. It is still rejected: a token that reads as a
    # suppression has no business in a governed recipe.
    return name.startswith("--ignore")


def _line_has_ignore_option(code: str) -> bool:
    """Return True when any long option on this Makefile line is a suppression option."""
    return any(_is_ignore_option(match.group()) for match in LONG_OPTION.finditer(code))


def _command_ignore_tokens(command: list[str]) -> list[str]:
    """Return one command's suppression tokens, each with its attached advisory ID."""
    tokens: list[str] = []
    index = 0
    while index < len(command):
        token = command[index]
        if _is_ignore_option(token):
            tokens.append(token)
            if "=" not in token and index + 1 < len(command):
                tokens.append(command[index + 1])
                index += 1
        index += 1
    return tokens


VERSION = re.compile(r"\d+(?:\.\d+)+")
# A cap with no published fix says so in these words rather than being left blank.
NO_FIX = "no-fix-published"
PLACEHOLDERS = frozenset({"", "-", "?", "n/a", "na", "none", "tbd", "todo", "unknown"})
GOVERNED_SOURCE_RECIPES = {
    "audit": ("\tpip-audit -r requirements.txt $(PIP_AUDIT_IGNORES)",),
    "security": (
        "\tbandit -c pyproject.toml -r $(SURFACE) --severity-level medium --confidence-level medium",
        "\tpip-audit -r requirements.txt $(PIP_AUDIT_IGNORES)",
        "\tpip-audit --no-deps --disable-pip -r requirements.txt $(PIP_AUDIT_IGNORES)",
        "\tpip-audit --vulnerability-service osv --no-deps --disable-pip -r requirements.txt $(PIP_AUDIT_IGNORES)",
    ),
}
# The exact contiguous contract the Makefile must carry in the comment block directly
# above the assignment. Token-presence checks are too weak: scattered words are not an
# instruction and were the P-10 failure mode.
CONTRACT_LINES = (
    "# SECDEP-01 canonical grammar (the fence rejects every other assignment shape):",
    "# Keep exactly one literal `PIP_AUDIT_IGNORES :=` assignment; do not use computed names, includes, `eval`, expansion or `+=`.",
    "# Use only exact `--ignore-vuln <ID>` or `--ignore-vuln=<ID>` tokens; abbreviations and other tokens are rejected.",
    "# Ignore-option tokens may appear only in that assignment; direct recipe flags and other variables are rejected.",
    "# Both `make security` and `make audit` are live-checked against the canonical advisory IDs.",
    "# The complete recipes are fixed: `audit` is only canonical resolve-mode pip-audit; `security` is exact Bandit then the canonical resolve-mode, declared-pin and OSV cross-check pip-audit passes.",
    "# `.ONESHELL`, `SHELL`, `.SHELLFLAGS`, shell preambles, aliases, functions, wrappers and extra commands are rejected; runtime sentinels prove all four invocations reach the expected binaries.",
    "# `.IGNORE`, Make flag variable assignments (`MAKEFLAGS`, `GNUMAKEFLAGS`,"
    " `MFLAGS`) and `-` recipe prefixes are rejected: a failing audit must fail the target, and sentinels forced to fail prove it does.",
    "# Each suppression has one physical declaration line in this comment block:",
    "# ignore-vuln: <ADVISORY-ID> | package: <name>==<version> | cap: <name><specifier> | lifted-by: <name> <version>|unknown | reason: <why the suppression is defensible>",
)


def _source_shape_violations(
    lines: list[str], assignments: list[tuple[int, int, str, str, str]]
) -> list[str]:
    """Reject Make features that can mutate the protected variable out of sight."""
    violations: list[str] = []
    assignment_lines = {
        line_number
        for start, end, _modifiers, _operator, _value in assignments
        for line_number in range(start, end + 1)
    }
    for line_number, line in enumerate(lines, start=1):
        stripped = line.lstrip()
        if not stripped or stripped.startswith("#"):
            continue
        source_index = line_number - 1
        code = line.split("#", 1)[0]
        if source_index not in assignment_lines and _line_has_ignore_option(code):
            violations.append(
                f"Makefile line {line_number}: ignore options may appear only in the "
                f"canonical {VARIABLE} assignment, never directly in recipes or "
                "other variables"
            )
        if ONESHELL_DIRECTIVE.match(code):
            violations.append(
                f"Makefile line {line_number}: `.ONESHELL` can carry shell state "
                "into a governed command and is not permitted by SECDEP-01"
            )
        if IGNORE_ERROR_DIRECTIVE.match(code):
            violations.append(
                f"Makefile line {line_number}: `.IGNORE` discards a governed "
                "command's exit status, so the gate would pass on a failing audit; "
                "it is not permitted by SECDEP-01"
            )
        if MAKEFLAGS_ASSIGNMENT.search(code):
            violations.append(
                f"Makefile line {line_number}: assigning MAKEFLAGS or MFLAGS lets the "
                "file set its own Make flags, including `-i`, and lets it override "
                f"{VARIABLE}; it is not permitted by SECDEP-01"
            )
        if SHELL_ASSIGNMENT.search(code):
            violations.append(
                f"Makefile line {line_number}: `SHELL` and `.SHELLFLAGS` overrides "
                "can change governed command resolution and are not permitted by "
                "SECDEP-01"
            )
        if INCLUDE_DIRECTIVE.match(line):
            violations.append(
                f"Makefile line {line_number}: include directives are not auditable; "
                f"keep {VARIABLE} in this file"
            )
        if EVAL_FUNCTION.search(line):
            violations.append(
                f"Makefile line {line_number}: `eval` can synthesize assignments and "
                "is not permitted by SECDEP-01"
            )

        dynamic_define = DYNAMIC_DEFINE.match(line)
        if dynamic_define is not None and "$" in dynamic_define.group("name"):
            violations.append(
                f"Makefile line {line_number}: computed `define` names are not "
                f"auditable for {VARIABLE}"
            )

        # A recipe line may contain shell assignments, not Make assignment names.
        # `eval` above remains forbidden in recipes because Make expands it first.
        if line.startswith("\t"):
            continue
        assignment = GENERIC_ASSIGNMENT.match(line)
        if assignment is not None and "$" in assignment.group("lhs"):
            violations.append(
                f"Makefile line {line_number}: computed assignment names are not "
                f"auditable for {VARIABLE}"
            )
    return violations


def _governed_recipe_violations(lines: list[str]) -> list[str]:
    """Require the complete source recipe for every governed target present."""
    violations: list[str] = []
    for target, expected_recipe in GOVERNED_SOURCE_RECIPES.items():
        declaration = re.compile(rf"^[ ]*{re.escape(target)}\s*::?(?:\s|$)")
        definitions = [
            index for index, line in enumerate(lines) if declaration.match(line)
        ]
        if not definitions:
            continue
        if len(definitions) != 1:
            violations.append(
                f"{target} must have exactly one target declaration, got "
                f"{len(definitions)}"
            )
            continue

        start = definitions[0]
        if lines[start] != f"{target}:":
            violations.append(
                f"{target} target declaration must be exactly `{target}:`, got "
                f"{lines[start]!r}"
            )
        recipe: list[str] = []
        index = start + 1
        while index < len(lines) and lines[index].startswith("\t"):
            recipe.append(lines[index])
            index += 1
        if tuple(recipe) != expected_recipe:
            violations.append(
                f"{target} complete source recipe must be exactly "
                f"{expected_recipe!r}, got {tuple(recipe)!r}"
            )
    return violations


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


def _parse_ignore_tokens(
    tokens: list[str],
    location: str,
    violations: list[str],
) -> list[str]:
    """Parse only the two canonical spellings; every other token fails closed."""
    suppressed: list[str] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        advisory: str | None = None
        if token == "--ignore-vuln":
            if index + 1 >= len(tokens):
                violations.append(f"{location}: `--ignore-vuln` has no advisory ID")
                index += 1
                continue
            advisory = tokens[index + 1]
            index += 2
        elif token.startswith("--ignore-vuln="):
            advisory = token.partition("=")[2]
            index += 1
        else:
            violations.append(
                f"{location}: unsupported token {token!r}; use only exact "
                "`--ignore-vuln <ID>` or `--ignore-vuln=<ID>` forms"
            )
            index += 1
            continue

        if ADVISORY_ID.fullmatch(advisory) is None:
            violations.append(f"{location}: invalid advisory ID {advisory!r}")
            continue
        suppressed.append(advisory)
    return suppressed


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

        parsed = _parse_ignore_tokens(
            tokens, f"{VARIABLE} line {start + 1}", violations
        )
        for advisory in parsed:
            if advisory in suppressed:
                violations.append(f"{advisory}: suppressed more than once")
            suppressed.append(advisory)
    return suppressed


def audit(makefile_text: str) -> list[str]:
    """Return one message per SECDEP-01 violation; an empty list means compliant."""
    lines = makefile_text.splitlines()
    assignments = _assignments(lines)
    violations = _source_shape_violations(lines, assignments)
    violations.extend(_governed_recipe_violations(lines))
    if not assignments:
        violations.append(f"{VARIABLE} assignment not found in the Makefile")
        return violations

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
GOVERNED_TARGETS = ("audit", "security")
PIP_AUDIT_PREFIX = ["pip-audit", "-r", "requirements.txt"]
PIP_AUDIT_DECLARED_PREFIX = [
    "pip-audit",
    "--no-deps",
    "--disable-pip",
    "-r",
    "requirements.txt",
]
# The feed cross-check pass (#1353 D-10): declared-pin coverage asked of OSV rather than
# PyPI's advisory API, which also keeps it off pip's HTTP cache (`use_pip=False`).
PIP_AUDIT_OSV_PREFIX = [
    "pip-audit",
    "--vulnerability-service",
    "osv",
    "--no-deps",
    "--disable-pip",
    "-r",
    "requirements.txt",
]
BANDIT_COMMAND = [
    "bandit",
    "-c",
    "pyproject.toml",
    "-r",
    "finance",
    "analytics",
    "api",
    "app",
    "wind_resource",
    "solar_resource",
    "analysis_tools",
    "--severity-level",
    "medium",
    "--confidence-level",
    "medium",
]


def _dry_run_target_commands(
    target: str, makefile_text: str | None = None
) -> list[list[str]]:
    """Return GNU Make's effective dry-run commands for one governed target."""
    command = ["make", "--no-print-directory", "-n"]
    if makefile_text is not None:
        command.extend(["-f", "-"])
    command.append(target)
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        input=makefile_text,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise AssertionError(f"make -n {target} failed: {detail}")
    return [
        shlex.split(line.strip(), comments=False, posix=True)
        for line in completed.stdout.splitlines()
        if line.strip()
    ]


def _declared_ignore_tokens(makefile_text: str) -> list[str]:
    """Return the literal tokens Make substitutes for ``$(PIP_AUDIT_IGNORES)``."""
    assignments = _assignments(makefile_text.splitlines())
    assert len(assignments) == 1, assignments
    return shlex.split(assignments[0][4], comments=True, posix=True)


def _declared_source_ids(makefile_text: str) -> list[str]:
    """Return the advisory IDs the subject's own declaration carries."""
    violations: list[str] = []
    ids = _suppressed_ids(_assignments(makefile_text.splitlines()), violations)
    assert violations == [], violations
    return ids


def _recipe_lines(makefile_text: str, target: str) -> list[str]:
    """Return one target's literal recipe lines, tab prefix included."""
    lines = makefile_text.splitlines()
    starts = [
        index for index, line in enumerate(lines) if line.startswith(f"{target}:")
    ]
    assert len(starts) == 1, f"{target}: {len(starts)} target lines"
    recipe: list[str] = []
    for line in lines[starts[0] + 1 :]:
        if not line.startswith("\t"):
            break
        recipe.append(line)
    assert recipe, f"{target}: no recipe lines"
    return recipe


def _effective_target_violations(
    target: str, source_ids: list[str], makefile_text: str | None = None
) -> list[str]:
    """Require each governed target's complete canonical command sequence."""
    violations: list[str] = []
    source_text = (
        MAKEFILE.read_text(encoding="utf-8") if makefile_text is None else makefile_text
    )
    assignments = _assignments(source_text.splitlines())
    if len(assignments) != 1:
        return [
            f"cannot derive the canonical command from {len(assignments)} "
            f"{VARIABLE} assignments"
        ]
    try:
        ignore_tokens = shlex.split(assignments[0][4], comments=True, posix=True)
    except ValueError as exc:
        return [f"cannot parse the canonical {VARIABLE} assignment: {exc}"]
    parsed_source_ids = _parse_ignore_tokens(
        ignore_tokens, f"canonical {VARIABLE} assignment", violations
    )
    if parsed_source_ids != source_ids:
        violations.append(
            f"canonical assignment IDs {parsed_source_ids!r} do not match source "
            f"IDs {source_ids!r}"
        )
    if violations:
        return violations

    try:
        commands = _dry_run_target_commands(target, makefile_text)
    except (AssertionError, ValueError) as exc:
        return [str(exc)]

    pip_audit_command = [*PIP_AUDIT_PREFIX, *ignore_tokens]
    pip_audit_declared_command = [*PIP_AUDIT_DECLARED_PREFIX, *ignore_tokens]
    pip_audit_osv_command = [*PIP_AUDIT_OSV_PREFIX, *ignore_tokens]
    expected = {
        "audit": [pip_audit_command],
        "security": [
            BANDIT_COMMAND,
            pip_audit_command,
            pip_audit_declared_command,
            pip_audit_osv_command,
        ],
    }.get(target)
    if expected is None:
        return [f"{target!r} is not a governed SECDEP-01 target"]
    if commands != expected:
        return [
            f"make -n {target} complete command sequence must be exactly "
            f"{expected!r}, got {commands!r}"
        ]
    return []


# Which governed invocation a sentinel run should make fail. A sentinel that can only
# succeed cannot tell "the audit ran and passed" from "the audit ran, failed, and its
# failure was discarded" - the gap F-1E was found in.
FAILURE_POINTS = (
    "bandit",
    "pip-audit-resolve",
    "pip-audit-declared",
    "pip-audit-osv",
)
SENTINEL_EXIT = 23


def _sentinel_body(executable: str, failing: str | None) -> str:
    """Return the stub shell for one executable, failing where asked."""
    record = (
        "#!/bin/sh\n"
        "set -u\n"
        "{\n"
        "  printf '%s\\n' '__SECDEP_CALL__'\n"
        "  printf '%s\\n' \"$@\"\n"
        f'}} >> "$SECDEP_SENTINEL_DIR/{executable}.argv"\n'
    )
    if failing is None:
        return record
    if executable == "bandit":
        return record + (f"exit {SENTINEL_EXIT}\n" if failing == "bandit" else "")
    # Each pip-audit pass is identified by its FIRST argument: the OSV cross-check
    # leads with `--vulnerability-service`, the declared-pin pass with `--no-deps`, and
    # the resolve-mode pass with neither. Distinguishing all three here is what lets
    # each invocation be failed on its own; a two-way split would fail the OSV pass
    # whenever the resolve-mode pass was the one asked for.
    if failing == "pip-audit-osv":
        return record + (
            f'case "${{1-}}" in --vulnerability-service) exit {SENTINEL_EXIT} ;; esac\n'
        )
    if failing == "pip-audit-declared":
        return record + f'case "${{1-}}" in --no-deps) exit {SENTINEL_EXIT} ;; esac\n'
    if failing == "pip-audit-resolve":
        return record + (
            f'case "${{1-}}" in --no-deps|--vulnerability-service) ;; '
            f"*) exit {SENTINEL_EXIT} ;; esac\n"
        )
    return record


def _run_target_with_sentinels(
    tmp_path: Path, target: str, makefile_text: str, failing: str | None = None
) -> tuple[subprocess.CompletedProcess[str], dict[str, list[list[str]]]]:
    """Execute a target with harmless binaries that record their exact arguments."""
    binary_dir = tmp_path / "bin"
    receipt_dir = tmp_path / "receipts"
    binary_dir.mkdir()
    receipt_dir.mkdir()
    assert failing is None or failing in FAILURE_POINTS, failing
    for executable in ("bandit", "pip-audit"):
        stub = binary_dir / executable
        stub.write_text(_sentinel_body(executable, failing), encoding="utf-8")
        stub.chmod(0o755)

    environment = os.environ.copy()
    environment["PATH"] = f"{binary_dir}{os.pathsep}{environment['PATH']}"
    environment["SECDEP_SENTINEL_DIR"] = str(receipt_dir)
    for variable in (
        "BASH_ENV",
        "ENV",
        "GNUMAKEFLAGS",
        "MAKEFLAGS",
        "MFLAGS",
        "SHELL",
    ):
        environment.pop(variable, None)
    # pip-audit takes its vulnerability service and index URLs from the environment,
    # which changes what an audit FINDS rather than its argv or exit status, so argv
    # pinning and the dry-run comparison are blind to it by construction. The sentinel
    # run is therefore given none of them (assurance W-4). pip-audit publishes no
    # environment default for `--ignore-vuln`, so the direct suppression channel is
    # closed; what the environment can still do to a REAL audit is named as a limit in
    # the rule row rather than claimed closed.
    for variable in [name for name in environment if name.startswith("PIP_AUDIT_")]:
        environment.pop(variable, None)

    completed = subprocess.run(
        ["make", "--no-print-directory", "-f", "-", target],
        cwd=REPO_ROOT,
        env=environment,
        input=makefile_text,
        check=False,
        capture_output=True,
        text=True,
    )
    receipts: dict[str, list[list[str]]] = {}
    for executable in ("bandit", "pip-audit"):
        receipt = receipt_dir / f"{executable}.argv"
        if not receipt.is_file():
            continue
        calls: list[list[str]] = []
        for line in receipt.read_text(encoding="utf-8").splitlines():
            if line == "__SECDEP_CALL__":
                calls.append([])
            elif not calls:
                raise AssertionError(f"malformed runtime receipt for {executable}")
            else:
                calls[-1].append(line)
        receipts[executable] = calls
    return completed, receipts


def _effective_suppression_violations(
    target: str, source_ids: list[str], makefile_text: str | None = None
) -> list[str]:
    """Require a governed target's effective suppressions to be the declared ones."""
    violations: list[str] = []
    source_text = (
        MAKEFILE.read_text(encoding="utf-8") if makefile_text is None else makefile_text
    )
    assignments = _assignments(source_text.splitlines())
    if len(assignments) != 1:
        return [
            f"cannot derive the canonical suppressions from {len(assignments)} "
            f"{VARIABLE} assignments"
        ]
    try:
        ignore_tokens = shlex.split(assignments[0][4], comments=True, posix=True)
    except ValueError as exc:
        return [f"cannot parse the canonical {VARIABLE} assignment: {exc}"]
    parsed_source_ids = _parse_ignore_tokens(
        ignore_tokens, f"canonical {VARIABLE} assignment", violations
    )
    if parsed_source_ids != source_ids:
        violations.append(
            f"canonical assignment IDs {parsed_source_ids!r} do not match source "
            f"IDs {source_ids!r}"
        )
    if violations:
        return violations
    if target not in GOVERNED_TARGETS:
        return [f"{target!r} is not a governed SECDEP-01 target"]

    try:
        commands = _dry_run_target_commands(target, makefile_text)
    except (AssertionError, ValueError) as exc:
        return [str(exc)]

    # Every emitted command is read, not the ones that look like an audit: a suppression
    # reaching the audit from a line this fence never anticipated is still a suppression,
    # and filtering for recognizable lines is what let F-1 through.
    #
    # Each command is compared ON ITS OWN. The mandatory target passes the allowlist to
    # two audits, as #1388 requires, so pooling their tokens makes one correct
    # declaration look like two suppressions - the F-1 defect the assurance lane found,
    # invisible while the live allowlist is empty.
    for position, command in enumerate(commands, start=1):
        tokens = _command_ignore_tokens(command)
        if not tokens:
            continue
        parsed = _parse_ignore_tokens(
            tokens, f"`make -n {target}` command {position}", violations
        )
        if parsed != source_ids:
            violations.append(
                f"make -n {target} command {position} suppresses {parsed!r}, not the "
                f"declared allowlist {source_ids!r}"
            )
    return violations


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


@pytest.mark.parametrize("target", GOVERNED_TARGETS)
def test_live_make_expansion_matches_the_canonical_source_allowlist(
    target: str,
) -> None:
    """Every governed effective command must reproduce the canonical allowlist."""
    makefile_text = MAKEFILE.read_text(encoding="utf-8")
    assert audit(makefile_text) == []

    source_violations: list[str] = []
    source_ids = _suppressed_ids(
        _assignments(makefile_text.splitlines()), source_violations
    )
    assert source_violations == []

    assert _effective_suppression_violations(target, source_ids) == []


@pytest.mark.parametrize("target", GOVERNED_TARGETS)
def test_the_sequence_oracle_passes_the_committed_makefile(target: str) -> None:
    """Positive control for the complete-sequence oracle on the real file.

    W-10: the oracle had negatives and one positive on a crafted file, and was never
    asserted clean against the committed `Makefile`. A guard with no positive control
    on a real input is the absence that let F-1 through and then F-2, so it gets one:
    whatever the live allowlist holds, the committed recipes must satisfy it.
    """
    makefile_text = MAKEFILE.read_text(encoding="utf-8")
    assert (
        _effective_target_violations(
            target, _declared_source_ids(makefile_text), makefile_text
        )
        == []
    )


@pytest.mark.parametrize(
    ("target", "expected_receipts"),
    [
        pytest.param(
            "audit",
            {"pip-audit": [PIP_AUDIT_PREFIX[1:]]},
            id="audit invokes pip-audit",
        ),
        pytest.param(
            "security",
            {
                "bandit": [BANDIT_COMMAND[1:]],
                "pip-audit": [
                    PIP_AUDIT_PREFIX[1:],
                    PIP_AUDIT_DECLARED_PREFIX[1:],
                    PIP_AUDIT_OSV_PREFIX[1:],
                ],
            },
            id="security invokes bandit then all three pip-audit passes",
        ),
    ],
)
def test_governed_targets_execute_the_expected_binaries(
    tmp_path: Path, target: str, expected_receipts: dict[str, list[list[str]]]
) -> None:
    """Runtime sentinels prove the printed commands resolve to real executables."""
    makefile_text = MAKEFILE.read_text(encoding="utf-8")
    # The declared tokens are read from the subject and appended to each expected
    # pip-audit argv. The parametrized prefixes carry none, and the sentinel records
    # the real argv, so hard-coding them asserted that the allowlist is empty (F-2).
    declared = _declared_ignore_tokens(makefile_text)
    expected = {
        name: [
            [*argv, *declared] if name == "pip-audit" else argv for argv in invocations
        ]
        for name, invocations in expected_receipts.items()
    }
    completed, receipts = _run_target_with_sentinels(tmp_path, target, makefile_text)
    assert completed.returncode == 0, completed.stderr
    assert receipts == expected


@pytest.mark.parametrize(
    ("failing", "expected_calls"),
    [
        pytest.param(
            "bandit",
            {"bandit": 1},
            id="a failing bandit stops the gate",
        ),
        pytest.param(
            "pip-audit-resolve",
            {"bandit": 1, "pip-audit": 1},
            id="a failing resolve-mode audit stops the gate",
        ),
        pytest.param(
            "pip-audit-declared",
            {"bandit": 1, "pip-audit": 2},
            id="a failing declared-pin audit stops the gate",
        ),
        pytest.param(
            "pip-audit-osv",
            {"bandit": 1, "pip-audit": 3},
            id="a failing OSV cross-check stops the gate",
        ),
    ],
)
def test_a_failing_governed_executable_fails_the_security_gate(
    tmp_path: Path, failing: str, expected_calls: dict[str, int]
) -> None:
    """The gate must go nonzero when any governed audit fails.

    Rejection 05 (F-1E) was possible because every runtime control until now ran
    sentinels that could only succeed, which cannot distinguish a gate that passed
    from a gate whose failure was discarded. Each governed executable is therefore
    failed in turn here, on the real committed Makefile.
    """
    makefile_text = MAKEFILE.read_text(encoding="utf-8")
    completed, receipts = _run_target_with_sentinels(
        tmp_path, "security", makefile_text, failing=failing
    )

    assert completed.returncode != 0, (
        f"`make security` passed although {failing} exited {SENTINEL_EXIT}: "
        f"{completed.stdout}{completed.stderr}"
    )
    # Make stops the recipe at the first failure, so the calls that precede the
    # failing one must have happened and the ones after it must not.
    assert {name: len(calls) for name, calls in receipts.items()} == expected_calls


def test_a_failing_audit_also_fails_the_convenience_target(tmp_path: Path) -> None:
    """`audit` is not the merge gate, but it must not lie about an audit either."""
    makefile_text = MAKEFILE.read_text(encoding="utf-8")
    completed, receipts = _run_target_with_sentinels(
        tmp_path, "audit", makefile_text, failing="pip-audit-resolve"
    )
    assert completed.returncode != 0, completed.stderr
    assert receipts == {
        "pip-audit": [[*PIP_AUDIT_PREFIX[1:], *_declared_ignore_tokens(makefile_text)]]
    }


@pytest.mark.parametrize(
    ("label", "prelude"),
    [
        pytest.param("global", ".IGNORE:\n", id="global .IGNORE"),
        pytest.param("governed target", ".IGNORE: security\n", id="target .IGNORE"),
        pytest.param("make flags", "MAKEFLAGS += -i\n", id="MAKEFLAGS ignore-errors"),
        pytest.param(
            "GNU make flags",
            "GNUMAKEFLAGS := -i\n",
            id="GNUMAKEFLAGS ignore-errors",
        ),
    ],
)
def test_ignore_error_state_is_an_effective_bypass_and_is_rejected(
    tmp_path: Path, label: str, prelude: str
) -> None:
    """Prove the bypass works before proving the fence rejects it.

    A control that only asserts rejection cannot show there was anything to reject,
    which is the P-9 defect on #1353. So the hostile Makefile is executed first: the
    audits fail, the gate reports success, and the commands are untouched.
    """
    makefile_text = MAKEFILE.read_text(encoding="utf-8")
    mutated = prelude + makefile_text

    completed, receipts = _run_target_with_sentinels(
        tmp_path, "security", mutated, failing="pip-audit-resolve"
    )
    assert completed.returncode == 0, (
        f"{label} ignore-error state was expected to swallow the failure: "
        f"{completed.stderr}"
    )
    assert len(receipts["pip-audit"]) == 3, receipts

    # The commands themselves are unchanged, so nothing but this guard sees it. The
    # declared set is read from the subject rather than hard-coded empty, or the oracle
    # returns early on a declared-set mismatch and this assertion stops meaning
    # "the oracle is blind to it" as soon as the allowlist holds an entry (F-2).
    assert _dry_run_target_commands("security", mutated) == _dry_run_target_commands(
        "security", makefile_text
    )
    assert (
        _effective_target_violations("security", _declared_source_ids(mutated), mutated)
        == []
    )

    violations = audit(mutated)
    assert violations, "the fence passed an ignore-error Makefile"
    assert any(
        "discards a governed" in item or "own Make flags" in item for item in violations
    ), violations


def test_a_dash_prefixed_governed_recipe_line_is_rejected() -> None:
    """`-command` is Make's third way to discard an exit status."""
    makefile_text = MAKEFILE.read_text(encoding="utf-8")
    mutated = makefile_text.replace(
        "\tpip-audit -r requirements.txt $(PIP_AUDIT_IGNORES)",
        "\t-pip-audit -r requirements.txt $(PIP_AUDIT_IGNORES)",
    )
    assert mutated != makefile_text
    violations = audit(mutated)
    assert violations, "the fence passed a recipe that ignores its own exit status"
    assert any("recipe must be exactly" in item for item in violations), violations


def test_security_recipe_cannot_carry_an_undeclared_direct_suppression() -> None:
    """F-1S control: the required CI target cannot diverge from ``audit``."""
    makefile_text = MAKEFILE.read_text(encoding="utf-8")
    canonical_recipe = "\tpip-audit -r requirements.txt $(PIP_AUDIT_IGNORES)"
    hostile_recipe = (
        "\tpip-audit -r requirements.txt --ignore-vuln CVE-2026-999999 "
        "$(PIP_AUDIT_IGNORES)"
    )
    assert makefile_text.count(canonical_recipe) == 2
    mutated = makefile_text.replace(canonical_recipe, hostile_recipe, 1)

    source_violations = audit(mutated)
    assert any(
        "ignore options may appear only" in violation for violation in source_violations
    ), source_violations

    # The convenience target stays clean: this is specifically a mandatory-target
    # divergence, not a fixture that poisons both recipes. Expected against the
    # declared tokens rather than the bare prefix, so the claim stays true once the
    # allowlist holds an entry - the case the rule exists to govern (F-1R).
    assert _dry_run_target_commands("audit", mutated) == [
        PIP_AUDIT_PREFIX + _declared_ignore_tokens(mutated)
    ]
    security_commands = _dry_run_target_commands("security", mutated)
    assert any("CVE-2026-999999" in command for command in security_commands)
    # The declared set is read from the subject too, for the same reason: hard-coding
    # the empty allowlist made the oracle short-circuit on "canonical assignment IDs do
    # not match source IDs" as soon as a real entry existed, so the injected ID was
    # never reached. That is the second half of F-1R, in this same test.
    effective_violations = _effective_suppression_violations(
        "security", _declared_source_ids(mutated), mutated
    )
    rejected_injected_id = any(
        "CVE-2026-999999" in violation for violation in effective_violations
    )
    assert rejected_injected_id, effective_violations


def test_oneshell_alias_cannot_intercept_the_security_audit(tmp_path: Path) -> None:
    """F-1W control: printed command text cannot stand in for runtime identity."""
    makefile_text = MAKEFILE.read_text(encoding="utf-8")
    canonical_recipe = "\tpip-audit -r requirements.txt $(PIP_AUDIT_IGNORES)"
    hostile_recipe = (
        f"\talias pip-audit='echo SECURITY-AUDIT-INTERCEPTED'\n{canonical_recipe}"
    )
    mutated = ".ONESHELL:\n" + makefile_text.replace(
        canonical_recipe, hostile_recipe, 1
    )

    source_violations = audit(mutated)
    assert any(".ONESHELL" in item for item in source_violations), source_violations
    rejected_source_recipe = any(
        "complete source recipe" in item for item in source_violations
    )
    assert rejected_source_recipe, source_violations
    # Declared set from the subject, for the same reason: with a literal empty list the
    # declared-set mismatch alone satisfies the assertion below, so the control stops
    # proving the oracle catches the interposition (F-2).
    effective_violations = _effective_target_violations(
        "security", _declared_source_ids(mutated), mutated
    )
    rejected_interposition = any(
        "complete command sequence" in item for item in effective_violations
    )
    assert rejected_interposition, effective_violations

    completed, receipts = _run_target_with_sentinels(tmp_path, "security", mutated)
    assert completed.returncode == 0, completed.stderr
    assert "SECURITY-AUDIT-INTERCEPTED" in completed.stdout
    assert receipts == {"bandit": [BANDIT_COMMAND[1:]]}


@pytest.mark.parametrize(
    ("recipe", "expected"),
    [
        pytest.param(
            "\tpip-audit -r requirements.txt --ignore-v CVE-2026-999999\n",
            "complete command sequence",
            id="abbreviated option",
        ),
        pytest.param(
            "\tpip-audit -r requirements.txt || true\n",
            "complete command sequence",
            id="shell success override",
        ),
        pytest.param(
            "\tenv pip-audit -r requirements.txt\n",
            "complete command sequence",
            id="alternate command wrapper",
        ),
        pytest.param(
            "\tpip-audit -r requirements.txt\n"
            "\tpython -m pip_audit -r requirements.txt\n",
            "complete command sequence",
            id="second invocation",
        ),
    ],
)
def test_effective_target_oracle_rejects_noncanonical_commands(
    recipe: str, expected: str
) -> None:
    """The live oracle fails closed on options, wrappers and extra commands."""
    makefile_text = f"{EMPTY}\naudit:\n{recipe}"
    violations = _effective_target_violations("audit", [], makefile_text)
    assert any(expected in violation for violation in violations), violations


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
        pytest.param(
            EMPTY
            + "SUFFIX := IGNORES\n"
            + "PIP_AUDIT_$(SUFFIX) := --ignore-vuln CVE-2026-999999\n",
            "computed assignment names",
            id="computed assignment name rejected",
        ),
        pytest.param(
            _replace_empty_assignment(
                "PIP_AUDIT_IGNORES := --ignore-v CVE-2026-999999"
            ),
            "unsupported token",
            id="pip-audit option abbreviation rejected",
        ),
        pytest.param(
            EMPTY
            + "security:\n"
            + "\tpip-audit -r requirements.txt --ignore-vuln CVE-2026-999999\n",
            "ignore options may appear only",
            id="direct recipe suppression rejected",
        ),
        pytest.param(
            EMPTY + "EXTRA_AUDIT_FLAGS := --ignore-v CVE-2026-999999\n",
            "ignore options may appear only",
            id="abbreviated suppression in another variable rejected",
        ),
        pytest.param(
            EMPTY + ".ONESHELL:\n",
            ".ONESHELL",
            id="one-shell state sharing rejected",
        ),
        pytest.param(
            EMPTY + "SHELL := /bin/bash\n",
            "SHELL",
            id="shell override rejected",
        ),
        pytest.param(
            EMPTY + ".SHELLFLAGS := -ec\n",
            ".SHELLFLAGS",
            id="shell flags override rejected",
        ),
        pytest.param(
            EMPTY + "include dependency-audit-overrides.mk\n",
            "include directives are not auditable",
            id="include-driven assignments rejected",
        ),
        pytest.param(
            EMPTY + "$(eval PIP_AUDIT_IGNORES := --ignore-vuln CVE-2026-999999)\n",
            "`eval` can synthesize assignments",
            id="eval-driven assignments rejected",
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


def test_make_oracle_confirms_a_computed_assignment_name_is_effective(
    tmp_path: Path,
) -> None:
    """GNU Make proves a computed left-hand side can replace the protected value."""
    computed_assignment = """\
SUFFIX := IGNORES
PIP_AUDIT_$(SUFFIX) := --ignore-vuln CVE-2026-999999
print:
\t@printf '%s\\n' "$(PIP_AUDIT_IGNORES)"
"""
    makefile_text = EMPTY + computed_assignment
    makefile = tmp_path / "Makefile"
    makefile.write_text(makefile_text, encoding="utf-8")
    completed = subprocess.run(
        ["make", "--no-print-directory", "-f", str(makefile), "print"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert completed.stdout.strip() == "--ignore-vuln CVE-2026-999999"
    assert any("computed assignment names" in item for item in audit(makefile_text))


ABBREVIATIONS = ("--ignore-v", "--igno", "--ign", "--ig")


def _pip_audit_parser() -> argparse.ArgumentParser:
    """Return pip-audit's own argument parser, the authority on what suppresses."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        pip_audit_cli = importlib.import_module("pip_audit._cli")
    parser = pip_audit_cli._parser()
    assert isinstance(parser, argparse.ArgumentParser)
    return parser


@pytest.mark.parametrize("abbreviation", ABBREVIATIONS)
@pytest.mark.parametrize("attached", [False, True], ids=["spaced", "equals"])
def test_pip_audit_parser_oracle_confirms_abbreviations_are_effective(
    abbreviation: str, attached: bool
) -> None:
    """pip-audit proves each abbreviation suppresses, so the fence rejects each one.

    F-1A: the earlier control matched the literal text ``--ignore``, which ``--ig`` and
    ``--ign`` never contain even though argparse resolves them to ``--ignore-vuln``.
    The grammar is now derived from this parser instead of a spelling.
    """
    advisory = "CVE-2026-999999"
    argv = [f"{abbreviation}={advisory}"] if attached else [abbreviation, advisory]
    assert _pip_audit_parser().parse_args(argv).ignore_vulns == [advisory]

    assignment = f"PIP_AUDIT_IGNORES := {' '.join(argv)}"
    violations = audit(_replace_empty_assignment(assignment))
    assert any("unsupported token" in item for item in violations), violations


def test_an_ambiguous_abbreviation_is_rejected_although_it_cannot_suppress() -> None:
    """`--i` matches two options, so pip-audit exits; the fence still fails closed."""
    with pytest.raises(SystemExit):
        _pip_audit_parser().parse_args(["--i", "CVE-2026-999999"])
    assert _is_ignore_option("--i")


@pytest.mark.parametrize("abbreviation", ABBREVIATIONS)
def test_an_abbreviated_recipe_suppression_is_effective_and_is_rejected(
    abbreviation: str,
) -> None:
    """Prove the recipe really suppresses before proving the fence rejects it."""
    makefile_text = MAKEFILE.read_text(encoding="utf-8")
    canonical_recipe = "\tpip-audit -r requirements.txt $(PIP_AUDIT_IGNORES)"
    hostile_recipe = (
        f"\tpip-audit -r requirements.txt {abbreviation} CVE-2026-999999 "
        "$(PIP_AUDIT_IGNORES)"
    )
    mutated = makefile_text.replace(canonical_recipe, hostile_recipe, 1)
    assert mutated != makefile_text

    # The suppression really reaches the audit: it is in the emitted command, and
    # pip-audit's own parser reads it as an ignore flag.
    commands = _dry_run_target_commands("security", mutated)
    assert any(abbreviation in command for command in commands), commands

    source_violations = audit(mutated)
    assert any(
        "ignore options may appear only" in item for item in source_violations
    ), source_violations
    # Against the subject's own declared set, so the rejection must NAME the injected
    # ID. A hard-coded empty allowlist would make this assertion a tautology the moment
    # a real entry existed: the oracle would report the declaration mismatch and the
    # abbreviation could go unnoticed (F-1R, third site).
    effective_violations = _effective_suppression_violations(
        "security", _declared_source_ids(mutated), mutated
    )
    assert any(
        "CVE-2026-999999" in item for item in effective_violations
    ), f"the live oracle passed an abbreviated suppression: {effective_violations}"


# The governed targets exactly as the committed Makefile writes them, so this fixture
# stays a faithful stand-in for the real file rather than a simplified one.
POPULATED_TARGETS = COMPLIANT + (
    "SURFACE := finance\n"
    "audit:\n"
    "\tpip-audit -r requirements.txt $(PIP_AUDIT_IGNORES)\n"
    "security:\n"
    "\tbandit -c pyproject.toml -r $(SURFACE) --severity-level medium"
    " --confidence-level medium\n"
    "\tpip-audit -r requirements.txt $(PIP_AUDIT_IGNORES)\n"
    "\tpip-audit --no-deps --disable-pip -r requirements.txt $(PIP_AUDIT_IGNORES)\n"
    "\tpip-audit --vulnerability-service osv --no-deps --disable-pip"
    " -r requirements.txt $(PIP_AUDIT_IGNORES)\n"
)
DECLARED_IDS = ["PYSEC-2026-4320"]


@pytest.mark.parametrize("target", GOVERNED_TARGETS)
def test_the_oracle_passes_one_declaration_carried_by_every_audit_pass(
    target: str,
) -> None:
    """Positive control: a real declaration must pass, on every audit pass.

    F-1: the oracle pooled the tokens of every emitted command, so the mandatory
    target - which passed the allowlist to two audits, as #1388 requires, and passes it
    to three since #1464 added the OSV cross-check - made one correct declaration look
    like several suppressions. The empty live allowlist hid it. Each command is now
    compared on its own.
    """
    assert audit(POPULATED_TARGETS) == []
    assert (
        _effective_suppression_violations(target, DECLARED_IDS, POPULATED_TARGETS) == []
    )


def test_the_positive_control_fixture_tracks_the_committed_recipes() -> None:
    """The fixture that drives the oracle must not drift from the real recipes.

    W-8: the fixture's fidelity to the committed ``Makefile`` was true but asserted
    nowhere, so a later change to an audit pass would leave the only test that reaches
    the oracle with a populated allowlist running against a stale shape - the F-1
    lesson one level up, where the fixtures agreed with the author's model and the
    committed file did not.
    """
    makefile_text = MAKEFILE.read_text(encoding="utf-8")
    for target in GOVERNED_TARGETS:
        assert _recipe_lines(POPULATED_TARGETS, target) == _recipe_lines(
            makefile_text, target
        ), target


def test_the_oracle_rejects_an_extra_suppression_on_one_audit_pass() -> None:
    """Per-command comparison must still catch a divergence between the two passes."""
    declared_pass = (
        "\tpip-audit --no-deps --disable-pip -r requirements.txt $(PIP_AUDIT_IGNORES)\n"
    )
    hostile_pass = (
        "\tpip-audit --no-deps --disable-pip -r requirements.txt "
        "--ignore-vuln CVE-2026-999999 $(PIP_AUDIT_IGNORES)\n"
    )
    mutated = POPULATED_TARGETS.replace(declared_pass, hostile_pass, 1)
    assert mutated != POPULATED_TARGETS

    violations = _effective_suppression_violations("security", DECLARED_IDS, mutated)
    assert any("CVE-2026-999999" in item for item in violations), violations
    # The untouched resolve-mode pass is not blamed for its neighbour's divergence.
    assert not any("command 1" in item for item in violations), violations


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
