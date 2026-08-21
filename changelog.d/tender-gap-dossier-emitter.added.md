Added `app/reports/tender_gap_dossier_emit.py` and its template — a vendor-neutral presentation
surface that renders a tender evidence gap register as a query pack a bidder can send to an OEM.
Follows the #884 grid-screening idiom: frozen dataclasses, a pure builder, a standalone Jinja2
template, un-suppressible caveats, and surfaced provenance (per-source SHA-256 and extraction
route) plus a verification-discipline statement. The module hard-codes no tender, OEM, bidder or
finding — the register is supplied by the caller and the bidder is referred to by the neutral
role label "Bidder", so one pack serves any bidding entity. Malformed registers fail loud.
