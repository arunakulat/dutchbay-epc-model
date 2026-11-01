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
executed here exactly as printed, with plain ``bash -c`` and no added ``-e``, against a throwaway
repository. A correct rebase-merge passes and prints its OK line. A squash, a changed tree (first
car of two, or middle car of three), a merge commit on the train and a stale base each fail with
no OK line. A hostile control strips each block's ``set -euo pipefail`` and watches the same bad
landings exit 0, which is why that line is pinned (#1515 assurance F-1).

The pre-landing block also checks each train commit against its car's reviewed head. A train
whose cars' messages are swapped, whose commit for one car carries a stray file, or whose commit
subject names the wrong pull request fails, and so does a landing whose message was reworded. A
hostile control keeps only the block's structural checks and watches the swapped train pass,
which is why the per-car loop is pinned (#1515 domain D-1).
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
    "each train commit is exactly its car's reviewed diff",
    "with the same modes and blobs, and its subject ends with that car's pull-request number",
    "each landed commit's tree and message equal the matching train commit's",
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
    "**Each train commit must be exactly its car's reviewed diff:**",
    "with the same modes and blobs, and its subject ends with that car's pull-request number",
    "The three proofs above compare trees, so they cannot say which commit carries which car.",
    "each landed commit's tree and message equal those of the matching train commit",
    "the first one's parent is the recorded `main` SHA",
    "the last landed commit's tree equals the train head's tree",
    "Any mismatch fails merge verification closed",
    "The commands that run these checks must fail closed on their own",
    "A check that passes in silence is not a check.",
    "Count shared runtime inputs as dependencies too",
    "Path-disjoint cars that share such an input are not isolated.",
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
    "and that each train commit is exactly its car's reviewed diff",
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


def _car(repo: Path, main: str, name: str, files: dict[str, str]) -> str:
    """A car: a branch off ``main`` carrying one reviewed change, returned as its head SHA."""
    _git(repo, "switch", "-q", "-c", f"car-{name}", main)
    for path, content in files.items():
        (repo / path).write_text(content, encoding="utf-8")
        _git(repo, "add", path)
    _git(repo, "commit", "-q", "-m", f"docs: car {name}, as reviewed")
    return _git(repo, "rev-parse", "HEAD")


def _build_train(
    repo: Path,
    main: str,
    commits: list[tuple[str, str]],
    stray: dict[str, str] | None = None,
) -> str:
    """Build a train the way the steward skill's build block does, one commit per car.

    Each entry is ``(car head, merge message)``. ``stray`` adds files to the first commit, which
    the skill forbids, so a negative control can show the check catching it.
    """
    _git(repo, "switch", "-q", "--detach", main)
    for index, (head, message) in enumerate(commits):
        base = _git(repo, "merge-base", main, head)
        patch = repo.parent / f"car-{index}.patch"
        patch.write_text(
            _git(repo, "diff", "--binary", base, head) + "\n", encoding="utf-8"
        )
        _git(repo, "apply", "--index", str(patch))
        for path, content in (stray or {}).items() if index == 0 else ():
            (repo / path).write_text(content, encoding="utf-8")
            _git(repo, "add", path)
        _git(repo, "commit", "-q", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


def _rebase_merge(repo: Path, main: str, train: str, cars: int) -> str:
    """Land a train as GitHub's rebase-merge does: each commit replayed onto main, new SHAs."""
    _git(repo, "switch", "-q", "--detach", main)
    for back in range(cars - 1, -1, -1):
        _git(repo, "cherry-pick", "--allow-empty", f"{train}~{back}")
        _git(repo, "commit", "-q", "--amend", "--no-edit", "--date=2030-01-01T00:00:00")
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture
def train_repo(tmp_path: Path) -> dict[str, str | Path]:
    """Two cars branched off an older ``main``, a train built on the current one, and a landing.

    ``main`` advances after the cars branch, as it does in practice, so each car's diff is taken
    from its own merge base rather than from the main the train starts at.
    """
    if shutil.which("git") is None:
        pytest.skip("git is not installed")
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    old_main = _commit(repo, "base.txt", "base\n", "chore: base")
    car_a = _car(repo, old_main, "a", {"car_a.txt": "a\n"})
    car_b = _car(repo, old_main, "b", {"car_b.txt": "b\n"})
    _git(repo, "switch", "-q", "main")
    main = _commit(repo, "other.txt", "main moved on\n", "chore: main moved")
    train = _build_train(
        repo, main, [(car_a, "docs: car a (#1)"), (car_b, "docs: car b (#2)")]
    )
    landed = _rebase_merge(repo, main, train, cars=2)
    assert landed != train
    return {
        "repo": repo,
        "main": main,
        "train": train,
        "landed": landed,
        "car_a": car_a,
        "car_b": car_b,
        "cars": f"1:{car_a} 2:{car_b}",
    }


PRE_OK = "TRAIN-01 pre-landing check: OK"
POST_OK = "TRAIN-01 landing check: OK"
FAIL_CLOSED = "set -euo pipefail"


def _assert_block_fails_closed_by_shape(block: str, ok_line: str) -> None:
    """A landing block opens with ``set -euo pipefail`` and ends by printing its OK line."""
    lines = [line.strip() for line in block.strip().splitlines()]
    first, last = lines[0], lines[-1]
    assert first == FAIL_CLOSED, f"block does not open with {FAIL_CLOSED!r}: {first!r}"
    assert last == f'echo "{ok_line}"', f"block does not end with its OK line: {last!r}"


def test_landing_blocks_fail_closed_by_shape() -> None:
    """Both landing blocks stop at the first failed test and only pass by saying so."""
    pre, post = _landing_checks()
    _assert_block_fails_closed_by_shape(pre, PRE_OK)
    _assert_block_fails_closed_by_shape(post, POST_OK)


@pytest.mark.parametrize("which", [0, 1], ids=["pre-landing", "post-landing"])
@pytest.mark.parametrize(
    "strip", [FAIL_CLOSED, "echo "], ids=["no-set-e", "no-ok-line"]
)
def test_block_shape_guard_fails_on_a_weakened_block(which: int, strip: str) -> None:
    """Negative control: dropping the set line or the OK line from either block fails."""
    block = _landing_checks()[which]
    weakened = "\n".join(line for line in block.splitlines() if strip not in line)
    with pytest.raises(AssertionError):
        _assert_block_fails_closed_by_shape(weakened, (PRE_OK, POST_OK)[which])


def _run_check(repo: Path, script: str) -> subprocess.CompletedProcess[str]:
    """Run a block exactly as a steward would paste it: plain ``bash -c``, no added ``-e``."""
    script = script.replace("git fetch origin main", "true")
    assert "<" not in script, f"unfilled placeholder: {script}"
    return subprocess.run(
        ["bash", "-c", script],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=60,
    )


def _passed(result: subprocess.CompletedProcess[str], ok_line: str) -> bool:
    """A block passed only if it exited 0 and printed its OK line."""
    return result.returncode == 0 and ok_line in result.stdout


def _failed_closed(result: subprocess.CompletedProcess[str], ok_line: str) -> bool:
    """A block failed closed only if it exited non-zero and never printed its OK line."""
    return result.returncode != 0 and ok_line not in result.stdout


def _pre_landing(
    repo: Path, main: str, train: str, cars: str, block: str | None = None
) -> subprocess.CompletedProcess[str]:
    """Run the pre-landing block; ``cars`` is the ``<pr>:<head>`` list in queue order."""
    block = _landing_checks()[0] if block is None else block
    script = (
        block.replace("<main-sha>", main)
        .replace("<train-head-sha>", train)
        .replace("<car list>", cars)
    )
    return _run_check(repo, script)


def _post_landing(
    repo: Path, main: str, train: str, landed: str, cars: int, block: str | None = None
) -> subprocess.CompletedProcess[str]:
    block = _landing_checks()[1] if block is None else block
    script = (
        block.replace("<number of cars>", str(cars))
        .replace("<sha-the-merge-returned>", landed)
        .replace("<train-head-sha>", train)
        .replace("<main-sha-recorded-before-landing>", main)
    )
    return _run_check(repo, script)


def _without_set_line(block: str) -> str:
    return "\n".join(line for line in block.splitlines() if FAIL_CLOSED not in line)


def test_landing_checks_pass_for_a_faithful_rebase_merge(
    train_repo: dict[str, str | Path],
) -> None:
    """A train of one commit per car on main, landed by rebase-merge, passes both checks."""
    repo, main = Path(train_repo["repo"]), str(train_repo["main"])
    train, landed = str(train_repo["train"]), str(train_repo["landed"])
    cars = str(train_repo["cars"])
    assert _passed(_pre_landing(repo, main, train, cars), PRE_OK)
    assert _passed(_post_landing(repo, main, train, landed, cars=2), POST_OK)


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
    assert _failed_closed(_post_landing(repo, main, train, squashed, cars=2), POST_OK)


def _tampered_first_car(repo: Path, main: str) -> str:
    """Land car a with a changed tree and car b restoring it, so the final tree still matches."""
    _git(repo, "switch", "-q", "--detach", main)
    _commit(repo, "car_a.txt", "a, edited on landing\n", "docs: car a (#1)")
    (repo / "car_a.txt").write_text("a\n", encoding="utf-8")
    (repo / "car_b.txt").write_text("b\n", encoding="utf-8")
    _git(repo, "add", "car_a.txt", "car_b.txt")
    _git(repo, "commit", "-q", "-m", "docs: car b (#2)")
    return _git(repo, "rev-parse", "HEAD")


def test_landing_check_fails_when_a_landed_tree_differs(
    train_repo: dict[str, str | Path],
) -> None:
    """Negative control: a landed car whose tree changed fails, even if the final tree matches."""
    repo, main, train = (
        Path(train_repo["repo"]),
        str(train_repo["main"]),
        str(train_repo["train"]),
    )
    tampered = _tampered_first_car(repo, main)
    assert _git(repo, "rev-parse", f"{tampered}^{{tree}}") == _git(
        repo, "rev-parse", f"{train}^{{tree}}"
    )
    assert _failed_closed(_post_landing(repo, main, train, tampered, cars=2), POST_OK)


def test_landing_check_fails_when_a_middle_car_of_three_differs(tmp_path: Path) -> None:
    """Negative control: in a three-car train, a tampered middle car fails inside the loop.

    The later comparisons in the loop would pass, so this case fails only if the block stops
    at the first failed ``test`` rather than reporting the last one.
    """
    if shutil.which("git") is None:
        pytest.skip("git is not installed")
    repo = tmp_path / "repo3"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    main = _commit(repo, "base.txt", "base\n", "chore: base")
    _git(repo, "switch", "-q", "-c", "train")
    _commit(repo, "car_a.txt", "a\n", "docs: car a (#1)")
    _commit(repo, "car_b.txt", "b\n", "docs: car b (#2)")
    train = _commit(repo, "car_c.txt", "c\n", "docs: car c (#3)")
    _git(repo, "switch", "-q", "--detach", main)
    _commit(repo, "car_a.txt", "a\n", "docs: car a (#1)")
    _commit(repo, "car_b.txt", "b, edited on landing\n", "docs: car b (#2)")
    (repo / "car_b.txt").write_text("b\n", encoding="utf-8")
    (repo / "car_c.txt").write_text("c\n", encoding="utf-8")
    _git(repo, "add", "car_b.txt", "car_c.txt")
    _git(repo, "commit", "-q", "-m", "docs: car c (#3)")
    tampered = _git(repo, "rev-parse", "HEAD")
    assert _git(repo, "rev-parse", f"{tampered}^{{tree}}") == _git(
        repo, "rev-parse", f"{train}^{{tree}}"
    )
    assert _failed_closed(_post_landing(repo, main, train, tampered, cars=3), POST_OK)


def test_pre_landing_check_fails_for_a_merge_commit_on_the_train(
    train_repo: dict[str, str | Path],
) -> None:
    """Negative control: a train carrying a merge commit is not one commit per car."""
    repo, main = Path(train_repo["repo"]), str(train_repo["main"])
    cars, car_a = str(train_repo["cars"]), str(train_repo["car_a"])
    merged = _merge_commit_train(repo, main)
    assert _failed_closed(_pre_landing(repo, main, merged, cars), PRE_OK)
    # Three entries match the merged train's commit count, so only the merge check stops it.
    three = f"{cars} 3:{car_a}"
    assert _failed_closed(_pre_landing(repo, main, merged, three), PRE_OK)


def _merge_commit_train(repo: Path, main: str) -> str:
    _git(repo, "switch", "-q", "-c", "side", main)
    _commit(repo, "car_a.txt", "a\n", "docs: car a (#1)")
    _git(repo, "switch", "-q", "-c", "merged-train", main)
    _commit(repo, "car_b.txt", "b\n", "docs: car b (#2)")
    _git(repo, "merge", "-q", "--no-ff", "-m", "chore: merge side", "side")
    return _git(repo, "rev-parse", "HEAD")


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
    cars = str(train_repo["cars"])
    assert _failed_closed(_pre_landing(repo, newer_main, train, cars), PRE_OK)
    assert _passed(_pre_landing(repo, main, train, cars), PRE_OK)


def test_dropping_the_set_line_makes_the_blocks_fail_open(
    train_repo: dict[str, str | Path],
) -> None:
    """Hostile control: without ``set -euo pipefail`` the same bad landings exit 0.

    This is what pins the line as load-bearing. Run with plain ``bash -c``, a block without
    it reports only its last command, so a tampered landing or a merge-commit train would
    pass in silence. The OK line is printed either way, which is why the block must also
    stop before reaching it.
    """
    repo, main, train = (
        Path(train_repo["repo"]),
        str(train_repo["main"]),
        str(train_repo["train"]),
    )
    pre, post = (_without_set_line(block) for block in _landing_checks())
    tampered = _tampered_first_car(repo, main)
    assert (
        _post_landing(repo, main, train, tampered, cars=2, block=post).returncode == 0
    )
    merged = _merge_commit_train(repo, main)
    cars = str(train_repo["cars"])
    assert _pre_landing(repo, main, merged, cars, block=pre).returncode == 0


def _structural_only(block: str) -> str:
    """The pre-landing block without its per-car loop: the checks #1515 had at ``95dbe158``."""
    lines = block.splitlines()
    start = next(i for i, line in enumerate(lines) if line.strip() == "k=0")
    end = next(i for i, line in enumerate(lines) if line.strip() == "done")
    return "\n".join(lines[:start] + lines[end + 1 :])


def _swapped_train(train_repo: dict[str, str | Path]) -> str:
    """Car b's diff under car a's message, then car a's diff under car b's (domain D-1)."""
    repo, main = Path(train_repo["repo"]), str(train_repo["main"])
    car_a, car_b = str(train_repo["car_a"]), str(train_repo["car_b"])
    return _build_train(
        repo, main, [(car_b, "docs: car a (#1)"), (car_a, "docs: car b (#2)")]
    )


def test_pre_landing_check_fails_when_car_messages_are_swapped(
    train_repo: dict[str, str | Path],
) -> None:
    """Negative control: each car's diff landing under the other car's message fails.

    The swapped train has one non-merge commit per car on the recorded main and the faithful
    train's final tree, so every structural and tree check passes it. Only the per-car loop
    sees that train commit 1 is not car 1's diff.
    """
    repo, main = Path(train_repo["repo"]), str(train_repo["main"])
    cars, train = str(train_repo["cars"]), str(train_repo["train"])
    swapped = _swapped_train(train_repo)
    assert _git(repo, "rev-parse", f"{swapped}^{{tree}}") == _git(
        repo, "rev-parse", f"{train}^{{tree}}"
    )
    assert _failed_closed(_pre_landing(repo, main, swapped, cars), PRE_OK)


def test_structural_checks_alone_pass_a_swapped_train(
    train_repo: dict[str, str | Path],
) -> None:
    """Hostile control: without the per-car loop, the swapped train passes in full.

    This is what pins the loop as load-bearing: the structural checks alone are what the block
    carried before #1515's domain D-1, and a mislabelled car would have landed on main.
    """
    repo, main = Path(train_repo["repo"]), str(train_repo["main"])
    cars = str(train_repo["cars"])
    swapped = _swapped_train(train_repo)
    block = _structural_only(_landing_checks()[0])
    assert "for car in" not in block
    assert _passed(_pre_landing(repo, main, swapped, cars, block=block), PRE_OK)


def test_pre_landing_check_fails_on_a_stray_file_in_a_car_commit(
    train_repo: dict[str, str | Path],
) -> None:
    """Negative control: a car's train commit that carries a file the car never changed fails."""
    repo, main, cars = (
        Path(train_repo["repo"]),
        str(train_repo["main"]),
        str(train_repo["cars"]),
    )
    car_a, car_b = str(train_repo["car_a"]), str(train_repo["car_b"])
    stray = _build_train(
        repo,
        main,
        [(car_a, "docs: car a (#1)"), (car_b, "docs: car b (#2)")],
        stray={"stray.txt": "not reviewed\n"},
    )
    assert _failed_closed(_pre_landing(repo, main, stray, cars), PRE_OK)


def test_pre_landing_check_fails_when_a_subject_names_the_wrong_car(
    train_repo: dict[str, str | Path],
) -> None:
    """Negative control: the right diff under a subject ending with another number fails."""
    repo, main, cars = (
        Path(train_repo["repo"]),
        str(train_repo["main"]),
        str(train_repo["cars"]),
    )
    car_a, car_b = str(train_repo["car_a"]), str(train_repo["car_b"])
    misnumbered = _build_train(
        repo, main, [(car_a, "docs: car a (#1)"), (car_b, "docs: car b (#12)")]
    )
    assert _failed_closed(_pre_landing(repo, main, misnumbered, cars), PRE_OK)


def test_pre_landing_check_fails_for_a_single_car(
    train_repo: dict[str, str | Path],
) -> None:
    """Negative control: a train of one car is not a train; it lands alone instead."""
    repo, main = Path(train_repo["repo"]), str(train_repo["main"])
    car_a = str(train_repo["car_a"])
    single = _build_train(repo, main, [(car_a, "docs: car a (#1)")])
    assert _failed_closed(_pre_landing(repo, main, single, f"1:{car_a}"), PRE_OK)


def test_landing_check_fails_when_a_landed_message_differs(
    train_repo: dict[str, str | Path],
) -> None:
    """Negative control: a landing with every tree right but a reworded car message fails."""
    repo, main, train = (
        Path(train_repo["repo"]),
        str(train_repo["main"]),
        str(train_repo["train"]),
    )
    _git(repo, "switch", "-q", "--detach", main)
    _git(repo, "cherry-pick", f"{train}~1")
    _git(repo, "cherry-pick", train)
    _git(repo, "commit", "-q", "--amend", "-m", "docs: car b, reworded (#2)")
    reworded = _git(repo, "rev-parse", "HEAD")
    assert _git(repo, "rev-parse", f"{reworded}^{{tree}}") == _git(
        repo, "rev-parse", f"{train}^{{tree}}"
    )
    assert _failed_closed(_post_landing(repo, main, train, reworded, cars=2), POST_OK)


def test_pre_landing_check_fails_for_four_cars(
    train_repo: dict[str, str | Path],
) -> None:
    """Negative control: a train carries at most three cars."""
    repo, main = Path(train_repo["repo"]), str(train_repo["main"])
    heads = [
        _car(repo, main, name, {f"car_{name}.txt": f"{name}\n"}) for name in "cdef"
    ]
    four = _build_train(
        repo,
        main,
        [(head, f"docs: car {n} (#{n})") for n, head in enumerate(heads, start=1)],
    )
    cars = " ".join(f"{n}:{head}" for n, head in enumerate(heads, start=1))
    assert _failed_closed(_pre_landing(repo, main, four, cars), PRE_OK)
    three = " ".join(cars.split()[:3])
    assert _passed(_pre_landing(repo, main, f"{four}~1", three), PRE_OK)


def test_pre_landing_check_fails_for_a_car_with_no_diff(
    train_repo: dict[str, str | Path],
) -> None:
    """Negative control: an empty commit for a car that changes nothing is not a car.

    A car whose reviewed head is already on ``main`` has an empty diff, and an empty train
    commit matches it, so only the block's non-empty test stops this train.
    """
    repo, main = Path(train_repo["repo"]), str(train_repo["main"])
    car_a = str(train_repo["car_a"])
    train = _build_train(repo, main, [(car_a, "docs: car a (#1)")])
    _git(repo, "commit", "-q", "--allow-empty", "-m", "docs: car b (#2)")
    empty = _git(repo, "rev-parse", "HEAD")
    cars = f"1:{car_a} 2:{main}"
    assert train != empty
    assert _failed_closed(_pre_landing(repo, main, empty, cars), PRE_OK)
