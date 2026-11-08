"""Guard ``TRAIN-01``: reviewed pull requests may share one full-suite run as a merge train.

The rule comes from the project owner's decision of 2026-10-31 ("Trains now"). Two or three
reviewed draft pull requests, the cars, are carried on one train branch that starts at ``main``
and has one commit per car. The full suite runs once on that branch, and the train lands by
rebase-merge, so each car stays its own commit on ``main``. A car's review binding reaches the
train head only through ``RECRUIT-01`` module 3 §8, which applies §7's three proofs to the train.

What is pinned here is the text that carries those controls: the rule row, module 3 §8, the
``DELIVERY-01`` sentence, and the routing in ``AGENTS.md`` and the steward skill. Each guard is a
pure function over text, so each pinned control has a negative control that removes it and
watches the guard fail.

The steward skill's check blocks are shell commands a merge coordinator runs by hand: the train
build, the pre-landing check, the landing check, the KPI check and the single-pull-request merge
check. Each is executed here exactly as printed, with plain ``bash -c`` and no added ``-e``,
against a throwaway repository with its own ``origin``. Each passes only by exiting 0 and
printing its OK line, and each fails closed with no OK line. The cases below exercise specific
failure modes and targeted mutations; they do not establish exhaustive mutation coverage. Hostile
controls strip a block's ``set -euo pipefail`` and watch bad landings exit 0, and strip the
pre-landing loop and watch a swapped train pass (#1515 assurance F-1, domain D-1).

On 2026-11-08 the owner narrowed proof 2 for trains (option A on the project thread's decision
card). A shared runtime input, such as ``VERSION`` or a module ``tests/conftest.py`` loads, links
two cars only when one side's changed bytes are consumed by the other side's code or tests, shown
by module 3 section 8's consumption artifact. The guards pin that text, and a separate guard keeps
the narrowing out of section 7, which still governs a single pull request's base advance.
"""

from __future__ import annotations

import csv
import hashlib
import re
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CANONICAL_RULESET = REPO_ROOT / "go_with_the_flow_rules_v3_0_clean.csv"
MODULE_3 = (
    REPO_ROOT
    / "docs"
    / "governance"
    / "recruit_01"
    / "03_independent_review_and_attestation.md"
)
AGENTS = REPO_ROOT / "AGENTS.md"
STEWARD = REPO_ROOT / ".claude" / "skills" / "steward" / "SKILL.md"

TRAIN_01_REQUIRED_CONTROLS = (
    "A train is optional: a pull request may always land alone as before.",
    "the delivery coordinator holding the merge lease builds, verifies and lands a train",
    "is not the writer of any car",
    "whose required lanes are bound to its frozen draft head under REVIEW-01",
    "A train carries two or three cars.",
    "The cars are path-disjoint, no car is stacked on another",
    "at most one car is R3_CONSEQUENTIAL or changes a KPI",
    "starts at the current main and carries one non-merge commit per car, in queue order",
    "carries the car's hand-written merge message, which meets R18",
    "A car whose diff does not apply cleanly leaves the train.",
    "Nothing else is committed to the train branch.",
    "a single focused train issue listing every car",
    "VERIFY-01 receipts table",
    "It is opened ready for review, so the full suite runs once on the union of the cars.",
    "only through RECRUIT-01 module 3 section 8",
    "blob-hash identity for every file the lane judged",
    "bidirectional import isolation between the car and everything else the train head changes",
    "the complete diff from the car's reviewed head to the train head",
    "links a car to another part of the train head only when one side changes bytes in it that the other side's code or tests consume",
    "The narrowing covers only an input shared by loading it, through tests/conftest.py, pytest's configuration or the installed environment",
    "a module or test file that one side changes and that imports a module the other side changes is a link under the import-reference test, whatever the consumption artifact shows",
    "Changed bytes that take effect when a file is loaded or tests are collected, without a consumer naming them, are a link too",
    "an autouse fixture, a pytest hook, a module-level statement with a side effect, and pytest's or coverage's own configuration in pyproject.toml",
    "Otherwise, loading a file is not consuming the bytes changed in it.",
    "the changed bytes, a reference search, and a differential run of each side's test selection",
    "Without that artifact the input is a link, and a judgement never substitutes for it.",
    "Single pull requests keep module 3 section 7's proof 2 unchanged.",
    "If any proof fails, that car leaves the train.",
    "the lender KPI vector on the train head must equal the vector the owner signed off",
    "otherwise the train waits for her sign-off on the train head's vector",
    "the train head's lender KPI vector must equal main's",
    "the train lands with rebase-merge, never squash",
    "no car is edited on the train branch",
    "restarts its reviews under module 3 section 6",
    "were never run by the full suite on their own",
    "does not change which checks are required",
    "what MERGE-01 means by green",
    "the module 3 section 6 and section 7 controls",
    "REVIEW-01's lane counts",
    "Any mismatch fails the merge verification closed.",
    "each train commit is exactly its car's reviewed diff",
    "keeps the car pull request's author as a squash merge of that pull request would record it",
    "before the train is opened ready and again just before landing, the recorded main SHA is origin/main",
    "its message and author equal the car's recorded merge message and author",
    "its subject ends with that car's pull-request number",
    "the car's reviewed head is still its pull request's head",
    "the train is rebuilt from the new main, never refreshed with a merge commit",
    "the SHA the merge returned equals the freshly fetched origin/main tip, the landed commits contain no merge commit",
    "each landed commit's tree, message and author equal the matching train commit's",
    "tests/lint/test_train_policy.py",
    "GitHub's merge queue is not used",
    "'Trains now' on the decision card in the project thread, 2026-10-31T17:40:55Z",
    "option A on the decision card in the project thread ('A please.', 2026-11-08T01:34:54Z)",
)

DELIVERY_01_TRAIN_SENTENCE = (
    "A TRAIN-01 merge train is not a whale: each car stays one dolphin-sized change on its own "
    "branch with its own review, and lands as its own independently revertable commit."
)

MODULE_3_REQUIRED_CONTROLS = (
    "## 8. Merge trains (`TRAIN-01`)",
    "It adds a second carry-forward beside §7 and does not change §7.",
    "only when its lane records all three of §7's proofs, applied to the train",
    "**BLOB-HASH IDENTITY** for every file the lane judged",
    "**BIDIRECTIONAL IMPORT ISOLATION** between the car and everything else the train head changes",
    "The **complete diff from the car's reviewed head to the train head**",
    "the car leaves the train and its disposition stays bound to its own head",
    "A judgement that another car cannot matter never substitutes for these artifacts.",
    "so §6 restarts both of the car's reviews",
    "The train lands by rebase-merge, never squash.",
    "**Each train commit must be exactly its car's reviewed diff:**",
    "Run the pre-landing check twice: on the built train before it is opened ready",
    "which must be `origin/main` at that moment",
    "with the same modes and blobs. Compare both old and new modes and blob IDs, change status, and",
    "the car pull request's author as a squash merge of that pull request would record it",
    "its subject ends with that car's pull-request number",
    "Each car's reviewed head must still be its pull request's head",
    "The three proofs above compare trees, so they cannot say which commit carries which car.",
    "never refreshed with a merge commit",
    "the SHA the merge returned equals the freshly fetched `origin/main` tip",
    "the landed commits contain no merge commit",
    "each landed commit's tree, message and author equal those of the matching train commit",
    "the first one's parent is the recorded `main` SHA",
    "the last landed commit's tree equals the train head's tree",
    "Any mismatch fails merge verification closed",
    "The commands that run these checks must fail closed on their own",
    "A check that passes in silence is not a check.",
    "Count shared runtime inputs as dependencies too",
    "A shared runtime input links the car to another part of the train head only when one",
    "side changes bytes in it that the other side's code or tests consume.",
    "Two kinds of change are links whatever the consumption artifact shows:",
    "**Import references.** The narrowing covers only an input shared by loading it, through",
    "that one side changes and that imports a module the other side changes is a link under the",
    "import-reference test, whatever the consumption artifact shows.",
    "**Load-time effects.** Changed bytes that take effect when a file is loaded or tests are",
    "collected, without a consumer naming them, are consumed by every test that loads them, so they",
    "an autouse fixture, a pytest hook, a module-level statement with a side effect",
    "and pytest's or coverage's own configuration in `pyproject.toml`.",
    "Otherwise, loading a file is not consuming the bytes changed in it: a definition or constant that",
    "only a named reference reaches is consumed only where something names it.",
    "are consumed is shown by that artifact, never by a judgement.",
    "Path-disjoint cars that share an input whose changed bytes are consumed are not isolated, and",
    "neither are cars whose consumption artifact is missing or incomplete.",
    "**Consumption artifact.**",
    "the lane records the artifact in both directions",
    "the lane re-runs what it needs before relying on it",
    "with their old and new literal values",
    "old or new literal values in the other side's changed files and test selection",
    "and any hit or difference is a link",
    "A hit is a link even when the test that holds it would pass either way.",
    "Each car's selection runs on `main` plus that car alone and on the train head",
    "Each car's selection also runs on its own train commit, the tree it lands as on `main`.",
    "the car's selection also runs on its reviewed head and on `main` plus the car",
    "the advance's selection runs on `main` and on `main` plus the car",
    "All runs of a car's selection must collect the same test IDs with the same outcomes.",
    "Where a side changes the lock or an installed library, each run uses an environment",
    "installed from its own tree's lock",
    "A side's test selection is the test files it adds or changes, and every test file whose own import statements name a module it changes.",
    "An empty selection is recorded as empty, and the reference search then carries the direction alone.",
    "A value that one side reads through code neither side changed",
    "bound that residual; they do not remove it.",
    "§7's proof 2 for a single pull request's base advance is unchanged",
    "were never run by the full suite on their own",
    "A train lifts no `HOLD`",
)

AGENTS_REQUIRED_CONTROLS = (
    "`TRAIN-01`: the merge coordinator may land two or three reviewed draft pull requests as one",
    "at most one of them changes a KPI",
    "the train lands by rebase-merge, never squash",
    "only through module 3 §8's three proofs",
    "A shared runtime input links a car to another car or to an advance of `main`",
    "only when one side's changed bytes are consumed by the other's code or tests",
    "shown by §8's recorded consumption artifact",
    "A changed file that imports a module the other side changes, and a change that acts when files load or tests are collected, are links whatever the artifact shows.",
)

STEWARD_REQUIRED_CONTROLS = (
    "### Merge trains (`TRAIN-01`)",
    "never a train that carries a car it wrote",
    "A pull request may always land alone instead.",
    "at most one may be `R3` or change a KPI",
    "record it on #1353",
    "take the pull-request number and the reviewed head from the car's lane records",
    "check the head against `refs/pull/<pr>/head`",
    "The author is the car pull request's author, as a squash merge of that pull request would",
    "If a car's diff does not apply cleanly, the block stops",
    "Commit nothing else.",
    "**Run the pre-landing check (step 6) on the train before you open it.**",
    "ready for review, with the train issue as its `Work item:`",
    "never merge `main` into the train",
    "Rebuild the train from the new `main` instead",
    "module 3 §8's three proofs",
    "is a link only when one side's changed bytes are consumed by the other side's code or tests",
    "A changed file that imports a module the other side changes is a link whatever the artifact shows",
    "a change that acts when files load or tests are collected",
    "Attach §8's consumption artifact for each such input, in both directions",
    "on its own train commit and on the train head, plus §8's reviewed-head and advance pairs when `main` has moved",
    "with the same test IDs and outcomes. Without the artifact the input is a link.",
    "edit no car on it",
    "**Land it with rebase-merge, never squash.**",
    "that the recorded `main` is `origin/main`",
    "each train commit is exactly its car's reviewed diff, under its recorded message and author",
    "with each car's reviewed head still its pull request's head",
    "It prints the count and SHA-256 of the 41-KPI lender vector at each revision",
    "The loop compares train commit `k` with car `k`",
    "Silence, or a missing `OK` line, is a failure.",
    "never drop its `set -euo pipefail` line",
    "The commits between cars on `main` were never run by the full suite on their own",
)


def _rules_by_id() -> dict[str, dict[str, str]]:
    """Load the canonical ruleset keyed by its unique rule identifiers."""
    with CANONICAL_RULESET.open(encoding="utf-8", newline="") as handle:
        return {row["rule_id"]: row for row in csv.DictReader(handle)}


def _policy_text(rule: dict[str, str]) -> str:
    """Join a rule's human-readable cells the way the canonical-source guards do."""
    return " ".join((rule["title"], rule["description"], rule["enforcement"]))


def _assert_train_01(rule: dict[str, str]) -> None:
    """The rule row is active, filed under Git Workflow, and carries every control."""
    assert rule["status"] == "active"
    assert rule["category"] == "Git Workflow"
    policy = _policy_text(rule)
    missing = [c for c in TRAIN_01_REQUIRED_CONTROLS if c not in policy]
    assert not missing, f"TRAIN-01 lost controls: {missing}"
    # A train that may squash loses each car's commit, which is what keeps a car revertable.
    assert "may squash" not in policy and "or squash" not in policy


def _assert_delivery_01(rule: dict[str, str]) -> None:
    """DELIVERY-01 names a train as compliant, and still rejects whale pull requests."""
    assert DELIVERY_01_TRAIN_SENTENCE in rule["enforcement"]
    assert "reviewers reject 'whale' mega-PRs" in rule["enforcement"]


def _normalize(text: str) -> str:
    """Collapse whitespace so re-wrapping a paragraph neither breaks nor satisfies a guard."""
    return " ".join(text.split())


def _assert_contains_all(text: str, controls: tuple[str, ...], where: str) -> None:
    """Every pinned control appears in ``text``, compared with whitespace collapsed."""
    flat = _normalize(text)
    missing = [c for c in controls if _normalize(c) not in flat]
    assert not missing, f"{where} lost controls: {missing}"


def test_train_01_row_carries_its_controls() -> None:
    """The canonical row is present, active and complete."""
    _assert_train_01(_rules_by_id()["TRAIN-01"])


def test_delivery_01_names_a_train_as_compliant() -> None:
    """DELIVERY-01 does not read a train as the whale it forbids."""
    _assert_delivery_01(_rules_by_id()["DELIVERY-01"])


def test_module_3_carries_the_train_carry_forward_and_landing_check() -> None:
    """Module 3 §8 applies §7's proofs to the train and verifies the landing commit by commit."""
    _assert_contains_all(
        MODULE_3.read_text(encoding="utf-8"), MODULE_3_REQUIRED_CONTROLS, "module 3"
    )


def test_agents_md_routes_to_train_01() -> None:
    """The Codex gateway carries the same train limits."""
    _assert_contains_all(
        AGENTS.read_text(encoding="utf-8"), AGENTS_REQUIRED_CONTROLS, "AGENTS.md"
    )


def test_steward_skill_routes_to_train_01() -> None:
    """The pull-request skill carries the build, carry-forward and landing steps."""
    _assert_contains_all(
        STEWARD.read_text(encoding="utf-8"), STEWARD_REQUIRED_CONTROLS, "steward skill"
    )


def _without(text: str, control: str) -> str:
    """Return ``text`` with one pinned control removed, failing if it was never there."""
    assert control in text, f"control not present to remove: {control!r}"
    return text.replace(control, "REMOVED_CONTROL")


@pytest.mark.parametrize("control", TRAIN_01_REQUIRED_CONTROLS)
def test_train_01_guard_fails_when_a_control_is_removed(control: str) -> None:
    """Negative control: each TRAIN-01 control is load-bearing for its guard."""
    rule = dict(_rules_by_id()["TRAIN-01"])
    for cell in ("title", "description", "enforcement"):
        if control in rule[cell]:
            rule[cell] = _without(rule[cell], control)
    with pytest.raises(AssertionError):
        _assert_train_01(rule)


def test_train_01_guard_fails_if_a_squash_landing_is_allowed() -> None:
    """Negative control: adding a squash option beside the rebase-merge wording fails."""
    rule = dict(_rules_by_id()["TRAIN-01"])
    rule["description"] += " Where convenient the train may squash instead."
    with pytest.raises(AssertionError):
        _assert_train_01(rule)


@pytest.mark.parametrize(
    "cell,value", [("status", "retired"), ("category", "Recruitment & Review")]
)
def test_train_01_guard_fails_on_a_demoted_row(cell: str, value: str) -> None:
    """Negative control: a retired or re-filed row does not pass as the live rule."""
    rule = dict(_rules_by_id()["TRAIN-01"])
    rule[cell] = value
    with pytest.raises(AssertionError):
        _assert_train_01(rule)


@pytest.mark.parametrize(
    "control",
    [DELIVERY_01_TRAIN_SENTENCE, "reviewers reject 'whale' mega-PRs"],
    ids=["train-sentence-removed", "whale-rejection-removed"],
)
def test_delivery_01_guard_fails_when_a_control_is_removed(control: str) -> None:
    """Negative control: losing the train sentence, or the whale rejection, fails."""
    rule = dict(_rules_by_id()["DELIVERY-01"])
    rule["enforcement"] = _without(rule["enforcement"], control)
    with pytest.raises(AssertionError):
        _assert_delivery_01(rule)


_TEXT_GUARDS: tuple[tuple[str, Path, tuple[str, ...]], ...] = (
    ("module 3", MODULE_3, MODULE_3_REQUIRED_CONTROLS),
    ("AGENTS.md", AGENTS, AGENTS_REQUIRED_CONTROLS),
    ("steward skill", STEWARD, STEWARD_REQUIRED_CONTROLS),
)


@pytest.mark.parametrize(
    "where,path,control",
    [(where, path, c) for where, path, controls in _TEXT_GUARDS for c in controls],
)
def test_text_guards_fail_when_a_control_is_removed(
    where: str, path: Path, control: str
) -> None:
    """Negative control: each routing and module control is load-bearing for its guard."""
    controls = next(c for w, _, c in _TEXT_GUARDS if w == where)
    altered = _without(
        _normalize(path.read_text(encoding="utf-8")), _normalize(control)
    )
    with pytest.raises(AssertionError):
        _assert_contains_all(altered, controls, where)


# The owner narrowed proof 2's shared-input test for trains on 2026-11-08 (option A). The
# narrowing is train-only: a single pull request's base advance keeps section 7's proof 2 as
# it was, and the blanket sentence it replaced must not come back beside it.
_SECTION_7 = re.compile(r"^## 7\. .*?(?=^## 8\. )", re.MULTILINE | re.DOTALL)
STRICT_SHARED_INPUT_SENTENCE = (
    "Path-disjoint cars that share such an input are not isolated."
)
TRAIN_ONLY_MARKERS = (
    "consumption artifact",
    "loading a file is not consuming",
    "import-reference test, whatever",
    "load-time effects",
    "is a link only when",
    "links the car to another part of the train head only when",
)


def _assert_shared_input_narrowing_is_train_only(text: str) -> None:
    """Section 7 carries none of the train-only narrowing, and the blanket sentence is gone."""
    section_7 = _SECTION_7.search(text)
    assert section_7, "module 3 section 7 not found before section 8"
    flat_7 = _normalize(section_7.group(0))
    leaked = [m for m in TRAIN_ONLY_MARKERS if m in flat_7.lower()]
    assert not leaked, f"section 7 picked up the train-only shared-input test: {leaked}"
    assert (
        "**BIDIRECTIONAL IMPORT ISOLATION**: no changed module references a reviewed module"
        in flat_7
    )
    blanket = _normalize(STRICT_SHARED_INPUT_SENTENCE) in _normalize(text)
    assert not blanket, "the blanket shared-input sentence came back"


def test_shared_input_narrowing_stays_in_section_8() -> None:
    """The narrower link test applies to trains only; section 7 is unchanged."""
    _assert_shared_input_narrowing_is_train_only(MODULE_3.read_text(encoding="utf-8"))


@pytest.mark.parametrize("marker", TRAIN_ONLY_MARKERS)
def test_shared_input_guard_fails_if_section_7_is_narrowed(marker: str) -> None:
    """Negative control: copying any narrowing phrase into section 7 fails."""
    text = MODULE_3.read_text(encoding="utf-8")
    altered = text.replace(
        "If any proof is absent, incomplete or fails, the disposition LAPSES.",
        f"A shared input {marker} applies here too. "
        "If any proof is absent, incomplete or fails, the disposition LAPSES.",
        1,
    )
    assert altered != text
    with pytest.raises(AssertionError):
        _assert_shared_input_narrowing_is_train_only(altered)


def test_shared_input_guard_fails_if_the_blanket_sentence_returns() -> None:
    """Negative control: restoring the old blanket sentence beside the narrowed test fails."""
    text = MODULE_3.read_text(encoding="utf-8").replace(
        "**Consumption artifact.**",
        STRICT_SHARED_INPUT_SENTENCE + "\n\n**Consumption artifact.**",
        1,
    )
    with pytest.raises(AssertionError):
        _assert_shared_input_narrowing_is_train_only(text)


# Domain lane D-1 on #1576: bytes that act when a file is loaded or tests are collected are
# consumed by every test that loads them. "Loading a file is not consuming" holds only for the
# remaining case, so wherever the sentence appears it must be the qualified "Otherwise," form.
_LOADING_SENTENCE = re.compile(
    r"(\S+\s+)?loading a file is not consuming", re.IGNORECASE
)


def _assert_loading_sentence_is_qualified(text: str, where: str) -> None:
    """Every "loading a file is not consuming" follows "Otherwise," and is not the blanket form."""
    hits = list(_LOADING_SENTENCE.finditer(_normalize(text)))
    assert hits, f"{where} lost the qualified loading sentence"
    bare = [m.group(0) for m in hits if (m.group(1) or "").strip() != "Otherwise,"]
    assert not bare, f"{where} states the unqualified loading sentence: {bare}"


def _train_01_text() -> str:
    return _policy_text(_rules_by_id()["TRAIN-01"])


def test_loading_sentence_is_qualified_in_module_3_and_the_rule() -> None:
    """Load-time effects stay links; only the remaining case is "not consuming"."""
    _assert_loading_sentence_is_qualified(
        MODULE_3.read_text(encoding="utf-8"), "module 3"
    )
    _assert_loading_sentence_is_qualified(_train_01_text(), "TRAIN-01")


@pytest.mark.parametrize("where", ["module 3", "TRAIN-01"])
def test_loading_sentence_guard_fails_on_the_blanket_form(where: str) -> None:
    """Negative control: dropping "Otherwise," restores the blanket sentence and fails."""
    text = (
        MODULE_3.read_text(encoding="utf-8")
        if where == "module 3"
        else _train_01_text()
    )
    altered = _normalize(text).replace(
        "Otherwise, loading a file is not consuming", "Loading a file is not consuming"
    )
    assert altered != _normalize(text)
    with pytest.raises(AssertionError):
        _assert_loading_sentence_is_qualified(altered, where)


# --------------------------------------------------------------------------- #
# The steward skill's landing checks, run against a throwaway repository.
# --------------------------------------------------------------------------- #

_FENCE = re.compile(r"^ *```bash\n(.*?)^ *```$", re.MULTILINE | re.DOTALL)
_PLACEHOLDER = re.compile(r"<[a-z0-9][a-z0-9 -]*>")

BUILD_OK = "TRAIN-01 train built: "
PRE_OK = "TRAIN-01 pre-landing check: OK"
POST_OK = "TRAIN-01 landing check: OK"
KPI_OK = "TRAIN-01 KPI check: OK"
MERGE_OK = "Merge check: OK"
# CLEANUP-01's branch retirement gate (#1563). It reads refs rather than certifying object
# identity, but it carries the same Git hygiene so a hostile environment cannot redirect it.
# Its behaviour is exercised in tests/lint/test_gwtf_canonical_source.py.
CLEANUP_OK = "CLEANUP-01 branch retirement: OK"
FAIL_CLOSED = "set -euo pipefail"
ALL_OK = (BUILD_OK, PRE_OK, POST_OK, KPI_OK, MERGE_OK, CLEANUP_OK)


def _block(ok: str) -> str:
    """Return the one shell block in the steward skill whose last line prints ``ok``."""
    fenced: list[str] = _FENCE.findall(STEWARD.read_text(encoding="utf-8"))
    blocks = [
        block
        for block in fenced
        if block.strip().splitlines()[-1].strip().startswith(f'echo "{ok}')
    ]
    assert len(blocks) == 1, f"expected one block printing {ok!r}, found {len(blocks)}"
    # Remove Markdown list indentation, including the Python heredoc terminator. The depth is
    # the fence's own: 3 for a top-level step, 5 for a fence inside a step's bullet (#1563).
    first = blocks[0].splitlines()[0]
    pad = " " * (len(first) - len(first.lstrip(" ")))
    return (
        "\n".join(
            line[len(pad) :] if line.startswith(pad) else line
            for line in blocks[0].splitlines()
        )
        + "\n"
    )


def _assert_block_fails_closed_by_shape(block: str, ok: str) -> None:
    """A check block opens with ``set -euo pipefail`` and ends by printing its OK line."""
    lines = [line.strip() for line in block.strip().splitlines()]
    first, last = lines[0], lines[-1]
    assert first == FAIL_CLOSED, f"block does not open with {FAIL_CLOSED!r}: {first!r}"
    ends_with_ok = last.startswith(f'echo "{ok}')
    assert ends_with_ok, f"block does not end with its OK line: {last!r}"


@pytest.mark.parametrize("ok", ALL_OK)
def test_check_blocks_fail_closed_by_shape(ok: str) -> None:
    """Every check block stops at the first failed test and only passes by saying so."""
    _assert_block_fails_closed_by_shape(_block(ok), ok)


@pytest.mark.parametrize("ok", ALL_OK)
@pytest.mark.parametrize(
    "strip", [FAIL_CLOSED, "echo "], ids=["no-set-e", "no-ok-line"]
)
def test_block_shape_guard_fails_on_a_weakened_block(ok: str, strip: str) -> None:
    """Negative control: dropping the set line or the OK line from any block fails."""
    block = _block(ok)
    lines = block.splitlines()
    if strip == "echo ":
        cut = max(i for i, line in enumerate(lines) if line.strip().startswith("echo "))
        weakened = "\n".join(lines[:cut] + lines[cut + 1 :])
    else:
        weakened = "\n".join(line for line in lines if strip not in line)
    with pytest.raises(AssertionError):
        _assert_block_fails_closed_by_shape(weakened, ok)


_ENV = {
    "GIT_AUTHOR_NAME": "Unrecorded Author",
    "GIT_AUTHOR_EMAIL": "unrecorded@example.invalid",
    "GIT_COMMITTER_NAME": "Merge Coordinator",
    "GIT_COMMITTER_EMAIL": "coordinator@example.invalid",
    "GIT_CONFIG_NOSYSTEM": "1",
    "PATH": "/usr/bin:/bin:/usr/local/bin",
}


def _env(repo: Path, extra: dict[str, str] | None = None) -> dict[str, str]:
    return {**_ENV, "HOME": str(repo.parent), **(extra or {})}


def _git(repo: Path, *args: str, env: dict[str, str] | None = None) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
        env=_env(repo, env),
    )
    return result.stdout.strip()


def _author_env(author: str) -> dict[str, str]:
    name, email = author[: author.index(" <")], author[author.index("<") + 1 : -1]
    return {"GIT_AUTHOR_NAME": name, "GIT_AUTHOR_EMAIL": email}


BASE_LINES = "".join(f"line {i}\n" for i in range(1, 16))
CARS = {
    1: ("a", "Car A Writer <a@example.invalid>"),
    2: ("b", "Car B Writer <b@example.invalid>"),
}


def _message(name: str, pr: int) -> str:
    return f"docs: car {name} (#{pr})\n\nWhy car {name} exists.\n\nWork item: #{pr}0\n"


@dataclass
class Rig:
    """A repository with an ``origin``, two reviewed cars and a ``main`` that moved on.

    The cars branch off ``old_main``. ``main`` then changes line 14 of ``base.txt`` and adds
    ``other.txt``, so each car's diff is taken from its own merge base. Each car's head is
    published as ``refs/pull/<pr>/head`` on ``origin``, and the car directory holds each car's
    ``<pr>.msg`` and ``<pr>.author``, as the steward skill's step 2 records them.
    """

    repo: Path
    cardir: Path
    old_main: str
    main: str
    heads: dict[int, str]

    def git(self, *args: str, env: dict[str, str] | None = None) -> str:
        return _git(self.repo, *args, env=env)

    def add_car(self, pr: int, name: str, files: dict[str, str], author: str) -> str:
        """Add a car off ``old_main``: its head, its pull-request ref and its records."""
        self.git("switch", "-q", "--detach", self.old_main)
        for path, content in files.items():
            (self.repo / path).write_text(content, encoding="utf-8")
            self.git("add", path)
        self.git(
            "commit", "-q", "-m", f"car {name}, as reviewed", env=_author_env(author)
        )
        head = self.git("rev-parse", "HEAD")
        self.git("push", "-q", "origin", f"{head}:refs/pull/{pr}/head")
        (self.cardir / f"{pr}.msg").write_text(_message(name, pr), encoding="utf-8")
        (self.cardir / f"{pr}.author").write_text(f"{author}\n", encoding="utf-8")
        self.heads[pr] = head
        return head

    def cars(self, *prs: int) -> str:
        return " ".join(f"{pr}:{self.heads[pr]}" for pr in prs)

    def publish(self, sha: str) -> None:
        """Move ``origin``'s ``main`` to ``sha``, as a merge on GitHub would."""
        self.git("push", "-q", "--force", "origin", f"{sha}:refs/heads/main")

    def commit_tree(
        self, tree: str, parents: list[str], message: str, author: str
    ) -> str:
        args = ["commit-tree", tree, "-m", message]
        for parent in parents:
            args += ["-p", parent]
        return self.git(*args, env=_author_env(author))

    def build(
        self, commits: list[tuple[int, str, str]], stray: dict[str, str] | None = None
    ) -> str:
        """Build a train by hand from ``(pr whose diff, message, author)`` entries.

        The steward skill's own build block is run by ``run_build``. This builder exists so the
        negative controls can build trains that the skill's block never would.
        """
        self.git("switch", "-q", "--detach", self.main)
        for index, (pr, message, author) in enumerate(commits):
            base = self.git("merge-base", self.main, self.heads[pr])
            patch = self.repo.parent / f"car-{index}.patch"
            patch.write_text(
                self.git("diff", "--binary", base, self.heads[pr]) + "\n",
                encoding="utf-8",
            )
            self.git("apply", "--index", str(patch))
            for path, content in (stray or {}).items() if index == 0 else ():
                (self.repo / path).write_text(content, encoding="utf-8")
                self.git("add", path)
            self.git("commit", "-q", "-m", message, env=_author_env(author))
        return self.git("rev-parse", "HEAD")

    def faithful(self, *prs: int) -> str:
        return self.build([(pr, _message(CARS[pr][0], pr), CARS[pr][1]) for pr in prs])

    def rebase_merge(self, train: str, n: int, onto: str | None = None) -> str:
        """Land a train as GitHub's rebase-merge does: each commit replayed, new SHAs."""
        self.git("switch", "-q", "--detach", onto or self.main)
        for back in range(n - 1, -1, -1):
            self.git("cherry-pick", "--allow-empty", f"{train}~{back}")
            self.git(
                "commit", "-q", "--amend", "--no-edit", "--date=2030-01-01T00:00:00"
            )
        return self.git("rev-parse", "HEAD")


@pytest.fixture
def rig(tmp_path: Path) -> Rig:
    if shutil.which("git") is None:
        pytest.skip("git is not installed")
    origin, repo, cardir = tmp_path / "origin.git", tmp_path / "repo", tmp_path / "cars"
    for path in (origin, repo, cardir):
        path.mkdir()
    _git(origin, "init", "-q", "--bare", "-b", "main")
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "remote", "add", "origin", str(origin))
    (repo / "base.txt").write_text(BASE_LINES, encoding="utf-8")
    _git(repo, "add", "base.txt")
    _git(repo, "commit", "-q", "-m", "chore: base")
    old_main = _git(repo, "rev-parse", "HEAD")
    (repo / "base.txt").write_text(
        BASE_LINES.replace("line 14", "line 14, moved"), "utf-8"
    )
    (repo / "other.txt").write_text("main moved on\n", encoding="utf-8")
    _git(repo, "add", "base.txt", "other.txt")
    _git(repo, "commit", "-q", "-m", "chore: main moved")
    main = _git(repo, "rev-parse", "HEAD")
    _git(repo, "push", "-q", "origin", "main")
    rig = Rig(repo=repo, cardir=cardir, old_main=old_main, main=main, heads={})
    for pr, (name, author) in CARS.items():
        rig.add_car(pr, name, {f"car_{name}.txt": f"{name}\n"}, author)
    return rig


def _fill(block: str, values: dict[str, str]) -> str:
    """Supply documented inputs as quoted data rather than replacing shell source."""
    names = {
        "<car directory>": "CAR_DIR",
        "<car list>": "TRAIN_CARS",
        "train/<date>-<n>": "TRAIN_BRANCH",
        "<main-sha>": "MAIN_SHA",
        "<train-head-sha>": "TRAIN_SHA",
        "<number of cars>": "CAR_COUNT",
        "<sha-the-merge-returned>": "LANDED_SHA",
        "<main-sha-recorded-before-landing>": "MAIN_SHA",
        "<kpi-car-head-or-main-sha>": "REFERENCE_SHA",
        "<merge-sha>": "MERGE_SHA",
        "<head-sha>": "HEAD_SHA",
        "<main-sha-recorded-in-step-2>": "MAIN_SHA",
        "<1 or 2>": "PARENTS",
    }
    supplied = {names[key]: value for key, value in values.items()}
    if "TRAIN_CARS" in supplied:
        directory = Path(supplied["CAR_DIR"])
        records = []
        for record in supplied["TRAIN_CARS"].split():
            pr, head = record.split(":")
            blobs = []
            for suffix in ("msg", "author"):
                data = (directory / f"{pr}.{suffix}").read_bytes()
                blobs.append(
                    hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()
                )
            records.append(":".join((pr, head, *blobs)))
        supplied["TRAIN_CARS"] = " ".join(records)
    prefix = "\n".join(
        f"export {key}={shlex.quote(value)}" for key, value in supplied.items()
    )
    return prefix + "\n" + block


def _run(
    rig: Rig, script: str, path: str | None = None
) -> subprocess.CompletedProcess[str]:
    """Run a block exactly as a steward would paste it: plain ``bash -c``, no added ``-e``."""
    env = _env(rig.repo, {"PATH": path} if path else None)
    return subprocess.run(
        ["bash", "-c", script],
        cwd=rig.repo,
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )


def _passed(result: subprocess.CompletedProcess[str], ok: str) -> bool:
    """A block passed only if it exited 0 and printed its OK line."""
    return result.returncode == 0 and ok in result.stdout


def _failed_closed(result: subprocess.CompletedProcess[str], ok: str) -> bool:
    """A block failed closed only if it exited non-zero and never printed its OK line."""
    return result.returncode != 0 and ok not in result.stdout


def _without_set_line(block: str) -> str:
    return "\n".join(line for line in block.splitlines() if FAIL_CLOSED not in line)


def run_build(
    rig: Rig, cars: str, block: str | None = None
) -> subprocess.CompletedProcess[str]:
    rig.git("switch", "-q", "--detach", rig.main)
    script = _fill(
        _block(BUILD_OK) if block is None else block,
        {
            "<car directory>": str(rig.cardir),
            "<car list>": cars,
            "train/<date>-<n>": f"train/test-{len(rig.git('branch', '--list', 'train/*').split())}",
        },
    )
    return _run(rig, script)


def run_pre(
    rig: Rig, train: str, cars: str, main: str | None = None, block: str | None = None
) -> subprocess.CompletedProcess[str]:
    script = _fill(
        _block(PRE_OK) if block is None else block,
        {
            "<main-sha>": main or rig.main,
            "<train-head-sha>": train,
            "<car directory>": str(rig.cardir),
            "<car list>": cars,
        },
    )
    return _run(rig, script)


def run_post(
    rig: Rig, train: str, landed: str, n: int = 2, block: str | None = None
) -> subprocess.CompletedProcess[str]:
    script = _fill(
        _block(POST_OK) if block is None else block,
        {
            "<number of cars>": str(n),
            "<sha-the-merge-returned>": landed,
            "<train-head-sha>": train,
            "<main-sha-recorded-before-landing>": rig.main,
        },
    )
    return _run(rig, script)


def _structural_only(block: str) -> str:
    """The pre-landing block without its per-car loop: the checks #1515 had at ``95dbe158``."""
    lines = block.splitlines()
    start = next(i for i, line in enumerate(lines) if line.strip() == "k=0")
    end = next(
        i for i, line in enumerate(lines) if i > start and line.strip() == "done"
    )
    return "\n".join(lines[:start] + lines[end + 1 :])


# --- build ----------------------------------------------------------------------------------


def test_build_block_builds_the_train_the_checks_accept(rig: Rig) -> None:
    """The skill's own build block makes a train that both landing checks pass."""
    result = run_build(rig, rig.cars(1, 2))
    assert _passed(result, BUILD_OK), result.stderr
    train = result.stdout.split(BUILD_OK)[1].strip()
    assert train == rig.faithful(1, 2) or rig.git(
        "rev-parse", f"{train}^{{tree}}"
    ) == rig.git("rev-parse", f"{rig.faithful(1, 2)}^{{tree}}")
    assert _passed(run_pre(rig, train, rig.cars(1, 2)), PRE_OK)
    landed = rig.rebase_merge(train, 2)
    rig.publish(landed)
    assert landed != train
    assert _passed(run_post(rig, train, landed), POST_OK)


def test_build_block_stops_when_a_car_does_not_apply(rig: Rig) -> None:
    """Negative control: a car whose diff conflicts with main stops the build, with no OK line."""
    rig.add_car(
        3, "c", {"other.txt": "not what main has\n"}, "Car C Writer <c@example.invalid>"
    )
    assert _failed_closed(run_build(rig, rig.cars(1, 3)), BUILD_OK)


# --- pre-landing ----------------------------------------------------------------------------


def test_pre_landing_check_fails_for_a_merge_commit_on_the_train(rig: Rig) -> None:
    """Negative control: car b landing as a content-carrying merge of an ancestor of main.

    The merge's first-parent chain is one commit per car on main, and its diff from its first
    parent is car b's diff under car b's message and author. Only the no-merges test stops it
    (#1515 assurance A-3).
    """
    first = rig.faithful(1)
    rig.git("switch", "-q", "--detach", first)
    (rig.repo / "car_b.txt").write_text("b\n", encoding="utf-8")
    rig.git("add", "car_b.txt")
    tree = rig.git("write-tree")
    merged = rig.commit_tree(tree, [first, rig.old_main], _message("b", 2), CARS[2][1])
    assert _failed_closed(run_pre(rig, merged, rig.cars(1, 2)), PRE_OK)


def test_pre_landing_check_fails_when_origin_main_moved(rig: Rig) -> None:
    """Negative control: a recorded main that is no longer origin/main fails (#1515 O-4)."""
    train = rig.faithful(1, 2)
    rig.git("switch", "-q", "--detach", rig.main)
    rig.git("commit", "-q", "--allow-empty", "-m", "chore: main moved again")
    rig.publish(rig.git("rev-parse", "HEAD"))
    assert _failed_closed(run_pre(rig, train, rig.cars(1, 2)), PRE_OK)


def test_pre_landing_check_fails_on_a_stale_base(rig: Rig) -> None:
    """Negative control: a train built on an older main fails against the recorded main."""
    train = rig.faithful(1, 2)
    rig.git("switch", "-q", "--detach", rig.main)
    rig.git("commit", "-q", "--allow-empty", "-m", "chore: main moved again")
    newer = rig.git("rev-parse", "HEAD")
    rig.publish(newer)
    assert _failed_closed(run_pre(rig, train, rig.cars(1, 2), main=newer), PRE_OK)


def _swapped_train(rig: Rig) -> str:
    """Car b's diff under car a's message and author, then the reverse (#1515 domain D-1)."""
    return rig.build(
        [(2, _message("a", 1), CARS[1][1]), (1, _message("b", 2), CARS[2][1])]
    )


def test_pre_landing_check_fails_when_car_messages_are_swapped(rig: Rig) -> None:
    """Negative control: each car's diff landing under the other car's message fails."""
    swapped = _swapped_train(rig)
    assert rig.git("rev-parse", f"{swapped}^{{tree}}") == rig.git(
        "rev-parse", f"{rig.faithful(1, 2)}^{{tree}}"
    )
    assert _failed_closed(run_pre(rig, swapped, rig.cars(1, 2)), PRE_OK)


def test_structural_checks_alone_pass_a_swapped_train(rig: Rig) -> None:
    """Hostile control: without the per-car loop, the swapped train passes in full."""
    block = _structural_only(_block(PRE_OK))
    assert "for car in" not in block
    assert _passed(
        run_pre(rig, _swapped_train(rig), rig.cars(1, 2), block=block), PRE_OK
    )


def test_pre_landing_check_fails_when_the_car_list_pairs_a_number_with_another_head(
    rig: Rig,
) -> None:
    """Negative control: a car list that carries the same swap as the train fails (A-1).

    Train commit 1 is car b's diff under car a's records, and the car list says car 1's head is
    car b's. Every comparison the loop makes from that list agrees, so only the check that
    ``refs/pull/1/head`` is still the listed head stops it.
    """
    swapped = rig.build(
        [(2, _message("a", 1), CARS[1][1]), (1, _message("b", 2), CARS[2][1])]
    )
    lying = f"1:{rig.heads[2]} 2:{rig.heads[1]}"
    assert _failed_closed(run_pre(rig, swapped, lying), PRE_OK)


def test_pre_landing_check_fails_on_a_stray_file_in_a_car_commit(rig: Rig) -> None:
    """Negative control: a car's train commit that carries a file the car never changed fails."""
    stray = rig.build(
        [(pr, _message(CARS[pr][0], pr), CARS[pr][1]) for pr in (1, 2)],
        stray={"stray.txt": "not reviewed\n"},
    )
    assert _failed_closed(run_pre(rig, stray, rig.cars(1, 2)), PRE_OK)


def test_pre_landing_check_fails_when_a_car_file_moved_on_main(rig: Rig) -> None:
    """Negative control: a car applied onto a file main changed lands a blob nobody reviewed.

    Car c edits line 2 of ``base.txt``, and main changed line 14 after car c branched. The diff
    applies cleanly and changes the same path with the same status, so only the blob column of
    the comparison stops it (#1515 assurance A-2).
    """
    rig.add_car(
        3, "c", {"base.txt": BASE_LINES.replace("line 2", "line 2, car c")}, CARS[2][1]
    )
    (rig.cardir / "3.author").write_text(f"{CARS[2][1]}\n", encoding="utf-8")
    result = run_build(rig, rig.cars(1, 3))
    assert _passed(result, BUILD_OK), result.stderr
    train = result.stdout.split(BUILD_OK)[1].strip()
    assert _failed_closed(run_pre(rig, train, rig.cars(1, 3)), PRE_OK)


def test_pre_landing_check_fails_when_a_message_body_differs(rig: Rig) -> None:
    """Negative control: the right subject over another car's body fails (#1515 DOM4-O2)."""
    body_swapped = rig.build(
        [
            (1, _message("a", 1), CARS[1][1]),
            (2, _message("a", 1).replace("(#1)", "(#2)", 1), CARS[2][1]),
        ]
    )
    assert _failed_closed(run_pre(rig, body_swapped, rig.cars(1, 2)), PRE_OK)


def test_pre_landing_check_fails_when_a_commit_has_the_wrong_author(rig: Rig) -> None:
    """Negative control: a train commit not under the recorded author fails (#1515 A-4)."""
    wrong = rig.build(
        [(1, _message("a", 1), CARS[1][1]), (2, _message("b", 2), CARS[1][1])]
    )
    assert _failed_closed(run_pre(rig, wrong, rig.cars(1, 2)), PRE_OK)


def test_pre_landing_check_fails_when_a_recorded_subject_names_the_wrong_car(
    rig: Rig,
) -> None:
    """Negative control: a recorded message whose subject ends with another number fails."""
    (rig.cardir / "2.msg").write_text(_message("b", 12), encoding="utf-8")
    result = run_build(rig, rig.cars(1, 2))
    assert _failed_closed(result, BUILD_OK)
    # Build independently so pre-landing also has to reject the bad recorded subject.
    train = rig.build(
        [(1, _message("a", 1), CARS[1][1]), (2, _message("b", 12), CARS[2][1])]
    )
    assert _failed_closed(run_pre(rig, train, rig.cars(1, 2)), PRE_OK)


def test_pre_landing_check_fails_for_a_single_car(rig: Rig) -> None:
    """Negative control: a train of one car is not a train; it lands alone instead."""
    assert _failed_closed(run_pre(rig, rig.faithful(1), rig.cars(1)), PRE_OK)


def test_pre_landing_check_fails_for_four_cars(rig: Rig) -> None:
    """Negative control: a train carries at most three cars."""
    for pr, name in ((3, "c"), (4, "d")):
        CARS_EXTRA[pr] = (name, f"Car {name.upper()} Writer <{name}@example.invalid>")
        rig.add_car(pr, name, {f"car_{name}.txt": f"{name}\n"}, CARS_EXTRA[pr][1])
    entries = [
        (pr, _message(name, pr), author)
        for pr, (name, author) in {**CARS, **CARS_EXTRA}.items()
    ]
    four = rig.build(entries)
    assert _failed_closed(run_pre(rig, four, rig.cars(1, 2, 3, 4)), PRE_OK)
    three = rig.build(entries[:3])
    assert _passed(run_pre(rig, three, rig.cars(1, 2, 3)), PRE_OK)


CARS_EXTRA: dict[int, tuple[str, str]] = {}


def test_pre_landing_check_fails_for_a_car_with_no_diff(rig: Rig) -> None:
    """Negative control: an empty commit for a car that changes nothing is not a car."""
    rig.git("push", "-q", "--force", "origin", f"{rig.main}:refs/pull/2/head")
    rig.heads[2] = rig.main
    first = rig.faithful(1)
    rig.git(
        "commit",
        "-q",
        "--allow-empty",
        "-m",
        _message("b", 2),
        env=_author_env(CARS[2][1]),
    )
    empty = rig.git("rev-parse", "HEAD")
    assert empty != first
    assert _failed_closed(run_pre(rig, empty, rig.cars(1, 2)), PRE_OK)


# --- post-landing ---------------------------------------------------------------------------


def _landed(rig: Rig, train: str) -> str:
    landed = rig.rebase_merge(train, 2)
    rig.publish(landed)
    return landed


def test_landing_check_fails_for_a_squash(rig: Rig) -> None:
    """Negative control: a squash has the train's final tree but not one commit per car."""
    train = rig.faithful(1, 2)
    rig.git("switch", "-q", "--detach", rig.main)
    rig.git("merge", "-q", "--squash", train)
    rig.git("commit", "-q", "-m", "docs: squashed train")
    squashed = rig.git("rev-parse", "HEAD")
    rig.publish(squashed)
    assert _failed_closed(run_post(rig, train, squashed), POST_OK)


def _tampered_first_car(rig: Rig) -> str:
    """Land car a with a changed tree and car b restoring it, so the final tree still matches."""
    rig.git("switch", "-q", "--detach", rig.main)
    (rig.repo / "car_a.txt").write_text("a, edited on landing\n", encoding="utf-8")
    rig.git("add", "car_a.txt")
    rig.git("commit", "-q", "-m", _message("a", 1), env=_author_env(CARS[1][1]))
    (rig.repo / "car_a.txt").write_text("a\n", encoding="utf-8")
    (rig.repo / "car_b.txt").write_text("b\n", encoding="utf-8")
    rig.git("add", "car_a.txt", "car_b.txt")
    rig.git("commit", "-q", "-m", _message("b", 2), env=_author_env(CARS[2][1]))
    tampered = rig.git("rev-parse", "HEAD")
    rig.publish(tampered)
    return tampered


def test_landing_check_fails_when_a_landed_tree_differs(rig: Rig) -> None:
    """Negative control: a landed car whose tree changed fails, even if the final tree matches."""
    train = rig.faithful(1, 2)
    tampered = _tampered_first_car(rig)
    assert rig.git("rev-parse", f"{tampered}^{{tree}}") == rig.git(
        "rev-parse", f"{train}^{{tree}}"
    )
    assert _failed_closed(run_post(rig, train, tampered), POST_OK)


def test_landing_check_fails_when_a_middle_car_of_three_differs(rig: Rig) -> None:
    """Negative control: in a three-car train, a tampered middle car fails inside the loop."""
    rig.add_car(3, "c", {"car_c.txt": "c\n"}, "Car C Writer <c@example.invalid>")
    train = rig.build(
        [
            (1, _message("a", 1), CARS[1][1]),
            (2, _message("b", 2), CARS[2][1]),
            (3, _message("c", 3), "Car C Writer <c@example.invalid>"),
        ]
    )
    rig.git("switch", "-q", "--detach", rig.main)
    rig.git("cherry-pick", f"{train}~2")
    (rig.repo / "car_b.txt").write_text("b, edited on landing\n", encoding="utf-8")
    rig.git("add", "car_b.txt")
    rig.git("commit", "-q", "-m", _message("b", 2), env=_author_env(CARS[2][1]))
    (rig.repo / "car_b.txt").write_text("b\n", encoding="utf-8")
    (rig.repo / "car_c.txt").write_text("c\n", encoding="utf-8")
    rig.git("add", "car_b.txt", "car_c.txt")
    rig.git(
        "commit",
        "-q",
        "-m",
        _message("c", 3),
        env=_author_env("Car C Writer <c@example.invalid>"),
    )
    tampered = rig.git("rev-parse", "HEAD")
    rig.publish(tampered)
    assert rig.git("rev-parse", f"{tampered}^{{tree}}") == rig.git(
        "rev-parse", f"{train}^{{tree}}"
    )
    assert _failed_closed(run_post(rig, train, tampered, n=3), POST_OK)


def test_landing_check_fails_when_a_landed_message_differs(rig: Rig) -> None:
    """Negative control: a landing with every tree right but a reworded car message fails."""
    train = rig.faithful(1, 2)
    landed = rig.rebase_merge(train, 2)
    rig.git("commit", "-q", "--amend", "-m", "docs: car b, reworded (#2)")
    reworded = rig.git("rev-parse", "HEAD")
    rig.publish(reworded)
    assert _failed_closed(run_post(rig, train, reworded), POST_OK)
    assert landed != reworded


def test_landing_check_fails_when_a_landed_author_differs(rig: Rig) -> None:
    """Negative control: a landing that changed a car's author fails (#1515 A-4)."""
    train = rig.faithful(1, 2)
    rig.rebase_merge(train, 2)
    rig.git("commit", "-q", "--amend", "--no-edit", "--reset-author")
    reauthored = rig.git("rev-parse", "HEAD")
    rig.publish(reauthored)
    assert _failed_closed(run_post(rig, train, reauthored), POST_OK)


def test_landing_check_fails_when_given_the_train_head(rig: Rig) -> None:
    """Negative control: the train head passed as the landed SHA fails (#1515 assurance O-4).

    The train head has every tree, message and author right, on top of the recorded main, so
    only the check that the landed SHA is on ``origin/main`` stops it.
    """
    train = rig.faithful(1, 2)
    _landed(rig, train)
    assert _failed_closed(run_post(rig, train, train), POST_OK)


def test_landing_check_fails_for_a_merge_with_foreign_parents(rig: Rig) -> None:
    """Negative control: a landed merge whose extra parent carries foreign commits fails.

    Every tree, message and author matches along the first-parent chain, so only the no-merges
    test stops it (#1515 domain lane 1, O-1).
    """
    train = rig.faithful(1, 2)
    first = rig.rebase_merge(f"{train}~1", 1)
    rig.git("switch", "-q", "--detach", rig.main)
    rig.git("commit", "-q", "--allow-empty", "-m", "chore: foreign one")
    rig.git("commit", "-q", "--allow-empty", "-m", "chore: foreign two")
    foreign = rig.git("rev-parse", "HEAD")
    merged = rig.commit_tree(
        rig.git("rev-parse", f"{train}^{{tree}}"),
        [first, foreign],
        _message("b", 2),
        CARS[2][1],
    )
    rig.publish(merged)
    assert _failed_closed(run_post(rig, train, merged), POST_OK)


def test_landing_check_fails_when_the_landing_skips_the_recorded_main(rig: Rig) -> None:
    """Negative control: a landing on an older main fails, even with every tree right (O-6).

    Car a's landed commit also carries main's last change, so every landed tree equals its
    train commit's. Only the check that the landing sits on the recorded main stops it.
    """
    train = rig.faithful(1, 2)
    rig.git("switch", "-q", "--detach", rig.old_main)
    rig.git("checkout", "-q", f"{train}~1", "--", ".")
    rig.git("commit", "-q", "-m", _message("a", 1), env=_author_env(CARS[1][1]))
    rig.git("cherry-pick", train)
    skipped = rig.git("rev-parse", "HEAD")
    for i in (0, 1):
        assert rig.git("rev-parse", f"{skipped}~{i}^{{tree}}") == rig.git(
            "rev-parse", f"{train}~{i}^{{tree}}"
        )
    rig.publish(skipped)
    assert _failed_closed(run_post(rig, train, skipped), POST_OK)


def test_dropping_the_set_line_makes_the_blocks_fail_open(rig: Rig) -> None:
    """Hostile control: without ``set -euo pipefail`` the same bad landings exit 0."""
    train = rig.faithful(1, 2)
    tampered = _tampered_first_car(rig)
    post = _without_set_line(_block(POST_OK))
    assert run_post(rig, train, tampered, block=post).returncode == 0
    pre = _without_set_line(_block(PRE_OK))
    assert run_pre(rig, _swapped_train(rig), rig.cars(1, 2), block=pre).returncode == 0


# --- KPI check ------------------------------------------------------------------------------


def _fake_python(tmp: Path) -> str:
    """A stand-in for the lender-case run: it prints a count and the digest of ``kpi.txt``."""
    bindir = tmp / "fakevenv" / "bin"
    bindir.mkdir(parents=True)
    fake = bindir / "python"
    fake.write_text(
        f"#!{sys.executable}\n"
        "import hashlib\nfrom pathlib import Path\n"
        "print('41', hashlib.sha256(Path('kpi.txt').read_bytes()).hexdigest())\n",
        "utf-8",
    )
    fake.chmod(0o755)
    return f"{bindir}:{_ENV['PATH']}"


def run_kpi(
    rig: Rig, reference: str, train: str, path: str
) -> subprocess.CompletedProcess[str]:
    script = _fill(
        _block(KPI_OK),
        {"<kpi-car-head-or-main-sha>": reference, "<train-head-sha>": train},
    )
    bindir = Path(path.split(":", 1)[0])
    script = (
        f"export DUTCHBAY_VENV={shlex.quote(str(bindir.parent))}\n"
        f"export TMPDIR={shlex.quote(str(rig.repo.parent))}\n" + script
    )
    return _run(rig, script, path=path)


def test_kpi_check_compares_the_vector_at_two_revisions(
    rig: Rig, tmp_path: Path
) -> None:
    """The KPI block passes when the vector is unchanged and fails closed when it moves.

    The lender-case run is replaced by a stand-in, so this tests the block's own plumbing:
    one detached worktree per revision, the comparison and the OK line.
    """
    path = _fake_python(tmp_path)
    rig.git("switch", "-q", "--detach", rig.main)
    (rig.repo / "kpi.txt").write_text("vector\n", encoding="utf-8")
    rig.git("add", "kpi.txt")
    rig.git("commit", "-q", "-m", "chore: a vector")
    same = rig.git("rev-parse", "HEAD")
    rig.git("commit", "-q", "--allow-empty", "-m", "docs: no KPI change")
    unchanged = rig.git("rev-parse", "HEAD")
    (rig.repo / "kpi.txt").write_text("moved\n", encoding="utf-8")
    rig.git("commit", "-q", "-am", "feat: a KPI change")
    moved = rig.git("rev-parse", "HEAD")
    assert _passed(run_kpi(rig, same, unchanged, path), KPI_OK)
    assert _failed_closed(run_kpi(rig, same, moved, path), KPI_OK)
    scratches = list(rig.repo.parent.glob("dutchbay-kpi.*/checkout"))
    assert len(scratches) == 4
    assert all((scratch / "kpi.txt").is_file() for scratch in scratches)


def test_kpi_check_fails_when_the_run_prints_nothing(rig: Rig, tmp_path: Path) -> None:
    """Negative control: a run that prints no vector at either revision is not a match."""
    bindir = tmp_path / "silentvenv" / "bin"
    bindir.mkdir(parents=True)
    (bindir / "python").write_text("#!/bin/sh\nexit 0\n", "utf-8")
    (bindir / "python").chmod(0o755)
    path = f"{bindir}:{_ENV['PATH']}"
    assert _failed_closed(run_kpi(rig, rig.main, rig.main, path), KPI_OK)


def test_kpi_check_runs_the_lender_case() -> None:
    """The KPI block runs the strict lender case and hashes its KPI vector."""
    block = _block(KPI_OK)
    assert 'config="scenarios/dutchbay_lendercase_2025Q4.yaml"' in block
    assert 'validation_mode="strict"' in block
    assert "sort_keys=True" in block


# --- single-PR merge check ------------------------------------------------------------------


def run_merge(
    rig: Rig, merge: str, head: str, parents: int, block: str | None = None
) -> subprocess.CompletedProcess[str]:
    script = _fill(
        _block(MERGE_OK) if block is None else block,
        {
            "<merge-sha>": merge,
            "<head-sha>": head,
            "<main-sha-recorded-in-step-2>": rig.main,
            "<1 or 2>": str(parents),
        },
    )
    return _run(rig, script)


def _pr_head(rig: Rig) -> str:
    """A pull request head on main, with one commit."""
    rig.git("switch", "-q", "--detach", rig.main)
    (rig.repo / "pr.txt").write_text("pr\n", encoding="utf-8")
    rig.git("add", "pr.txt")
    rig.git("commit", "-q", "-m", "docs: a pull request")
    return rig.git("rev-parse", "HEAD")


def _squash(
    rig: Rig, head: str, tree: str | None = None, parent: str | None = None
) -> str:
    return rig.commit_tree(
        tree or rig.git("rev-parse", f"{head}^{{tree}}"),
        [parent or rig.main],
        "docs: a pull request (#9)",
        CARS[1][1],
    )


def test_merge_check_passes_a_faithful_squash_and_merge_commit(rig: Rig) -> None:
    head = _pr_head(rig)
    squash = _squash(rig, head)
    rig.publish(squash)
    assert _passed(run_merge(rig, squash, head, 1), MERGE_OK)
    tree = rig.git("rev-parse", f"{head}^{{tree}}")
    merge = rig.commit_tree(tree, [rig.main, head], "Merge (#9)", CARS[1][1])
    rig.publish(merge)
    assert _passed(run_merge(rig, merge, head, 2), MERGE_OK)


def test_merge_check_fails_closed_on_each_bad_merge(rig: Rig) -> None:
    """Negative controls: each comparison in the single-PR block stops a bad merge on its own."""
    head = _pr_head(rig)
    tree = rig.git("rev-parse", f"{head}^{{tree}}")
    good = _squash(rig, head)
    rig.publish(good)
    # The head itself is not on origin/main.
    assert _failed_closed(run_merge(rig, head, head, 1), MERGE_OK)
    # A squash declared as a merge commit, and a merge commit declared as a squash.
    assert _failed_closed(run_merge(rig, good, head, 2), MERGE_OK)
    merge = rig.commit_tree(tree, [rig.main, head], "Merge (#9)", CARS[1][1])
    rig.publish(merge)
    assert _failed_closed(run_merge(rig, merge, head, 1), MERGE_OK)
    # A different tree.
    other = _squash(rig, head, tree=rig.git("rev-parse", f"{rig.main}^{{tree}}"))
    rig.publish(other)
    assert _failed_closed(run_merge(rig, other, head, 1), MERGE_OK)
    # The wrong first parent.
    stale = _squash(rig, head, parent=rig.old_main)
    rig.publish(stale)
    assert _failed_closed(run_merge(rig, stale, head, 1), MERGE_OK)
    # A merge commit whose second parent is not the head.
    wrong = rig.commit_tree(tree, [rig.main, rig.old_main], "Merge (#9)", CARS[1][1])
    rig.publish(wrong)
    assert _failed_closed(run_merge(rig, wrong, head, 2), MERGE_OK)


def test_dropping_the_set_line_makes_the_merge_check_fail_open(rig: Rig) -> None:
    """Hostile control: the single-PR block without its set line passes a wrong tree in silence."""
    head = _pr_head(rig)
    other = _squash(rig, head, tree=rig.git("rev-parse", f"{rig.main}^{{tree}}"))
    rig.publish(other)
    block = _without_set_line(_block(MERGE_OK))
    assert run_merge(rig, other, head, 1, block=block).returncode == 0


@pytest.mark.parametrize("count", [0, 1, 4])
def test_landing_rejects_an_invalid_recorded_count(rig: Rig, count: int) -> None:
    """An empty or out-of-policy loop must not certify a landing."""
    train = rig.faithful(1, 2)
    landed = _landed(rig, train)
    assert _failed_closed(run_post(rig, train, landed, n=count), POST_OK)


def test_landing_rejects_a_nonexistent_train(rig: Rig) -> None:
    """A failed object lookup must not produce an empty successful iteration."""
    train = rig.faithful(1, 2)
    assert _failed_closed(run_post(rig, "0" * 40, _landed(rig, train)), POST_OK)


def test_single_merge_rejects_a_landing_only_on_a_side_parent(rig: Rig) -> None:
    """Reachability cannot substitute for the exact fetched protected tip."""
    head = _pr_head(rig)
    good = _squash(rig, head)
    side_merge = rig.commit_tree(
        rig.git("rev-parse", f"{good}^{{tree}}"),
        [rig.main, good],
        "chore: unrelated protected merge",
        CARS[1][1],
    )
    rig.publish(side_merge)
    assert _failed_closed(run_merge(rig, good, head, 1), MERGE_OK)


def test_car_directory_is_data_even_with_shell_punctuation(rig: Rig) -> None:
    """A path containing spaces and punctuation cannot inject a shell command."""
    destination = rig.cardir.parent / "Train Records; touch INJECTION"
    rig.cardir.rename(destination)
    rig.cardir = destination
    built = run_build(rig, rig.cars(1, 2))
    assert _passed(built, BUILD_OK), built.stderr
    train = built.stdout.split(BUILD_OK)[1].strip()
    assert _passed(run_pre(rig, train, rig.cars(1, 2)), PRE_OK)
    assert not (rig.repo / "INJECTION").exists()


@pytest.mark.parametrize(
    ("output", "exit_code"),
    [
        ("identical diagnostic", 17),
        ("41 " + "a" * 64, 17),
        ("0 " + "a" * 64, 0),
        ("39 " + "a" * 64, 0),
        ("41 not-a-digest", 0),
    ],
)
def test_kpi_refuses_failed_or_malformed_matching_runs(
    rig: Rig, tmp_path: Path, output: str, exit_code: int
) -> None:
    """Matching text is insufficient when either evaluator failed or its receipt is invalid."""
    bindir = tmp_path / "controlledvenv" / "bin"
    bindir.mkdir(parents=True)
    executable = bindir / "python"
    executable.write_text(
        f"#!{sys.executable}\nprint({output!r})\nraise SystemExit({exit_code})\n",
        encoding="utf-8",
    )
    executable.chmod(0o755)
    assert _failed_closed(
        run_kpi(rig, rig.main, rig.main, f"{bindir}:{_ENV['PATH']}"), KPI_OK
    )


def test_failed_scratch_add_never_attempts_removal(rig: Rig, tmp_path: Path) -> None:
    """A safe Git double refuses creation and records any forbidden cleanup attempt."""
    path = _fake_python(tmp_path)
    bindir = Path(path.split(":", 1)[0])
    record = tmp_path / "scratch-operations.txt"
    real_git = shutil.which("git")
    assert real_git is not None
    wrapper = bindir / "git"
    wrapper.write_text(
        "#!/bin/sh\n"
        f"printf '%s\\n' \"$*\" >> {shlex.quote(str(record))}\n"
        'if [ "$1" = worktree ] && [ "$2" = add ]; then exit 128; fi\n'
        f'exec {shlex.quote(real_git)} "$@"\n',
        encoding="utf-8",
    )
    wrapper.chmod(0o755)
    try:
        assert _failed_closed(run_kpi(rig, rig.main, rig.main, path), KPI_OK)
        operations = record.read_text(encoding="utf-8")
        assert "worktree add" in operations
        assert "worktree remove" not in operations
        assert "--force" not in operations
    finally:
        record.unlink(missing_ok=True)


def test_deletion_cannot_hide_a_changed_preimage(rig: Rig) -> None:
    """Deleting two different input blobs gives the same absence but different reviewed diffs."""
    rig.git("switch", "-q", "--detach", rig.old_main)
    rig.git("rm", "base.txt")
    rig.git("commit", "-q", "-m", "docs: reviewed deletion")
    deletion = rig.git("rev-parse", "HEAD")
    rig.heads[3] = deletion
    rig.git("push", "-q", "origin", f"{deletion}:refs/pull/3/head")
    (rig.cardir / "3.msg").write_text(_message("c", 3), encoding="utf-8")
    (rig.cardir / "3.author").write_text(CARS[1][1] + "\n", encoding="utf-8")
    first = rig.faithful(1)
    rig.git("switch", "-q", "--detach", first)
    rig.git("rm", "base.txt")
    rig.git("commit", "-q", "-m", _message("c", 3), env=_author_env(CARS[1][1]))
    train = rig.git("rev-parse", "HEAD")
    assert _failed_closed(run_pre(rig, train, rig.cars(1, 3)), PRE_OK)
    assert _passed(
        run_pre(rig, train, rig.cars(1, 3), block=_without_old_diff_columns()), PRE_OK
    )


def _without_old_diff_columns() -> str:
    """Recreate the rejected projection for a targeted hostile mutation control."""
    block = _block(PRE_OK)
    start = block.index("raw_diff() {")
    end = block.index("\n}", start) + 2
    replacement = (
        "raw_diff() {\n"
        '  git diff --raw --no-renames --no-abbrev "$1" "$2" -- | '
        "cut -d' ' -f2,4-\n}"
    )
    return block[:start] + replacement + block[end:]


def test_mode_preimage_has_its_own_hostile_control(rig: Rig) -> None:
    """Identical old/new blobs and new modes cannot hide an unreviewed old mode."""
    rig.git("switch", "-q", "--detach", rig.old_main)
    changed = BASE_LINES.replace("line 2", "line 2, reviewed")
    target = rig.repo / "base.txt"
    target.write_text(changed, encoding="utf-8")
    target.chmod(0o755)
    rig.git("add", "base.txt")
    rig.git("commit", "-q", "-m", "docs: reviewed mode and content")
    head = rig.git("rev-parse", "HEAD")
    rig.heads[3] = head
    rig.git("push", "-q", "origin", f"{head}:refs/pull/3/head")
    (rig.cardir / "3.msg").write_text(_message("c", 3), encoding="utf-8")
    (rig.cardir / "3.author").write_text(CARS[1][1] + "\n", encoding="utf-8")
    rig.git("switch", "-q", "--detach", rig.main)
    target.write_text(BASE_LINES, encoding="utf-8")
    target.chmod(0o755)
    rig.git("add", "base.txt")
    rig.git("commit", "-q", "-m", "chore: main already executable")
    rig.main = rig.git("rev-parse", "HEAD")
    rig.publish(rig.main)
    first = rig.faithful(1)
    rig.git("switch", "-q", "--detach", first)
    target.write_text(changed, encoding="utf-8")
    rig.git("add", "base.txt")
    rig.git("commit", "-q", "-m", _message("c", 3), env=_author_env(CARS[1][1]))
    train = rig.git("rev-parse", "HEAD")
    assert _failed_closed(run_pre(rig, train, rig.cars(1, 3)), PRE_OK)
    assert _passed(
        run_pre(rig, train, rig.cars(1, 3), block=_without_old_diff_columns()), PRE_OK
    )


def test_kpi_preserves_unexpected_scratch_dirt(rig: Rig, tmp_path: Path) -> None:
    """A newly dirty owned checkout is retained and cannot yield a successful receipt."""
    bindir = tmp_path / "dirtyvenv" / "bin"
    bindir.mkdir(parents=True)
    executable = bindir / "python"
    executable.write_text(
        f"#!{sys.executable}\nfrom pathlib import Path\n"
        "Path('unexpected-evidence.txt').write_text('preserve me')\n"
        "print('41', 'a' * 64)\n",
        encoding="utf-8",
    )
    executable.chmod(0o755)
    assert _failed_closed(
        run_kpi(rig, rig.main, rig.main, f"{bindir}:{_ENV['PATH']}"), KPI_OK
    )
    preserved = list(
        rig.repo.parent.glob("dutchbay-kpi.*/checkout/unexpected-evidence.txt")
    )
    assert preserved
    assert all(path.read_text(encoding="utf-8") == "preserve me" for path in preserved)


HYGIENE_CONTROL = (
    "unset GIT_CONFIG_PARAMETERS GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_OBJECT_DIRECTORY\n"
    "unset GIT_ALTERNATE_OBJECT_DIRECTORIES"
)
REPLACE_CONTROL = "export GIT_NO_REPLACE_OBJECTS=1 GIT_GRAFT_FILE=/dev/null"
GRAPH_CONTROL = (
    "export GIT_CONFIG_COUNT=2 GIT_CONFIG_KEY_0=core.commitGraph GIT_CONFIG_VALUE_0=false\n"
    "export GIT_CONFIG_KEY_1=advice.graftFileDeprecated GIT_CONFIG_VALUE_1=false\n"
    'test "$(git config --get core.commitGraph)" = false'
)


@pytest.mark.parametrize("ok", ALL_OK)
def test_every_block_disables_local_object_substitution(ok: str) -> None:
    """Object identity controls travel with each literal, independently runnable fence."""
    assert REPLACE_CONTROL in _block(ok)
    assert GRAPH_CONTROL in _block(ok)


def test_replacement_cannot_certify_a_different_physical_merge(rig: Rig) -> None:
    """A fixture-local replacement must not turn a wrong landed tree into an accepted one."""
    head = _pr_head(rig)
    faithful = _squash(rig, head)
    rig.publish(faithful)
    assert _passed(run_merge(rig, faithful, head, 1), MERGE_OK)
    wrong = _squash(rig, head, tree=rig.git("rev-parse", f"{rig.main}^{{tree}}"))
    rig.publish(wrong)
    assert _failed_closed(run_merge(rig, wrong, head, 1), MERGE_OK)
    rig.git("replace", wrong, faithful)
    assert rig.git("rev-parse", f"{wrong}^{{tree}}") == rig.git(
        "rev-parse", f"{head}^{{tree}}"
    )
    assert rig.git("--no-replace-objects", "rev-parse", f"{wrong}^{{tree}}") != rig.git(
        "--no-replace-objects", "rev-parse", f"{head}^{{tree}}"
    )
    assert _failed_closed(run_merge(rig, wrong, head, 1), MERGE_OK)
    weakened = _block(MERGE_OK).replace(
        "export GIT_NO_REPLACE_OBJECTS=1 GIT_GRAFT_FILE=/dev/null", ""
    )
    assert _passed(run_merge(rig, wrong, head, 1, block=weakened), MERGE_OK)


@pytest.mark.parametrize("hidden", ["assume-unchanged", "skip-worktree", "fifo"])
def test_kpi_preserves_state_that_porcelain_misses(
    rig: Rig, tmp_path: Path, hidden: str
) -> None:
    """Real Git flags and a real FIFO cannot cause the evaluation trap to delete evidence."""
    bindir = tmp_path / "hiddenvenv" / "bin"
    bindir.mkdir(parents=True)
    if hidden == "fifo":
        action = "os.mkfifo('owner-channel')\n"
    else:
        action = (
            f"subprocess.run(['git', 'update-index', '--{hidden}', '--', 'base.txt'], "
            "check=True)\nPath('base.txt').write_text('preserve changed tracked bytes')\n"
        )
    executable = bindir / "python"
    executable.write_text(
        f"#!{sys.executable}\nimport os, subprocess\nfrom pathlib import Path\n"
        + action
        + "assert not subprocess.check_output(['git', 'status', '--porcelain'])\n"
        + "print('41', 'a' * 64)\n",
        encoding="utf-8",
    )
    executable.chmod(0o755)
    result = run_kpi(rig, rig.main, rig.main, f"{bindir}:{_ENV['PATH']}")
    assert _failed_closed(result, KPI_OK), result.stderr
    scratches = list(rig.repo.parent.glob("dutchbay-kpi.*/checkout"))
    assert scratches
    for scratch in scratches:
        if hidden == "fifo":
            assert (scratch / "owner-channel").is_fifo()
        else:
            assert (
                scratch / "base.txt"
            ).read_text() == "preserve changed tracked bytes"
    assert "worktree remove" not in _block(KPI_OK)


def test_destination_mode_has_its_own_hostile_control(rig: Rig) -> None:
    """Changing only the new mode must fail even when every other raw-diff field agrees."""
    train = rig.faithful(1, 2)
    assert _passed(run_pre(rig, train, rig.cars(1, 2)), PRE_OK)
    rig.git("update-index", "--chmod=+x", "car_b.txt")
    rig.git("commit", "-q", "--amend", "--no-edit")
    wrong = rig.git("rev-parse", "HEAD")
    assert rig.git("rev-parse", f"{wrong}:car_b.txt") == rig.git(
        "rev-parse", f"{train}:car_b.txt"
    )
    assert _failed_closed(run_pre(rig, wrong, rig.cars(1, 2)), PRE_OK)
    # Project only the second header field away; retain NUL paths, old mode, both blobs and status.
    projection = (
        "import sys; parts=sys.stdin.buffer.read().split(b'\\0'); "
        "\nfor i in range(0, len(parts)-1, 2):\n"
        " fields=parts[i].split(b' '); fields[1]=b'000000'; parts[i]=b' '.join(fields)\n"
        "sys.stdout.buffer.write(b'\\0'.join(parts))"
    )
    block = _block(PRE_OK)
    needle = "    od -An -v -tx1"
    assert block.count(needle) == 1
    weakened = block.replace(
        needle,
        f"    {shlex.quote(sys.executable)} -c {shlex.quote(projection)} | od -An -v -tx1",
    )
    assert _passed(run_pre(rig, wrong, rig.cars(1, 2), block=weakened), PRE_OK)


def test_build_uses_the_issued_message_hash_before_file_tampering(rig: Rig) -> None:
    """Normalize-equivalent tampering must fail against a hash issued before the edit."""
    rig.git("switch", "-q", "--detach", rig.main)
    issued_script = _fill(
        _block(BUILD_OK),
        {
            "<car directory>": str(rig.cardir),
            "<car list>": rig.cars(1, 2),
            "train/<date>-<n>": "train/issued-record-control",
        },
    )
    message = rig.cardir / "1.msg"
    original = message.read_bytes()
    message.write_bytes(original + b"\n\n")
    assert _failed_closed(_run(rig, issued_script), BUILD_OK)
    comparison = '  test "$(git hash-object --stdin < "$msg")" = "$msg_blob"\n'
    assert issued_script.count(comparison) == 1
    weakened = issued_script.replace(comparison, "")
    result = _run(rig, weakened)
    assert _passed(result, BUILD_OK), result.stderr


def _point_first_parent_in_commit_graph(rig: Rig, commit: str, parent: str) -> None:
    """Rewrite one commit's cached first parent in a real commit-graph file, as local
    tampering or corruption would, leaving every object in the store unchanged."""
    rig.git("update-ref", "refs/graph/commit", commit)
    rig.git("update-ref", "refs/graph/parent", parent)
    rig.git("commit-graph", "write", "--no-progress", "--reachable")
    path = rig.repo / ".git" / "objects" / "info" / "commit-graph"
    data = bytearray(path.read_bytes())
    path.chmod(0o644)  # Git writes the file read-only; a non-root owner must unlock it.
    chunks = {}
    for i in range(data[6] + 1):
        offset = 8 + 12 * i
        chunks[bytes(data[offset : offset + 4])] = int.from_bytes(
            data[offset + 4 : offset + 12], "big"
        )
    oids, cdat = chunks[b"OIDL"], chunks[b"CDAT"]
    count = (cdat - oids) // 20
    ids = [bytes(data[oids + 20 * i : oids + 20 * i + 20]).hex() for i in range(count)]
    entry = cdat + 36 * ids.index(commit)
    data[entry + 20 : entry + 24] = ids.index(parent).to_bytes(4, "big")
    path.write_bytes(bytes(data))


def test_commit_graph_cannot_certify_a_different_physical_parent(rig: Rig) -> None:
    """A tampered commit-graph must not turn a landing on the wrong parent into an OK."""
    head = _pr_head(rig)
    wrong = _squash(rig, head, parent=rig.old_main)
    rig.publish(wrong)
    assert _failed_closed(run_merge(rig, wrong, head, 1), MERGE_OK)
    _point_first_parent_in_commit_graph(rig, wrong, rig.main)
    assert rig.git("show", "-s", "--format=%P", wrong) == rig.main
    assert rig.git(
        "-c", "core.commitGraph=false", "show", "-s", "--format=%P", wrong
    ) == (rig.old_main)
    assert _failed_closed(run_merge(rig, wrong, head, 1), MERGE_OK)
    weakened = _block(MERGE_OK).replace(GRAPH_CONTROL, "")
    assert _passed(run_merge(rig, wrong, head, 1, block=weakened), MERGE_OK)


def _lender_case_evaluator() -> str:
    """The KPI block's embedded Python, exactly as printed between its heredoc markers."""
    block = _block(KPI_OK)
    start = block.index("<<'PY'\n") + len("<<'PY'\n")
    end = block.index("\nPY\n", start)
    return block[start:end] + "\n"


def _evaluate_lender_case(source: str) -> subprocess.CompletedProcess[str]:
    """Run the evaluator on the real strict lender case at this checkout, as the block does."""
    env = {
        **_ENV,
        "DUTCHBAY_VENV": sys.prefix,
        "PYTHONPATH": str(REPO_ROOT),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    return subprocess.run(
        [sys.executable, "-"],
        input=source,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=600,
        env=env,
    )


def test_kpi_schema_matches_the_real_lender_vector() -> None:
    """The KPI block's key schema and count must accept the lender case this checkout produces.

    Every other KPI test replaces the evaluator with a stand-in, so a KPI added to or removed
    from the pipeline would otherwise surface only when the first train fails its KPI step
    (#1542 domain lane D-1, after #1452 added two equity KPIs).
    """
    source = _lender_case_evaluator()
    result = _evaluate_lender_case(source)
    assert result.returncode == 0, result.stderr[-2000:]
    receipt = result.stdout.strip()
    assert re.fullmatch(r"41 [0-9a-f]{64}", receipt), receipt
    assert "receipt='^41 [0-9a-f]{64}$'" in _block(KPI_OK)
    # Negative control: a schema that has fallen one key behind the vector refuses.
    stale = source.replace("equity_sponsor_cure_usd ", "", 1)
    assert stale != source
    refused = _evaluate_lender_case(stale)
    assert refused.returncode != 0
    assert "Unexpected lender KPI key set" in refused.stderr


def test_object_controls_refuse_a_git_that_ignores_config_from_the_environment(
    rig: Rig, tmp_path: Path
) -> None:
    """A Git that drops GIT_CONFIG_COUNT (older than 2.31) must stop each block, not run it bare."""
    real_git = shutil.which("git")
    assert real_git
    bindir = tmp_path / "oldgit" / "bin"
    bindir.mkdir(parents=True)
    wrapper = bindir / "git"
    wrapper.write_text(
        "#!/bin/sh\n"
        "unset GIT_CONFIG_COUNT GIT_CONFIG_KEY_0 GIT_CONFIG_VALUE_0 "
        "GIT_CONFIG_KEY_1 GIT_CONFIG_VALUE_1\n"
        f'exec {shlex.quote(real_git)} "$@"\n',
        encoding="utf-8",
    )
    wrapper.chmod(0o755)
    old_git = f"{bindir}:{_ENV['PATH']}"
    for ok in ALL_OK:
        block = _block(ok)
        # The guard follows the exports and precedes every other Git command in the block.
        prologue, _, rest = block.partition(GRAPH_CONTROL)
        assert rest
        assert prologue.count("git ") == 0, ok
        guard = prologue + GRAPH_CONTROL + "\necho guarded\n"
        assert _passed(_run(rig, guard), "guarded")
        assert _failed_closed(_run(rig, guard, path=old_git), "guarded")
    head = _pr_head(rig)
    faithful = _squash(rig, head)
    rig.publish(faithful)
    script = _fill(
        _block(MERGE_OK),
        {
            "<merge-sha>": faithful,
            "<head-sha>": head,
            "<main-sha-recorded-in-step-2>": rig.main,
            "<1 or 2>": "1",
        },
    )
    assert _passed(_run(rig, script), MERGE_OK)
    assert _failed_closed(_run(rig, script, path=old_git), MERGE_OK)
    unguarded = script.replace(
        'test "$(git config --get core.commitGraph)" = false\n', ""
    )
    assert unguarded != script
    assert _passed(_run(rig, unguarded, path=old_git), MERGE_OK)


def test_inherited_git_settings_cannot_override_the_object_controls(rig: Rig) -> None:
    """An enclosing ``git -c core.commitGraph=true`` or a foreign GIT_DIR is dropped first."""
    hostile = (
        "export GIT_CONFIG_PARAMETERS=\"'core.commitgraph'='true'\"\n"
        "export GIT_DIR=/nonexistent GIT_OBJECT_DIRECTORY=/nonexistent\n"
    )
    for ok in ALL_OK:
        block = _block(ok)
        assert HYGIENE_CONTROL in block
        prologue, _, _ = block.partition(GRAPH_CONTROL)
        assert prologue.index(HYGIENE_CONTROL) < prologue.index(REPLACE_CONTROL)
        guard = hostile + prologue + GRAPH_CONTROL + "\necho guarded\n"
        assert _passed(_run(rig, guard), "guarded"), ok
        assert _failed_closed(_run(rig, guard.replace(HYGIENE_CONTROL, "")), "guarded")
