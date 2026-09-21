"""Bind every tracked file's spelling of CASPER, CESSPIT and CCCDIR to the canonical ruleset.

`tests/lint/test_gwtf_canonical_source.py` guards the contents of
`go_with_the_flow_rules_v3_0_clean.csv` itself, cell by cell. Nothing guarded the other
direction: a derived file could define CASPER however it liked and stay green forever.
That is how `.github/SPRINT_WORKFLOW_CHECKLIST.md` came to file CASPER and CESSPIT as
sub-items `C2` and `C3` of CCCDIR, with two invented members `C4` and `C5`, and went
unnoticed from December 2025 until PR #1283 -- and how five further live-guidance files
(PR #1286) each carried a different invented triple.

The three acronyms are PEER rows of the CSV -- `FRAMEWORK-01`, `FRAMEWORK-02`,
`FRAMEWORK-03`, category "Framework Principles" -- not components of one another.

Two independent fences, because neither alone is sufficient:

1. `test_no_retired_framework_expansion_returns` is a regression guard over the exact
   strings PRs #1283 and #1286 removed. It catches a bad expansion coming back by
   copy-paste. It matches per LINE, not per file: in every occurrence those two PRs
   removed, the acronym and its wrong expansion sat on one line. A document that REPORTS
   the defect -- a dated compliance review tabulating which file says what -- puts the
   filename in one column and the wrong wording in another, so a whole-file match would
   red the write-up that corrects the problem. Checked against PR #1285: five pairs match
   somewhere in that document, none on a shared line.
2. `test_every_spelled_out_expansion_is_canonical` is the general fence. Where an acronym
   is immediately followed by a phrase whose word-initials SPELL that acronym, the phrase
   is a definition, and it must appear in the CSV. This catches expansions nobody has seen
   yet. Keying on the initials is what makes it safe: the repository carries hundreds of
   legitimate inline compliance notes (`CASPER-guarded`, `CESSPIT -- fail loud`,
   `CCCDIR -- one contract surface`) which are usages, not definitions, and none of them
   spells out the acronym.

`DATED_RECORDS` are exempt. They are audits, retrospectives and sprint completion reports
that record what was believed on a stated date. Correcting them would falsify a receipt,
so they are listed explicitly rather than skipped by a glob -- a new file cannot drift into
the exemption without someone adding its path here. Two of the fifteen were found by this
fence rather than by the sweep that preceded it: `docs/INTERNAL_HARDENING_AUDIT_20251219.md`
carries a third invented triple, and `analytics/sensitivity/REORGANIZATION.md` carries the
same one as the already-exempt Sprint 16 completion report.

`changelog.d/` and `CHANGELOG.md` are exempt for a different reason: an entry recording
that an expansion was removed has to name the expansion. This module exempts ITSELF for the
same reason -- see `SELF` below.
"""

from __future__ import annotations

import csv
import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CANONICAL_RULESET = REPO_ROOT / "go_with_the_flow_rules_v3_0_clean.csv"

# This module scans itself out. It is the one file that MUST contain the wrong expansions:
# `RETIRED_EXPANSIONS` is a denylist of them, and every control below plants one to watch a
# guard fire. Scanning it would make the guard fail on its own evidence.
SELF = Path(__file__).resolve().relative_to(REPO_ROOT).as_posix()

FRAMEWORK_ACRONYMS = ("CASPER", "CESSPIT", "CCCDIR")

# Dated records: receipts of what was believed on a date. See the module docstring.
DATED_RECORDS = frozenset(
    {
        "analytics/sensitivity/REORGANIZATION.md",
        "docs/AUDIT_CASHFLOW_V14_FINAL.md",
        "docs/FX_INTEGRATION_v14R6.md",
        "docs/INTERNAL_HARDENING_AUDIT_20251219.md",
        "docs/PIPELINE_ANALYSIS_SPRINT15.md",
        "docs/SPRINT_16_REORGANIZATION_COMPLETE.md",
        "docs/SPRINT_18_IMPLEMENTATION_PLAN.md",
        "docs/archive/RETROSPECTIVE_SPRINT9_ITERATION1.md",
        "docs/archive/RETROSPECTIVE_SPRINT9_ITERATION2.md",
        "docs/archive/SPRINT_17_ITERATION_3_AUDIT.md",
        "docs/sprints/SPRINT_18_COMPLETION_SUMMARY.md",
        "docs/tax_mechanics_fix_v2.md",
        "docs/tax_optimization_methodology.md",
        "legacy/sprint_snapshots/REGRESSION_TEST_SUITE.md",
        "legacy/sprint_snapshots/SPRINT15_SECOND_ITERATION_FIXES.md",
    }
)

# Exact expansions removed by #1283 and #1286. None of these appears in the CSV.
RETIRED_EXPANSIONS = (
    ("CASPER", "Clean Architecture"),
    ("CASPER", "Contract-First Design"),
    ("CESSPIT", "Core-Easy-Simple"),
    ("CESSPIT", "Core/Easy/Simple"),
    ("CESSPIT", "Comprehensive Error Handling"),
    ("CESSPIT", "Evidence-based tracking"),
    ("CCCDIR", "Clear, Complete, Consistent Documentation"),
    ("CCCDIR", "Configuration in Config DIRectory"),
    ("CCCDIR", "Comprehensive documentation standards"),
)

# The invented members of the checklist's C1-C5 structure. Neither is a rule.
RETIRED_PSEUDO_RULES = ("LIBsct", "Config-Directory-Import-Reproducibility")

# Acronym, optionally closing a markdown emphasis, then ( : - or an em/en dash, then the
# candidate definition. `**CASPER** (...)` is the form the docs actually use, so the
# emphasis run has to be part of the pattern rather than something a reader strips first.
_DEFINITION = re.compile(
    r"\b(CASPER|CESSPIT|CCCDIR)\b[*_`]{0,2}[ \t]*[-–—:(]{1,2}[ \t]*"
    r"([A-Za-z][^)\n|\"]{4,140})"
)
# Two tokenisations, because a hyphenated member may be one word or two: the CSV's own
# CESSPIT wording has "Pre-flight" as the P, while the retired "Core-Easy-Simple" is three.
_SPLITTERS = (re.compile(r"[ ,;/&]+"), re.compile(r"[ ,;/&–—-]+"))

# Connectors that carry no initial. "Clear API Surfaces *with* Predictable Error Responses"
# is the canonical CASPER wording and spells the acronym only once "with" is set aside.
_CONNECTORS = frozenset(
    {"a", "an", "and", "for", "in", "of", "or", "the", "to", "with"}
)

# Binary and vendored paths a text scan should not open.
_SKIP_SUFFIXES = (
    ".png",
    ".jpg",
    ".jpeg",
    ".pdf",
    ".gz",
    ".zip",
    ".ico",
    ".woff",
    ".woff2",
)
_SKIP_PREFIXES = ("feasibility_reproduce/cache/",)

# Change records. A changelog entry saying an expansion was removed has to name the
# expansion, and `changelog.d/` fragments are compiled verbatim into `CHANGELOG.md`, so
# exempting the fragments without the file they become would only defer the failure.
_CHANGE_RECORDS = ("changelog.d/", "CHANGELOG.md")


def _tracked_text_files() -> list[str]:
    """Return every git-tracked path worth scanning, as repo-relative POSIX strings."""
    listing = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files"],
        capture_output=True,
        text=True,
        check=True,
    )
    return [
        path
        for path in listing.stdout.split("\n")
        if path
        and not path.endswith(_SKIP_SUFFIXES)
        and not path.startswith(_SKIP_PREFIXES)
        and path != CANONICAL_RULESET.name
    ]


def _tokens(
    text: str, splitter: re.Pattern[str], *, drop_connectors: bool
) -> list[str]:
    """Split `text` into comparable lowercase words, discarding anything unalphabetic."""
    # `\n` and `\t` here are the two-character escapes as they appear in a Python source
    # line, not real whitespace: this scans files as text, so a string literal's trailing
    # escape would otherwise ride along on the last word of a phrase.
    text = text.replace("\\n", " ").replace("\\t", " ")
    words = [w.strip("*_`'\".,:;!?()[]“”‘’").casefold() for w in splitter.split(text)]
    words = [w for w in words if w and w[0].isalpha()]
    if drop_connectors:
        words = [w for w in words if w not in _CONNECTORS]
    return words


def _canonical_phrasings() -> dict[tuple[int, bool], str]:
    """Return the ruleset's prose, tokenised every way `_spelled_definition` may ask for.

    Both sides of the comparison have to be normalised identically, or the CSV's own
    wording would fail against itself the moment a connector or hyphen is set aside.
    """
    with CANONICAL_RULESET.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    prose = " ".join(
        " ".join((row["title"], row["description"], row["enforcement"])) for row in rows
    )
    return {
        (index, drop): " ".join(_tokens(prose, splitter, drop_connectors=drop))
        for index, splitter in enumerate(_SPLITTERS)
        for drop in (False, True)
    }


def _spelled_definition(tail: str, acronym: str) -> tuple[str, tuple[int, bool]] | None:
    """Return the phrase spelling out `acronym`, with the tokenisation that found it.

    Returns None when no reading of `tail` spells the acronym, which is the signal that
    this is an inline compliance note rather than a definition.
    """
    for index, splitter in enumerate(_SPLITTERS):
        for drop in (False, True):
            words = _tokens(tail, splitter, drop_connectors=drop)
            if len(words) < len(acronym):
                continue
            candidate = words[: len(acronym)]
            if "".join(w[0].upper() for w in candidate) == acronym:
                return " ".join(candidate), (index, drop)
    return None


def _read(relative_path: str) -> str:
    """Read a tracked file, tolerating the handful that are not valid UTF-8."""
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8", errors="ignore")


def _scannable_files() -> list[str]:
    """Return the tracked files this fence applies to, i.e. excluding the dated records."""
    return [
        p
        for p in _tracked_text_files()
        if p != SELF and p not in DATED_RECORDS and not p.startswith(_CHANGE_RECORDS)
    ]


def test_dated_record_exemptions_all_exist() -> None:
    """A path that stops existing must leave the allowlist, or the exemption rots."""
    missing = sorted(p for p in DATED_RECORDS if not (REPO_ROOT / p).is_file())
    assert not missing, (
        "DATED_RECORDS lists paths that no longer exist; remove them so the "
        f"exemption cannot silently cover a different file later: {missing}"
    )


def test_the_guard_scans_itself_out() -> None:
    """The self-exemption has to hold, and has to be the only file exempted implicitly.

    Found by CI rather than by reasoning: the first push of this guard failed on its own
    source, because `git ls-files` starts listing a file the moment it is staged, and the
    local runs that had passed were made while it was still untracked. Everything else is
    exempted by an explicit path a reader can audit.
    """
    scannable = _scannable_files()
    assert SELF not in scannable
    assert (
        SELF in _tracked_text_files()
    ), "the guard must be tracked, or it scans nothing"
    assert any(
        p.startswith("tests/lint/") for p in scannable
    ), "other lint modules must still be scanned; only this one is exempt"


def test_the_three_acronyms_are_peer_rows() -> None:
    """Guard the premise the whole fence rests on: they are siblings, not a hierarchy."""
    with CANONICAL_RULESET.open(encoding="utf-8", newline="") as handle:
        rows = {row["rule_id"]: row for row in csv.DictReader(handle)}

    for rule_id, acronym in (
        ("FRAMEWORK-01", "CASPER"),
        ("FRAMEWORK-02", "CESSPIT"),
        ("FRAMEWORK-03", "CCCDIR"),
    ):
        row = rows[rule_id]
        assert row["status"] == "active"
        assert row["category"] == "Framework Principles"
        assert row["title"].startswith(f"{acronym} -")


def test_no_retired_framework_expansion_returns() -> None:
    """Fail if an expansion #1283 or #1286 removed reappears outside the dated records."""
    violations: list[str] = []
    for relative_path in _scannable_files():
        for line_number, line in enumerate(_read(relative_path).splitlines(), start=1):
            for acronym, expansion in RETIRED_EXPANSIONS:
                if expansion in line and acronym in line:
                    violations.append(
                        f"{relative_path}:{line_number}: {acronym} as {expansion!r}"
                    )
            for pseudo_rule in RETIRED_PSEUDO_RULES:
                if pseudo_rule in line:
                    violations.append(
                        f"{relative_path}:{line_number}: invented rule {pseudo_rule!r}"
                    )

    assert not violations, (
        "Retired framework expansions are back. The canonical source is "
        f"{CANONICAL_RULESET.name}; CASPER/CESSPIT/CCCDIR are rows FRAMEWORK-01/02/03.\n  "
        + "\n  ".join(sorted(violations))
    )


def test_every_spelled_out_expansion_is_canonical() -> None:
    """Fail if a phrase spelling out one of the acronyms is absent from the ruleset."""
    canonical = _canonical_phrasings()
    violations: list[str] = []

    for relative_path in _scannable_files():
        for line_number, line in enumerate(_read(relative_path).splitlines(), start=1):
            for match in _DEFINITION.finditer(line):
                acronym, tail = match.group(1), match.group(2)
                spelled = _spelled_definition(tail, acronym)
                if spelled is None:
                    continue  # a usage note, not a definition
                phrase, tokenisation = spelled
                if phrase in canonical[tokenisation]:
                    continue
                violations.append(
                    f"{relative_path}:{line_number}: {acronym} spelled out as "
                    f"{phrase!r}, which is not in {CANONICAL_RULESET.name}"
                )

    assert not violations, (
        "A file spells out a framework acronym in terms the canonical ruleset does not "
        "contain. Quote FRAMEWORK-01/02/03 instead, or cite the rule id.\n  "
        + "\n  ".join(sorted(violations))
    )


@pytest.mark.parametrize(("acronym", "expansion"), RETIRED_EXPANSIONS)
def test_retired_expansion_guard_rejects_each_string(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, acronym: str, expansion: str
) -> None:
    """Observe the regression guard firing on every string it claims to catch."""
    planted = tmp_path / "planted.md"
    planted.write_text(f"### {acronym} ({expansion})\n", encoding="utf-8")

    monkeypatch.setattr(f"{__name__}._scannable_files", lambda: [planted.name])
    monkeypatch.setattr(
        f"{__name__}._read", lambda _p: planted.read_text(encoding="utf-8")
    )

    with pytest.raises(AssertionError):
        test_no_retired_framework_expansion_returns()


def test_retired_guard_allows_a_document_that_reports_the_defect(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The inverse control for line scoping: naming the defect must stay possible.

    This is the shape `docs/Framework_Compliance_Review_2026-09-20.md` (PR #1285) has --
    a table whose rows name a file and the wording it gives. Under the whole-file matching
    this guard started with, that document failed on five pairs, none of which shared a
    line. A fence that reds the write-up correcting the problem would teach people to stop
    writing them down.
    """
    planted = tmp_path / "planted.md"
    planted.write_text(
        "| Source | CESSPIT | CASPER | CCCDIR |\n"
        "|---|---|---|---|\n"
        "| the canonical CSV | Config Explicit, Schema Strict, Pre-flight Integrity "
        "Tests | Clear API Surfaces with Predictable Error Responses | Contracts "
        "Centralized, Compliance Documented, Import Relationships explicit |\n"
        '| `SPRINT_16_REORGANIZATION_COMPLETE.md` | "Comprehensive Error Handling" | '
        '"Contract-First Design" | "Clear, Complete, Consistent Documentation" |\n',
        encoding="utf-8",
    )

    monkeypatch.setattr(f"{__name__}._scannable_files", lambda: [planted.name])
    monkeypatch.setattr(
        f"{__name__}._read", lambda _p: planted.read_text(encoding="utf-8")
    )

    test_no_retired_framework_expansion_returns()
    test_every_spelled_out_expansion_is_canonical()


@pytest.mark.parametrize(
    ("acronym", "expansion"),
    [
        ("CASPER", "Clean Architecture"),
        ("CESSPIT", "Comprehensive Error Handling"),
        ("CCCDIR", "Clear, Complete, Consistent Documentation"),
    ],
)
def test_retired_guard_still_fires_when_the_pairing_is_on_one_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, acronym: str, expansion: str
) -> None:
    """And the other half of it: line scoping must not have disarmed the guard.

    Every occurrence #1283 and #1286 removed had this shape, including the checklist's
    `#### C2: CASPER (Clean Architecture)` heading.
    """
    planted = tmp_path / "planted.md"
    planted.write_text(f"#### C2: {acronym} ({expansion})\n", encoding="utf-8")

    monkeypatch.setattr(f"{__name__}._scannable_files", lambda: [planted.name])
    monkeypatch.setattr(
        f"{__name__}._read", lambda _p: planted.read_text(encoding="utf-8")
    )

    with pytest.raises(AssertionError):
        test_no_retired_framework_expansion_returns()


@pytest.mark.parametrize(
    ("acronym", "expansion"),
    [
        (
            "CASPER",
            "Comprehensive Argument Specification, Pydantic Enforcement, Runtime",
        ),
        ("CCCDIR", "Clear, Comprehensive, Correct, Defensible, Informative, Robust"),
    ],
)
def test_initials_guard_fires_through_markdown_emphasis(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, acronym: str, expansion: str
) -> None:
    """`**CASPER** (...)` is the form the documents use, so the pattern must reach it.

    Both strings here are real: they are what `docs/INTERNAL_HARDENING_AUDIT_20251219.md`
    gives, a file this fence found and the sweep before it did not.
    """
    planted = tmp_path / "planted.md"
    planted.write_text(f"- **{acronym}** ({expansion}): notes\n", encoding="utf-8")

    monkeypatch.setattr(f"{__name__}._scannable_files", lambda: [planted.name])
    monkeypatch.setattr(
        f"{__name__}._read", lambda _p: planted.read_text(encoding="utf-8")
    )

    with pytest.raises(AssertionError):
        test_every_spelled_out_expansion_is_canonical()


@pytest.mark.parametrize(
    ("acronym", "invented"),
    [
        ("CASPER", "Capital Analytics Sensitivity Portfolio Evaluation Rigor"),
        ("CESSPIT", "Careful Error Specification Strict Principle Input Typology"),
        ("CCCDIR", "Completely Commented Code Directory Import Rules"),
    ],
)
def test_initials_guard_rejects_an_invented_expansion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, acronym: str, invented: str
) -> None:
    """Observe the general fence firing on an expansion no denylist anticipated.

    The CASPER case is the one from `Full Dolphin Rules` in the DutchBay_RAG repository,
    which read as authoritative because its other two entries were the CSV's real
    secondary meanings.
    """
    planted = tmp_path / "planted.md"
    planted.write_text(f"**{acronym}** ({invented})\n", encoding="utf-8")

    monkeypatch.setattr(f"{__name__}._scannable_files", lambda: [planted.name])
    monkeypatch.setattr(
        f"{__name__}._read", lambda _p: planted.read_text(encoding="utf-8")
    )

    with pytest.raises(AssertionError):
        test_every_spelled_out_expansion_is_canonical()


@pytest.mark.parametrize(
    ("acronym", "wording"),
    [
        ("CASPER", "Clear API Surfaces with Predictable Error Responses"),
        ("CESSPIT", "Config Explicit, Schema Strict, Pre-flight Integrity Tests"),
        (
            "CCCDIR",
            "Contracts Centralized, Compliance Documented, Import Relationships explicit",
        ),
    ],
)
def test_canonical_wording_is_recognised_as_a_definition(
    acronym: str, wording: str
) -> None:
    """Each canonical wording must be READ as a definition, not skipped as a usage note.

    Without this the acceptance test below passes vacuously. Two of the three need help to
    spell: CASPER's has the connector "with" in it, and CESSPIT's turns on "Pre-flight"
    counting as one word.
    """
    spelled = _spelled_definition(wording, acronym)
    assert (
        spelled is not None
    ), f"{acronym} canonical wording is not read as a definition"
    phrase, tokenisation = spelled
    assert phrase in _canonical_phrasings()[tokenisation]


def test_initials_guard_accepts_the_canonical_wording(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The inverse control: the CSV's own wording must pass, or the fence is unusable."""
    planted = tmp_path / "planted.md"
    planted.write_text(
        "### CASPER - Clear API Surfaces with Predictable Error Responses\n"
        "### CESSPIT: Config Explicit, Schema Strict, Pre-flight Integrity Tests\n"
        "### CCCDIR (Contracts Centralized, Compliance Documented, "
        "Import Relationships explicit)\n"
        # The same wording as it appears inside a Python string literal, trailing escape
        # and all. This is the shape that failed CI on the first push of this guard.
        '        "### CASPER - Clear API Surfaces with Predictable Error '
        'Responses\\n"\n',
        encoding="utf-8",
    )

    monkeypatch.setattr(f"{__name__}._scannable_files", lambda: [planted.name])
    monkeypatch.setattr(
        f"{__name__}._read", lambda _p: planted.read_text(encoding="utf-8")
    )

    test_every_spelled_out_expansion_is_canonical()


def test_initials_guard_ignores_inline_usage_notes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The repository's hundreds of compliance notes are usages, and must not trip it."""
    planted = tmp_path / "planted.py"
    planted.write_text(
        "# CASPER-guarded on the [gis] extra; rasterio fails at call time.\n"
        "# CESSPIT - a typo fails loud rather than being silently dropped.\n"
        "# CCCDIR - one contract surface; no new result type invented.\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(f"{__name__}._scannable_files", lambda: [planted.name])
    monkeypatch.setattr(
        f"{__name__}._read", lambda _p: planted.read_text(encoding="utf-8")
    )

    test_every_spelled_out_expansion_is_canonical()
