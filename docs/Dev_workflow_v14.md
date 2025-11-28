Nice, that whole FX + tests + CI loop is now in a good place. 🧼

Given where we are, the next sane priority isn’t more code — it’s locking in the workflow we just built so Future You (and anyone else touching this repo) can reproduce it without digging through chat logs.

So next item I’d push up the list:

Document the v14 developer workflow + CI/release path in a single, tight dev doc and link it from the root README.

This hits all your constraints:
	•	No runtime regression risk
	•	Encodes the exact commands, paths, and CAT pattern we’re using
	•	Small, focused file under docs/, easy to maintain
	•	Treats all the helper scripts (regression_smoke.sh, gh_tools.py, CI workflow) as first-class citizens

Below are two CAT blocks:
	1.	New doc: docs/dev_workflow_v14.md
	2.	Small pointer section in README.md (optional but recommended)

As always: only paste the CAT blocks, not the commentary.

⸻

1️⃣ Dev workflow doc — docs/dev_workflow_v14.md

# CAT >>> docs/dev_workflow_v14.md
cat > docs/dev_workflow_v14.md << 'EOF'
# DutchBay EPC Model — v14 Developer Workflow

This document captures the v14-centric workflow used by the DutchBay EPC Model Core Team for day-to-day development, testing, and releases.

It assumes:
- v14 is the canonical path (branch: `v14chat-upgrade`).
- Legacy v13 code is quarantined from core CI.
- CI is wired via `.github/workflows/ci-v14.yml`.
- `gh_tools.py` is the preferred way to bump versions and push.

---

## 1. Local environment

From the repo root:

```bash
cd /Users/aruna/Desktop/DutchBay_EPC_Extracted/DutchBay_EPC_Model

python -m venv .venv311
source .venv311/bin/activate

python -m pip install --upgrade pip
pip install -r requirements.txt

If the virtualenv is already present and stale, blow it away and recreate:

rm -rf .venv311
python -m venv .venv311
source .venv311/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

CI uses its own .venv under Ubuntu; local naming (.venv311) is purely for developer convenience.

⸻

2. Core test workflow (v14 only)

The canonical local test command is:

python -m pytest

This uses pytest.ini, which:
	•	Restricts testpaths to v14-relevant tests:
	•	tests/api/test_epc_helper_v14.py
	•	tests/api/test_export_helpers_v14.py
	•	tests/api/test_irr_core.py
	•	tests/api/test_metrics_module.py
	•	tests/api/test_scenario_manager_smoke.py
	•	tests/api/test_tax_calculator_v14.py
	•	tests/api/test_kpi_normalizer.py
	•	tests/api/test_fx_resolver_unit.py
	•	tests/test_cli_v14_smoke.py
	•	tests/test_export_smoke.py
	•	tests/test_fx_config_strictness.py
	•	tests/test_metrics_integration.py
	•	tests/test_scenario_analytics_smoke.py
	•	tests/test_v14_pipeline_smoke.py
	•	Enforces coverage focused on:
	•	analytics/*
	•	dutchbay_v14chat/*
	•	finance/utils.py
	•	Uses a coverage fail-under threshold (e.g. 65% as of v0.2.x).

To run a single test file without coverage pressure:

python -m pytest --no-cov tests/test_fx_config_strictness.py
python -m pytest --no-cov tests/test_cli_v14_smoke.py


⸻

3. Regression smoke script

For a full v14 regression + coverage check, use the helper script:

./scripts/regression_smoke.sh

This prints a header like:

=== DutchBay v14 Regression Smoke @ 2025-11-21T17:26:14+0530 (rev: <sha>) ===

and then runs python -m pytest with coverage as defined in pytest.ini.

scripts/regression_smoke_v13_legacy.sh is preserved for historical v13 runs but is not wired into the v14 CI.

⸻

4. FX schema rules (v14)

The v14 path only allows mapping-style FX configs:

fx:
  start_lkr_per_usd: 375.0
  annual_depr: 0.03

Scalar FX (e.g. fx: 375.0) is considered invalid and is rejected by tests.

Key enforcement points:
	•	analytics.scenario_loader:
	•	Interprets and validates fx as a mapping.
	•	analytics.fx_config + tests/test_fx_config_strictness.py:
	•	Ensure scalar/null FX is rejected with a clear error.
	•	Ensure scenarios under scenarios/ use the mapping form.

Helper scripts:
	•	scripts/fix_fx_schema.sh: normalize old configs into the mapping shape.
	•	scripts/fix_fx_schema_cleanup.sh: clean up duplicates and ensure canonical mapping.

⸻

5. CI workflow (GitHub Actions)

CI is defined in:

.github/workflows/ci-v14.yml

Key points:
	•	Triggers:
	•	push on main and v14chat-upgrade
	•	pull_request targeting main and v14chat-upgrade
	•	Jobs:
	•	quick-smoke:
	•	Checkout + Python 3.11.
	•	Install requirements.txt.
	•	Run: python -m pytest --no-cov -k "cli and smoke".
	•	full-regression:
	•	Depends on quick-smoke.
	•	Repeats checkout + Python 3.11 + install.
	•	Runs: ./scripts/regression_smoke.sh.

To update CI locally:
	•	Edit .github/workflows/ci-v14.yml.
	•	Run python -m pytest and ./scripts/regression_smoke.sh locally.
	•	Commit and push via gh_tools.py (see below).

⸻

6. gh_tools workflow (versioned commits)

gh_tools.py standardises version bumps and commit messages.

Typical workflow after making changes:

git status -sb         # sanity-check
git add <files...>     # or git add -A

python gh_tools.py commit --version 0.2.x --message "Short description of change"
git push

gh_tools.py does the following:
	•	Updates VERSION.
	•	Injects a new v0.2.x section into CHANGELOG.md under [Unreleased].
	•	Runs git add -A.
	•	Commits with a structured message: "Your message (v0.2.x)".
	•	You then push explicitly to the remote.

Rule of thumb: every meaningful change that affects tests, CI, or lender-facing outputs should go through gh_tools.py so VERSION and CHANGELOG.md stay in sync.

⸻

7. CAT-wrapped edits (house style)

All text/code refactors in this project are done via CAT-wrapped blocks to keep edits reproducible:

# CAT >>> path/to/file.ext
cat > path/to/file.ext << 'EOF'
...new file content...
EOF
# CAT <<< path/to/file.ext

Guidelines:
	•	Always paste the whole block into the terminal from repo root.
	•	Never paste only the inner content (that causes the shell to execute it).
	•	Prefer breaking large scripts into:
	•	Smaller helper modules under analytics/, dutchbay_v14chat/finance/v14/, or
	•	Focused shell helpers under scripts/.

⸻

8. Refactor rules (v14 path)

When touching existing long scripts/modules:
	1.	Do not regress v14 tests
	•	Run python -m pytest and ./scripts/regression_smoke.sh after changes.
	2.	Extract helpers instead of growing monoliths
	•	Move reusable logic into smaller modules:
	•	analytics/core/metrics.py
	•	analytics/export_helpers.py
	•	dutchbay_v14chat/finance/v14/*.py
	•	Keep top-level scripts thin (argument parsing + orchestration only).
	3.	Keep schemas and constants centralised
	•	FX, KPI names, and scenario schema sketches live in analytics / docs.
	•	Avoid duplicating magic numbers across modules.
	4.	Tests first for new surfaces
	•	New modes/handlers or export variants must ship with at least:
	•	A smoke test (tests/test_*_smoke.py), and
	•	A small contract test if they affect lender-facing outputs.

⸻

Status: v14 workflow stabilised (v0.2.x)
Maintainers: DutchBay EPC Model Core Team
EOF

CAT <<< docs/dev_workflow_v14.md

---

### 2️⃣ Optional pointer in `README.md`

If you want the root README to link to this workflow (recommended), you can append a small section.

If your `README.md` already has a “Developer notes” or similar, tweak the heading as needed. Otherwise, from repo root:

```bash
# CAT >>> README.md
cat >> README.md << 'EOF'

---

## Developer workflow (v14)

For day-to-day development on the canonical v14 path (`v14chat-upgrade`), see:

- `docs/dev_workflow_v14.md` — local env, tests, CI, and `gh_tools.py` usage.
- `docs/architecture_v14.md` — module responsibilities and data flow.
- `analytics/README.md` — analytics/KPI layer details.
- `docs/executive_workbook_readme.md` — board/lender workbook interface.

EOF
# CAT <<< README.md


⸻

After that:

git diff docs README.md
git add docs/dev_workflow_v14.md README.md
python gh_tools.py commit --version 0.2.6 --message "Docs: add v14 dev workflow"
git push

Once this is in, the next priority can safely move back to code (e.g., tightening coverage to 70+ with minimal new tests, or a tiny smoke around analytics.executive_workbook). We can pick that next once you confirm these docs are in.
