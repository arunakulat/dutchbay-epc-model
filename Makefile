.PHONY: setup lint type security audit test cov html package lock clean

PY ?= python
PIP ?= pip

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

# Install the pinned reproducibility lock + the dev/CI toolchain (pyproject [dev]).
setup:
	$(PY) -m pip install --upgrade pip
	$(PIP) install -r requirements.txt
	$(PIP) install -e ".[dev]"

# Mandatory gates: ruff. Advisory (matches CI): black --check (the committed tree is
# style-drifted vs the current formatter, so black is non-blocking by design).
lint:
	ruff check .
	black --check . || true
	isort --check-only --profile=black . || true

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
	pytest -n auto $(COV) --cov-report=term-missing --cov-fail-under=95

cov:
	pytest -n auto $(COV) --cov-report=term-missing

html:
	pytest $(COV) --cov-report=html && echo "Open htmlcov/index.html"

package:
	$(PY) -m build

# Regenerate the pinned reproducibility lock from a CLEAN install of pyproject (the
# abstract source of truth). requirements.txt is THE lock CI installs; constraints.txt
# holds the freeze-policy version caps (the versions the mandatory gates were cleared
# against) and is applied via PIP_CONSTRAINT so the regenerated lock respects them (see
# the constraints.txt header). Run in a fresh venv.
lock:
	PIP_CONSTRAINT=constraints.txt $(PIP) install -e ".[dev,api,dashboard,wind,gis,report]"
	$(PIP) freeze --exclude-editable | sort > requirements.txt
	@echo "Regenerated requirements.txt. Review the diff and re-run 'make audit'."

clean:
	rm -rf build dist *.egg-info .mypy_cache .pytest_cache .ruff_cache htmlcov
	find . -name "__pycache__" -type d -exec rm -rf {} +
	find . -name "*.pyc" -delete
