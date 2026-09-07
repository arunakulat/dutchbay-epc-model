# LTSA workbook re-supply, 3 September 2026 - deduplication receipt

## Source

| Field | Receipt |
|---|---|
| Received | 3 September 2026, via the project owner |
| Supplied filename | `LTSA Solution.xlsx` |
| Supplied size | 30,990 bytes |
| Supplied SHA-256 | `53a51d5c3c9cf91763f01b35086bb1bf2e97ba4357a0265d7b26223547be4123` |
| Canonical corpus object | `../oem/envision/commercial/23_LTSA_Solution.xlsx` |
| Canonical SHA-256 | `53a51d5c3c9cf91763f01b35086bb1bf2e97ba4357a0265d7b26223547be4123` |
| Result | **Byte-identical. No new payload. Nothing copied into the corpus.** |

The supplied file matches the canonical object exactly, in both size and content hash. The corpus
copy was added by `0e63f7a` / PR #1181 in the 27 August tranche merged 29 August, and was already
re-supplied once — in the `Archive.zip` of 1 September, where it likewise deduplicated against the
same hash. This is therefore the **second** re-supply of the same object.

## Why the identity matters, rather than being a formality

The workbook is the only document in the corpus that carries the LTSA **scope schedule** and the
`Performance guarantee` rows for Availability, RTE and Usable capacity. Finding **A7** of the
29 August session archive rests on its state: the `Full Scope year 0-15` column is the only column
carrying an availability guarantee to year 15, and it *"carries no price, no guarantee level, no
term, no response times, no LD indemnity and no signature"*; its BESS tab is labelled
`BESS-100225-Draft` and the workbook's other tab is a **wind turbine** service catalogue.

Byte-identity establishes that **the draft has not been revised.** The budgetary commercial offers
received the same day price two options named *Basic scope* and *Full scope* without carrying any
scope schedule of their own, so they must be read against this workbook — and this workbook is
still the draft A7 describes. That is why A7 moves only partway on the strength of the offers: the
price now exists, and the guarantee still does not appear in the priced instrument.

The consequence is recorded as finding **C-4** in
[`../reviews/Envision_Budgetary_Commercial_Offers_Ingress_Evaluation_2026-09-03.md`](../reviews/Envision_Budgetary_Commercial_Offers_Ingress_Evaluation_2026-09-03.md).

## Extract

The existing derived extract `../oem/envision/extracted/23_LTSA_Solution.markitdown.md`
(SHA-256 `58e247fc9c9ba8bf6388307cb9cf327b07bbb2ca29aabc858b9c81f52943f1b0`) remains current and was
not regenerated, the source being unchanged.

## Handling

Unchanged from the canonical object. This receipt records a re-supply and introduces no new
handling question.
