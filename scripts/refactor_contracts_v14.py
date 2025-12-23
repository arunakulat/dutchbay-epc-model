import shutil
import textwrap
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
ANALYTICS_DIR = PROJECT_ROOT / "analytics"
OLD_CONTRACTS_FILE = ANALYTICS_DIR / "contracts_v14.py"
CONTRACTS_PKG_DIR = ANALYTICS_DIR / "contracts"


def ensure_dir(path: Path) -> None:
    if not path.exists():
        print(f"[CREATE DIR] {path}")
        path.mkdir(parents=True, exist_ok=True)


def ensure_file(path: Path, content: str = "") -> None:
    if not path.exists():
        print(f"[CREATE FILE] {path}")
        path.write_text(content, encoding="utf-8")


def append_if_missing(path: Path, snippet: str) -> None:
    existing = path.read_text(encoding="utf-8")
    if snippet.strip() not in existing:
        print(f"[PATCH] {path} (+snippet)")
        path.write_text(
            existing.rstrip() + "\n\n" + snippet.strip() + "\n", encoding="utf-8"
        )


def main() -> None:
    # 1. Sanity checks
    if not ANALYTICS_DIR.exists():
        raise SystemExit(f"analytics/ directory not found at {ANALYTICS_DIR}")

    if not OLD_CONTRACTS_FILE.exists():
        raise SystemExit(f"contracts_v14.py not found at {OLD_CONTRACTS_FILE}")

    # 2. Create analytics/contracts package
    ensure_dir(CONTRACTS_PKG_DIR)

    init_path = CONTRACTS_PKG_DIR / "__init__.py"
    ensure_file(
        init_path,
        content=textwrap.dedent(
            """
            # analytics.contracts package
            # Refactored from analytics.contracts_v14 into a proper package.
            """
        ).lstrip(),
    )

    # 3. Move old contracts_v14.py into package as contracts_v14.py (façade)
    new_contracts_facade = CONTRACTS_PKG_DIR / "contracts_v14.py"
    if not new_contracts_facade.exists():
        print(f"[MOVE] {OLD_CONTRACTS_FILE} -> {new_contracts_facade}")
        shutil.move(str(OLD_CONTRACTS_FILE), str(new_contracts_facade))
    else:
        print(f"[SKIP MOVE] {new_contracts_facade} already exists; NOT overwriting.")

    # 4. Create scaffolding modules if they do not exist
    types_path = CONTRACTS_PKG_DIR / "contracts_types_v14.py"
    calculators_path = CONTRACTS_PKG_DIR / "contracts_calculators_v14.py"
    loaders_path = CONTRACTS_PKG_DIR / "contracts_loaders_v14.py"

    ensure_file(
        types_path,
        content=textwrap.dedent(
            """
            \"\"\"Types and dataclasses for contracts_v14.

            This module is the single source of truth for:
            - Contract configuration types
            - Parameter range config (for sensitivity)
            - Result objects returned to upstream layers
            \"\"\"

            # TODO: move existing type definitions (e.g. ParameterRangeConfig) here
            # from contracts_v14.py and update imports accordingly.
            """
        ).lstrip(),
    )

    ensure_file(
        calculators_path,
        content=textwrap.dedent(
            """
            \"\"\"Pure calculators for contracts_v14.

            This module should contain only side-effect-free numerical logic:
            - Contract cashflow derivation
            - Discounting / NPV for contracts
            - Aggregation across multiple contracts
            \"\"\"

            # TODO: move pure calculation helpers from contracts_v14.py here.
            """
        ).lstrip(),
    )

    ensure_file(
        loaders_path,
        content=textwrap.dedent(
            """
            \"\"\"Config / scenario loaders for contracts_v14.

            This module should handle:
            - Reading YAML / JSON configuration
            - Mapping raw config into contracts_types_v14 objects
            - Validation of configuration
            \"\"\"

            # TODO: move scenario/config loading functions from contracts_v14.py here.
            """
        ).lstrip(),
    )

    # 5. Patch analytics/contracts/__init__.py to re-export key types
    append_if_missing(
        init_path,
        textwrap.dedent(
            """
            # Public re-exports for convenience (and backward compatibility)
            try:
                from .contracts_types_v14 import ParameterRangeConfig  # type: ignore[attr-defined]
            except Exception:
                # Keep import safe during incremental refactor
                ParameterRangeConfig = None  # type: ignore[assignment]
            """
        ),
    )

    # 6. Create thin compatibility shim at analytics/contracts_v14.py
    shim_path = ANALYTICS_DIR / "contracts_v14.py"
    if not shim_path.exists():
        print(f"[CREATE SHIM] {shim_path}")
        shim_content = textwrap.dedent(
            """
            \"\"\"Backward-compatibility shim for analytics.contracts_v14.

            This file delegates all behavior to analytics.contracts.contracts_v14.
            Existing imports like

                from analytics.contractsv14 import ParameterRangeConfig

            will continue to work, but new code should import from:

                from analytics.contracts import ParameterRangeConfig
                # or
                from analytics.contracts.contracts_v14 import <symbol>

            This shim can be removed after callers are updated.
            \"\"\"

            from .contracts.contracts_v14 import *  # noqa: F401,F403
            """
        ).lstrip()
        shim_path.write_text(shim_content, encoding="utf-8")
    else:
        print(f"[SKIP SHIM] {shim_path} already exists; NOT overwriting.")

    print("\n[DONE] Basic refactor scaffolding for analytics/contracts is in place.")
    print("Next steps (manual):")
    print("  1) Move type definitions from contracts_v14.py -> contracts_types_v14.py.")
    print("  2) Move pure calculators into contracts_calculators_v14.py.")
    print("  3) Move loaders/IO into contracts_loaders_v14.py.")
    print(
        "  4) Update internal imports within analytics/contracts/* to use the new modules."
    )
    print(
        "  5) Gradually update callers to import from analytics.contracts instead of analytics.contractsv14."
    )


if __name__ == "__main__":
    main()
