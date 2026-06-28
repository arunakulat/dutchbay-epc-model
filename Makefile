.PHONY: setup lint type security audit test cov html package lock clean

PY ?= python
PIP ?= pip

# Engine/application surface scanned by the type + security gates (mirrors CI).
SURFACE := finance analytics api app wind_resource solar_resource analysis_tools
ENTRYPOINTS := run_full_pipeline_v14.py run_scenario_analytics_v14.py \
	dutchbay_bootstrap.py dutchbay_bootstrap_rules.py constants.py

# pip-audit allowlist — ACCEPTED, version-capped CVEs (reviewed; re-check at each release).
# Each is non-core or blocked behind a coordinated major upgrade:
#   starlette  PYSEC-2026-161/248/249, CVE-2026-48818/48817 — fixed in starlette 1.x, which
#              needs a coordinated FastAPI 0.121->0.137 bump (separate upgrade PR).
#   streamlit  PYSEC-2026-212, CVE-2026-33682 — fixed in streamlit 1.53/1.54; dashboard-only,
#              and the bump also pulls pyarrow>=23 (coordinated dashboard upgrade).
#   pyarrow    PYSEC-2026-113 — capped by streamlit's pin; clears with the streamlit upgrade.
#   black      CVE-2026-32274 — dev-only formatter; black 26 forces a repo-wide reformat.
#   curl-cffi  CVE-2026-33752 — transitive via yfinance (peripheral market-data), not in the
#              finance engine's network path.
PIP_AUDIT_IGNORES := \
	--ignore-vuln PYSEC-2026-161 --ignore-vuln PYSEC-2026-248 --ignore-vuln PYSEC-2026-249 \
	--ignore-vuln CVE-2026-48818 --ignore-vuln CVE-2026-48817 \
	--ignore-vuln PYSEC-2026-212 --ignore-vuln CVE-2026-33682 \
	--ignore-vuln PYSEC-2026-113 \
	--ignore-vuln CVE-2026-32274 --ignore-vuln CVE-2026-33752

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

# The real test gate: pytest (xdist-parallel) with the coverage floor from pyproject.
test:
	pytest -n auto

cov:
	pytest -n auto --cov-report=term-missing

html:
	pytest --cov-report=html && echo "Open htmlcov/index.html"

package:
	$(PY) -m build

# Regenerate the pinned reproducibility lock from a CLEAN install of pyproject (the
# abstract source of truth). requirements.txt is THE lock CI installs — there is no
# separate constraints.txt / requirements.lock (those were retired). Run in a fresh venv.
lock:
	$(PIP) install -e ".[dev,api,dashboard,wind,gis,report]"
	$(PIP) freeze --exclude-editable | sort > requirements.txt
	@echo "Regenerated requirements.txt. Review the diff and re-run 'make audit'."

clean:
	rm -rf build dist *.egg-info .mypy_cache .pytest_cache .ruff_cache htmlcov
	find . -name "__pycache__" -type d -exec rm -rf {} +
	find . -name "*.pyc" -delete
