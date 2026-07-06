"""Per-technology grid-capability plug-ins (issues #876, #877).

Each module in this package answers the CONVERTER-INTERFACE capability question for ONE
technology class: given the plant's ratings and grid-code envelope, what fault-current
and reactive (PQ) capability does *this* converter topology actually present at the point
of connection? The plug-ins are keyed on the :mod:`finance.tech_types` classification
(``is_generation_type`` / ``is_storage_type`` / ``is_modelled_generation_type``) and are
STANDALONE — no shared registry (a later dolphin wires dispatch). They REUSE the D4a
ride-through core (:mod:`analytics.grid.ride_through`) and the D3
:class:`analytics.contracts_v14.ReactiveCapabilityResult` rather than modelling new
dynamics; nothing here re-implements a dynamic model.

Design invariants (shared by every capability plug-in)
------------------------------------------------------
* SCREENING / DESIGN-STAGE ONLY — every emitted result is ADVISORY (``bankable=False``)
  and NEVER feeds the finance engine, so committed scenarios stay byte-identical
  (KPI-neutral). The utility-accepted study is a PSS/E / PowerFactory / EMT run against
  the CEB/NSCC confidential base case with the OEM binaries.
* CASPER — the heavy grid libraries (``pandapower`` / ``andes``) are OPTIONAL deps of the
  ``[grid]`` extra, guarded at call-time via ``_require_*()`` and NEVER imported at
  module-import time. The pure capability MATH here (PQ envelope, DC:AC clipping, fault-
  current characterisation) is grid-library-free and runs in the default install.
* NO SPURIOUS PASS — where a quantity cannot be established from physical inputs, the
  plug-in returns an explicit ``None`` / NOT-RUN with a reason, never a defaulted pass.

Public plug-ins:
    - :mod:`analytics.grid.capabilities.wind` — wind turbine reactive-capability (PQ
      envelope; Type-3 DFIG partial-load narrowing vs Type-4 full-converter rectangular
      box) + LVRT ride-through via the D4a core.
    - :mod:`analytics.grid.capabilities.solar` — solar PV as a CURRENT-LIMITED grid-
      following source (~1.1 pu max fault current, negligible fault infeed; MUST NOT be
      modelled as a synchronous machine / voltage source, which would OVERSTATE grid
      strength). Derives DC:AC clipping WITHOUT double-counting the pvlib inverter loss
      (that already lives in :mod:`solar_resource.pv_producer`).
"""

from __future__ import annotations

__all__ = ["solar", "wind"]
