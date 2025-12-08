from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Mapping,
    MutableMapping,
    Optional,
    Sequence,
)

import yaml

from analytics.contracts_v14 import ParameterRangeConfig, TornadoResult
from analytics.evaluation_v14 import evaluate_scenario  # new v14 evaluation surface

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public request object
# ---------------------------------------------------------------------------


@dataclass
class SensitivityRequest:
    """
    Coordinator request for v14 sensitivity / tornado analysis.

    This object is intentionally *thin*: it only knows how to call the
    evaluation surface with nested overrides and interpret a single metric.

    Attributes
    ----------
    config_path:
        Path to the base v14 scenario config (YAML/JSON) file.

    metric:
        Name of the KPI in the evaluation result to analyze
        (e.g. "project_irr", "equity_irr", "min_dscr", "avg_dscr").

    parameters:
        In-memory list of ParameterRangeConfig entries. Mutually exclusive
        with `parameters_yaml_path`. If both are provided, `parameters`
        takes precedence.

    parameters_yaml_path:
        Optional YAML file describing the parameter ranges in a list/dict
        format that can be parsed into ParameterRangeConfig objects.

    base_overrides:
        Optional nested dict of overrides applied for *all* evaluations
        (base + shocks). This is useful to lock in a specific lender case,
        FX regime, etc.

    evaluation_func:
        Hook for injecting a custom evaluation function for tests.
        Defaults to `evaluate_scenario` from analytics.evaluation_v14.

    sort_by_impact:
        If True (default), results are sorted by absolute impact on the
        chosen metric (descending).
    """

    config_path: Path
    metric: str

    parameters: Optional[Sequence[ParameterRangeConfig]] = None
    parameters_yaml_path: Optional[Path] = None

    base_overrides: Mapping[str, Any] | None = None

    evaluation_func: Callable[[Path, Mapping[str, Any] | None], Mapping[str, Any]] = (
        evaluate_scenario
    )
    sort_by_impact: bool = True

    # internal cache for base result so we don't recompute it
    _base_result: Mapping[str, Any] | None = field(
        default=None, repr=False, compare=False
    )

    def load_parameters(self) -> List[ParameterRangeConfig]:
        """
        Resolve the parameter list from either in-memory config or YAML file.
        """
        if self.parameters is not None:
            return list(self.parameters)

        if self.parameters_yaml_path is None:
            raise ValueError(
                "SensitivityRequest requires either `parameters` or "
                "`parameters_yaml_path` to be provided."
            )

        return _load_parameters_from_yaml(self.parameters_yaml_path)

    def get_base_result(self) -> Mapping[str, Any]:
        """
        Compute (and cache) the base evaluation result without any shocks.
        """
        if self._base_result is None:
            logger.info(
                "Running base evaluation for sensitivity on %s", self.config_path
            )
            self._base_result = self.evaluation_func(
                self.config_path,
                self.base_overrides,
            )
        return self._base_result

    def get_base_metric_value(self) -> float:
        """
        Extract the base metric from the cached base result.
        """
        base_result = self.get_base_result()
        try:
            value = float(base_result[self.metric])
        except KeyError as exc:
            raise KeyError(
                f"Metric '{self.metric}' not found in evaluation result keys: "
                f"{sorted(base_result.keys())}"
            ) from exc
        except (TypeError, ValueError) as exc:
            raise TypeError(
                f"Metric '{self.metric}' value is not numeric: {base_result.get(self.metric)!r}"
            ) from exc

        return value


# ---------------------------------------------------------------------------
# YAML loader for parameter ranges
# ---------------------------------------------------------------------------


def _load_parameters_from_yaml(path: Path | str) -> List[ParameterRangeConfig]:
    """
    Load a list of ParameterRangeConfig objects from a YAML file.

    Expected YAML structure (example):

    ```yaml
    - name: Capex
      path: project.capex_usd_per_kw
      base_value: 1200.0
      low_pct: -0.1
      high_pct: 0.15
      steps: 3
    - name: Capacity factor
      path: generation.capacity_factor_pct
      base_value: 38.0
      low_pct: -0.05
      high_pct: 0.05
      steps: 3
    ```

    Any additional fields supported by ParameterRangeConfig are passed through.
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Sensitivity parameter YAML not found: {path}")

    with path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or []

    if not isinstance(raw, Iterable):
        raise TypeError(
            f"Sensitivity parameter YAML must be a list of objects, got {type(raw).__name__}"
        )

    configs: List[ParameterRangeConfig] = []
    for idx, item in enumerate(raw):
        if not isinstance(item, dict):
            raise TypeError(
                f"Parameter entry at index {idx} must be a mapping, got {type(item).__name__}"
            )
        configs.append(ParameterRangeConfig.model_validate(item))

    logger.info("Loaded %d sensitivity parameters from %s", len(configs), path)
    return configs


# ---------------------------------------------------------------------------
# Nested override utilities
# ---------------------------------------------------------------------------


def _build_nested_override(path: str, value: Any) -> Dict[str, Any]:
    """
    Build a nested dict override from a dot-separated path.

    Example
    -------
    >>> _build_nested_override("generation.capacity_factor_pct", 38.5)
    {'generation': {'capacity_factor_pct': 38.5}}
    """
    if not path:
        raise ValueError("Override path must be a non-empty string")

    parts = path.split(".")
    root: Dict[str, Any] = {}
    current: MutableMapping[str, Any] = root
    for idx, part in enumerate(parts):
        if not part:
            raise ValueError(f"Invalid empty segment in override path: {path!r}")
        if idx == len(parts) - 1:
            current[part] = value
        else:
            child: Dict[str, Any] = {}
            current[part] = child
            current = child
    return root


def _merge_overrides(
    base: Mapping[str, Any] | None,
    extra: Mapping[str, Any] | None,
) -> Dict[str, Any]:
    """
    Deep-merge two nested override dicts.

    Values in `extra` take precedence over `base`. Non-dict leaves are
    overwritten. This is intentionally simple and typed for the use case
    of nested config overrides.
    """
    if base is None and extra is None:
        return {}

    if base is None:
        return dict(extra or {})

    if extra is None:
        return dict(base)

    def _merge(a: Mapping[str, Any], b: Mapping[str, Any]) -> Dict[str, Any]:
        result: Dict[str, Any] = dict(a)
        for key, value in b.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = _merge(result[key], value)
            else:
                result[key] = value
        return result

    return _merge(base, extra)


# ---------------------------------------------------------------------------
# Core analysis helpers
# ---------------------------------------------------------------------------


def _generate_step_values(param: ParameterRangeConfig) -> List[float]:
    """
    Generate the sequence of numeric values to test for a parameter.

    Uses the base value plus low/high percentage adjustments over
    `param.steps`. The default behaviour is symmetric linear spacing
    between low and high bounds (inclusive).

    Examples
    --------
    base = 100, low_pct = -0.1, high_pct = 0.1, steps = 3
    -> [90.0, 100.0, 110.0]
    """
    base = float(param.base_value)
    low = base * (1.0 + float(param.low_pct))
    high = base * (1.0 + float(param.high_pct))

    steps = int(param.steps)
    if steps <= 1:
        return [base]

    step_size = (high - low) / float(steps - 1)
    return [low + i * step_size for i in range(steps)]


def _analyze_single_parameter(
    request: SensitivityRequest,
    param: ParameterRangeConfig,
) -> TornadoResult:
    """
    Run a one-dimensional sensitivity sweep for a single parameter.

    This function:
      1. Evaluates the base metric value (cached on the request).
      2. Builds nested overrides for each step value along the range.
      3. Calls the evaluation surface for each step.
      4. Records low/high metric outcomes and deltas.
    """
    logger.info("Analyzing sensitivity for parameter '%s' (%s)", param.name, param.path)

    base_metric = request.get_base_metric_value()
    values = _generate_step_values(param)

    low_metric: Optional[float] = None
    high_metric: Optional[float] = None

    for v in values:
        override = _build_nested_override(param.path, v)
        merged_overrides = _merge_overrides(request.base_overrides, override)

        result = request.evaluation_func(request.config_path, merged_overrides)
        try:
            metric_value = float(result[request.metric])
        except KeyError as exc:
            raise KeyError(
                f"Metric '{request.metric}' not found in evaluation result during "
                f"sensitivity for parameter '{param.name}'"
            ) from exc
        except (TypeError, ValueError) as exc:
            raise TypeError(
                f"Non-numeric metric '{request.metric}' during sensitivity for "
                f"parameter '{param.name}': {result.get(request.metric)!r}"
            ) from exc

        if low_metric is None or metric_value < low_metric:
            low_metric = metric_value

        if high_metric is None or metric_value > high_metric:
            high_metric = metric_value

    assert low_metric is not None and high_metric is not None  # defensive

    delta_down = low_metric - base_metric
    delta_up = high_metric - base_metric

    return TornadoResult(
        parameter_name=param.name,
        path=param.path,
        base_value=base_metric,
        low_value=low_metric,
        high_value=high_metric,
        delta_down=delta_down,
        delta_up=delta_up,
    )


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------


def run(request: SensitivityRequest) -> List[TornadoResult]:
    """
    Execute a full tornado-style sensitivity analysis.

    Returns a list of TornadoResult objects, optionally sorted by the
    absolute impact on the chosen metric (descending).
    """
    params = request.load_parameters()
    if not params:
        raise ValueError("SensitivityRequest has no parameters to analyze.")

    base_value = request.get_base_metric_value()
    logger.info(
        "Starting sensitivity run for %d parameters on metric '%s' (base=%.6f)",
        len(params),
        request.metric,
        base_value,
    )

    results: List[TornadoResult] = [
        _analyze_single_parameter(request, param) for param in params
    ]

    if request.sort_by_impact:
        results.sort(
            key=lambda r: max(abs(r.delta_down), abs(r.delta_up)),
            reverse=True,
        )

    return results
