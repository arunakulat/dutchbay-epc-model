- **A withdrawal, itself withdrawn: Addendum 01 exists, is held, and governs the delivery
  timeline.** On 2026-09-06 the NSO 250 MW scenario headers withdrew their own citation of a
  two-month SCOD extension in "Addendum 01", on the stated ground that no such addendum was held
  in the corpus. That was wrong, and the way it was wrong is the useful part. Addendum 01 of
  07-Aug-2026 and the RFP Clarifications of 21-Aug-2026 are both held in **this repository**, at
  `docs/source_materials/nso_bess_250mw_2026/rfp/` — ingressed by #1180 on **27 August 2026**, ten
  days before the withdrawal, and present in the very base tree the withdrawal was reviewed
  against.

  **Two things this is not.** It is not "we searched the wrong repository". The private corpus
  *also* carried the governing schedule, tabulated in full in an evaluation dated **three days
  before** the withdrawal, and the public repository had carried a complete Addendum ingress
  review since 27 August. Both corpora already discussed the document. The failure was never
  grepping for "Addendum 01" by name in either of them before declaring it unheld.

  And it is not "the error survived a double veto", which flatters the review. That veto was of a
  *different* defect — an enhanced capital allowance. The Addendum withdrawal was **introduced by
  the remediation of that veto** and then **affirmatively certified**: the assurance record graded
  it "correct, and the replacement is honest… Good practice". Being certified is a worse failure
  than being missed, and both reviewers said so on re-review.

  Addendum 01 item 01 revises RFP Volume I clause 1.4 **in full**. The governing schedule is
  Letter of Award 06-Nov-2026, acceptance 13-Nov-2026, ESA signing 14-Dec-2026, Financial Closure
  15-Mar-2027 (three months from signing) and COD 16-Aug-2027 (eight months from signing).
  Financial close to COD is **five months**, not the four the headers asserted from a schedule
  that never governed. The decisive check is the closing date: Volume I says 14-Aug-2026,
  Addendum 01 says 04-Sep-2026, and the bids were opened on **04-Sep-2026**.

  Clarification 47 states that "the Scheduled Commercial Operation Date (SCOD) has been extended
  by two (2) months" — a second document, but **not** a second source, since it derives its
  authority from the Addendum it points to. Nor is its "two months" the same measure as the
  102-day absolute move from 06-May to 16-Aug-2027: two months is the ESA-relative milestone
  (6 months from signing becomes 8), and the other 38 days are the whole ESA chain shifting when
  the closing date moved from 14-Aug to 04-Sep-2026. They reconcile; they are not one number.

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
