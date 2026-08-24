# DutchBay August 2026 controlled audit successor — Errata control

**Document ID:** `DB-AUD-ERR-2026-08-24-v1.0`
**Applies to:** `docs/audit/2026-08-controlled-successor/`
**Evidence cutoff:** `2026-08-24T00:00:00+05:30`
**Status:** **CONTROLLED ADDENDUM — RELEASE HOLD**
**Tracking issue:** [#1141](https://github.com/arunakulat/dutchbay-epc-model/issues/1141)
**Original-record treatment:** immutable; the affected dated records remain unchanged

## ERR-01 — Fixed GWTF rule-count instructions

The instruction at line 215 of
`06_CURRENT_PROGRAMMING_REVIEW_AND_TODO_v3_2026-08-19.md` says to re-ingress
all 66 GWTF rules. That count was understated at the record's own cutoff and
is withdrawn as a current instruction. The historical line remains unchanged
because the file is a dated control record with fixed commit and evidence
anchors.

At this errata cutoff, the canonical
`go_with_the_flow_rules_v3_0_clean.csv` contains 72 active v3.0 rules. This is
dated evidence, not a standing instruction. It was verified with:

```bash
export DUTCHBAY_VENV="/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv"
DUTCHBAY_FLOW_RULESET_CSV="$PWD/go_with_the_flow_rules_v3_0_clean.csv" \
  PYTHONPATH="$PWD" "$DUTCHBAY_VENV/bin/python" \
  dutchbay_bootstrap_rules.py
```

Result: `72 rules; versions: v3.0; active=72`.

For all work after the historical cutoff, the controlling instruction is:

> Re-ingress every active rule from `go_with_the_flow_rules_v3_0_clean.csv`;
> derive the current count from `dutchbay_bootstrap_rules.py` rather than
> copying a fixed count into an instruction.

The same correction applies to architecture pointer `RS-F3` in
`registers/architecture_pointer_dispositions.json` and
`registers/architecture_pointer_dispositions.csv`. Its area text, “63 of 66
GWTF rules have unpinned enforcement text,” is a preserved pointer from
`01_architecture_map.md:537`, not a current ruleset population or a completed
adjudication. The pointer remains `not_examined`; this erratum does not decide
how many current rules have sufficiently pinned enforcement text.

## Effect and limitations

This additive control corrects an instruction and the interpretation of a
preserved architecture pointer. It does not amend the canonical ruleset,
change any finding or pointer disposition, alter a project KPI, close a
remediation item other than #1141, or lift the audit successor's release HOLD.
