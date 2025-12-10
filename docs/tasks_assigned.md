# Assigned Roles and Tasks

| Role | Tasks |
| --- | --- |
| Architecture lead & tech writer | Document `CasperResult v1` JSON contract (fields, optionality, versioning). Create architecture notes. Prepare release notes. |
| Dev lead | Merge feature branches, bump version, update `CHANGELOG.md`, tag release, run full test suite (pytest, mypy, Black, isort, Ruff). |
| Architecture dev | Extend `CasperResult` with generation and technology breakdown fields; implement `TechnologyBreakdown` dataclass; ensure backward compatibility and update `__all__`. |
| Analytics dev | Finalize `analytics/sensitivity_v14.run()` API; remove leftover type ignores; add unit tests; start on `GenerationProfile` and `MultiTechGenerationResult` dataclasses. |
| Architecture + Analytics dev | Harden `run_casper_analysis` and orchestrator; ensure no direct finance imports; convert xfail integration test to real smoke test once MC naming is fixed; coordinate multi‑tech integration. |
| QA & tech writer | Create `test_casper_v14_smoke.py` for orchestrator; update architecture docs with CASPER orchestrator section; ensure docs are clear and concise. |
| Config/Ops dev | Extend `constants.py` and master config with multi‑tech ranges and generation block; ensure backward compatibility; update schema guard tests. |
| QA | Run full test suite; ensure coverage ≥ 60%; remove xfail after MC alignment; report issues. |
| Project manager | Coordinate tasks, run integration checks, store CCCDIR deliverables in depository, assign follow‑up tasks based on lint/test results, produce final deliverable archive. |
