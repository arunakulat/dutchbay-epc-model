- **A withdrawal, itself withdrawn: Addendum 01 exists, is held, and governs the delivery
  timeline.** On 2026-09-06 the NSO 250 MW scenario headers withdrew their own citation of a
  two-month SCOD extension in "Addendum 01", on the stated ground that no such addendum was held
  in the corpus. That was wrong, and it was wrong in the most avoidable way: Addendum 01 of
  07-Aug-2026 and the RFP Clarifications of 21-Aug-2026 are both held in **this repository**, at
  `docs/source_materials/nso_bess_250mw_2026/rfp/`, as PDFs with extracted transcripts. The
  search that concluded otherwise covered only the private corpus. Two independent RECRUIT-01
  reviewers repeated the same search and reached the same wrong conclusion, so the error survived
  a double veto and merged.

  Addendum 01 item 01 revises RFP Volume I clause 1.4 **in full**. The governing schedule is
  Letter of Award 06-Nov-2026, acceptance 13-Nov-2026, ESA signing 14-Dec-2026, Financial Closure
  15-Mar-2027 (three months from signing) and COD 16-Aug-2027 (eight months from signing).
  Financial close to COD is **five months**, not the four the headers asserted from a schedule
  that never governed. The decisive check is the closing date: Volume I says 14-Aug-2026,
  Addendum 01 says 04-Sep-2026, and the bids were opened on **04-Sep-2026**. Clarification 47
  confirms the extension independently: "the Scheduled Commercial Operation Date (SCOD) has been
  extended by two (2) months".

  **No KPI moves.** `Financing_Terms.construction_years` stays 1 — 154 days is 0.42 years and
  rounds to the same integer as the 0.33 the superseded schedule implied — and `cod_year` stays
  2027, because 16-Aug-2027 is still 2027. The oracle at
  `tests/integration/test_nso250_ltl_scenarios.py` passes unchanged, which is what says the
  correction is documentary rather than economic. The headers now carry the governing dates and
  record the superseded ones as superseded.

  Two further claims are corrected. The clarifications were labelled UNVERIFIABLE; they are held
  and every clause cited is now verified verbatim — item 13 leaves import SSCL to "the prevailing
  laws and regulations in effect at the time of importation", item 47 places responsibility for
  the bonded facility on the bidder, and item 48 restricts the facility to "imported equipment
  that forms part of the BESS facility" with transmission-line materials and external
  interconnection works "not eligible". The clause 48 carve-out, still deliberately unmodelled,
  is now quoted from the transcript rather than cited at second hand.

  The finding that prompted this was raised as a defect in the *other* direction: a register in
  the private corpus asserts these documents are "held in the public corpus", and that assertion
  was queued for correction as false provenance. Checking it showed the register was right and
  the scenarios were wrong.
