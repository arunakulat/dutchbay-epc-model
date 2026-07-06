"""Per-technology grid-capability plug-ins (D4-series, #878).

Each module in this package is a STANDALONE capability plug-in keyed on the technology
class from :mod:`finance.tech_types` (``is_generation_type`` / ``is_storage_type``). A
plug-in answers, for ONE technology, the design-stage grid-capability questions the D1 SCR
screen (:mod:`analytics.grid.short_circuit`) and the D3 reactive/voltage screen
(:mod:`analytics.grid.reactive_screen`) frame at the plant level — reusing the D4a
ride-through core (:mod:`analytics.grid.ride_through`) and the D3
:class:`analytics.contracts_v14.ReactiveCapabilityResult` rather than modelling new
dynamics or inventing new result types (CCCDIR).

There is deliberately NO shared registry / dispatch here yet: the plug-ins are independent
modules with pure, importable entry points. A LATER dolphin wires the per-tech dispatch
(reading ``generation.technologies.<name>.grid`` and routing to the matching plug-in) into
the :func:`analytics.grid.evaluate_grid.evaluate_grid` gateway.

Like the rest of :mod:`analytics.grid`, every plug-in is default-OFF and additive: nothing
here is imported by the finance engine, so committed scenarios stay byte-identical
(KPI-neutral). The heavy grid libraries (``pandapower`` / ``andes``) remain OPTIONAL
``[grid]``-extra dependencies, guarded at call-time (CASPER) and NEVER imported at
module-import time — the default (grid-free) install imports this package cleanly.

Public surface:
    - :mod:`analytics.grid.capabilities.bess` — the BESS (storage) capability plug-in:
      a MANUAL per-site PCS short-circuit contribution fed into the SCR screen, plus an
      SoH-degraded reactive/PQ capability screen (year-15 reactive headroom shrinks as the
      state-of-health degrades). Returns the advisory
      :class:`analytics.contracts_v14.GridStrengthResult` +
      :class:`analytics.contracts_v14.ReactiveCapabilityResult`.
"""

from __future__ import annotations

__all__ = ["bess"]
