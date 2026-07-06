"""In-house grid interconnection / hosting-capacity study (issue #872).

SCREENING / DESIGN-STAGE ONLY — NOT the utility-accepted bankable grid-connection
study. CEB/NSCC require PSS/E or PowerFactory run against their confidential grid
base case; the OEM ``.dyr/.dll/.pfd`` binaries feed *that* study, not this one.

This package is default-OFF and additive: nothing here is imported by the finance
engine, so committed scenarios stay byte-identical (KPI-neutral). The heavy grid
libraries (``pandapower`` / ``andes`` / ``opendssdirect``) are OPTIONAL dependencies
of the ``[grid]`` extra, guarded at call-time via ``_require_*()`` (CASPER) and NEVER
imported at module-import time — so the default (grid-free) environment imports this
package cleanly and the guards fail loud only when a grid entrypoint is actually
called without the extra installed.

Public surface:
    - :func:`analytics.grid.short_circuit.screen_grid_strength` — SCR@POC via
      pandapower IEC 60909 (min + max), banded into the GFL/GFM screen, with a
      closed-form Thevenin fallback; returns the advisory
      :class:`analytics.contracts_v14.GridStrengthResult`.
    - :func:`analytics.grid.ride_through_poc.run_lvrt_case` — one ANDES RMS LVRT
      case parameterised from the D0 grid-code fixture (dynamics-layer scaffold).
"""

from __future__ import annotations

__all__ = ["short_circuit", "ride_through_poc"]
