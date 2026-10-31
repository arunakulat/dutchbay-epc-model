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

The steward skill's landing checks are shell commands a merge coordinator runs by hand. They are
executed here against a throwaway repository: a correct rebase-merge passes, and a squash, a
changed tree, a merge commit on the train or a stale base each fail.
"""

from __future__ import annotations

import csv
import re
import shutil
import subprocess
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
    "tests/lint/test_train_policy.py",
    "GitHub's merge queue is not used",
    "'Trains now' on the decision card in the project thread, 2026-10-31T17:40:55Z",
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
    "each landed commit's tree equals the tree of the matching train commit",
    "the first one's parent is the recorded `main` SHA",
    "the last landed commit's tree equals the train head's tree",
    "Any mismatch fails merge verification closed",
    "were never run by the full suite on their own",
    "A train lifts no `HOLD`",
)

AGENTS_REQUIRED_CONTROLS = (
    "`TRAIN-01`: the merge coordinator may land two or three reviewed draft pull requests as one",
    "at most one of them changes a KPI",
    "the train lands by rebase-merge, never squash",
    "only through module 3 §8's three proofs",
)

STEWARD_REQUIRED_CONTROLS = (
    "### Merge trains (`TRAIN-01`)",
    "never a train that carries a car it wrote",
    "A pull request may always land alone instead.",
    "at most one may be `R3` or change a KPI",
    "record it on #1353",
    "If a car's diff does not apply cleanly, leave that car out. Commit nothing else.",
    "ready for review, with the train issue as its `Work item:`",
    "module 3 §8's three proofs",
    "edit no car on it",
    "**Land it with rebase-merge, never squash.**",
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


# --------------------------------------------------------------------------- #
# The steward skill's landing checks, run against a throwaway repository.
# --------------------------------------------------------------------------- #

_FENCE = re.compile(r"^ *```bash\n(.*?)^ *```$", re.MULTILINE | re.DOTALL)


def _train_section() -> str:
    text = STEWARD.read_text(encoding="utf-8")
    start = text.index("### Merge trains (`TRAIN-01`)")
    end = text.index("Merging is delivery authority only.", start)
    return text[start:end]


def _landing_checks() -> tuple[str, str]:
    """Return the pre-landing and post-landing shell blocks from the steward skill."""
    blocks = _FENCE.findall(_train_section())
    assert len(blocks) == 3, f"expected build, pre-landing and landing blocks: {blocks}"
    return blocks[1], blocks[2]


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
        env={
            "GIT_AUTHOR_NAME": "Car Author",
            "GIT_AUTHOR_EMAIL": "car@example.invalid",
            "GIT_COMMITTER_NAME": "Merge Coordinator",
            "GIT_COMMITTER_EMAIL": "coordinator@example.invalid",
            "PATH": "/usr/bin:/bin:/usr/local/bin",
            "HOME": str(repo),
        },
    )
    return result.stdout.strip()


def _commit(repo: Path, path: str, content: str, message: str) -> str:
    (repo / path).write_text(content, encoding="utf-8")
    _git(repo, "add", path)
    _git(repo, "commit", "-q", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture
def train_repo(tmp_path: Path) -> dict[str, str | Path]:
    """A repository with ``main``, a two-car train on it, and a faithful rebase-merge landing."""
    if shutil.which("git") is None:
        pytest.skip("git is not installed")
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _commit(repo, "base.txt", "base\n", "chore: base")
    main = _git(repo, "rev-parse", "HEAD")
    _git(repo, "switch", "-q", "-c", "train")
    _commit(repo, "car_a.txt", "a\n", "docs: car a (#1)")
    train = _commit(repo, "car_b.txt", "b\n", "docs: car b (#2)")
    # GitHub's rebase-merge replays each commit onto main with a new committer, so the
    # landed SHAs differ from the train's while every tree is the same.
    _git(repo, "switch", "-q", "--detach", main)
    for sha in (f"{train}~1", train):
        _git(repo, "cherry-pick", "--allow-empty", sha)
        _git(repo, "commit", "-q", "--amend", "--no-edit", "--date=2030-01-01T00:00:00")
    landed = _git(repo, "rev-parse", "HEAD")
    assert landed != train
    return {"repo": repo, "main": main, "train": train, "landed": landed}


def _run_check(repo: Path, script: str) -> subprocess.CompletedProcess[str]:
    script = script.replace("git fetch origin main", "true")
    assert "<" not in script, f"unfilled placeholder: {script}"
    return subprocess.run(
        ["bash", "-e", "-c", script],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=60,
    )


def _pre_landing(repo: Path, main: str, train: str, cars: int) -> int:
    block, _ = _landing_checks()
    script = (
        block.replace("<main-sha>", main)
        .replace("<train-head-sha>", train)
        .replace("<number of cars>", str(cars))
    )
    return _run_check(repo, script).returncode


def _post_landing(repo: Path, main: str, train: str, landed: str, cars: int) -> int:
    _, block = _landing_checks()
    script = (
        block.replace("<number of cars>", str(cars))
        .replace("<sha-the-merge-returned>", landed)
        .replace("<train-head-sha>", train)
        .replace("<main-sha-recorded-before-landing>", main)
    )
    return _run_check(repo, script).returncode


def test_landing_checks_pass_for_a_faithful_rebase_merge(
    train_repo: dict[str, str | Path],
) -> None:
    """A train of one commit per car on main, landed by rebase-merge, passes both checks."""
    repo, main = Path(train_repo["repo"]), str(train_repo["main"])
    train, landed = str(train_repo["train"]), str(train_repo["landed"])
    assert _pre_landing(repo, main, train, cars=2) == 0
    assert _post_landing(repo, main, train, landed, cars=2) == 0


def test_landing_check_fails_for_a_squash(train_repo: dict[str, str | Path]) -> None:
    """Negative control: a squash has the train's final tree but not one commit per car."""
    repo, main, train = (
        Path(train_repo["repo"]),
        str(train_repo["main"]),
        str(train_repo["train"]),
    )
    _git(repo, "switch", "-q", "--detach", main)
    _git(repo, "merge", "-q", "--squash", train)
    _git(repo, "commit", "-q", "-m", "docs: squashed train")
    squashed = _git(repo, "rev-parse", "HEAD")
    assert _git(repo, "rev-parse", f"{squashed}^{{tree}}") == _git(
        repo, "rev-parse", f"{train}^{{tree}}"
    )
    assert _post_landing(repo, main, train, squashed, cars=2) != 0


def test_landing_check_fails_when_a_landed_tree_differs(
    train_repo: dict[str, str | Path],
) -> None:
    """Negative control: a landed car whose tree changed fails, even if the final tree matches."""
    repo, main, train = (
        Path(train_repo["repo"]),
        str(train_repo["main"]),
        str(train_repo["train"]),
    )
    _git(repo, "switch", "-q", "--detach", main)
    _commit(repo, "car_a.txt", "a, edited on landing\n", "docs: car a (#1)")
    (repo / "car_a.txt").write_text("a\n", encoding="utf-8")
    (repo / "car_b.txt").write_text("b\n", encoding="utf-8")
    _git(repo, "add", "car_a.txt", "car_b.txt")
    _git(repo, "commit", "-q", "-m", "docs: car b (#2)")
    tampered = _git(repo, "rev-parse", "HEAD")
    assert _git(repo, "rev-parse", f"{tampered}^{{tree}}") == _git(
        repo, "rev-parse", f"{train}^{{tree}}"
    )
    assert _post_landing(repo, main, train, tampered, cars=2) != 0


def test_pre_landing_check_fails_for_a_merge_commit_on_the_train(
    train_repo: dict[str, str | Path],
) -> None:
    """Negative control: a train carrying a merge commit is not one commit per car."""
    repo, main = Path(train_repo["repo"]), str(train_repo["main"])
    _git(repo, "switch", "-q", "-c", "side", main)
    _commit(repo, "car_a.txt", "a\n", "docs: car a (#1)")
    _git(repo, "switch", "-q", "-c", "merged-train", main)
    _commit(repo, "car_b.txt", "b\n", "docs: car b (#2)")
    _git(repo, "merge", "-q", "--no-ff", "-m", "chore: merge side", "side")
    merged = _git(repo, "rev-parse", "HEAD")
    assert _pre_landing(repo, main, merged, cars=2) != 0
    assert _pre_landing(repo, main, merged, cars=3) != 0


def test_pre_landing_check_fails_on_a_stale_base(
    train_repo: dict[str, str | Path],
) -> None:
    """Negative control: a train built on an older main fails against the recorded main."""
    repo, main, train = (
        Path(train_repo["repo"]),
        str(train_repo["main"]),
        str(train_repo["train"]),
    )
    _git(repo, "switch", "-q", "--detach", main)
    newer_main = _commit(repo, "other.txt", "moved on\n", "chore: main moved")
    assert _pre_landing(repo, newer_main, train, cars=2) != 0
    assert _pre_landing(repo, main, train, cars=2) == 0
