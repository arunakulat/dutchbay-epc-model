"""Per-technology grid-capability plug-ins (D4b, #876).

Each module here is a STANDALONE, technology-keyed capability plug-in that answers the
design-stage grid-interface question for ONE generation/storage class — the reactive
(PQ-envelope) capability and the fault-ride-through behaviour of that technology's
converter interface. The plug-ins are keyed on the :mod:`finance.tech_types` /
:mod:`finance.grid.grid_types` classification and are wired into a dispatch surface by a
LATER dolphin; today they are called directly (no shared registry needed yet).

They REUSE, rather than re-model, the shared grid cores:
  * the D4a ANDES ride-through core (:mod:`analytics.grid.ride_through`) drives the LVRT
    behaviour (parameterised from the D0 grid-code envelope), and
  * the D3 :class:`analytics.contracts_v14.ReactiveCapabilityResult` carries the reactive
    verdict.

Everything here is design-stage ADVISORY (``bankable=False``) and PURE-ADVISORY: nothing
in this package feeds the finance engine, so committed scenarios stay byte-identical
(KPI-neutral). The heavy grid libraries (``andes`` / ``pandapower``) remain OPTIONAL
``[grid]``-extra dependencies guarded at call-time (CASPER); the PQ-envelope and config
math in these plug-ins is pure Python and imports no grid library.

Public surface:
    - :func:`analytics.grid.capabilities.wind.screen_wind_capability` — the WIND turbine
      reactive-capability (PQ envelope) + LVRT ride-through plug-in.
"""

from __future__ import annotations

__all__ = ["wind"]
