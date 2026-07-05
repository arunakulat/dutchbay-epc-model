"""Import levies + indirect-tax (VAT) configuration for capex and opex (#738).

Single source of the capex uplift arithmetic for Sri Lankan import levies and
unrecoverable VAT. The config surface is the opt-in TOP-LEVEL ``taxes_indirect:``
block (a sibling of the revenue-side ``statutory:`` block; the strictly-parsed
direct-tax ``tax:`` block is deliberately not touched):

.. code-block:: yaml

    taxes_indirect:                # ABSENT block => byte-identical (all lines 0)
      import_share_pct: 0.69       # imported (CIF) share of the pre-levy capex base
      cid_pct: 0.0                 # Customs Import Duty (HS 8502.31: Free)
      pal_pct: 0.05                # Ports & Airports Levy on CIF
      sscl_import_pct: 0.025       # SSCL on imports (Act 24/2025 exemption restriction)
      vat_capex_pct: 0.18          # unrecoverable input VAT (exempt supply => no credit)
      vat_on_full_capex: false     # true => VAT also on the domestic capex share
      vat_on_duties: true          # import-VAT base includes CIF + duties (SL cascade)
      vat_opex_pct: 0.18           # unrecoverable input VAT on O&M (opex uplift, expensed)
      relief:                      # per-line toggles: the relief instruments differ
        bonded_scheme: false       # true => CID/PAL/SSCL(import) = 0 (BOI s.17 + bonded)
        vat_capex_relieved: false  # true => capex VAT = 0 (SDP / specified project)
        vat_opex_relieved: false   # operating-phase VAT usually survives project relief

Cascade (duties on CIF flat; VAT on the duties-inclusive base):

.. code-block:: text

    import_base = import_share_pct * capex_base_usd
    duties      = import_base * (cid + pal + sscl_import)      [0 if relief.bonded_scheme]
    vat_base    = (import_base + duties if vat_on_duties else import_base)
                  + (capex_base - import_base if vat_on_full_capex else 0)
    vat_capex   = vat_base * vat_capex_pct                     [0 if relief.vat_capex_relieved]
    uplift_usd  = duties + vat_capex

Approximation note (documented, deliberately not over-modelled): the exact SL
Customs computation carries second-order cascades (SSCL's CIF+10% import markup,
VAT-on-SSCL ordering) worth ~0.1% of CIF; this module applies each ad-valorem
rate flat on CIF and VAT on the duties-inclusive base.

Opex-VAT mixed-supply simplification (documented): ``vat_opex_pct`` applies to
the ENTIRE O&M line, including components that are not standard-rated VAT
supplies in SL practice (insurance premia, land lease) — a prudent-direction
simplification; calibrate via a lower effective rate if a scenario needs the
split modelled.

QRA ordering (documented): the capex uplift applies to the base AFTER any AACE
QRA contingency recomputation (``_extract_capex_base_usd`` returns the
QRA-inclusive base), i.e. duties are charged on the risk reserve too — mildly
conservative, since an unspent contingency imports nothing; calibrate via
``import_share_pct`` if that materially overstates the CIF base.

Currency note: CID/PAL/SSCL/VAT are ad-valorem percentages of the CIF/invoice
value — a pure ratio is currency-invariant at each payment date, so
``uplift_usd = rate * base_usd`` is exact at the construction-window FX. The
LKR depreciable base translates the uplift at the SAME year-0 FX the USD capex
rung uses (see ``finance.cashflow_v14._prepare_cashflow_context``), so there is
no basis mismatch and no new FX config.

CASPER: pure functions + a frozen dataclass; ``resolve_indirect_taxes`` is the
CESSPIT call-time authority (strict decimals, unknown-key rejection, fail-loud
``ValueError``) and the pre-flight schema guard delegates to it verbatim, so the
two can never disagree (the #733a pattern).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional

__all__ = [
    "IndirectTaxes",
    "capex_uplift_from_config",
    "capex_uplift_lines_usd",
    "compute_capex_uplift_usd",
    "has_taxes_indirect",
    "resolve_indirect_taxes",
]

_BLOCK_KEY = "taxes_indirect"

# Strict decimals (FIN-02 unit-suffix convention): a rate of 18 for "18%" is a
# config error, never auto-divided — an 18x levy and an 18% levy must not be
# one typo apart.
_RATE_KEYS = ("cid_pct", "pal_pct", "sscl_import_pct", "vat_capex_pct", "vat_opex_pct")
_BOOL_KEYS = ("vat_on_full_capex", "vat_on_duties")
_RELIEF_KEYS = ("bonded_scheme", "vat_capex_relieved", "vat_opex_relieved")
_ALLOWED_KEYS = frozenset(("import_share_pct", "relief", *_RATE_KEYS, *_BOOL_KEYS))
_CAPEX_RATE_KEYS = ("cid_pct", "pal_pct", "sscl_import_pct", "vat_capex_pct")


@dataclass(frozen=True)
class IndirectTaxes:
    """Parsed, validated ``taxes_indirect:`` block (immutable value object)."""

    import_share_pct: float
    cid_pct: float
    pal_pct: float
    sscl_import_pct: float
    vat_capex_pct: float
    vat_opex_pct: float
    vat_on_full_capex: bool
    vat_on_duties: bool
    bonded_scheme: bool
    vat_capex_relieved: bool
    vat_opex_relieved: bool

    @property
    def duty_rate(self) -> float:
        """Combined CID+PAL+SSCL rate on the import base (0.0 under bonded relief)."""
        if self.bonded_scheme:
            return 0.0
        return self.cid_pct + self.pal_pct + self.sscl_import_pct

    @property
    def capex_vat_rate(self) -> float:
        """Effective unrecoverable capex-VAT rate (0.0 when relieved)."""
        return 0.0 if self.vat_capex_relieved else self.vat_capex_pct

    @property
    def opex_vat_rate(self) -> float:
        """Effective unrecoverable opex-VAT rate (0.0 when relieved)."""
        return 0.0 if self.vat_opex_relieved else self.vat_opex_pct

    @property
    def has_capex_lines(self) -> bool:
        """True when any capex-side line survives the relief toggles."""
        return self.duty_rate > 0.0 or self.capex_vat_rate > 0.0


def _find_block(config: Mapping[str, Any]) -> Optional[Any]:
    """Locate the top-level block case-insensitively (matches the capex/fx style)."""
    if not isinstance(config, Mapping):
        return None
    for key, value in config.items():
        if isinstance(key, str) and key.lower() == _BLOCK_KEY:
            return value
    return None


def has_taxes_indirect(config: Optional[Mapping[str, Any]]) -> bool:
    """True when the config declares a ``taxes_indirect`` block (however malformed).

    Presence probe for the flat-path capex mirrors (``analytics.core.metrics`` /
    ``finance.equity_distribution_v14_hydra``): a declared block routes them
    through the single debt-engine resolver so the NPV / equity capex base cannot
    diverge from the financed (levy-inclusive) base. A malformed block still
    returns True — the delegated resolver then fails loud rather than one surface
    silently ignoring what another surface charges.
    """
    if config is None:
        return False
    return _find_block(config) is not None


def _require_rate(block: Mapping[str, Any], key: str) -> float:
    """Parse an optional rate key as a strict decimal in [0, 1); absent -> 0.0."""
    raw = block.get(key)
    if raw is None:
        return 0.0
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise ValueError(
            f"taxes_indirect.{key} must be a numeric decimal rate (got {raw!r})"
        )
    rate = float(raw)
    if not 0.0 <= rate < 1.0:
        raise ValueError(
            f"taxes_indirect.{key} must be a decimal in [0, 1) — e.g. 18% -> 0.18 "
            f"(got {rate!r}; a value like 18 is a percent typed where a decimal "
            "belongs and is refused, never auto-divided)"
        )
    return rate


def _require_bool(block: Mapping[str, Any], key: str, default: bool, ctx: str) -> bool:
    raw = block.get(key)
    if raw is None:
        return default
    if not isinstance(raw, bool):
        raise ValueError(f"{ctx}.{key} must be a boolean true/false (got {raw!r})")
    return raw


def resolve_indirect_taxes(
    config: Optional[Mapping[str, Any]],
) -> Optional[IndirectTaxes]:
    """Resolve + strictly validate the ``taxes_indirect:`` block, or ``None``.

    Returns ``None`` when the block is absent (feature off, byte-identical).
    Raises ``ValueError`` (CESSPIT, fail-loud at call time) on: a non-mapping
    block, unknown keys (typo guard), any rate outside ``[0, 1)``,
    ``import_share_pct`` outside ``[0, 1]`` or missing while a capex-side rate is
    declared, non-bool flags, a non-mapping ``relief`` block, or unknown relief
    keys. The pre-flight schema guard (``analytics.schema_guard``) delegates to
    this exact function, so pre-flight and call-time can never disagree.
    """
    if config is None:
        return None
    block = _find_block(config)
    if block is None:
        return None
    if not isinstance(block, Mapping):
        raise ValueError(
            "taxes_indirect must be a mapping of levy/VAT keys "
            f"(got {type(block).__name__})"
        )

    unknown = sorted(str(k) for k in block if str(k) not in _ALLOWED_KEYS)
    if unknown:
        raise ValueError(
            f"taxes_indirect has unknown key(s) {unknown}; "
            f"valid keys: {sorted(_ALLOWED_KEYS)}"
        )

    rates = {key: _require_rate(block, key) for key in _RATE_KEYS}
    flags = {
        "vat_on_full_capex": _require_bool(
            block, "vat_on_full_capex", False, "taxes_indirect"
        ),
        "vat_on_duties": _require_bool(block, "vat_on_duties", True, "taxes_indirect"),
    }

    relief_raw = block.get("relief")
    if relief_raw is None:
        relief_map: Mapping[str, Any] = {}
    elif isinstance(relief_raw, Mapping):
        relief_map = relief_raw
    else:
        raise ValueError(
            "taxes_indirect.relief must be a mapping of relief toggles "
            f"(got {type(relief_raw).__name__})"
        )
    unknown_relief = sorted(str(k) for k in relief_map if str(k) not in _RELIEF_KEYS)
    if unknown_relief:
        raise ValueError(
            f"taxes_indirect.relief has unknown key(s) {unknown_relief}; "
            f"valid keys: {sorted(_RELIEF_KEYS)}"
        )
    relief = {
        key: _require_bool(relief_map, key, False, "taxes_indirect.relief")
        for key in _RELIEF_KEYS
    }

    share_raw = block.get("import_share_pct")
    if share_raw is None:
        if any(rates[k] > 0.0 for k in _CAPEX_RATE_KEYS):
            raise ValueError(
                "taxes_indirect.import_share_pct is required when any capex-side "
                "rate (cid_pct / pal_pct / sscl_import_pct / vat_capex_pct) is "
                "non-zero — declare the imported (CIF) share of capex explicitly "
                "(no silent default)"
            )
        share = 0.0
    else:
        if isinstance(share_raw, bool) or not isinstance(share_raw, (int, float)):
            raise ValueError(
                "taxes_indirect.import_share_pct must be a numeric decimal "
                f"(got {share_raw!r})"
            )
        share = float(share_raw)
        if not 0.0 <= share <= 1.0:
            raise ValueError(
                "taxes_indirect.import_share_pct must be a decimal in [0, 1] "
                f"(got {share!r})"
            )

    return IndirectTaxes(
        import_share_pct=share,
        cid_pct=rates["cid_pct"],
        pal_pct=rates["pal_pct"],
        sscl_import_pct=rates["sscl_import_pct"],
        vat_capex_pct=rates["vat_capex_pct"],
        vat_opex_pct=rates["vat_opex_pct"],
        vat_on_full_capex=flags["vat_on_full_capex"],
        vat_on_duties=flags["vat_on_duties"],
        bonded_scheme=relief["bonded_scheme"],
        vat_capex_relieved=relief["vat_capex_relieved"],
        vat_opex_relieved=relief["vat_opex_relieved"],
    )


def capex_uplift_lines_usd(
    base_usd: float, indirect: IndirectTaxes
) -> Dict[str, float]:
    """Per-line capex uplift breakdown in USD (disclosure surface).

    Keys: ``cid_usd`` / ``pal_usd`` / ``sscl_import_usd`` (0.0 each under bonded
    relief), ``vat_capex_usd`` (0.0 when relieved), and ``total_usd``. Pure
    function of the PRE-LEVY capex base and the parsed block.
    """
    import_base = indirect.import_share_pct * float(base_usd)
    if indirect.bonded_scheme:
        cid = pal = sscl = 0.0
    else:
        cid = import_base * indirect.cid_pct
        pal = import_base * indirect.pal_pct
        sscl = import_base * indirect.sscl_import_pct
    duties = cid + pal + sscl

    if indirect.capex_vat_rate > 0.0:
        vat_base = import_base + duties if indirect.vat_on_duties else import_base
        if indirect.vat_on_full_capex:
            vat_base += float(base_usd) - import_base
        vat = vat_base * indirect.capex_vat_rate
    else:
        vat = 0.0

    return {
        "cid_usd": cid,
        "pal_usd": pal,
        "sscl_import_usd": sscl,
        "vat_capex_usd": vat,
        "total_usd": duties + vat,
    }


def compute_capex_uplift_usd(base_usd: float, indirect: IndirectTaxes) -> float:
    """Total capitalized capex uplift (duties + unrecoverable VAT) in USD."""
    return capex_uplift_lines_usd(base_usd, indirect)["total_usd"]


def capex_uplift_from_config(config: Optional[Mapping[str, Any]]) -> float:
    """Config-level convenience: the capex uplift in USD, 0.0 when levy-free.

    Used by the depreciation-base ladder (``finance.cashflow_v14``): resolves the
    block, and only when a capex-side line survives the relief toggles reaches
    for the PRE-LEVY capex base via the debt engine's base resolver (call-site
    lazy import — the repo's standard cycle-breaker; ``finance.debt_v14``
    top-level-imports this module's pure functions, and only this config-level
    helper reaches back).
    """
    indirect = resolve_indirect_taxes(config)
    if indirect is None or not indirect.has_capex_lines:
        return 0.0

    from finance.debt_v14 import _extract_capex_base_usd

    base = _extract_capex_base_usd(dict(config or {}))
    return compute_capex_uplift_usd(base, indirect)
