"""FastAPI surface for the DutchBay EPC model.

A single application that unifies the existing routers and adds the
wizard-facing ``POST /v1/cases`` endpoint. The public surface is version-pinned
under ``/v1`` (#841). Import ``app.api.main:app`` to serve
(e.g. ``uvicorn app.api.main:app``).
"""
