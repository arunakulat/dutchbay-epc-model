"""Pin the reconciled DOC-02 governance rule, PR template, and changelog workflow (#1565).

Validates Option 2 resolution for Issue #1565 / Remediation R-6:
1. DOC-02 in `go_with_the_flow_rules_v3_0_clean.csv` specifies changelog fragments
   recording as-merged figures under `changelog.d/` for KPI-moving changes.
2. DOC-02 enforcement text accurately documents the actual workflow:
   PR template 'Financial impact' section, reviewer sign-off on as-merged figures,
   and release-time compilation into CHANGELOG.md and VERSION bump.
3. DOC-02 enforcement text no longer claims non-existent CI checks that compare
   VERSION/CHANGELOG.md against analytics/ or finance/ diffs.
4. The PR template and changelog.d/README.md are consistent with DOC-02.
"""

from __future__ import annotations

import csv
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RULESET_PATH = REPO_ROOT / "go_with_the_flow_rules_v3_0_clean.csv"
PR_TEMPLATE_PATH = REPO_ROOT / ".github/pull_request_template.md"
CHANGELOG_README_PATH = REPO_ROOT / "changelog.d/README.md"


def _get_doc02_row() -> dict[str, str]:
    with RULESET_PATH.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    doc02 = next((r for r in rows if r["rule_id"] == "DOC-02"), None)
    assert doc02 is not None, "DOC-02 rule not found in canonical CSV"
    return doc02


def test_doc02_rule_is_active() -> None:
    """DOC-02 must be an active rule in the canonical ruleset."""
    row = _get_doc02_row()
    assert row["status"] == "active"
    assert row["version"] == "v3.0"
    assert row["category"] == "Documentation"


def test_doc02_does_not_claim_nonexistent_ci_check() -> None:
    """The CSV must not claim that non-existent CI checks verify VERSION and CHANGELOG."""
    row = _get_doc02_row()
    enforcement = row["enforcement"]
    # Negative pin: ensure the historical false assertion does not recur
    assert (
        "CI checks verify VERSION and CHANGELOG" not in enforcement
    ), "DOC-02 enforcement still makes the false claim that CI verifies VERSION/CHANGELOG directly."


def test_doc02_documents_fragment_and_release_compile_workflow() -> None:
    """DOC-02 must document fragments under changelog.d/ and release-time compilation."""
    row = _get_doc02_row()
    desc = row["description"]
    enforcement = row["enforcement"]

    # Description requires fragments and as-merged figures
    assert "changelog.d" in desc
    assert "as-merged figures" in desc
    assert "release cuts compile fragments" in desc.lower()

    # Enforcement requires template, reviewer sign-off, and release compile
    assert "Financial impact" in enforcement
    assert "changelog.d" in enforcement
    assert "reviewer sign-off" in enforcement
    assert "compile fragments" in enforcement


def test_pr_template_aligns_with_doc02() -> None:
    """The PR template must include Financial impact section and changelog fragment guidance."""
    template = PR_TEMPLATE_PATH.read_text(encoding="utf-8")
    assert "### Financial impact" in template
    assert "KPI impact:" in template
    assert "changelog.d/" in template
    assert "CHANGELOG.md" in template


def test_changelog_readme_documents_fragment_architecture() -> None:
    """changelog.d/README.md must document fragment usage and release compilation."""
    readme = CHANGELOG_README_PATH.read_text(encoding="utf-8")
    assert "scripts/compile_changelog.py" in readme
    assert "Do **not** edit `CHANGELOG.md` directly for routine changes" in readme
