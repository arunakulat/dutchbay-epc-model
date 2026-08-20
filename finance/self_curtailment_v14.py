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
  2. The surrounding QSTS configuration is complete and canonical: the study gate is
     exactly true, ``input_kind`` is utility/site, ``feeder_model_path`` is non-empty,
     and finance mode/eligibility are exactly ``canonical``/``True``. This is rechecked
     at the KPI-moving seam because direct callers need the same protection as schema-
     validated pipelines.
  3. The D6a study actually ``ran`` and the typed result is a non-generated,
     site-representative utility/engineer model with
     ``canonical_finance_eligible=True``. A synthetic/test path may run diagnostically,
     but it fails loudly here rather than moving a KPI.
  4. ``result.self_curtailed_pct`` is a real, finite, ``>= 0`` percentage.

Enabling this on a committed scenario is a SEPARATE, user-gated decision; it is not done
by shipping this module.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from analytics.contracts_v14 import (
    CANONICAL_FEEDER_INPUT_KINDS,
    CurtailmentShareResult,
)

__all__ = [
    "FINANCE_WIRING_ENABLED_PATH",
    "compose_curtailment",
    "self_curtailment_finance_wiring_enabled",
    "require_canonical_self_curtailment_finance_config",
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


def require_canonical_self_curtailment_finance_config(
    config: Mapping[str, Any] | None,
) -> tuple[str, str, str]:
    """Return the canonical feeder kind/path/evidence digest for enabled finance.

    This is intentionally pure: callers can enforce the CESSPIT configuration contract
    before importing or executing an optional grid solver. It is defence in depth for
    direct callers that do not pass through the scenario schema.
    """
    grid = config.get("grid") if isinstance(config, Mapping) else None
    qsts = grid.get("qsts") if isinstance(grid, Mapping) else None
    wiring = qsts.get("finance_wiring") if isinstance(qsts, Mapping) else None
    config_kind = qsts.get("input_kind") if isinstance(qsts, Mapping) else None
    feeder_path = qsts.get("feeder_model_path") if isinstance(qsts, Mapping) else None
    evidence_manifest_path = (
        qsts.get("evidence_manifest_path") if isinstance(qsts, Mapping) else None
    )
    evidence_manifest_sha256 = (
        qsts.get("evidence_manifest_sha256") if isinstance(qsts, Mapping) else None
    )
    mode = wiring.get("mode") if isinstance(wiring, Mapping) else None
    canonical_eligible = (
        wiring.get("canonical_eligible") if isinstance(wiring, Mapping) else None
    )
    use_synthetic_demo = (
        qsts.get("use_synthetic_demo") if isinstance(qsts, Mapping) else None
    )
    if (
        not isinstance(qsts, Mapping)
        or qsts.get("enabled") is not True
        or not (use_synthetic_demo is None or use_synthetic_demo is False)
        or not isinstance(config_kind, str)
        or config_kind not in CANONICAL_FEEDER_INPUT_KINDS
        or not isinstance(feeder_path, str)
        or not feeder_path.strip()
        or not isinstance(evidence_manifest_path, str)
        or not evidence_manifest_path.strip()
        or not isinstance(evidence_manifest_sha256, str)
        or len(evidence_manifest_sha256) != 64
        or any(
            character not in "0123456789abcdef"
            for character in evidence_manifest_sha256
        )
        or not isinstance(wiring, Mapping)
        or wiring.get("enabled") is not True
        or mode != "canonical"
        or canonical_eligible is not True
    ):
        raise ValueError(
            "QSTS canonical finance configuration refused: finance_wiring.enabled=true "
            "requires grid.qsts.enabled=true, input_kind utility_observed_model or "
            "engineer_prepared_site_model, a non-empty feeder_model_path, "
            "a non-empty evidence_manifest_path, an exact externally pinned "
            "evidence_manifest_sha256, "
            "finance_wiring.mode='canonical', and canonical_eligible=true. Synthetic "
            "placeholders and test fixtures belong only in the separately governed "
            "counterfactual pathway; they cannot enter canonical cashflow."
        )
    return str(config_kind), feeder_path.strip(), evidence_manifest_sha256


def resolve_self_curtailment_decimal(
    config: Mapping[str, Any] | None,
    result: CurtailmentShareResult | None,
) -> float:
    """The incremental self-curtailment decimal (``0.0`` when off) — the ONLY KPI-mover.

    Returns a haircut in ``[0, 1)`` only when the opt-in is set and D6a produced an
    explicitly canonical-finance-eligible site/utility ``self_curtailed_pct``. Default-off
    and NOT-RUN paths return ``0.0``; a ran-but-noncanonical result raises.

    ONLY ``result.self_curtailed_pct`` is read; ``deemed_paid_*`` is deliberately never
    consulted, so grid-instructed (deemed-paid) curtailment can never haircut revenue.
    """
    if not self_curtailment_finance_wiring_enabled(config):
        return 0.0

    config_kind, configured_feeder_path, configured_evidence_sha256 = (
        require_canonical_self_curtailment_finance_config(config)
    )

    if result is None or result.ran is False:
        # Opt-in set but the study did not run → refuse to fabricate a loss. NO SPURIOUS
        # PASS: an inert result never moves a KPI.
        return 0.0
    if result.ran is not True:
        raise ValueError(
            "QSTS finance wiring requires CurtailmentShareResult.ran to be the literal "
            f"boolean True or False, got {result.ran!r}."
        )
    if (
        not isinstance(result.feeder_input_kind, str)
        or result.feeder_input_kind not in CANONICAL_FEEDER_INPUT_KINDS
        or result.feeder_input_kind != config_kind
        or not isinstance(result.feeder_source, str)
        or result.feeder_source.strip() != configured_feeder_path
        or result.generated_input is not False
        or result.site_representative is not True
        or result.canonical_finance_eligible is not True
        or result.bankable is not False
        or result.evidence_manifest_sha256 != configured_evidence_sha256
        or result.source_manifest_sha256 is not None
        or result.qsts_run_manifest is None
        or result.qsts_run_manifest.input_kind != config_kind
        or result.qsts_run_manifest.evidence_manifest_sha256
        != configured_evidence_sha256
        or result.qsts_run_manifest.finance_wiring_mode != "canonical"
        or result.qsts_run_manifest.finance_wiring_enabled is not True
        or result.qsts_run_manifest.canonical_finance_eligible is not True
        or result.qsts_run_manifest.bankable is not False
        or result.qsts_run_manifest.lender_eligible is not False
        or result.qsts_run_manifest.board_approval_eligible is not False
        or result.qsts_run_manifest.release_eligible is not False
        or (
            config_kind == "utility_observed_model"
            and result.observed_network_data is not True
        )
    ):
        raise ValueError(
            "QSTS finance wiring refused a noncanonical feeder result: "
            f"input_kind={result.feeder_input_kind!r}, "
            f"feeder_source={result.feeder_source!r}, "
            f"generated_input={result.generated_input!r}, "
            f"observed_network_data={result.observed_network_data!r}, "
            f"site_representative={result.site_representative!r}, "
            f"evidence_manifest_sha256={result.evidence_manifest_sha256!r}, "
            "canonical_finance_eligible="
            f"{result.canonical_finance_eligible!r}. Synthetic placeholders and test "
            "fixtures may exercise advisory QSTS code, but they cannot enter canonical "
            "finance. Use the separately governed synthetic-counterfactual pathway once "
            "implemented; never reclassify a generated file as real."
        )
    pct = result.self_curtailed_pct
    if pct is None:
        raise ValueError(
            "QSTS finance wiring received ran=true but "
            "CurtailmentShareResult.self_curtailed_pct is missing. Refusing to convert a "
            "failed/incomplete enabled calculation into a silent zero-loss pass."
        )
    if isinstance(pct, bool) or not isinstance(pct, (int, float)):
        raise ValueError(
            "CurtailmentShareResult.self_curtailed_pct must be a real finite number, "
            f"not bool or another type; got {pct!r}."
        )
    if not math.isfinite(pct):
        raise ValueError(
            "CurtailmentShareResult.self_curtailed_pct must be finite for ran=true, got "
            f"{pct!r}. Refusing a silent zero-loss pass."
        )
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
