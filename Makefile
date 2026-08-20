.PHONY: setup lint type security audit test test-stochastic-qualification test-report-qualification cov html package lock clean

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

# pip-audit allowlist — EMPTY. The coordinated major upgrade (fastapi 0.121->0.137 +
# starlette 0.49->1.3.1, streamlit 1.51->1.54 + pyarrow 21->24, black 25->26 [+ pathspec/
# pytokens], curl-cffi 0.13->0.15) cleared every previously-accepted advisory, so pip-audit
# is clean with NO ignores. Keep this variable as the home for any FUTURE genuinely-capped
# CVE (add `--ignore-vuln <ID>` with a one-line reason), and prefer fixing over ignoring.
PIP_AUDIT_IGNORES :=

# Coverage surface for the floor gate (#439, +solar_resource #456): the six engine
# packages, mirroring the CI test step. The --cov-fail-under=95 floor is enforced in
# `test` and CI — NOT in pyproject addopts — so a partial dev run does not spuriously trip it.
COV := --cov=finance --cov=analytics --cov=wind_resource --cov=api --cov=app --cov=solar_resource

# Resolve, create if absent, and validate the governed environment. The setup
# script installs the pinned reproducibility lock without an editable checkout.
setup:
	./setup_venv.sh

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
# dependency CVE audit of the pinned lock (fail on any non-allowlisted advisory).
security:
	bandit -c pyproject.toml -r $(SURFACE) --severity-level medium --confidence-level medium
	pip-audit -r requirements.txt $(PIP_AUDIT_IGNORES)

# Convenience alias for the dependency audit alone.
audit:
	pip-audit -r requirements.txt $(PIP_AUDIT_IGNORES)

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
