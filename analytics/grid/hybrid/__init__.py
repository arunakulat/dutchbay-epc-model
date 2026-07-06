"""Static hybrid-POC aggregation (issue #880).

A hybrid plant puts MULTIPLE converter-interfaced resources (wind + solar + BESS) behind
ONE point of connection. Two grid-interface metrics only exist for the *combined* fleet
(they are NOT a single-tech box), and this package screens them STATICALLY:

  * a COMPOSITE / weighted SCR (WSCR) — every IBR MW added behind the POC shares the same
    upstream fault level, so stacking solar/BESS behind a wind POC LOWERS the effective
    SCR each inverter sees (fault level ÷ TOTAL IBR MVA); and
  * an AGGREGATE ±Q(P) capability envelope — the VECTOR SUM of each resource's reactive
    headroom (from its D4b/c/d per-tech plug-in) MINUS the reactive absorbed by the
    collector network + POC transformer between the resources and the POC.

Design invariants (shared with the rest of :mod:`analytics.grid`)
-----------------------------------------------------------------
* SCREENING / DESIGN-STAGE ONLY — pure STATIC aggregation (no ANDES / EMT). Every emitted
  result is ADVISORY (``bankable=False``) and NEVER feeds the finance engine, so committed
  scenarios stay byte-identical (KPI-neutral).
* CASPER — the aggregation MATH is pure Python and imports NO grid library. It REUSES the
  D4b/c/d per-tech plug-ins for each resource's contribution; those plug-ins guard the
  heavy grid libraries (``pandapower`` / ``andes``) at call-time. In the default
  (grid-free) install the SCR fold uses the closed-form path and this aggregation imports
  and runs cleanly.
* NO SPURIOUS PASS — where a quantity cannot be established from physical inputs, the
  aggregation raises (CESSPIT) rather than defaulting a value into a spurious PASS.

Public surface:
    - :func:`analytics.grid.hybrid.poc_aggregation.aggregate_poc_capability` — walk the
      resolved multi-tech resources, sum each tech's electrical model onto one POC bus, and
      emit the advisory :class:`analytics.contracts_v14.PocCapabilityEnvelope`.
    - :func:`analytics.grid.hybrid.frequency_response.run_hybrid_frequency_response` (D5c,
      #881) — the COMBINED frequency-droop study: split a frequency event's P(f) response
      across the ENPPC dispatch groups (per-group ``freq_droop_pct``, dispatched in
      ``p_priority_order``), each group's droop command capped at its physical headroom
      (wind spinning/de-load; a BESS group via the ONE shared D5a SOC / frequency reserve —
      no double-count), screen the settling frequency against the grid-code band, and emit
      the advisory :class:`analytics.contracts_v14.FreqResponseResult`. The per-group split
      + band compliance are pure Python (grid-free); the ANDES dynamic solve is reached only
      through the shared D4a machinery at call-time, and the un-modelled dynamic nadir is
      returned NOT-RUN — never fabricated (NO SPURIOUS PASS).
"""

from __future__ import annotations

__all__ = ["poc_aggregation", "frequency_response"]
