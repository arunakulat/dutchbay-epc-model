"""Render the NSO 250 MW gap dossier as an ADVISORY-GROUP issue, for a bidder other than the
one the committed register was raised for.

Why this is a separate script rather than an edit to the register
----------------------------------------------------------------
The committed register at
``docs/source_materials/nso_bess_250mw_2026/registers/build_gap_dossier_2026-08-27.py``
is the internal record and correctly names the bidding entity it was raised for. That record must
not be rewritten to produce an external issue. This script imports it unchanged and applies the
three changes an external issue needs, so the two documents cannot drift and the internal record
keeps its identity.

The three changes
-----------------
1. ``bidder_label`` becomes the advisory group, so the "Raised by" control field attributes the
   document to its actual preparer rather than to a bidder.

2. Two passages say "the bidder" in a sense that is TRUE OF THE ORIGINAL RECIPIENT ONLY, and would
   be false or misleading read by anyone else:

   * gap A6 — "the bidder asked for precisely that relief at clarification 64 and was refused".
     The issued clarification register does not attribute questions, and the recipient of this
     issue did not necessarily ask it. Restated to attribute the question to the register.
   * closure pathway (2) — "The bidder holds both models". A different recipient may hold neither.
     Restated to say the models exist in the OEM's pack.

   These are corrected, not deleted: the underlying fact survives, only the false attribution goes.

3. An "Issue and reliance" section records who prepared it, for whom it is issued, and what it is
   not — so the document cannot be mistaken for a bid, a compliance determination, or advice the
   recipient may rely on without their own verification.

Nothing else is altered. The gap register, evidence inventory, source provenance and every hash
are the committed ones.
"""

from __future__ import annotations

import dataclasses
import importlib.util
import sys
from pathlib import Path

# Resolved from this file's own location, so the script runs from any checkout. This file lives
# at <repo>/docs/source_materials/nso_bess_250mw_2026/registers/, hence five parents up.
REPO = Path(__file__).resolve().parents[4]
REGISTER = Path(__file__).resolve().parent / "build_gap_dossier_2026-08-27.py"

ADVISORY_LABEL = "DutchBay / Icomunicamos Advisory Group"

sys.path.insert(0, str(REPO))

_spec = importlib.util.spec_from_file_location("nso_register", REGISTER)
assert _spec and _spec.loader
reg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(reg)

from app.reports.tender_gap_dossier_emit import (  # noqa: E402
    as_dbpl_document,
    build_dossier,
)

# ── change 2: de-attribute the two bidder-specific statements ────────────────────────────────
_A6_FROM = (
    "and the bidder asked for precisely that relief at clarification 64 and was refused"
)
_A6_TO = "and clarification 64 sought precisely that relief and was refused"

_PATH_FROM = "The bidder holds both models, so the stated rejection ground is clearable at bid stage"
_PATH_TO = (
    "Both models exist in the OEM's pack, so the stated rejection ground is clearable at "
    "bid stage by any bidder holding them"
)

gaps = []
a6_patched = False
for g in reg.GAPS:
    if _A6_FROM in g.why_insufficient:
        g = dataclasses.replace(
            g, why_insufficient=g.why_insufficient.replace(_A6_FROM, _A6_TO)
        )
        a6_patched = True
    gaps.append(g)
if not a6_patched:
    raise SystemExit(
        "A6 attribution string not found — the register changed. Re-read it before issuing."
    )

# Search every section rather than assuming which one carries it — the passage lives in
# "What changed since the 31 July gap statement", not the closure pathways.
sections = dict(reg.SECTIONS)
_hits = [k for k, v in sections.items() if _PATH_FROM in v]
if len(_hits) != 1:
    raise SystemExit(
        f"expected exactly one section carrying the bidder-holds-models statement, "
        f"found {len(_hits)}: {_hits}. The register changed — re-read it before issuing."
    )
sections[_hits[0]] = sections[_hits[0]].replace(_PATH_FROM, _PATH_TO)

# ── change 3: issue and reliance ─────────────────────────────────────────────────────────────
sections["Issue and reliance"] = (
    f"PREPARED BY. This dossier was prepared by {ADVISORY_LABEL} as an independent evidence "
    "audit of the OEM bid pack against the controlling tender documents. It is the advisory "
    "group's own work product.\n\n"
    "WHAT IT IS. A register of gaps between what the tender's controlling clauses REQUIRE and "
    "what the OEM's pack actually SUPPLIED, with the question that would close each one. Every "
    "finding is anchored to a document listed under Source provenance, and each of those rows "
    "carries the document's SHA-256 and the extraction route used to read it, so a clause quoted "
    "from a digital original can be told from one recovered by OCR.\n\n"
    "WHAT IT IS NOT. It is not the tender, not a bid, not a compliance determination, and not a "
    "statement that the OEM cannot meet the requirement. A gap here means the evidence in the "
    "pack reviewed does not close the clause — the OEM may hold evidence that does. Where the "
    "register records a supplier declaration, that is recorded as a declaration and never counted "
    "as evidence.\n\n"
    "RELIANCE. The recipient should verify each finding against its own copy of the controlling "
    "documents and its own correspondence with the OEM before acting on it. Commercial positions "
    "in this register — warranty, liquidated damages, availability exposure — are read from the "
    "documents named and are not legal advice.\n\n"
    "CURRENCY. The register is dated 27 August 2026 and states a submission deadline of "
    "4 September 2026. The clarification window closed on 25 August 2026, so several gaps are "
    "marked as no longer closable through that route."
)

model = build_dossier(
    tender_ref=reg.TENDER_REF,
    tender_title=reg.TENDER_TITLE,
    oem_label="Envision Energy / the supplying group entity",
    bidder_label=ADVISORY_LABEL,
    gaps=gaps,
    evidence=reg.EVIDENCE,
    sources=reg.SOURCES,
    sections=sections,
    submission_deadline="4 September 2026, 10.00 hrs (Addendum No. 01 item 01)",
    working_days_remaining=6,
)


def main() -> None:
    from jinja2 import Environment, FileSystemLoader

    from app.reports.dbpl import render_dbpl_pdf

    out = Path(sys.argv[1] if len(sys.argv) > 1 else "advisory_gap_dossier.pdf")

    env = Environment(
        loader=FileSystemLoader(str(REPO / "app/reports/dbpl/templates")),
        autoescape=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template("dbpl_base.html.j2")

    first = render_dbpl_pdf(template.render(doc=as_dbpl_document(model)))
    substituted = first.substituted_fonts
    embedded = first.house_fonts_embedded
    provenance = (
        f"Rendered by the DutchBay Presentation Layer (WeasyPrint), "
        f"Python {model.python_version}.",
        f"PDF variant {first.pdf_variant}; house stylesheet applied: "
        f"{first.stylesheet_applied}.",
        (
            "Font substitution: "
            + (", ".join(substituted) + " substituted" if substituted else "none")
            + "; house fonts embedded: "
            + (
                "UNVERIFIED (poppler unavailable)"
                if embedded is None
                else ("yes" if embedded else "NO")
            )
            + "."
        ),
    )
    second = render_dbpl_pdf(
        template.render(doc=as_dbpl_document(model, provenance_lines=provenance))
    )
    out.write_bytes(second.pdf)
    print(f"wrote {out} ({len(second.pdf):,} bytes)")
    print(f"gaps: {len(model.gaps)}")
    print(f"raised by: {model.bidder_label}")


if __name__ == "__main__":
    main()
