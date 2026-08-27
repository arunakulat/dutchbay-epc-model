Added the NSO 250 MW gap register and the tender evidence gap dossier it renders. This is the
first caller of `app/reports/tender_gap_dossier_emit.py`, which until now had none — the emitter
was vendor-neutral machinery with no register to instantiate it, so the corpus findings lived only
as prose.

The register carries 21 gaps (5 critical, 6 high, 7 medium, 2 low, 1 informational) against the
controlling documents, and renders through the DutchBay Presentation Layer to a 25-page PDF written
to be sent to Envision as-is: each gap states the controlling clause, what the bid pack contains,
why that does not close it, the question to put to the OEM, and the objective closure test.

It supersedes parts of the 31 July detailed gap statement and the 21 August checklist evaluation:
the instruction to delete the supplier's dual-mode grid-forming language is withdrawn (Annex A
A.05.17(i) requires it), the SCR sweep moves off the bid-stage critical path (A.05.23(d) makes it
the alternative to submitting both models), and the recorded 20 % monthly liquidated-damages cap is
corrected — clarification 54 establishes no aggregate cap over the term and puts availability
deductions outside the monthly cap, so the capacity charge can fall to LKR 0.

Closure pathways are researched and referenced, covering grid-forming stability at SCR 1.0, the
UL 9540A sixth-edition test route, the 45 degrees C thermal case that governs both the cycle-life
and round-trip-efficiency exposures, and the clarification-62 product-family equivalence route for
uncertified standards. One null result is stated rather than papered over: no published equivalence
mapping between IEEE 2800-2022 or UL 1741-SB and EN 50549-2 or G99 was found, so that argument must
be constructed clause by clause.

Two findings are marked UNVERIFIED and state their basis in their own text — the `.dyr` protection
envelope (B2) and the reactive capability at a declared 11 MW (B3). Both are checks to run against
the delivered artifacts, not established facts.

The bidding entity is named in the dossier on the project owner's direction of 27 August 2026,
consistent with the corpus index and the 30 July gap review, which already name it.
