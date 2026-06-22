"""FastAPI surface for the DutchBay EPC model.

A single application that unifies the existing routers and adds the
wizard-facing ``POST /cases`` endpoint. Import ``app.api.main:app`` to serve
(e.g. ``uvicorn app.api.main:app``).
"""
