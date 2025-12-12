from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List

# Resolve repo root and make "analytics" importable
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from analytics.evaluation_v14 import evaluate_with_overrides  # noqa: E402
from analytics.monte_carlo_v14 import (  # noqa: E402
    MonteCarloConfig,
    run_monte_carlo_analysis,
)
from analytics.sensitivity_v14 import (  # noqa: E402
    ParameterRangeConfig,
    SensitivityRequest,
    load_parameters_from_yaml,
    run_multi_metric_tornado,
)

logger = logging.getLogger(__name__)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run v14 base pipeline + optional sensitivity tornado + optional "
            "Monte Carlo in one shot."
        )
    )

    parser.add_argument(
        "--config",
        required=True,
        help="Path to v14 scenario config (YAML/JSON).",
    )
    parser.add_argument(
        "--out-dir",
        default="out/full_analytics",
        help="Output directory for JSON/CSV artifacts (default: out/full_analytics).",
    )

    # Sensitivity (tornado) options
    parser.add_argument(
        "--sensitivity-params",
        help="YAML file with ParameterRangeConfig entries "
        "(for tornado / sensitivity_v14).",
    )
    parser.add_argument(
        "--metrics",
        nargs="+",
        default=["project_irr", "dscr_min"],
        help=(
            "Metrics to include in tornado (multi-metric). "
            "Default: project_irr dscr_min"
        ),
    )

    # Monte Carlo options
    parser.add_argument(
        "--monte-carlo-config",
        help=(
            "YAML/JSON config for Monte Carlo "
            "(e.g. config/monte_carlo_defaults.yaml). "
            "If omitted, Monte Carlo is skipped."
        ),
    )
    parser.add_argument(
        "--mc-output-prefix",
        default="monte_carlo",
        help="Prefix for Monte Carlo JSON output file (default: monte_carlo).",
    )

    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO).",
    )

    return parser.parse_args()


def _ensure_out_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _run_base_pipeline(config_path: Path, out_dir: Path) -> Dict[str, float]:
    logger.info("Running base v14 pipeline for %s", config_path)
    kpis = evaluate_with_overrides(
        config_path,
        overrides=None,
        validation_modules=None,
    )
    base_json = out_dir / "base_kpis.json"
    base_json.write_text(json.dumps(kpis, indent=2))
    logger.info("Wrote base KPIs JSON to %s", base_json)
    return kpis


def _run_sensitivity(
    config_path: Path,
    params_path: Path,
    metrics: List[str],
    out_dir: Path,
) -> None:
    logger.info(
        "Running sensitivity_v14 tornado for metrics=%s using params=%s",
        metrics,
        params_path,
    )

    param_configs: List[ParameterRangeConfig] = load_parameters_from_yaml(params_path)

    # IMPORTANT: match the real SensitivityRequest contract.
    # In your repo, this expects scenario_path (not config_path).
    request = SensitivityRequest(
        scenario_path=str(config_path),
        parameters=param_configs,
    )

    suite = run_multi_metric_tornado(request, metrics=metrics)

    df = suite.to_dataframe()
    tornado_csv = out_dir / "tornado_multi_metric.csv"
    df.to_csv(tornado_csv, index=False)

    logger.info("Wrote tornado CSV to %s", tornado_csv)


def _run_monte_carlo(
    config_path: Path,
    mc_config_path: Path,
    out_dir: Path,
    prefix: str,
) -> None:
    logger.info(
        "Running Monte Carlo v14 with config=%s for scenario=%s",
        mc_config_path,
        config_path,
    )

    mc_cfg = MonteCarloConfig.from_file(mc_config_path)
    result = run_monte_carlo_analysis(
        config_path=str(config_path),
        mc_config=mc_cfg,
    )

    mc_json = out_dir / f"{prefix}_result.json"
    payload: Dict[str, Any] = result.model_dump(mode="json")  # type: ignore[attr-defined]
    mc_json.write_text(json.dumps(payload, indent=2))

    logger.info("Wrote Monte Carlo JSON to %s", mc_json)


def main() -> int:
    args = _parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )

    config_path = Path(args.config).resolve()
    out_dir = Path(args.out_dir).resolve()
    _ensure_out_dir(out_dir)

    if not config_path.is_file():
        logger.error("Config file does not exist: %s", config_path)
        return 1

    # 1. Base v14 pipeline
    _run_base_pipeline(config_path, out_dir)

    # 2. Sensitivity / tornado (optional)
    if args.sensitivity_params:
        params_path = Path(args.sensitivity_params).resolve()
        if not params_path.is_file():
            logger.error("Sensitivity params file does not exist: %s", params_path)
            return 1
        _run_sensitivity(config_path, params_path, args.metrics, out_dir)
    else:
        logger.info("No --sensitivity-params specified; skipping tornado.")

    # 3. Monte Carlo (optional)
    if args.monte_carlo_config:
        mc_path = Path(args.monte_carlo_config).resolve()
        if not mc_path.is_file():
            logger.error("Monte Carlo config file does not exist: %s", mc_path)
            return 1
        _run_monte_carlo(config_path, mc_path, out_dir, args.mc_output_prefix)
    else:
        logger.info("No --monte-carlo-config specified; skipping Monte Carlo.")

    logger.info("Full analytics run completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
