"""Vendor-neutral TENDER GAP DOSSIER emitter — a bidder's query pack to an OEM.

What this is
------------
A procurement-side counterpart to :mod:`app.reports.grid_screening_emit`. Where that emitter
surfaces an *engineering screen*, this one surfaces an *evidence audit*: it renders a register of
gaps between what a tender's controlling clauses REQUIRE and what an OEM's bid pack actually
SUPPLIED, together with the question a bidder should put to the OEM to close each one.

The output is written to be sent to the OEM as-is. Every gap carries the controlling clause, the
requirement verbatim, what was received, why that is insufficient, and a closure test — so the
recipient can act without re-reading the tender.

Vendor-neutral by construction
------------------------------
This module is MACHINERY ONLY. It hard-codes no tender, no OEM, no bidder and no findings — the
register is supplied by the caller as :class:`TenderGapDossier` (typically loaded from a YAML/JSON
register held wherever the underlying evidence is held). The bidder is referred to throughout by
the neutral role label :data:`DEFAULT_BIDDER_LABEL` ("Bidder"), so a dossier can be handed to any
bidding entity without edit. A caller may override the label, but the default is deliberately
generic.

That separation is also the confidentiality boundary: the machinery is publishable, the register
that instantiates it inherits the classification of the evidence it describes.

Provenance (surfaced, not internal — the ``surface-provenance-in-presentation-layer`` directive)
-------------------------------------------------------------------------------------------------
The dossier surfaces (a) SOURCE PROVENANCE — every source document that was read, its SHA-256, and
the extraction route (native text / MarkItDown / OCR), so a reader can tell a clause quoted from a
digital original from one recovered by OCR — and (b) VERIFICATION DISCIPLINE — that findings are
evidence-anchored, that a supplier declaration is never counted as evidence, and that a gap the
tool could not verify is surfaced as unverified rather than silently dropped.

Un-suppressible caveats
-----------------------
:data:`MANDATORY_DOSSIER_CAVEAT` and :data:`SOURCE_GOVERNS_CAVEAT` are baked structurally into the
model and the template. There is no flag that removes them: a derived gap register must never be
mistaken for the tender, nor for a compliance determination.

CASPER
------
The optional PDF backend is guarded at call time by the shared renderer. Markdown and HTML need no
optional dependency, so the dossier always emits in at least one format — a missing WeasyPrint
degrades the PDF surface, never the dossier.

GWTF:
    - CESSPIT: fail loud on a malformed register — an empty gap register, a gap with no clause, or
      a severity outside the known set RAISES. There are no silent defaults, because a silently
      dropped gap is the one failure mode this report cannot have.
    - CCCDIR: pure presentation. Consumes its own frozen dataclasses only; no finance, no IRR, no
      scenario or engine import. Nothing here can influence canonical KPIs.
    - DATA-01: the register is rendered losslessly — every field supplied is surfaced, and a field
      left unset renders as an explicit "not stated", never as an inferred value.
"""

from __future__ import annotations

import hashlib
import platform
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Sequence

from jinja2 import Environment, FileSystemLoader

__all__ = [
    "DEFAULT_BIDDER_LABEL",
    "MANDATORY_DOSSIER_CAVEAT",
    "SOURCE_GOVERNS_CAVEAT",
    "VERIFICATION_DISCIPLINE",
    "SEVERITIES",
    "GapItem",
    "SourceDocument",
    "EvidenceLine",
    "TenderGapDossier",
    "build_dossier",
    "render_dossier_html",
    "render_dossier_markdown",
    "as_dbpl_document",
]

#: Neutral role label. The dossier never names the bidding entity, so one pack serves any bidder.
DEFAULT_BIDDER_LABEL = "Bidder"

#: Un-suppressible headline caveat — a gap register is an audit aid, never a determination.
MANDATORY_DOSSIER_CAVEAT = (
    "DERIVED GAP REGISTER — NOT A COMPLIANCE DETERMINATION. This dossier records, for each "
    "controlling clause, what the tender requires against what the bid pack was found to "
    "contain. It is an aid to querying the OEM and to closing evidence gaps before submission. "
    "It does not determine compliance, it does not bind the procuring authority, and it confers "
    "no waiver of any tender requirement."
)

#: Un-suppressible precedence caveat — the source always wins over the derived register.
SOURCE_GOVERNS_CAVEAT = (
    "SOURCE DOCUMENTS GOVERN. Where this register and a tender document, an OEM document or an "
    "issued addendum/clarification disagree, that document governs and this register is wrong. "
    "Quotations are reproduced from the extracts listed under Source provenance; verify any "
    "clause against the issued original before relying on it contractually."
)

#: Verification-discipline statement — surfaced so the reader sees the method, not just findings.
VERIFICATION_DISCIPLINE = (
    "Verification discipline: every gap below is anchored to a controlling clause and to the "
    "document actually received. A supplier declaration is recorded as a declaration and is "
    "never counted as evidence — a checklist row marked 'Received' against a document that does "
    "not answer the requirement is reported as a gap, not as closure. Where a finding could not "
    "be verified from the supplied material it is marked UNVERIFIED and its basis is stated, "
    "rather than being asserted or dropped."
)

#: The ordered severity vocabulary. Ordering drives the register sort (most severe first).
SEVERITIES: tuple[str, ...] = ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFORMATIONAL")

#: Extraction routes, surfaced per source so an OCR-recovered quote is never mistaken for a
#: digital-original quote.
_EXTRACTION_ROUTES = frozenset({"native", "markitdown", "ocr", "ooxml", "manual"})

_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
_TEMPLATE_NAME = "tender_gap_dossier.html.j2"


class DossierRegisterError(ValueError):
    """Raised when a supplied gap register is malformed (CESSPIT — fail loud, never default)."""


# ═════════════════════════════════════════════════════════════════════════════
# Frozen data model. Pure data, assembled by the caller, rendered by the template.
# ═════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class SourceDocument:
    """One source document that was read to build the register (source provenance).

    Fields
        label: human name as it should appear to the OEM.
        role: what the document controls — e.g. "controlling tender volume", "OEM evidence".
        sha256: content hash of the received file, or ``None`` when not hashed.
        extraction: how text was recovered — one of :data:`_EXTRACTION_ROUTES`.
        document_date: the date printed ON the document, when it states one.
        note: any caveat about fidelity (e.g. handwritten form, poor OCR).
    """

    label: str
    role: str
    sha256: Optional[str] = None
    extraction: str = "native"
    document_date: Optional[str] = None
    note: Optional[str] = None

    def __post_init__(self) -> None:
        if self.extraction not in _EXTRACTION_ROUTES:
            raise DossierRegisterError(
                f"{self.label}: unknown extraction route {self.extraction!r}; "
                f"expected one of {sorted(_EXTRACTION_ROUTES)}"
            )

    @property
    def short_hash(self) -> str:
        """First 12 hex characters of the hash, or an explicit marker when absent."""
        return self.sha256[:12] if self.sha256 else "not hashed"


@dataclass(frozen=True)
class EvidenceLine:
    """One row of the received-evidence inventory, tracked separately from the gaps.

    ``declared`` is what the supplier's own checklist claims; ``received`` is what the audit found
    actually present. The two are deliberately separate columns — the divergence is the finding.
    """

    item: str
    declared: str
    received: str
    adequate: Optional[bool] = None
    note: Optional[str] = None

    @property
    def status_label(self) -> str:
        """Render-ready adequacy label; ``None`` means 'not assessed', not 'adequate'."""
        if self.adequate is None:
            return "not assessed"
        return "adequate" if self.adequate else "NOT adequate"


@dataclass(frozen=True)
class GapItem:
    """One gap between a controlling requirement and the evidence supplied.

    Fields
        gap_id: stable identifier, e.g. ``A1``. Used by the OEM to reply item-by-item.
        title: one-line statement of the gap.
        severity: one of :data:`SEVERITIES`.
        clause: the controlling clause reference, e.g. ``Volume I §3.1(c)``.
        requirement: the requirement, quoted or closely paraphrased from the clause.
        supplied: what the bid pack actually contains against that clause.
        why_insufficient: why what was supplied does not discharge the requirement.
        question: the question to put to the OEM — written to be sent verbatim.
        closure_test: the objective test that would close the gap.
        tier: delivery tier, e.g. ``critical path`` / ``document`` / ``cannot close in window``.
        verified: False marks a finding the tool could not confirm from the material.
        consequence: the tender consequence, when the clause states one.
    """

    gap_id: str
    title: str
    severity: str
    clause: str
    requirement: str
    supplied: str
    why_insufficient: str
    question: str
    closure_test: str
    tier: str = "document"
    verified: bool = True
    consequence: Optional[str] = None

    def __post_init__(self) -> None:
        if self.severity not in SEVERITIES:
            raise DossierRegisterError(
                f"{self.gap_id}: unknown severity {self.severity!r}; expected one of "
                f"{list(SEVERITIES)}"
            )
        if not self.clause.strip():
            raise DossierRegisterError(
                f"{self.gap_id}: every gap must cite a controlling clause; none supplied"
            )

    @property
    def severity_rank(self) -> int:
        """Sort key — lower is more severe."""
        return SEVERITIES.index(self.severity)


@dataclass(frozen=True)
class TenderGapDossier:
    """The assembled, render-ready dossier model.

    Pure data. The caveats and the verification-discipline statement are echoed from module
    constants onto the model so the template renders them structurally rather than by convention.
    """

    tender_ref: str
    tender_title: str
    oem_label: str
    generated_at: str
    submission_deadline: Optional[str] = None

    bidder_label: str = DEFAULT_BIDDER_LABEL
    gaps: tuple[GapItem, ...] = ()
    evidence: tuple[EvidenceLine, ...] = ()
    sources: tuple[SourceDocument, ...] = ()
    sections: Mapping[str, str] = field(default_factory=dict)
    working_days_remaining: Optional[int] = None

    mandatory_caveat: str = MANDATORY_DOSSIER_CAVEAT
    source_governs: str = SOURCE_GOVERNS_CAVEAT
    verification_discipline: str = VERIFICATION_DISCIPLINE
    python_version: str = ""
    register_digest: str = ""

    @property
    def gaps_by_severity(self) -> tuple[GapItem, ...]:
        """Gaps ordered most-severe first, stable within a severity by gap id."""
        return tuple(sorted(self.gaps, key=lambda g: (g.severity_rank, g.gap_id)))

    @property
    def severity_counts(self) -> tuple[tuple[str, int], ...]:
        """(severity, count) in severity order, omitting severities with no gaps."""
        counts = {s: 0 for s in SEVERITIES}
        for gap in self.gaps:
            counts[gap.severity] += 1
        return tuple((s, n) for s, n in counts.items() if n)

    @property
    def critical_path(self) -> tuple[GapItem, ...]:
        """Gaps on the critical path — the ones that gate other work."""
        return tuple(g for g in self.gaps_by_severity if g.tier == "critical path")

    @property
    def unverified(self) -> tuple[GapItem, ...]:
        """Findings the tool could not confirm; surfaced rather than dropped (DATA-01)."""
        return tuple(g for g in self.gaps_by_severity if not g.verified)


# ═════════════════════════════════════════════════════════════════════════════
# Builder
# ═════════════════════════════════════════════════════════════════════════════


def _register_digest(gaps: Sequence[GapItem]) -> str:
    """Stable digest over the gap register, so a reissued dossier is diffable by hash."""
    hasher = hashlib.sha256()
    for gap in sorted(gaps, key=lambda g: g.gap_id):
        hasher.update(
            "\x1f".join(
                (gap.gap_id, gap.severity, gap.clause, gap.title, gap.closure_test)
            ).encode("utf-8")
        )
        hasher.update(b"\x1e")
    return hasher.hexdigest()


def build_dossier(
    *,
    tender_ref: str,
    tender_title: str,
    oem_label: str,
    gaps: Iterable[GapItem],
    evidence: Iterable[EvidenceLine] = (),
    sources: Iterable[SourceDocument] = (),
    sections: Optional[Mapping[str, str]] = None,
    bidder_label: str = DEFAULT_BIDDER_LABEL,
    submission_deadline: Optional[str] = None,
    working_days_remaining: Optional[int] = None,
    generated_at: Optional[str] = None,
) -> TenderGapDossier:
    """Assemble a :class:`TenderGapDossier` from a caller-supplied register.

    Args:
        tender_ref: the tender number, reproduced verbatim.
        tender_title: the tender title, reproduced verbatim.
        oem_label: the OEM the queries are addressed to.
        gaps: the gap register. Must be non-empty.
        evidence: the received-evidence inventory (declared vs actually received).
        sources: source-provenance rows.
        sections: optional free-text sections keyed by heading, rendered after the register.
        bidder_label: neutral role label for the bidding entity.
        submission_deadline: the deadline as stated by the procuring authority.
        working_days_remaining: working days to the deadline, when known.
        generated_at: ISO timestamp override (tests pin this for byte-identical output).

    Returns:
        The assembled, render-ready model.

    Raises:
        DossierRegisterError: the register is empty or contains duplicate gap ids.
    """
    gap_tuple = tuple(gaps)
    if not gap_tuple:
        # CESSPIT: an empty register is far more likely to be a wiring bug than a clean bill.
        raise DossierRegisterError(
            "gap register is empty; refusing to emit a dossier that would read as "
            "'no gaps found'. Pass an explicit register, even if it is a single "
            "INFORMATIONAL row."
        )
    seen: set[str] = set()
    for gap in gap_tuple:
        if gap.gap_id in seen:
            raise DossierRegisterError(f"duplicate gap id {gap.gap_id!r} in register")
        seen.add(gap.gap_id)

    stamp = generated_at or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    return TenderGapDossier(
        tender_ref=tender_ref,
        tender_title=tender_title,
        oem_label=oem_label,
        generated_at=stamp,
        submission_deadline=submission_deadline,
        bidder_label=bidder_label,
        gaps=gap_tuple,
        evidence=tuple(evidence),
        sources=tuple(sources),
        sections=dict(sections or {}),
        working_days_remaining=working_days_remaining,
        python_version=platform.python_version(),
        register_digest=_register_digest(gap_tuple),
    )


# ═════════════════════════════════════════════════════════════════════════════
# Renderers
# ═════════════════════════════════════════════════════════════════════════════


def _environment() -> Environment:
    """Build the Jinja2 environment with autoescaping forced on (no injection via a label)."""
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render_dossier_html(model: TenderGapDossier) -> str:
    """Render the dossier to a standalone HTML document string."""
    return _environment().get_template(_TEMPLATE_NAME).render(m=model)


def _md_row(cells: Sequence[Any]) -> str:
    """One GitHub-flavoured Markdown table row, pipe-escaped."""
    return "| " + " | ".join(str(c).replace("|", "\\|") for c in cells) + " |"


def render_dossier_markdown(model: TenderGapDossier) -> str:
    """Render the dossier to Markdown — the format most often pasted into an OEM email.

    Kept as a first-class surface (not an HTML-to-text fallback) so the dossier is usable with no
    optional dependency at all.
    """
    out: list[str] = []
    add = out.append

    add(f"# Tender evidence gap dossier — {model.tender_ref}")
    add("")
    add(f"**{model.tender_title}**")
    add("")
    add(f"- Addressed to: **{model.oem_label}**")
    add(f"- Raised by: **{model.bidder_label}**")
    if model.submission_deadline:
        days = (
            f" ({model.working_days_remaining} working days remaining)"
            if model.working_days_remaining is not None
            else ""
        )
        add(f"- Submission deadline: **{model.submission_deadline}**{days}")
    add(f"- Generated: {model.generated_at} · Python {model.python_version}")
    add(f"- Register digest: `{model.register_digest[:16]}`")
    add("")
    add(f"> ⚠ **{model.mandatory_caveat}**")
    add("")
    add(f"> **{model.source_governs}**")
    add("")

    counts = ", ".join(f"{n} {s.lower()}" for s, n in model.severity_counts)
    add(f"**{len(model.gaps)} open items:** {counts}.")
    add("")

    if model.critical_path:
        add("## Critical path — raise these first")
        add("")
        add(
            "These gate other work: nothing downstream can start until they are answered."
        )
        add("")
        for gap in model.critical_path:
            add(f"- **{gap.gap_id}** — {gap.title}")
        add("")

    add("## Gap register")
    add("")
    for gap in model.gaps_by_severity:
        flag = "" if gap.verified else " · ⚠ UNVERIFIED"
        add(f"### {gap.gap_id} · {gap.title}")
        add("")
        add(
            f"**Severity:** {gap.severity} · **Clause:** {gap.clause} · "
            f"**Tier:** {gap.tier}{flag}"
        )
        add("")
        add(f"**What the tender requires.** {gap.requirement}")
        add("")
        add(f"**What the pack contains.** {gap.supplied}")
        add("")
        add(f"**Why that does not close it.** {gap.why_insufficient}")
        if gap.consequence:
            add("")
            add(f"**Stated tender consequence.** {gap.consequence}")
        add("")
        add(f"**Question to {model.oem_label}.** {gap.question}")
        add("")
        add(f"**Closes when.** {gap.closure_test}")
        add("")

    if model.evidence:
        add("## Evidence inventory — declared against received")
        add("")
        add(_md_row(["Item", "Supplier declares", "Audit found", "Adequate?", "Note"]))
        add(_md_row(["---"] * 5))
        for line in model.evidence:
            add(
                _md_row(
                    [
                        line.item,
                        line.declared,
                        line.received,
                        line.status_label,
                        line.note or "—",
                    ]
                )
            )
        add("")

    for heading, body in model.sections.items():
        add(f"## {heading}")
        add("")
        add(body)
        add("")

    if model.unverified:
        add("## Unverified findings")
        add("")
        add(
            "Surfaced rather than dropped. Each could not be confirmed from the supplied "
            "material and should be treated as a question, not a finding of fact."
        )
        add("")
        for gap in model.unverified:
            add(f"- **{gap.gap_id}** — {gap.title}")
        add("")

    add("## Source provenance")
    add("")
    add(_md_row(["Document", "Role", "Dated", "SHA-256", "Extraction", "Note"]))
    add(_md_row(["---"] * 6))
    for src in model.sources:
        add(
            _md_row(
                [
                    src.label,
                    src.role,
                    src.document_date or "not stated",
                    f"`{src.short_hash}`",
                    src.extraction,
                    src.note or "—",
                ]
            )
        )
    add("")
    add(f"_{model.verification_discipline}_")
    add("")
    return "\n".join(out)


# ═════════════════════════════════════════════════════════════════════════════
# DBPL adapter (GWTF DBPL-01)
# ═════════════════════════════════════════════════════════════════════════════


def as_dbpl_document(
    model: TenderGapDossier,
    *,
    provenance_lines: Sequence[str] = (),
) -> dict[str, Any]:
    """Project the dossier into the DutchBay Presentation Layer document model.

    The house style is field/value tables under a numbered heading with a caveat band, which is
    exactly the shape of a gap: a controlling clause, what was supplied, why that does not close
    it, and the question that would. Each gap therefore becomes one DBPL section rather than being
    flattened into prose.

    The un-suppressible furniture is filled from the dossier's own caveats, so the running banner
    carries the derived-register warning on every page — the property that matters most for a
    document that will be forwarded to a counterparty.

    Args:
        model: the assembled dossier.
        provenance_lines: print-core provenance from a first pass, stamped into the second.

    Returns:
        A mapping consumable by ``dbpl_base.html.j2``. Note the section list uses ``points``,
        never ``items`` — on a dict Jinja resolves ``.items`` to the built-in method.
    """
    counts = ", ".join(f"{n} {s.lower()}" for s, n in model.severity_counts)
    sections: list[dict[str, Any]] = [
        {
            "heading": "Document control",
            "table": {
                "columns": ["Control field", "Controlled value"],
                "rows": [
                    ["Tender", model.tender_ref],
                    ["Tender title", model.tender_title],
                    ["Addressed to", model.oem_label],
                    ["Raised by", model.bidder_label],
                    ["Submission deadline", model.submission_deadline or "not stated"],
                    [
                        "Working days remaining",
                        (
                            str(model.working_days_remaining)
                            if model.working_days_remaining is not None
                            else "not stated"
                        ),
                    ],
                    ["Open items", f"{len(model.gaps)} ({counts})"],
                    ["Register digest", model.register_digest[:16]],
                    ["Generated", model.generated_at],
                    ["Status", "Derived gap register - not a compliance determination"],
                ],
            },
        }
    ]

    if model.critical_path:
        sections.append(
            {
                "heading": "Critical path - raise these first",
                "intro": (
                    "These gate other work: nothing downstream can start until they are answered."
                ),
                "points": [f"{g.gap_id} - {g.title}" for g in model.critical_path],
            }
        )

    for gap in model.gaps_by_severity:
        rows: list[list[str]] = [
            ["Severity", gap.severity],
            ["Controlling clause", gap.clause],
            ["Delivery tier", gap.tier],
            ["What the tender requires", gap.requirement],
            ["What the pack contains", gap.supplied],
            ["Why that does not close it", gap.why_insufficient],
        ]
        if gap.consequence:
            rows.append(["Stated tender consequence", gap.consequence])
        if not gap.verified:
            rows.append(
                ["Verification", "UNVERIFIED - treat as a question, not a finding"]
            )
        rows.append([f"Question to {model.oem_label}", gap.question])
        rows.append(["Closes when", gap.closure_test])
        sections.append(
            {
                "heading": f"{gap.gap_id} - {gap.title}",
                "table": {"columns": ["Field", "Content"], "rows": rows},
            }
        )

    if model.evidence:
        sections.append(
            {
                "heading": "Evidence inventory - declared against received",
                "intro": (
                    "The two columns are deliberately separate. Where they diverge, the divergence "
                    "is the finding: a row marked received against a document that does not answer "
                    "the requirement is a gap, not closure."
                ),
                "table": {
                    "columns": [
                        "Item",
                        "Supplier declares",
                        "Audit found",
                        "Adequate?",
                        "Note",
                    ],
                    "rows": [
                        [e.item, e.declared, e.received, e.status_label, e.note or "-"]
                        for e in model.evidence
                    ],
                },
            }
        )

    for heading, body in model.sections.items():
        sections.append({"heading": heading, "body": body})

    if model.sources:
        sections.append(
            {
                "heading": "Source provenance",
                "intro": (
                    "Every document read to build this register, with the route by which its text "
                    "was recovered. A clause quoted from an OCR-recovered scan is not the same "
                    "evidence as one quoted from a digital original."
                ),
                "table": {
                    "columns": [
                        "Document",
                        "Role",
                        "Dated",
                        "SHA-256",
                        "Extraction",
                        "Note",
                    ],
                    "rows": [
                        [
                            s.label,
                            s.role,
                            s.document_date or "not stated",
                            s.short_hash,
                            s.extraction,
                            s.note or "-",
                        ]
                        for s in model.sources
                    ],
                },
            }
        )

    sections.append(
        {
            "heading": "Verification discipline",
            "body": model.verification_discipline,
        }
    )

    return {
        "title": f"Tender evidence gap dossier - {model.tender_ref}",
        "banner": f"DERIVED GAP REGISTER | NOT A COMPLIANCE DETERMINATION | {model.tender_ref}",
        "document_id": f"DBAY-TGD-{model.register_digest[:8].upper()}",
        "version": "v1.0",
        "issue_date": model.generated_at.split(" ")[0],
        "headline_caveat": model.mandatory_caveat,
        "disclaimer": model.source_governs,
        "section_caveat": (
            "CONTROL NOTICE - DERIVED GAP REGISTER / NOT A COMPLIANCE DETERMINATION / "
            "SOURCE DOCUMENTS GOVERN"
        ),
        "first_section_number": 0,
        "sections": sections,
        "provenance_lines": tuple(provenance_lines),
    }
