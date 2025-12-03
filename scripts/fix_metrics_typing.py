from __future__ import annotations

from pathlib import Path


def main() -> None:
    metrics_path = Path("analytics/core/metrics.py")
    if not metrics_path.exists():
        raise SystemExit(f"Cannot find {metrics_path} – run this from repo root.")

    text = metrics_path.read_text(encoding="utf-8")

    # --- Patch 1: make _derive_capex_usd mypy-safe --------------------------
    old_block = '''def _derive_capex_usd(config: Optional[Mapping[str, Any]]) -> float:
    """
    Extract total capex from config (used for NPV/IRR calculation).
    Falls back back to 0.0 if no valid capex found.
    """
    if not config:
        return 0.0
    capex = config.get("capex") if isinstance(config, Mapping) else None
    if not isinstance(capex, Mapping):
        return 0.0
    val = capex.get("usd_total")
    try:
        return float(val)
    except (TypeError, ValueError):
        return 0.0
'''

    new_block = '''def _derive_capex_usd(config: Optional[Mapping[str, Any]]) -> float:
    """
    Extract total capex from config (used for NPV/IRR calculation).

    Ensures mypy-safe coercion by removing ``None`` from the type space
    before calling ``float(...)`` and falling back cleanly on invalid
    values.
    """
    if not config:
        return 0.0
    capex = config.get("capex") if isinstance(config, Mapping) else None
    if not isinstance(capex, Mapping):
        return 0.0
    val = capex.get("usd_total")
    if val is None:
        return 0.0
    try:
        return float(val)
    except (TypeError, ValueError):
        return 0.0
'''

    if old_block not in text:
        raise SystemExit(
            "Expected _derive_capex_usd block not found – "
            "metrics.py has drifted from the known baseline; aborting instead of guessing."
        )

    patched = text.replace(old_block, new_block)

    # --- Patch 2: annotate raw_dscr as list[float] ---------------------------
    if "raw_dscr: list[float] = []" not in patched:
        if "    raw_dscr = []" not in patched:
            raise SystemExit(
                "Could not find 'raw_dscr = []' in metrics.py – "
                "structure may have changed; aborting."
            )
        patched = patched.replace(
            "    raw_dscr = []",
            "    raw_dscr: list[float] = []",
        )

    metrics_path.write_text(patched, encoding="utf-8")
    print("✅ Patched analytics/core/metrics.py (mypy-safe capex + raw_dscr typing)")


if __name__ == "__main__":
    main()
