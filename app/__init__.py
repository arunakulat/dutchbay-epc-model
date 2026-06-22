"""Web/service layer for the DutchBay EPC model.

This package is the framework-agnostic seam between callers (FastAPI, notebooks,
batch jobs) and the canonical v14 finance pipeline. It contains NO finance logic
of its own — every compute path delegates to the canonical engine gateways
(``analytics.pipeline_v14_enhanced.run_v14_pipeline`` and the wind adapter). See
``docs/ARCHITECTURE.md`` and ``docs/WEB_SERVICE_ROADMAP.md``.
"""
