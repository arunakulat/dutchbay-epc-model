.PHONY: setup hooks lint type security audit audit-declared test test-stochastic-qualification test-report-qualification cov html package lock clean

PY ?= python
PIP ?= pip
VENV_PY := $(wildcard .venv/bin/python)
PYTEST ?= $(if $(VENV_PY),$(VENV_PY),$(PY)) -m pytest

# Exact abstract capability set used to regenerate the CI lock. Keep this aligned
# with the recipe in requirements.txt and docs/ENVIRONMENT_PROVISIONING.md.
LOCK_EXTRAS := dev,test,api,dashboard,wind,gis,grid,micrositing,ingestion,report,jobs

# Engine/application surface scanned by the type + security gates (mirrors CI).
SURFACE := finance analytics api app wind_resource solar_resource analysis_tools
ENTRYPOINTS := run_full_pipeline_v14.py run_scenario_analytics_v14.py \
	dutchbay_bootstrap.py dutchbay_bootstrap_rules.py constants.py

# pip-audit allowlist — EMPTY. The eight pillow advisories accepted in #1369 are gone, fixed
# rather than suppressed: `streamlit 1.66.1` (PyPI, published 2026-10-21T17:02:55Z, twelve
# minutes after #1369 merged) raises its cap from `pillow<13` to `pillow<14,>=9.2.0`, which was
# the only thing holding `pillow` at 12.3.0. The lock now carries `pillow==13.0.0`, the release
# that fixes all eight, and `streamlit==1.66.1`; PyPI reports no advisory against either. That
# is the lift condition the #1369 block named, met four hours after it was written.
# Earlier accepted advisories were cleared the same way, by the coordinated major upgrade
# (fastapi 0.121->0.137 + starlette 0.49->1.3.1, streamlit 1.51->1.54 + pyarrow 21->24, black
# 25->26 [+ pathspec/pytokens], curl-cffi 0.13->0.15). Keep this variable as the home for any
# FUTURE genuinely-capped CVE, and prefer fixing over ignoring.
#
# An accepted advisory is a dated claim about the world, not a property of this repository:
# streamlit 1.66.1 lifted the `pillow<13` cap twelve minutes after #1369 merged, and the
# unchanged pin carried eight advisories that evening and twenty-four by morning. The fence
# validates literal syntax and declaration shape, not the package index. RELEASING.md step 2
# therefore re-checks the cap before lock regeneration; a lifted cap removes the suppression
# and updates dependency inputs before `make lock`. Quote only a fresh `make audit` result.
#
# Use `cap: no-fix-published` only when upstream has published no fixed release.
# SECDEP-01 canonical grammar (the fence rejects every other assignment shape):
# Keep exactly one literal `PIP_AUDIT_IGNORES :=` assignment; do not use computed names, includes, `eval`, expansion or `+=`.
# Use only exact `--ignore-vuln <ID>` or `--ignore-vuln=<ID>` tokens; abbreviations and other tokens are rejected.
# Ignore-option tokens may appear only in that assignment; direct recipe flags and other variables are rejected.
# Both `make security` and `make audit` are live-checked against the canonical advisory IDs.
# The complete recipes are fixed: `audit` is only canonical pip-audit; `security` is exact Bandit then that pip-audit.
# `.ONESHELL`, `SHELL`, `.SHELLFLAGS`, shell preambles, aliases, functions, wrappers and extra commands are rejected; runtime sentinels prove both binaries are reached.
# Each suppression has one physical declaration line in this comment block:
# ignore-vuln: <ADVISORY-ID> | package: <name>==<version> | cap: <name><specifier> | lifted-by: <name> <version>|unknown | reason: <why the suppression is defensible>
PIP_AUDIT_IGNORES :=

# Coverage surface for the floor gate (#439, +solar_resource #456): the six engine
# packages, mirroring the CI test step. The --cov-fail-under=95 floor is enforced in
# `test` and CI — NOT in pyproject addopts — so a partial dev run does not spuriously trip it.
COV := --cov=finance --cov=analytics --cov=wind_resource --cov=api --cov=app --cov=solar_resource

# Resolve, create if absent, and validate the governed environment. The setup
# script installs the pinned reproducibility lock without an editable checkout.
setup:
	./setup_venv.sh

# Resolve the interpreter that owns pre-commit: the governed EXTERNAL environment
# (DUTCHBAY_VENV, per ENV-01/THREAD-01) first, then an in-checkout .venv, then PATH.
# VENV_PY alone never resolves in this project, because the governed venv lives
# outside the checkout - so the bare-PATH fallback was doing all the work.
# Install the configured git pre-commit hook set. `setup` already does this; this target
# lets an existing checkout restore the enabled local checks and GOV-02 guard without a
# full environment reconcile. R10's mypy mismatch remains tracked in #1270. Idempotent.
# Hooks are untracked, so a fresh clone has none.
HOOK_PY := $(if $(DUTCHBAY_VENV),$(DUTCHBAY_VENV)/bin/python,$(VENV_PY))
hooks:
	$(if $(HOOK_PY),"$(HOOK_PY)" -m pre_commit install,pre-commit install)

# Mandatory gates: ruff. Advisory (matches CI): black --check (the committed tree is
# style-drifted vs the current formatter, so black is non-blocking by design).
lint:
	ruff check .
	black --check .
	isort --check-only --profile=black .

# Strict, complete-annotation mypy over the whole typed surface (mirrors CI test-suite.yml).
type:
	mypy $(SURFACE) $(ENTRYPOINTS)

# Security gate (mirrors CI). SAST over own code (fail on MEDIUM+ severity/confidence) +
# dependency CVE audit of the pinned lock in BOTH of pip-audit's coverage modes (fail on
# any non-allowlisted advisory). The same $(PIP_AUDIT_IGNORES) applies to both passes, so a
# suppression can never hold in one mode and not the other.
#
# TWO passes, because neither alone audits the whole lock. Measured 2026-10-25 against
# requirements.txt at main 9b2b51e0 (312 pins), pip-audit 2.10.1, Python 3.12.3:
#
#   resolve mode   pip-audit -r requirements.txt                          -> 310 audited
#   declared mode  pip-audit --no-deps --disable-pip -r requirements.txt  -> 312 audited
#
# RESOLVE mode builds a temporary venv, dry-run resolves the file and audits the resolve
# report, so it is authoritative for what an install really pulls in and is the ONLY pass
# that sees a package the lock does not pin - that is how `cloudpickle` was audited in the
# window before #1387 pinned it. What it cannot see is a pin its own scaffolding already
# satisfies: pip-audit's `VirtualEnv.post_setup` runs `pip install --upgrade pip wheel
# setuptools` inside that venv BEFORE the `pip install --dry-run --report` resolve, and that
# prologue lands `packaging` and `wheel` at exactly the versions this lock pins, so pip
# reports neither as to-install and pip-audit audits neither. `packaging==26.3` and
# `wheel==0.48.0` were therefore unaudited lock pins, and the omission is VERSION-
# COINCIDENTAL - it appears and disappears as upstream moves, with nothing announcing either
# way. Nobody wrote a rule excluding them; the auditor's own environment hid them.
#
# DECLARED mode closes that. `--no-deps --disable-pip` takes pip-audit's pre-resolved path,
# skipping the venv entirely, and audits every requirement the file declares, so no pin can
# hide behind the auditor's environment. It costs under a second and needs no resolve. It is
# a COMPLEMENT, not a replacement: it audits only what is written down, which is why both
# passes run and neither is dropped.
#
# Out of scope in both passes, stated rather than implied: `pip` itself, which this lock
# deliberately does not pin - it is the resolver, and the one unpinned entry the lock-closure
# check of #1359/#1387 expects to see. Tracked as a residual on #1353.
security:
	bandit -c pyproject.toml -r $(SURFACE) --severity-level medium --confidence-level medium
	pip-audit -r requirements.txt $(PIP_AUDIT_IGNORES)
	pip-audit --no-deps --disable-pip -r requirements.txt $(PIP_AUDIT_IGNORES)

# Convenience alias for the resolve-mode audit alone. Deliberately ONE recipe line carrying
# no flags beyond the lock and the allowlist: this is the canonical spelling of the effective
# suppression set, and #1386 proposes a SECDEP-01 fence that reads `make -n audit` as its
# oracle for it. Added coverage belongs in `audit-declared` and `security`, not here.
audit:
	pip-audit -r requirements.txt $(PIP_AUDIT_IGNORES)

# The declared-pin pass on its own: audits every pin in the lock, including the ones resolve
# mode skips, in under a second and with no network resolve. The fast local pre-flight.
audit-declared:
	pip-audit --no-deps --disable-pip -r requirements.txt $(PIP_AUDIT_IGNORES)

# The real test gate: pytest (xdist-parallel) with the coverage floor (#439). The floor
# is enforced HERE and in the CI test step, not in pyproject addopts.
test:
	DUTCHBAY_TEST_MODE=full $(PYTEST) -n auto $(COV) --cov-report=term-missing --cov-fail-under=95

# Explicit scale/qualification path for TEST-03 tests above the ordinary suite's
# 200-effective-model-evaluation cap. A green run is not by itself a lender,
# bankability, convergence, or release receipt (see docs/development/stochastic_test_policy.md).
test-stochastic-qualification:
	DUTCHBAY_TEST_MODE=qualification $(PYTEST) -n auto -m stochastic_qualification --tb=short

# TEST-04 live report paths: the complete supplemental-sensitivity builder and
# real PDF backend. Transport/renderer contracts stay in the bounded ordinary suite.
test-report-qualification:
	DUTCHBAY_TEST_MODE=qualification $(PYTEST) -n 2 tests/integration/test_lender_report_e2e.py tests/integration/test_synthetic_qsts_finance_report.py -m report_qualification --tb=short

cov:
	DUTCHBAY_TEST_MODE=full $(PYTEST) -n auto $(COV) --cov-report=term-missing

html:
	DUTCHBAY_TEST_MODE=full $(PYTEST) $(COV) --cov-report=html && echo "Open htmlcov/index.html"

package:
	$(PY) -m build

# Regenerate the pinned reproducibility lock in a CLEAN venv. Install the existing
# cleared lock first so an additive dependency dolphin cannot silently refresh unrelated
# packages inside broad abstract ranges; then resolve the complete abstract capability
# set under constraints.txt. A deliberate whole-lock refresh is a separate migration.
lock:
	$(PIP) install -r requirements.txt
	PIP_CONSTRAINT=constraints.txt $(PIP) install -e ".[$(LOCK_EXTRAS)]"
	@lock_tmp=$$(mktemp); \
		awk 'BEGIN { separators = 0 } { print } /^# ─/ { separators++; if (separators == 2) exit }' requirements.txt > "$$lock_tmp"; \
		$(PIP) freeze --exclude-editable | sort -f >> "$$lock_tmp"; \
		mv "$$lock_tmp" requirements.txt
	@echo "Regenerated requirements.txt. Review the diff and re-run 'make audit'."

clean:
	rm -rf build dist *.egg-info .mypy_cache .pytest_cache .ruff_cache htmlcov
	find . -name "__pycache__" -type d -exec rm -rf {} +
	find . -name "*.pyc" -delete
