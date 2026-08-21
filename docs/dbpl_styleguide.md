# DutchBay Presentation Layer (DBPL) — style guide and print contract

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
