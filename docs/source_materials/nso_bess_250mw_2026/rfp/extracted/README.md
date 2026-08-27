# Searchable extracts of the controlling NSO procurement documents

These files are derived, searchable extracts. They do not replace the received PDFs and are not
themselves controlling. Where an extract and its source PDF differ, **the PDF governs**.

| Extract | Source | Method | Quality decision |
|---|---|---|---|
| `NSO_250MW_BESS_Addendum_01_2026-08-07.markitdown.md` | `../NSO_250MW_BESS_Addendum_01_2026-08-07.pdf` | MarkItDown 0.1.7 (governed, GWTF R26) | Complete embedded text layer (Word 2016). All 10 pages extracted; the four attachments referenced by items 19–22 are separate files and are **not** part of this PDF |
| `NSO_250MW_BESS_Annex_A_Functional_Performance_Requirement.markitdown.md` | `../NSO_250MW_BESS_Annex_A_Functional_Performance_Requirement.pdf` | MarkItDown 0.1.7 (governed, GWTF R26) | Complete embedded text layer (Word for M365). All 27 pages extracted; embedded figures on 6 pages are not reproduced in the text extract |
| `NSO_250MW_BESS_RFP_Clarifications_2026-08-21.verified-transcript.md` | `../NSO_250MW_BESS_RFP_Clarifications_2026-08-21.pdf` | **Page-image reading of all 15 content pages** | The source is an **image-only scan with no text layer**. MarkItDown returned an empty document and tesseract scrambled the two-column Q&A table, so every content page was rendered at 300 dpi and read directly. This is the **only searchable record** of the register |
| `NSO_250MW_BESS_RFP_Clarifications_2026-08-21.tesseract-raw.txt` | as above | tesseract 5.3.4, `--psm 6`, 300 dpi | **Retained for provenance only — do not cite.** Column-interleaved and unreliable (e.g. "Please refer to item 23 of Addendum 01" OCR'd as "PISase fblet to em 25 er adden Ol"). Superseded by the verified transcript above |

Interpretation, findings and the revised punch list are in
`../../reviews/NSO250MW_Addendum01_AnnexA_Clarifications_Ingress_Evaluation_2026-08-27.md`.
