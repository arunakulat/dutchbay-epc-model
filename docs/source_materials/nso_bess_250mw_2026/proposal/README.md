# Draft Envision technical proposal — build chain

Draft technical proposal against NSO tender `TR/REP&PM/ICB/2026/001/C`, assembled **only** from
the corpus in `../`. Committed on the project owner's explicit instruction so the deliverable is
reproducible rather than surviving only in a working container.

## What the red text means

Every statement in the document is one of two kinds, and the document says which on every line:

| Colour | Meaning |
|---|---|
| **Black** | Sourced. Traceable to a document held in `../` |
| **Red** | **Drafted gap-fill.** Not found in any received Envision document. Written the way the tender requires it to read, so Envision can confirm, correct or replace it |

The red text is a drafting aid, **not a representation about the offered product**. Nothing in red
has been verified against Envision, and the document is not an Envision issue. A tool that silently
dropped the red distinction would present drafted text as sourced — which is the single failure
mode this chain exists to prevent, and which it has already produced once (see *A bug worth
remembering*).

## Building it

Both formats are rendered from **one** document model, so they cannot drift.

```bash
# from the repository root
PYTHONPATH=. python docs/source_materials/nso_bess_250mw_2026/proposal/build_envision_proposal_2026-08-27.py \
    proposal.pdf proposal.json

# Word issue, from the same model
cd docs/source_materials/nso_bess_250mw_2026/proposal
npm install            # docx ^9.7.1
node make_docx.js ../../../../../proposal.json proposal.docx
```

The second argument to the Python script is optional; omit it and only the PDF is produced. The
JSON is the Word renderer's input and is **not** committed — it is derived, and committing it would
create a second source that can go stale.

The JSON is exported **without** the render-provenance lines that appear in the PDF. Those describe
how the PDF was rasterised (PDF variant, font substitution, embedded fonts) and would read in a
Word file as claims about a document they do not describe.

## Reproduction check

Verified 29 August 2026 against the delivered `drafts/Envision_Technical_Proposal_DRAFT_v0.3_2026-08-27.docx`:

| | Delivered v0.3 | Rebuilt from this chain |
|---|---|---|
| Text runs | 474 | 474 |
| Red (gap-fill) runs | 82 | 82 |
| Differing runs | — | **0 — exact text match** |

## Draft history

| Draft | Note |
|---|---|
| `v0.1` | First issue. PDF and Word |
| `v0.2` | Word only |
| `v0.3` | **Current.** Red reduced where the corpus turned out to support a black, sourced statement — principally the SCADA section (EnOS BESS SCADA Univers V2.4.4 replacing "to be confirmed by Envision") and the grid-forming section, which gained specification citations for the dual-mode declaration and the SCR position |

The generator is at the **v0.3** state. v0.1 and v0.2 are retained as delivered and are not
rebuildable from this script.

## A bug worth remembering

In `make_docx.js`, the gap-fill run was originally constructed as:

```js
out.push(new TextRun({ color: RED, ...opts, text: ... }));   // WRONG
```

Spreading `opts` **after** `color` let a caller-supplied base colour silently overwrite the red. The
result was **1 red run instead of 83** — a document that looked entirely plausible and presented
every drafted gap-fill as sourced Envision content. It was caught only by inspecting
`word/document.xml` directly. The fix is to spread `opts` first:

```js
// opts FIRST: a caller-supplied base colour must not override the gap-fill red.
out.push(new TextRun({ ...opts, text: ..., color: RED }));
```

Any future edit to run construction should re-count the red runs in the output, not trust that it
looks right.

## Handling

This is the **bidder's own draft proposal text**, a different disclosure category from the OEM
documentation elsewhere in this corpus, and this repository is public. It is committed here on the
project owner's explicit instruction, given after that distinction was put to them.
