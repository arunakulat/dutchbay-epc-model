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


# #1826, owner ruling 2026-11-21 option B: a KPI-moving PR bumps VERSION; CHANGELOG.md is
# compiled only at release cuts. The CSV is the authority; these files restate it.
GATEWAYS = ("CLAUDE.md", "AGENTS.md", "Rules to follow.md", "RELEASING.md")
# The stale wording each gateway carried before #1826: a PR edits both files.
STALE_GATEWAY_WORDING = (
    "Update `VERSION` and `CHANGELOG.md` when",
    "also need\n    `VERSION` and `CHANGELOG.md`",
    "updates the model [`CHANGELOG.md`](CHANGELOG.md) (via `changelog.d/`) and bumps",
)


def _flat(text: str) -> str:
    """Collapse whitespace so a wrapped line reads as one sentence."""
    return " ".join(text.split())


def gateway_problems(texts: dict[str, str], description: str) -> list[str]:
    """Return one message per gateway that disagrees with the DOC-02 row.

    Args:
        texts: Gateway file name to its full text.
        description: The DOC-02 CSV description.

    Returns:
        Human-readable problems; empty when every gateway agrees with the row.
    """
    problems = []
    if "bump VERSION in the same PR" not in description:
        problems.append("CSV: DOC-02 no longer says a KPI-moving PR bumps VERSION")
    if "A PR never edits CHANGELOG.md" not in description:
        problems.append("CSV: DOC-02 no longer says a PR never edits CHANGELOG.md")
    for name, text in texts.items():
        flat = _flat(text)
        if "DOC-02" not in flat:
            problems.append(f"{name}: does not cite DOC-02")
        if "bumps `VERSION`" not in flat and "bumps [`VERSION`](VERSION)" not in flat:
            problems.append(f"{name}: does not say a KPI-moving PR bumps VERSION")
        if (
            "never edits" not in flat
            or "release cuts compile the fragments" not in flat
        ):
            problems.append(
                f"{name}: does not say CHANGELOG.md is compiled at release cuts"
            )
        for stale in STALE_GATEWAY_WORDING:
            if _flat(stale) in flat:
                problems.append(
                    f"{name}: still carries the pre-#1826 wording {stale!r}"
                )
    return problems


def _gateway_texts() -> dict[str, str]:
    return {name: (REPO_ROOT / name).read_text(encoding="utf-8") for name in GATEWAYS}


def test_gateways_restate_doc02_option_b() -> None:
    """CLAUDE.md, AGENTS.md, Rules to follow.md and RELEASING.md agree with the DOC-02 row."""
    assert gateway_problems(_gateway_texts(), _get_doc02_row()["description"]) == []


def test_gateway_check_fires_on_drift() -> None:
    """VERIFY-01(5): each way a gateway or the row can drift is observed failing."""
    description = _get_doc02_row()["description"]
    texts = _gateway_texts()
    old_line = "\n- Update `VERSION` and `CHANGELOG.md` when it moves a KPI.\n"
    stale = {**texts, "AGENTS.md": texts["AGENTS.md"] + old_line}
    assert any("pre-#1826" in p for p in gateway_problems(stale, description))
    no_bump = {**texts, "CLAUDE.md": texts["CLAUDE.md"].replace("bumps `VERSION`", "x")}
    assert any("bumps VERSION" in p for p in gateway_problems(no_bump, description))
    no_cut = {
        **texts,
        "RELEASING.md": texts["RELEASING.md"].replace("never edits", "may edit"),
    }
    assert any("release cuts" in p for p in gateway_problems(no_cut, description))
    option_a = description.replace("bump VERSION in the same PR, ", "")
    assert any("CSV:" in p for p in gateway_problems(texts, option_a))
