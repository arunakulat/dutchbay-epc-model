"""Guard the canonical GWTF source and current branch-integration policy."""

from __future__ import annotations

import csv
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CANONICAL_RULESET = REPO_ROOT / "go_with_the_flow_rules_v3_0_clean.csv"
RETIRED_RULESET_NAME = "go_with_the_flow_rules_v3_0_merged_with_v14.csv"
RETIRED_INTEGRATION_BRANCH = "feature/add-finance-contracts-pydantic-v2-20251219"


def _rules_by_id() -> dict[str, dict[str, str]]:
    """Load the canonical ruleset keyed by its unique rule identifiers."""
    with CANONICAL_RULESET.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return {row["rule_id"]: row for row in rows}


def test_bootstrap_uses_the_canonical_ruleset() -> None:
    """Keep executable bootstrap paths pinned to the tracked canonical CSV."""
    venv_script = (REPO_ROOT / "scripts" / "venv_up.sh").read_text(encoding="utf-8")
    bootstrap = (REPO_ROOT / "dutchbay_bootstrap.py").read_text(encoding="utf-8")
    bootstrap_helper = (REPO_ROOT / "dutchbay_bootstrap_rules.py").read_text(
        encoding="utf-8"
    )

    assert CANONICAL_RULESET.is_file()
    assert CANONICAL_RULESET.name in venv_script
    assert CANONICAL_RULESET.name in bootstrap
    assert CANONICAL_RULESET.name in bootstrap_helper
    assert RETIRED_RULESET_NAME not in venv_script
    assert RETIRED_RULESET_NAME not in bootstrap
    assert RETIRED_RULESET_NAME not in bootstrap_helper


def test_r25_uses_current_pr_and_worktree_flow() -> None:
    """Prevent R25 enforcement from reverting to a retired sprint branch."""
    r25 = _rules_by_id()["R25"]
    policy = " ".join((r25["title"], r25["description"], r25["enforcement"]))

    assert r25["status"] == "active"
    assert "origin/main" in policy
    assert "worktree" in policy.lower()
    assert "PR" in policy
    assert "CI" in policy
    assert RETIRED_INTEGRATION_BRANCH not in policy


def test_r21_uses_the_governed_python312_environment() -> None:
    """Keep the active developer workflow off the retired Python 3.11 venv."""

    r21 = _rules_by_id()["R21"]
    policy = " ".join((r21["title"], r21["description"], r21["enforcement"]))

    assert r21["status"] == "active"
    assert "Python 3.12" in policy
    assert "./setup_venv.sh" in policy
    assert "source .venv/bin/activate" in policy
    assert "source .venv311/bin/activate" not in policy
    assert "do not use .venv311" in policy


def test_r26_uses_the_governed_ingestion_toolchain() -> None:
    """Pin PDF ingestion to the reconstructable Python 3.12 dependency lock."""

    r26 = _rules_by_id()["R26"]
    policy = " ".join((r26["title"], r26["description"], r26["enforcement"]))

    assert r26["status"] == "active"
    assert "Python 3.12" in policy
    assert "[ingestion]" in policy
    assert ".venv/bin/python -m markitdown" in policy
    assert "pdfplumber/PyMuPDF" in policy


def test_thread_01_requires_the_project_and_persistent_venv() -> None:
    """Keep every new thread bound to the durable Codex project runtime."""

    thread_01 = _rules_by_id()["THREAD-01"]
    policy = " ".join(
        (thread_01["title"], thread_01["description"], thread_01["enforcement"])
    )

    assert thread_01["status"] == "active"
    assert "regardless of subject" in policy
    assert "DutchBay_EPC_Model" in policy
    assert "/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/python" in policy
    assert "Python 3.12" in policy
    assert "/Users/aruna/Downloads/dutchbay-epc-model" in policy
    for prohibited in ("temporary venv", ".venv311", "bare/system Python"):
        assert prohibited in policy


def test_active_r25_scripts_do_not_hardcode_a_retired_branch() -> None:
    """Keep operational R25 scripts branch-agnostic."""
    for relative_path in (
        "scripts/gwtf-preflight.sh",
        "scripts/gwtf-daily-audit.sh",
        "scripts/README.md",
    ):
        content = (REPO_ROOT / relative_path).read_text(encoding="utf-8")
        assert RETIRED_INTEGRATION_BRANCH not in content
