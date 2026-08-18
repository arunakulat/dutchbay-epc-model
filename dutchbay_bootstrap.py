from __future__ import annotations

import csv
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Mapping, Optional, Sequence

# --------------------------------------------------------------------------
# Import-time debug – kept ON on purpose for future troubleshooting
# --------------------------------------------------------------------------
try:
    _DbgPath = Path
except NameError:  # pragma: no cover - ultra defensive
    from pathlib import Path as _DbgPath

print(">>> dutchbay_bootstrap.py: module imported")
try:
    print("Current working directory:", _DbgPath.cwd())
    print("Resolved bootstrap file:", _DbgPath(__file__).resolve())
except Exception as _exc:  # pragma: no cover - path edge cases
    print("Warning: bootstrap import debug failed:", _exc)
del _DbgPath

logger = logging.getLogger(__name__)

"""
DutchBay EPC – developer bootstrap helper (Go-with-the-Flow v3.0 aware).

Run this from the repo root:

    ./.venv/bin/python dutchbay_bootstrap.py

What it does (read-only, no mutations):
- Infers the repo root from this file.
- Detects the governed Python 3.12 virtualenv (.venv) in sensible locations.
- Checks for venv helper scripts (setup_venv.sh, scripts/venv_up.sh).
- Verifies critical project files and v14 entrypoints.
- Locates the Go-with-the-Flow ruleset CSV and does a basic structural check.
- Integrates with dutchbay_bootstrap_rules.run_ruleset_check() to print a
  short ruleset summary.
- Writes a JSON report to .dutchbay_bootstrap_report.json for tooling.

If anything important is missing, it prints a clear message and exits
non-zero. Ruleset-related issues are "soft" failures: you see them, but they
won't block everything else.
"""

# ============================================================================
# Paths and constants
# ============================================================================

THIS_FILE = Path(__file__).resolve()
REPO_ROOT = THIS_FILE.parent
PARENT_DIR = REPO_ROOT.parent

# The supported environment is .venv only. Creation/version enforcement lives in
# setup_venv.sh and scripts/venv_up.sh; retired legacy trees must not satisfy this
# bootstrap check.
VENV_DIR_CANDIDATES: Sequence[Path] = (
    REPO_ROOT / ".venv",
    PARENT_DIR / ".venv",
)

# Known venv bootstrap helpers
VENV_SCRIPT_CANDIDATES: Sequence[Path] = (
    REPO_ROOT / "scripts" / "venv_up.sh",
    REPO_ROOT / "venv_up.sh",
    REPO_ROOT / "setup_venv.sh",
)

# Go-with-the-Flow ruleset – canonical filenames, in priority order.
RULESET_CANDIDATE_NAMES: Sequence[str] = (
    "go_with_the_flow_rules_v3_0_clean.csv",
    "go_with_the_flow_rules_v3_0.csv",
    "go_with_the_flow_v14_ruleset.csv",
)

# Critical infra files that should exist in a healthy checkout
CRITICAL_FILES: Mapping[str, str] = {
    "pyproject.toml": "Project configuration",
    ".pre-commit-config.yaml": "Pre-commit hooks configuration",
    "ruff.toml": "Ruff linter config",
}

# Canonical v14 entrypoints – the surfaces we actually care about.
CANONICAL_ENTRYPOINTS: Sequence[str] = (
    "run_full_pipeline_v14.py",
    "run_scenario_analytics_v14.py",
)

# Where we stash a tiny JSON report for future tooling.
BOOTSTRAP_REPORT = REPO_ROOT / ".dutchbay_bootstrap_report.json"


@dataclass
class CheckResult:
    name: str
    ok: Optional[bool]
    details: Optional[str] = None


# ============================================================================
# Small helpers
# ============================================================================


def _status_icon(ok: Optional[bool]) -> str:
    if ok is True:
        return "✅"
    if ok is False:
        return "❌"
    return "⚪"  # unknown / informational


def print_status(label: str, ok: Optional[bool], details: Optional[str] = None) -> None:
    icon = _status_icon(ok)
    msg = f"{icon} {label}"
    if details:
        msg = f"{msg} — {details}"
    print(msg)


def _pick_first_existing(candidates: Sequence[Path]) -> Optional[Path]:
    for p in candidates:
        if p.exists():
            return p
    return None


def _find_ruleset_path(repo_root: Path) -> Optional[Path]:
    for name in RULESET_CANDIDATE_NAMES:
        candidate = repo_root / name
        if candidate.exists():
            return candidate
    return None


# ============================================================================
# Check implementations
# ============================================================================


def validate_repo_structure() -> List[CheckResult]:
    results: List[CheckResult] = []

    # 1. Repo root sanity (pyproject.toml as a sentinel)
    pyproject = REPO_ROOT / "pyproject.toml"
    if not pyproject.exists():
        results.append(
            CheckResult(
                name="repo_root",
                ok=False,
                details=(
                    f"pyproject.toml not found under {REPO_ROOT}. "
                    "Are you running this from the DutchBay_EPC_Model repo root?"
                ),
            )
        )
    else:
        results.append(
            CheckResult(
                name="repo_root",
                ok=True,
                details=str(REPO_ROOT),
            )
        )

    # 2. Virtualenv presence (we don't enforce activation here)
    venv_dir = _pick_first_existing(VENV_DIR_CANDIDATES)
    if venv_dir is not None:
        results.append(
            CheckResult(
                name="venv:virtualenv",
                ok=True,
                details=str(venv_dir),
            )
        )
    else:
        results.append(
            CheckResult(
                name="venv:virtualenv",
                ok=False,
                details=(
                    "No governed Python 3.12 .venv found in repo or parent. "
                    "Run ./setup_venv.sh or source scripts/venv_up.sh to create it."
                ),
            )
        )

    # 3. venv helper script sanity
    venv_script = _pick_first_existing(VENV_SCRIPT_CANDIDATES)
    if venv_script is not None:
        results.append(
            CheckResult(
                name="venv:script",
                ok=True,
                details=str(venv_script),
            )
        )
    else:
        results.append(
            CheckResult(
                name="venv:script",
                ok=False,
                details=(
                    "No venv helper script found. Expected one of: "
                    + ", ".join(str(p) for p in VENV_SCRIPT_CANDIDATES)
                ),
            )
        )

    return results


def validate_critical_files() -> List[CheckResult]:
    results: List[CheckResult] = []

    for rel, desc in CRITICAL_FILES.items():
        path = REPO_ROOT / rel
        if path.exists():
            results.append(
                CheckResult(
                    name=f"file:{rel}",
                    ok=True,
                    details=str(path),
                )
            )
        else:
            results.append(
                CheckResult(
                    name=f"file:{rel}",
                    ok=False,
                    details=f"{desc} missing ({path})",
                )
            )

    results.append(validate_pytest_config())

    return results


def validate_pytest_config() -> CheckResult:
    """
    Pytest config lives in pyproject.toml [tool.pytest.ini_options] (the
    consolidated single source per #439/#451); a standalone pytest.ini is
    also accepted for older layouts.
    """
    pyproject = REPO_ROOT / "pyproject.toml"
    if pyproject.exists():
        try:
            content = pyproject.read_text(encoding="utf-8")
        except OSError as exc:  # pragma: no cover - filesystem edge
            return CheckResult(
                name="file:pytest-config",
                ok=False,
                details=f"Could not read {pyproject}: {exc}",
            )
        if "[tool.pytest.ini_options]" in content:
            return CheckResult(
                name="file:pytest-config",
                ok=True,
                details=f"[tool.pytest.ini_options] in {pyproject}",
            )

    pytest_ini = REPO_ROOT / "pytest.ini"
    if pytest_ini.exists():
        return CheckResult(
            name="file:pytest-config",
            ok=True,
            details=str(pytest_ini),
        )

    return CheckResult(
        name="file:pytest-config",
        ok=False,
        details=(
            "No pytest configuration found: expected "
            "[tool.pytest.ini_options] in pyproject.toml (or a pytest.ini)."
        ),
    )


def validate_canonical_entrypoints() -> List[CheckResult]:
    results: List[CheckResult] = []

    for rel in CANONICAL_ENTRYPOINTS:
        path = REPO_ROOT / rel
        if path.exists():
            results.append(
                CheckResult(
                    name=f"entrypoint:{rel}",
                    ok=True,
                    details=str(path),
                )
            )
        else:
            results.append(
                CheckResult(
                    name=f"entrypoint:{rel}",
                    ok=False,
                    details=f"Canonical v14 entrypoint missing: {path}",
                )
            )

    return results


def validate_go_with_the_flow_ruleset() -> List[CheckResult]:
    """
    Minimal structural sanity on the Go-with-the-Flow CSV:
    - Must exist under one of the canonical names.
    - Must have required columns.
    - rule_id must be non-empty and unique.
    - We report basic version info from the CSV itself.
    """
    results: List[CheckResult] = []
    rules_path = _find_ruleset_path(REPO_ROOT)

    if rules_path is None:
        results.append(
            CheckResult(
                name="ruleset:present",
                ok=False,
                details=(
                    "No Go-with-the-Flow ruleset CSV found. Tried: "
                    + ", ".join(RULESET_CANDIDATE_NAMES)
                ),
            )
        )
        return results

    required_columns = {"version", "rule_id", "category", "title", "description"}
    seen_ids: set[str] = set()
    duplicate_ids: set[str] = set()
    versions: set[str] = set()
    row_count = 0

    with rules_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        header = set(reader.fieldnames or [])

        missing = required_columns - header
        if missing:
            results.append(
                CheckResult(
                    name="ruleset:columns",
                    ok=False,
                    details=(
                        f"{rules_path.name} is missing required columns: "
                        + ", ".join(sorted(missing))
                    ),
                )
            )
            return results

        for row in reader:
            row_count += 1
            rule_id = (row.get("rule_id") or "").strip()
            version = (row.get("version") or "").strip()

            if version:
                versions.add(version)

            if not rule_id:
                continue
            if rule_id in seen_ids:
                duplicate_ids.add(rule_id)
            else:
                seen_ids.add(rule_id)

    if row_count == 0:
        results.append(
            CheckResult(
                name="ruleset:rows",
                ok=False,
                details=f"{rules_path.name} appears to be empty.",
            )
        )
        return results

    if duplicate_ids:
        results.append(
            CheckResult(
                name="ruleset:rule_id_unique",
                ok=False,
                details=(
                    "Duplicate rule_id values detected: "
                    + ", ".join(sorted(duplicate_ids))
                ),
            )
        )
    else:
        results.append(
            CheckResult(
                name="ruleset:rule_id_unique",
                ok=True,
                details=(
                    f"{len(seen_ids)} unique rule_id values across {row_count} rows "
                    f"in {rules_path.name}."
                ),
            )
        )

    latest_version = max(versions) if versions else "unknown"
    results.append(
        CheckResult(
            name="ruleset:versions",
            ok=True,
            details=(
                f"{rules_path.name}: {len(versions)} version tag(s), latest={latest_version}"
            ),
        )
    )
    results.append(
        CheckResult(
            name="ruleset:path",
            ok=True,
            details=str(rules_path),
        )
    )

    return results


def run_ruleset_helper(rules_path: Optional[Path]) -> CheckResult:
    """
    Glue into dutchbay_bootstrap_rules.run_ruleset_check() so that
    bootstrap can also print a one-line ruleset summary and verify
    the environment variable wiring.
    """
    if rules_path is None:
        return CheckResult(
            name="ruleset:helper",
            ok=None,
            details="No ruleset file found; skipping dutchbay_bootstrap_rules helper.",
        )

    # Ensure the helper sees the same file we validated.
    os.environ.setdefault("DUTCHBAY_FLOW_RULESET_CSV", str(rules_path))

    try:
        from dutchbay_bootstrap_rules import run_ruleset_check
    except ImportError as exc:
        return CheckResult(
            name="ruleset:helper",
            ok=False,
            details=f"dutchbay_bootstrap_rules import failed: {exc}",
        )

    try:
        summary = run_ruleset_check(quiet=True)
    except Exception as exc:  # pragma: no cover - defensive
        return CheckResult(
            name="ruleset:helper",
            ok=False,
            details=f"run_ruleset_check() failed: {exc}",
        )

    # The summary is a RulesetSummary dataclass; we access attributes defensively.
    path = getattr(summary, "path", rules_path)
    latest_version = getattr(summary, "latest_version", "unknown")
    n_rules = getattr(summary, "n_rules", "unknown")
    versions = getattr(summary, "versions", None)

    details = f"path={path}, latest_version={latest_version}, n_rules={n_rules}"
    if versions:
        details += f", versions={', '.join(versions)}"

    return CheckResult(
        name="ruleset:helper",
        ok=True,
        details=details,
    )


# ============================================================================
# Reporting
# ============================================================================


def write_report(checks: Iterable[CheckResult]) -> None:
    data = [
        {
            "name": c.name,
            "ok": None if c.ok is None else bool(c.ok),
            "details": c.details or "",
        }
        for c in checks
    ]
    try:
        BOOTSTRAP_REPORT.write_text(
            json.dumps(data, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        print_status("bootstrap:report", True, details=str(BOOTSTRAP_REPORT))
    except OSError as exc:  # pragma: no cover - filesystem edge
        print_status("bootstrap:report", False, details=str(exc))


# ============================================================================
# Main
# ============================================================================


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    print("\n=== DutchBay EPC – Bootstrap (Go-with-the-Flow v3.0) ===\n")
    print("Current working directory:", Path.cwd())
    print("Resolved bootstrap file: ", THIS_FILE)
    print("Repo root as seen by code:", REPO_ROOT, "\n")

    all_results: List[CheckResult] = []

    # 1. Repo + venv layout
    repo_results = validate_repo_structure()
    all_results.extend(repo_results)
    for r in repo_results:
        print_status(r.name, r.ok, r.details)

    # 2. Critical files
    crit_results = validate_critical_files()
    all_results.extend(crit_results)
    for r in crit_results:
        print_status(r.name, r.ok, r.details)

    # 3. Canonical v14 entrypoints
    entry_results = validate_canonical_entrypoints()
    all_results.extend(entry_results)
    for r in entry_results:
        print_status(r.name, r.ok, r.details)

    # 4. Go-with-the-Flow ruleset structural sanity
    rules_results = validate_go_with_the_flow_ruleset()
    all_results.extend(rules_results)
    for r in rules_results:
        print_status(r.name, r.ok, r.details)

    # 5. Optional deeper ruleset check via dutchbay_bootstrap_rules helper
    rules_path = _find_ruleset_path(REPO_ROOT)
    helper_result = run_ruleset_helper(rules_path)
    all_results.append(helper_result)
    print_status(helper_result.name, helper_result.ok, helper_result.details)

    # 6. Persist a tiny machine-readable report
    write_report(all_results)

    # Overall exit code: non-zero if any *mandatory* check failed.
    # Ruleset-related checks (name starts with "ruleset:") are treated as
    # soft failures for now – they'll nag, but won't block bootstrapping.
    hard_fail = any(
        r.ok is False and not r.name.startswith("ruleset:") for r in all_results
    )

    if hard_fail:
        print("\nSome mandatory checks failed. See messages above.\n")
        return 1

    print("\nBootstrap checks completed. You are good to Go with the Flow.\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
