- Derive the NSO 250 MW LTL scenario capex from a sourced equipment price instead of an
  assumed all-in figure. The generator previously hard-coded USD 78/95/125 per kWh and
  inverted the stack to produce the "equipment USD 63.50/kWh CIF" its own file headers
  quoted as provenance, and claimed the base supported "roughly a 15% equity return" when
  the same derivation puts USD 95/kWh at about 9.7%. Equipment is now the input, taken from
  the OEM offers held in the private corpus and restated onto the contracted-capacity
  denominator the scenarios use. Adds a fourth `bidimplied` variant carrying the capex the
  winning bids can support, so the bid-implied ceiling sits alongside the quoted prices.
- Stop deducting SSCL from NSO 250 MW scenario revenue. ESA Volume III Article 5(o) adds
  "any applicable Value Added Tax or similar Sales Taxes" to payments, and the Section 4
  bid form quotes the Capacity Charge Rate excluding VAT with SSCL as a separate line on
  top, so the levy is recovered from the offtaker rather than borne by the project.
- State the NSO 250 MW import-levy position explicitly with a `taxes_indirect` block. The
  block was absent, which `finance.import_levies` treats as every line zero — silently the
  most favourable tax corner available. Bonded Warehousing relief is now asserted on three
  variants and withheld on `stress`, matching RFP Clarifications cl. 8/13/47/48, under
  which the relief is real but conditional and the bidder's own responsibility to obtain.
