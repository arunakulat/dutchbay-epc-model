# Changelog

All notable changes to this project will be documented here.

## [Unreleased]

- TBD

## [1.0.0] - Initial public baseline
- CI: matrix (Ubuntu/Windows/macOS) + Python 3.10–3.12, workflow_dispatch, nightly, concurrency guard
- Pre-commit: black/flake8/isort/mypy + hygiene hooks
- Strict configs: .flake8, mypy.ini, pytest.ini (coverage ≥90% gate)
- Scenario runner: YAML → JSONL/CSV, multi-path `--scenarios`
- CLI: modes mapped (baseline/sensitivity/optimize/report/scenarios/api) + finance handlers + EPC
- Schema/docs: EPC parameters (ranges + units) in `schema.py`/`schema.md`
- Packaging: `python -m build`, smoke-install, artifact upload with versioned names
- Security/hygiene: CODEOWNERS, SECURITY.md, CONTRIBUTING.md
