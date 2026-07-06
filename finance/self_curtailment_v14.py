"""D6b — wire ONLY the self-curtailment fraction of a QSTS study into the finance loss key.

This is the SOLE KPI-moving seam of grid-capability epic #870, and it is
**default-off**: with the wiring switch absent (every committed scenario), the resolver
returns ``0.0`` and the cashflow is byte-identical to the pre-D6b canon.

Why a separate module
---------------------
The D6a QSTS study (:mod:`analytics.grid.curtailment_qsts`) already splits a hybrid
plant's curtailment into two physically distinct, contractually OPPOSITE parts on the
advisory :class:`analytics.contracts_v14.CurtailmentShareResult`:

  * ``deemed_paid_*`` — grid-instructed / operator-dispatch curtailment. Under the CEB
    standardised PPA this is PAID as *deemed energy*, so it MUST NOT haircut revenue
    (KPI-neutral). This module NEVER reads that field.
  * ``self_curtailed_*`` — the plant's OWN physical export-cap shed AFTER BESS recovery.
    This is a REAL energy loss that reduces net energy → CFADS → IRR / DSCR. This module
    reads ONLY ``self_curtailed_pct`` and turns it into an incremental decimal haircut
    that composes into the existing ``curtailment_pct`` loss key.

The finance layer already owns a first-class incremental grid-curtailment lever
(``project.curtailment_pct``, applied multiplicatively in
:func:`finance.cashflow_v14_production._calculate_net_production`). D6b REUSES that exact
loss key — it does not re-implement the cashflow — by composing the self-curtailment
fraction into it (see :func:`compose_curtailment`). Deemed-paid, grid_loss and grid_outage
are distinct multiplicative stages and are never touched here, so nothing double-counts.

The default-off gate (CESSPIT — no silent default that moves a KPI)
-------------------------------------------------------------------
:func:`resolve_self_curtailment_decimal` returns a NON-ZERO addend ONLY when **all** hold:

  1. ``grid.qsts.finance_wiring.enabled`` is exactly ``True`` — the EXPLICIT finance
     opt-in. Its absence (the committed canon) short-circuits to ``0.0`` before any QSTS
     is even consulted.
  2. The D6a study actually ``ran`` against a REAL feeder (``result.ran`` True). An inert
     / NOT-RUN / synthetic result (``ran`` False, energy fields ``None``) can NEVER move a
     KPI — a fabricated zero-loss "pass" is refused upstream, and a ``None`` share is
     refused here (NO SPURIOUS PASS).
  3. ``result.self_curtailed_pct`` is a real, finite, ``>= 0`` percentage.

Enabling this on a committed scenario is a SEPARATE, user-gated decision; it is not done
by shipping this module.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from analytics.contracts_v14 import CurtailmentShareResult

__all__ = [
    "FINANCE_WIRING_ENABLED_PATH",
    "compose_curtailment",
    "self_curtailment_finance_wiring_enabled",
    "resolve_self_curtailment_decimal",
]

# The single explicit finance opt-in path (documented in one place, CESSPIT).
FINANCE_WIRING_ENABLED_PATH = "grid.qsts.finance_wiring.enabled"


def self_curtailment_finance_wiring_enabled(config: Mapping[str, Any] | None) -> bool:
    """True ONLY when ``grid.qsts.finance_wiring.enabled`` is exactly the bool ``True``.

    Anything else — the key absent (every committed scenario), a non-mapping ``grid`` /
    ``qsts`` / ``finance_wiring`` block, or a truthy-but-not-``True`` value (``1``,
    ``"true"``) — is treated as OFF. Requiring the literal ``True`` keeps the sole
    KPI-moving switch strict and un-fat-fingerable (no silent enable).
    """
    if not isinstance(config, Mapping):
        return False
    grid = config.get("grid")
    if not isinstance(grid, Mapping):
        return False
    qsts = grid.get("qsts")
    if not isinstance(qsts, Mapping):
        return False
    wiring = qsts.get("finance_wiring")
    if not isinstance(wiring, Mapping):
        return False
    return wiring.get("enabled") is True


def resolve_self_curtailment_decimal(
    config: Mapping[str, Any] | None,
    result: CurtailmentShareResult | None,
) -> float:
    """The incremental self-curtailment decimal (``0.0`` when off) — the ONLY KPI-mover.

    Returns a haircut in ``[0, 1)`` to compose into ``curtailment_pct`` when — and ONLY
    when — the finance-wiring opt-in is set AND the D6a study produced a real
    ``self_curtailed_pct``. Every other path returns ``0.0`` (byte-identical canon).

    ONLY ``result.self_curtailed_pct`` is read; ``deemed_paid_*`` is deliberately never
    consulted, so grid-instructed (deemed-paid) curtailment can never haircut revenue.
    """
    if not self_curtailment_finance_wiring_enabled(config):
        return 0.0
    if result is None or not result.ran:
        # Opt-in set but the study did not run against a real feeder → refuse to
        # fabricate a loss. NO SPURIOUS PASS: an inert result never moves a KPI.
        return 0.0
    pct = result.self_curtailed_pct
    if pct is None or not math.isfinite(pct):
        return 0.0
    if pct < 0.0:
        raise ValueError(
            "CurtailmentShareResult.self_curtailed_pct is negative "
            f"({pct}) — a physical energy loss cannot be < 0. Refusing to wire a "
            "nonsensical self-curtailment fraction into finance."
        )
    decimal = pct / 100.0
    if decimal >= 1.0:
        raise ValueError(
            "CurtailmentShareResult.self_curtailed_pct is "
            f"{pct}% (>= 100%) — self-curtailment cannot shed the entire plant. "
            "Refusing to wire an out-of-range self-curtailment fraction into finance."
        )
    return decimal


def compose_curtailment(config_curtailment: float, self_curtailment: float) -> float:
    """Compose the config ``curtailment_pct`` with the self-curtailment addend.

    Both are export-side energy haircuts applied to the SAME net-energy stream, so they
    compose MULTIPLICATIVELY (not additively): the surviving energy fraction is
    ``(1 - config) * (1 - self)``, i.e. the combined haircut is
    ``1 - (1 - config) * (1 - self)``. This is the exact algebra the loss stack already
    uses to chain grid_loss / curtailment / grid_outage, so no stage double-counts.

    When ``self_curtailment == 0.0`` (default-off) the function returns
    ``config_curtailment`` UNCHANGED — an explicit short-circuit rather than the algebraic
    ``1 - (1 - c) * (1 - 0)``, because that product is NOT bit-exact for every ``c`` in
    IEEE-754 (e.g. ``1 - (1 - 0.02) * 1.0 == 0.020000000000000018 != 0.02``). Returning the
    input verbatim guarantees the committed curtailment_pct — and therefore the whole
    cashflow — is byte-identical when the wiring is off.
    """
    if not 0.0 <= config_curtailment < 1.0:
        raise ValueError(
            f"config curtailment_pct {config_curtailment} out of range [0, 1)."
        )
    if not 0.0 <= self_curtailment < 1.0:
        raise ValueError(
            f"self-curtailment decimal {self_curtailment} out of range [0, 1)."
        )
    if self_curtailment == 0.0:
        return config_curtailment
    return 1.0 - (1.0 - config_curtailment) * (1.0 - self_curtailment)
