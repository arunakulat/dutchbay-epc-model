# DutchBay Presentation Layer (DBPL) — style guide and print contract

> **v2.** The stylesheet is [`app/reports/dbpl/templates/dbpl.css`](../app/reports/dbpl/templates/dbpl.css);
> its design tokens are generated from [`app/reports/dbpl/style.py`](../app/reports/dbpl/style.py)
> and prepended at render time. **The `.css` must never contain a literal colour, size or margin** —
> a surface that hard-codes its own values has forked the house style, and a test enforces zero
> literals in the house rules.

**DBPL / dbpl** names a **print contract**, not a look. When work is described as a *DutchBay
Presentation Layer PDF*, three things are required, and they are enforced in code rather than left
to discipline:

1. The **complete `[report]` optional extra** — `weasyprint`, `reportlab`, `geopandas`,
   `contextily` — plus the DBPL font stack.
2. The **house style** in [`app/reports/dbpl/style.py`](../app/reports/dbpl/style.py).
3. **Surfaced font provenance** — any substitution recorded, never hidden.

Governed by **GWTF `DBPL-01`** (`go_with_the_flow_rules_v3_0_clean.csv`, Documentation Delivery).

## How to render

```python
from jinja2 import Environment, FileSystemLoader
from app.reports.dbpl import render_dbpl_pdf

env = Environment(
    loader=FileSystemLoader("app/reports/dbpl/templates"),
    autoescape=True, trim_blocks=True, lstrip_blocks=True,
)
html = env.get_template("dbpl_base.html.j2").render(doc=doc)
result = render_dbpl_pdf(html)

result.pdf                  # bytes
result.substituted_fonts    # () when the house fonts resolved natively
result.provenance_lines()   # extra versions, style source, per-font resolution
```

`render_dbpl_pdf` **raises `DbplDependencyError`** if any `[report]` package is missing, violates
its declared pin, or is installed but not importable. That is deliberate: elsewhere in the
reporting layer a missing WeasyPrint degrades gracefully because the HTML report is still useful,
but here **the PDF is the deliverable** — degrading would emit a document that claims to be a DBPL
PDF while missing the machinery that makes it one. If you want a best-effort render, use
`app.reports.renderer` and do not call the result DBPL.

## Reference document

Every token was **measured, not invented**, from:

```
DUTCHBAY_ANALYST_GENERATED_SYNTHETIC_LENDER_TERM_SHEET_2026-08-18.pdf
DBAY-SLTS-2026-08-18 · v0.1 · A4 · 29 pp · tagged
```

Colours sampled from a 110 dpi raster of pages 1 and 4; rule weights measured by scanning for
horizontal pixel runs and converting at that density (1 px = 0.6545 pt).

## Palette

| Token | Value | Role |
|---|---|---|
| `ink` | `#123B5D` | Titles, section headings, caveat text |
| `rule_title` | `#1D698D` | Heavy rule under the document title (2.6 pt) |
| `band` | `#1D5877` | Table header band |
| `rule_section` | `#8CB6CA` | Thin rule under a section heading |
| `warn_text` | `#AB5044` | Running header banner text |
| `warn_rule` | `#9E3426` | Rule under the banner |
| `warn_bar` | `#C1533D` | Caveat band left bar (4 pt) |
| `warn_bg` | `#FFF1ED` | Caveat band ground |
| `accent_id` | `#5B245F` | **Controlled values** — document IDs, paths, SHA-256 digests |
| `body` | `#000000` | Body text |
| `meta` | `#767F88` | Footer and metadata |
| `rule_body` | `#808080` | Block separator |
| `rule_footer` | `#31546B` | Rule above the running footer |

The `accent_id` colour is load-bearing: a reader must be able to tell at a glance which values are
**identifiers** rather than prose.

> **Token naming.** Rule *colours* emit as `--dbpl-rulecolour-*`; rule *weights* emit as
> `--dbpl-rule-*`. They are namespaced apart because they collided — four variables were defined
> twice and the later weight silently won, so every rule colour was being lost and the stylesheet
> was quietly falling back to hard-coded literals. `as_css_variables()` is the only place tokens
> become CSS; never hand-copy a value into the stylesheet.

## Type scale (pt)

| title | section | subsection | body | table | caveat | banner | footer |
|---|---|---|---|---|---|---|---|
| 26.0 | 15.5 | 12.0 | 10.0 | 9.5 | 9.5 | 7.5 | 7.5 |

Page: **A4**, 18 mm margins.

## Fonts

```
serif: 'Liberation Serif', 'Times New Roman', 'DejaVu Serif', Times, serif
sans:  'Liberation Sans', Arial, 'DejaVu Sans', Helvetica, sans-serif
mono:  'Liberation Mono', 'DejaVu Sans Mono', 'Courier New', monospace
```

Liberation is the reference document's own family and is **metric-compatible** with Times New
Roman and Arial, so a substitution changes glyph shapes but **not line breaks or pagination**.
Absence is therefore not fatal — but it is **surfaced**.

> ⚠ **WeasyPrint renders successfully with a substituted face.** A successful render proves the
> pipeline works, *not* that the requested font was used. `probe_fonts()` resolves each family
> through `fc-match` explicitly, because that is the only way to know.

The deployed image installs `fonts-liberation` and `fonts-dejavu-core` (see `Dockerfile`). On a
developer machine without Liberation installed, expect `Liberation Serif: SUBSTITUTED by Times New
Roman` — correct behaviour, and metrically identical output.

## Structural furniture — un-suppressible

Emitted by the base template, not offered as options:

| Element | Content |
|---|---|
| Running header banner | Classification, on **every** page |
| Running footer (left) | `document_id \| version \| issue_date` |
| Running footer (right) | `Page n of m` |
| Caveat band | Under **every** section heading |

**A DBPL document without its banner is not a styled document — it is an unlabelled one.** For
analyst-generated material that is the failure mode that matters, which is why the furniture is
structural rather than configurable.

## Document model

```python
doc = {
  "title": ..., "banner": ..., "document_id": ..., "version": ..., "issue_date": ...,
  "headline_caveat": ..., "disclaimer": ..., "section_caveat": ...,
  "first_section_number": 0,
  "sections": [
     {"heading": ..., "caveat": ..., "intro": ..., "body": ...,
      "table": {"columns": [...], "rows": [[...]]},
      "points": [...]},          # NOT "items" — see below
  ],
  "provenance_lines": (...),     # from result.provenance_lines()
}
```

> ⚠ **Use `points`, not `items`.** On a dict, Jinja resolves `section.items` to the built-in dict
> method rather than your key, so an ordered list silently becomes a `TypeError`. The same trap
> applies to `keys` and `values` — avoid those names in a section mapping.

Render twice when stamping provenance: once to obtain `result.provenance_lines()`, then again with
those lines in the model.

## Adding a new DBPL surface

1. Build a document model; render through `dbpl_base.html.j2` (or extend it — do not fork it).
2. Call `render_dbpl_pdf`. Do not call WeasyPrint directly.
3. Never hard-code a colour, size or margin. If a token is missing, **add it to `style.py`** — a
   surface that renders its own colours has forked the house style, and two documents that
   disagree about what a caveat looks like teach a reader to stop noticing caveats.
4. Stamp `provenance_lines()` into the document.


---

# v2 — the symbiotic decisions

Where the authorities disagree, the DBPL takes a position and records why. These are the contested
ones; the consensus is uncontroversial and simply implemented.

## Table rules — **Vignelli over Tufte**

Tufte would erase rules as non-data-ink. Vignelli treats them as load-bearing structure in a graded
hierarchy, and that is what the DBPL adopts:

| Weight | Role |
|---|---|
| **2 pt** | separates major parts — closes the header band |
| **1 pt** | separates items within a part — under the last row (Urban's rule too) |
| **0.5 pt** | finest division — group-header rows |

Verbatim: *"Type should always hang from the ruler, regardless of the size."* Implemented as
asymmetric cell padding (`4pt 8pt 6pt 8pt`) — tighter above than below.

Rationale: for a covenant table where a credit officer must find one row among forty, structure
beats minimalism.

## Row shading — **Urban over Tufte**

Zebra shading is ink that encodes nothing, and Tufte would strike it. **Adopted anyway.** The
reading task is row-tracking across a wide table, and a mis-tracked row in a covenant schedule
costs more than a slightly lower data-ink ratio. The tint is near-threshold by design.

Urban's rule set comes with it: a rule under the column headers and under the last row, and **no
interior vertical rules** — the one point where Urban, ADB and Lazard all agree.

## When in doubt — **the ADB Handbook**

Note blocks render in the ADB order, verbatim, at 9 pt, immediately below the table and never at
the foot of the page:

```
abbreviations → notes → footnotes → sources
```

Footnote indicators are **superscript lowercase letters, not bold**. Every table carries a source,
and it should be documentary rather than an organisation name.

**Key Symbols** are carried as tokens because this is a data-integrity control, not a typographic
nicety — a table that renders "not available" and "zero" identically has misstated the data:

| Symbol | Meaning |
|---|---|
| `...` | data not available |
| `–` | magnitude equals zero |
| `(-/+) 0` | less than half of unit employed |
| `*` | provisional / preliminary / estimate |
| `\|` | marks break in series |
| `n.a.` | not applicable |

## Wide tables — **Lazard landscape**

`.dbpl-landscape` on a section switches that section to an A4 landscape page. It is **a page size,
not a second design** — it inherits every rule above. Use it only where a table's width cannot be
carried by a portrait column.

```python
{"heading": "Sensitivity register", "landscape": True, "table": {...}}
```

## Document control — **mandatory**

Following Outer Dowsing / Arup. Supply `control` and/or `revisions` and the block renders:

```python
doc["control"]   = [("Document ID", "DBAY-..."), ("Version", "v1.0")]
doc["revisions"] = [{"rev": "1.0", "date": "21 Aug 2026",
                     "status": "Responding to client comments",
                     "prepared": "...", "checked": "...",
                     "reviewed": "...", "approved": "..."}]
doc["status"]    = "Final Report"      # rides the running footer
```

A **four-eyes** chain (Prepared / Checked / Reviewed / Approved), not three. And note the
convention: **draft versus final is the `Status / Reason for issue` field, never a watermark.**
No professional deliverable examined used one.

## Measure and rhythm

66-character target (Bringhurst's anchor — the safer end of a genuine 15-character disagreement
with Butterick), applied to **prose only**; tables and exhibits are exempt because a 66-character
cap would cripple them. Body leading 1.42, inside Butterick's 120–145 % band. Vertical intervals
are multiples of a 14.2 pt rhythm unit.

## Fonts

Bundled OFL superfamily, all **tabular by default** — verified against the font binaries, not
assumed from a feature tag:

| Role | Family | Use |
|---|---|---|
| serif | **Source Serif 4** | body prose (also carries an optical-size axis) |
| sans | **Source Sans 3** | tables, headings, furniture |
| mono | **Source Code Pro** | identifiers, paths, digests |

Resolution is **bundled → system → web (opt-in) → metric-compatible fallback**, and the tier that
answered is surfaced. Two traps worth knowing:

- A variable-font weight **range** (`font-weight: 100 900`) is **invalid in WeasyPrint** and is
  dropped with a warning. Discrete weights are registered against the same variable file instead.
- `fc-match` is **blind to an `@font-face`-embedded file**, so it will report a bundled family as
  "SUBSTITUTED". The provisioning tier is authoritative; fc-match is consulted only for families
  the provisioner did not supply.

## Conformance — PDF/UA-1

Output is produced at `pdf/ua-1` (ISO 14289-1) and reports `Tagged: yes`. This was the DBPL's own
former defect, shared with most of the sector — of fifteen multilateral-bank PDFs sampled, only
four were tagged.

Stated by the standard's own custodian: **conformance does not by itself ensure accessibility.**
Colour, contrast and cognitive load are out of scope, so WCAG 2.2 contrast (4.5:1 normal, 3:1
large) is applied separately. PDF/UA-1 may additionally conform to PDF/A-2 or PDF/A-3, but **not**
PDF/A-1, which predates features it requires.

One consequence worth stating: **row labels are repeated, not merged.** Schwabish's "label only the
first row" collides with WCAG PDF6, and accessibility wins over visual tidiness.

## Tables and page breaks — the keep-together wrapper

Tagged output has a sharp edge. WeasyPrint's PDF/UA tag builder raises
`ValueError: Table wrapper without a table` when a **captioned table's wrapper is split so a
caption-only fragment lands on a page with no rows** — which happens when a short table that does not
fit the remaining space is pushed whole to the next page, orphaning its caption on the previous one.
Because DBPL mandates both captions and `pdf/ua-1` tagging, this would otherwise make *any* document
with a page-straddling table fail to render.

The fix is structural: every table (document control, revision history and each section table) is
wrapped in a `.dbpl-keep` block, and `.dbpl-keep { break-inside: avoid; }` moves the table and its
caption to the next page as a unit. `break-inside: avoid` is **ignored on the anonymous
table-wrapper box** but **honoured on this real block box**, which is why the wrapper is necessary
rather than a rule on `table` itself. A table taller than one page cannot be kept whole; it then
splits normally, which the tag builder handles correctly — so keep a single table under a page, use a
Lazard landscape section, or split it into grouped tables. Regression-guarded in
`tests/app/test_dbpl.py` (`test_every_table_sits_in_a_keep_together_block`,
`test_page_straddling_table_renders_under_pdf_ua`).
