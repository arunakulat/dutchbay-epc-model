"""Guard the repository-level Codex instruction gateway."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_FILE = REPO_ROOT / "AGENTS.md"
CANONICAL_RULESET = "go_with_the_flow_rules_v3_0_clean.csv"
RETIRED_RULESET = "go_with_the_flow_rules_v3_0_merged_with_v14.csv"
RETIRED_BRANCH = "feature/add-finance-contracts-pydantic-v2-20251219"


def _guidance() -> str:
    """Return the complete repository-level Codex guidance."""
    return AGENTS_FILE.read_text(encoding="utf-8")


def test_codex_guidance_is_present_and_bounded() -> None:
    """Keep project guidance discoverable and below Codex's default size limit."""
    assert AGENTS_FILE.is_file()
    assert AGENTS_FILE.stat().st_size < 32 * 1024


def test_codex_guidance_uses_current_gwtf_authority() -> None:
    """Route Codex to the canonical ruleset and current governance rules."""
    guidance = _guidance()

    assert CANONICAL_RULESET in guidance
    for rule_id in ("WORKTREE-01", "GOV-02", "R23", "R25", "DELIVERY-01", "PERSIST-01"):
        assert rule_id in guidance
    assert RETIRED_RULESET not in guidance
    assert RETIRED_BRANCH not in guidance


def test_codex_guidance_preserves_required_safety_and_quality_gates() -> None:
    """Prevent the Codex gateway from losing core workflow and model safeguards."""
    guidance = _guidance()

    required_phrases = (
        "dedicated worktree",
        "Dolphin Strategy",
        "origin/main",
        "finance/irr.py",
        "evaluate_with_overrides()",
        "strict=False",
        "DATA-01",
        "PYTHONDONTWRITEBYTECODE=1",
        "git diff --check",
    )
    for phrase in required_phrases:
        assert phrase in guidance
