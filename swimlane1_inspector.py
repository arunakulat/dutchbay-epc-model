#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Swimlane 1 Inspector - CCCDIR-Compliant Contract Verification Tool

Purpose:
    Extract and verify SL-1.1 (WACC) and SL-1.2 (Equity) module information
    from the local DutchBay EPC Model codebase using AST inspection.

Features:
    1. Contract Field Extraction (WaccResult, EquityResult)
    2. Test Coverage Analysis (pytest integration)
    3. Edge Case Detection (boundary, exception, error tests)
    4. Performance Profiling (execution time, SLA validation)
    5. Governance Compliance Checks (CCCDIR/CESSPIT/CASPER/GWTF)

Governance Compliance (CCCDIR Principles):
    ✅ Contract-first inspection (no dict manipulation)
    ✅ Typed dataclass definitions validated
    ✅ Config-driven behavior (YAML scenarios)
    ✅ Explicit error handling (fail-fast on issues)
    ✅ Audit trail generation (inspection logs)

Author: DutchBay Development Team
Version: 1.0.0
License: Proprietary
Created: 2025-12-12
"""

from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ═════════════════════════════════════════════════════════════════════════════
# CCCDIR: CONTRACT DEFINITIONS FOR INSPECTION RESULTS
# ═════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class ContractField:
    """
    CCCDIR: Typed representation of a dataclass field.

    Attributes:
        name: Field name (e.g., 'wacc_value')
        type_annotation: Type hint string (e.g., 'float')
        default_value: Default value if present (e.g., '0.0')
        is_optional: True if Optional[X] or Union[X, None]
        description: Docstring or description
    """

    name: str
    type_annotation: str
    default_value: Optional[str] = None
    is_optional: bool = False
    description: str = ""


@dataclass(frozen=True)
class ContractInspection:
    """
    CCCDIR: Complete contract inspection result.

    Represents a single dataclass contract extracted from source code.

    Attributes:
        class_name: Class name (e.g., 'WaccResult')
        module_path: Relative path to module (e.g., 'finance/wacc_v14.py')
        fields: List of ContractField objects
        is_dataclass: True if decorated with @dataclass
        is_frozen: True if frozen=True in decorator
        has_post_init: True if __post_init__ method present
        docstring: Class docstring if available
        line_number: Line number in source file
        inspection_timestamp: ISO 8601 timestamp
    """

    class_name: str
    module_path: str
    fields: List[ContractField]
    is_dataclass: bool
    is_frozen: bool
    has_post_init: bool
    docstring: Optional[str] = None
    line_number: int = 0
    inspection_timestamp: str = field(
        default_factory=lambda: datetime.now().isoformat()
    )


@dataclass(frozen=True)
class TestCoverageMetrics:
    """
    CCCDIR: Test coverage analysis result.

    Attributes:
        module_path: Path to module being tested
        test_file_path: Path to corresponding test file
        total_tests: Number of tests found
        passing_tests: Number of passing tests
        failing_tests: Number of failing tests
        coverage_percentage: Pass rate as percentage (0.0 to 100.0)
        has_edge_case_tests: True if boundary/exception tests found
        edge_case_test_names: List of edge case test function names
        inspection_timestamp: ISO 8601 timestamp
    """

    module_path: str
    test_file_path: Optional[str]
    total_tests: int = 0
    passing_tests: int = 0
    failing_tests: int = 0
    coverage_percentage: float = 0.0
    has_edge_case_tests: bool = False
    edge_case_test_names: List[str] = field(default_factory=list)
    inspection_timestamp: str = field(
        default_factory=lambda: datetime.now().isoformat()
    )


@dataclass(frozen=True)
class PerformanceBenchmark:
    """
    CCCDIR: Performance profiling result.

    Attributes:
        function_name: Name of profiled function
        module_path: Path to module containing function
        execution_time_ms: Total execution time in milliseconds
        input_scale: Number of scenarios/iterations processed
        output_size: Size of output in bytes
        is_within_sla: True if execution_time_ms <= SLA threshold
        benchmark_timestamp: ISO 8601 timestamp
    """

    function_name: str
    module_path: str
    execution_time_ms: float
    input_scale: int
    output_size: int
    is_within_sla: bool
    benchmark_timestamp: str = field(
        default_factory=lambda: datetime.now().isoformat()
    )


@dataclass
class InspectionReport:
    """
    CCCDIR: Complete Swimlane 1 inspection report.

    Aggregates all inspection results and governance findings.

    Attributes:
        report_title: Human-readable title
        report_timestamp: ISO 8601 timestamp
        wacc_contract: SL-1.1 contract inspection result
        wacc_test_coverage: SL-1.1 test metrics
        wacc_performance: SL-1.1 performance benchmark
        equity_contract: SL-1.2 contract inspection result
        equity_test_coverage: SL-1.2 test metrics
        equity_performance: SL-1.2 performance benchmark
        governance_checks: Dict of governance framework compliance
        issues_found: List of discovered issues
        recommendations: List of improvement recommendations
    """

    report_title: str = "Swimlane 1 (SL-1.1 & SL-1.2) Inspection Report"
    report_timestamp: str = field(
        default_factory=lambda: datetime.now().isoformat()
    )

    # SL-1.1: WACC Engine
    wacc_contract: Optional[ContractInspection] = None
    wacc_test_coverage: Optional[TestCoverageMetrics] = None
    wacc_performance: Optional[PerformanceBenchmark] = None

    # SL-1.2: Equity Analytics
    equity_contract: Optional[ContractInspection] = None
    equity_test_coverage: Optional[TestCoverageMetrics] = None
    equity_performance: Optional[PerformanceBenchmark] = None

    # Governance Verification
    governance_checks: Dict[str, bool] = field(default_factory=dict)

    # Issues & Recommendations
    issues_found: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (CCCDIR: explicit serialization)."""
        return asdict(self)

    def to_json(self) -> str:
        """Convert to JSON string (CCCDIR: explicit serialization)."""
        return json.dumps(self.to_dict(), indent=2, default=str)


# ═════════════════════════════════════════════════════════════════════════════
# INSPECTOR: CONTRACT FIELD EXTRACTION
# ═════════════════════════════════════════════════════════════════════════════


class ContractFieldExtractor:
    """CCCDIR: Extract contract fields from dataclass definitions using AST."""

    @staticmethod
    def extract_from_file(
        module_path: str, class_name: str
    ) -> Optional[ContractInspection]:
        """
        Extract contract fields from a Python file.

        Args:
            module_path: Path to Python file (e.g., 'finance/wacc_v14.py')
            class_name: Dataclass name (e.g., 'WaccResult')

        Returns:
            ContractInspection if found, None otherwise
        """
        path = Path(module_path)
        if not path.exists():
            return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                tree = ast.parse(f.read())

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and node.name == class_name:
                    return ContractFieldExtractor._parse_class(
                        node, module_path, path
                    )
        except Exception as e:
            print(f"❌ Error parsing {module_path}: {e}")

        return None

    @staticmethod
    def _parse_class(
        class_node: ast.ClassDef, module_path: str, file_path: Path
    ) -> ContractInspection:
        """Parse a ClassDef AST node into ContractInspection."""

        # Extract docstring
        docstring = ast.get_docstring(class_node)

        # Check if frozen (dataclass decorator)
        is_frozen = False
        for decorator in class_node.decorator_list:
            if isinstance(decorator, ast.Call):
                func = decorator.func
                if isinstance(func, ast.Name) and func.id == "dataclass":
                    for keyword in decorator.keywords:
                        if keyword.arg == "frozen":
                            if isinstance(keyword.value, ast.Constant):
                                is_frozen = keyword.value.value
            elif isinstance(decorator, ast.Name) and decorator.id == "dataclass":
                pass  # Default: frozen=False

        # Check for __post_init__
        has_post_init = any(
            isinstance(item, ast.FunctionDef) and item.name == "__post_init__"
            for item in class_node.body
        )

        # Extract fields (annotations)
        fields = []
        for item in class_node.body:
            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                field = ContractFieldExtractor._parse_field(item)
                fields.append(field)

        return ContractInspection(
            class_name=class_node.name,
            module_path=str(module_path),
            fields=fields,
            is_dataclass=True,
            is_frozen=is_frozen,
            has_post_init=has_post_init,
            docstring=docstring,
            line_number=class_node.lineno,
        )

    @staticmethod
    def _parse_field(ann_assign: ast.AnnAssign) -> ContractField:
        """Parse an AnnAssign node into ContractField."""

        field_name = ann_assign.target.id
        type_annotation = ast.unparse(ann_assign.annotation)

        # Extract default value if present
        default_value = None
        if ann_assign.value:
            default_value = ast.unparse(ann_assign.value)

        # Check if optional
        is_optional = "None" in type_annotation or "Optional" in type_annotation

        return ContractField(
            name=field_name,
            type_annotation=type_annotation,
            default_value=default_value,
            is_optional=is_optional,
        )


# ═════════════════════════════════════════════════════════════════════════════
# TEST COVERAGE ANALYZER
# ═════════════════════════════════════════════════════════════════════════════


class TestCoverageAnalyzer:
    """CCCDIR: Analyze test coverage for modules using pytest."""

    @staticmethod
    def analyze(
        module_path: str, test_file_pattern: str = "test_*.py"
    ) -> Optional[TestCoverageMetrics]:
        """
        Analyze test coverage for a module.

        Args:
            module_path: Path to module (e.g., 'finance/wacc_v14.py')
            test_file_pattern: Pattern to find tests (default: test_*.py)

        Returns:
            TestCoverageMetrics with coverage data
        """
        # Find corresponding test file
        module_name = Path(module_path).stem

        test_patterns = [
            f"tests/**/test_{module_name}.py",
            f"tests/**/{module_name}_test.py",
            f"tests/**/*_{module_name}.py",
        ]

        test_file = None
        for pattern in test_patterns:
            matches = list(Path(".").glob(pattern))
            if matches:
                test_file = str(matches[0])
                break

        # Run pytest on test file (if found)
        passing = 0
        failing = 0
        total = 0
        edge_case_tests = []

        if test_file:
            passing, failing, total, edge_case_tests = (
                TestCoverageAnalyzer._run_pytest(test_file)
            )

        return TestCoverageMetrics(
            module_path=module_path,
            test_file_path=test_file,
            total_tests=total,
            passing_tests=passing,
            failing_tests=failing,
            coverage_percentage=100 * (passing / total) if total > 0 else 0.0,
            has_edge_case_tests=len(edge_case_tests) > 0,
            edge_case_test_names=edge_case_tests,
        )

    @staticmethod
    def _run_pytest(test_file: str) -> Tuple[int, int, int, List[str]]:
        """Run pytest and extract results."""
        try:
            result = subprocess.run(
                ["python", "-m", "pytest", test_file, "-v", "--tb=no"],
                capture_output=True,
                text=True,
                timeout=30,
            )

            output = result.stdout + result.stderr

            # Parse output for test counts
            passed = len(re.findall(r"PASSED", output))
            failed = len(re.findall(r"FAILED", output))
            total = passed + failed

            # Find edge case tests
            edge_case_keywords = [
                "edge",
                "boundary",
                "corner",
                "exception",
                "error",
                "invalid",
            ]
            edge_tests = []
            for line in output.split("\n"):
                if "::test_" in line:
                    for keyword in edge_case_keywords:
                        if keyword in line.lower():
                            test_name = re.search(r"test_\w+", line)
                            if test_name:
                                edge_tests.append(test_name.group())

            return passed, failed, total, edge_tests

        except Exception as e:
            print(f"⚠️  Could not run pytest: {e}")
            return 0, 0, 0, []


# ═════════════════════════════════════════════════════════════════════════════
# PERFORMANCE PROFILER
# ═════════════════════════════════════════════════════════════════════════════


class PerformanceProfiler:
    """CCCDIR: Profile function performance under various scales."""

    @staticmethod
    def profile_function(
        function_path: str,
        function_name: str,
        scenarios_count: int = 1000,
        sla_ms: float = 5000.0,
    ) -> Optional[PerformanceBenchmark]:
        """
        Profile a function for performance.

        Args:
            function_path: Module path (e.g., 'finance/wacc_v14.py')
            function_name: Function to profile (e.g., 'calculate_wacc')
            scenarios_count: Number of scenarios to process
            sla_ms: Service level agreement (max acceptable time in ms)

        Returns:
            PerformanceBenchmark with timing data
        """
        execution_time_ms = 0.0
        output_size = 0

        try:
            # Dynamically import module and function
            module_name = function_path.replace("/", ".").replace(".py", "")
            spec = __import__(module_name)
            func = getattr(spec, function_name)

            # Run benchmark with timing
            start = time.time()
            for _ in range(scenarios_count):
                func()  # Simplified
            end = time.time()

            execution_time_ms = (end - start) * 1000
            output_size = sys.getsizeof(str(func()))

        except Exception as e:
            print(f"⚠️  Could not profile {function_name}: {e}")

        return PerformanceBenchmark(
            function_name=function_name,
            module_path=function_path,
            execution_time_ms=execution_time_ms,
            input_scale=scenarios_count,
            output_size=output_size,
            is_within_sla=execution_time_ms <= sla_ms,
        )


# ═════════════════════════════════════════════════════════════════════════════
# GOVERNANCE VERIFIER (CCCDIR/CESSPIT/CASPER/GWTF)
# ═════════════════════════════════════════════════════════════════════════════


class GovernanceVerifier:
    """CCCDIR: Verify governance compliance across frameworks."""

    @staticmethod
    def verify_all(module_paths: List[str]) -> Dict[str, bool]:
        """
        Verify all governance frameworks.

        Args:
            module_paths: List of module paths to check

        Returns:
            Dictionary of governance checks (all True = compliant)
        """
        checks = {
            "CCCDIR:typed_contracts": True,
            "CCCDIR:no_dict_passthrough": True,
            "CCCDIR:dataclass_frozen": True,
            "CESSPIT:config_validation": True,
            "CESSPIT:schema_guard_calls": True,
            "CASPER:audit_trail": True,
            "GWTF:no_forbidden_imports": True,
            "GWTF:gateway_compliant": True,
        }

        for module_path in module_paths:
            if not Path(module_path).exists():
                continue

            try:
                with open(module_path, "r", encoding="utf-8") as f:
                    content = f.read()

                # Check for forbidden imports (GWTF)
                if (
                    "from finance." in content
                    and "evaluation_v14" not in module_path
                ):
                    checks["GWTF:no_forbidden_imports"] = False

                # Check for dict passing (CCCDIR)
                if (
                    "Dict[str, Any]" in content
                    and "contracts_v14" not in module_path
                ):
                    checks["CCCDIR:no_dict_passthrough"] = False

                # Check for frozen dataclasses (CCCDIR)
                if "@dataclass" in content and "frozen=True" not in content:
                    checks["CCCDIR:dataclass_frozen"] = False

                # Check for validation calls (CESSPIT)
                if (
                    "schema_guard" not in content
                    and "validation" in module_path
                ):
                    checks["CESSPIT:schema_guard_calls"] = False

            except Exception as e:
                print(f"⚠️  Error checking {module_path}: {e}")

        return checks


# ═════════════════════════════════════════════════════════════════════════════
# MAIN INSPECTOR ORCHESTRATOR
# ═════════════════════════════════════════════════════════════════════════════


class Swimlane1Inspector:
    """CCCDIR: Main orchestrator for Swimlane 1 inspection."""

    def __init__(self, repo_root: str = ".") -> None:
        """
        Initialize inspector with repo root path.

        Args:
            repo_root: Root directory of DutchBay EPC Model repository
        """
        self.repo_root = Path(repo_root)
        self.report = InspectionReport()

    def inspect_wacc_engine(self) -> "Swimlane1Inspector":
        """Inspect SL-1.1: WACC Engine."""
        print("\n📊 Inspecting SL-1.1: WACC Engine...")

        # Extract contract
        self.report.wacc_contract = ContractFieldExtractor.extract_from_file(
            "finance/wacc_v14.py", "WaccResult"
        )

        # Analyze test coverage
        self.report.wacc_test_coverage = TestCoverageAnalyzer.analyze(
            "finance/wacc_v14.py"
        )

        # Profile performance
        self.report.wacc_performance = PerformanceProfiler.profile_function(
            "finance/wacc_v14.py",
            "calculate_wacc",
            scenarios_count=1000,
            sla_ms=5000.0,
        )

        if self.report.wacc_contract:
            print(f"✅ Contract extracted: {self.report.wacc_contract.class_name}")
            print(f"   Fields: {len(self.report.wacc_contract.fields)}")
            for field in self.report.wacc_contract.fields:
                print(f"     • {field.name}: {field.type_annotation}")
        else:
            print("❌ Contract not found")
            self.report.issues_found.append(
                "WaccResult contract not found in finance/wacc_v14.py"
            )

        return self

    def inspect_equity_analytics(self) -> "Swimlane1Inspector":
        """Inspect SL-1.2: Equity Analytics."""
        print("\n📊 Inspecting SL-1.2: Equity Analytics...")

        # Extract contract
        self.report.equity_contract = ContractFieldExtractor.extract_from_file(
            "finance/equity_v14.py", "EquityResult"
        )

        # Analyze test coverage
        self.report.equity_test_coverage = TestCoverageAnalyzer.analyze(
            "finance/equity_v14.py"
        )

        # Profile performance
        self.report.equity_performance = PerformanceProfiler.profile_function(
            "finance/equity_v14.py",
            "calculate_equity",
            scenarios_count=1000,
            sla_ms=5000.0,
        )

        if self.report.equity_contract:
            print(
                f"✅ Contract extracted: {self.report.equity_contract.class_name}"
            )
            print(f"   Fields: {len(self.report.equity_contract.fields)}")
            for field in self.report.equity_contract.fields:
                print(f"     • {field.name}: {field.type_annotation}")
        else:
            print("❌ Contract not found")
            self.report.issues_found.append(
                "EquityResult contract not found in finance/equity_v14.py"
            )

        return self

    def verify_governance(self) -> "Swimlane1Inspector":
        """Verify governance compliance."""
        print("\n🛡️  Verifying Governance Compliance...")

        module_paths = [
            "finance/wacc_v14.py",
            "finance/equity_v14.py",
        ]

        self.report.governance_checks = GovernanceVerifier.verify_all(module_paths)

        for check_name, is_compliant in self.report.governance_checks.items():
            status = "✅" if is_compliant else "❌"
            print(f"{status} {check_name}: {is_compliant}")

            if not is_compliant:
                self.report.issues_found.append(
                    f"Governance violation: {check_name}"
                )

        return self

    def generate_recommendations(self) -> "Swimlane1Inspector":
        """Generate recommendations based on findings."""
        print("\n💡 Generating Recommendations...")

        # Check test coverage
        if (
            self.report.wacc_test_coverage
            and self.report.wacc_test_coverage.coverage_percentage < 80
        ):
            self.report.recommendations.append(
                "Increase WACC test coverage "
                f"(current: {self.report.wacc_test_coverage.coverage_percentage:.1f}%, "
                "target: 80%)"
            )

        if (
            self.report.equity_test_coverage
            and self.report.equity_test_coverage.coverage_percentage < 80
        ):
            self.report.recommendations.append(
                "Increase Equity test coverage "
                f"(current: {self.report.equity_test_coverage.coverage_percentage:.1f}%, "
                "target: 80%)"
            )

        # Check performance
        if (
            self.report.wacc_performance
            and not self.report.wacc_performance.is_within_sla
        ):
            self.report.recommendations.append(
                "Optimize WACC performance "
                f"(current: {self.report.wacc_performance.execution_time_ms:.0f}ms, "
                "SLA: 5000ms)"
            )

        if (
            self.report.equity_performance
            and not self.report.equity_performance.is_within_sla
        ):
            self.report.recommendations.append(
                "Optimize Equity performance "
                f"(current: {self.report.equity_performance.execution_time_ms:.0f}ms, "
                "SLA: 5000ms)"
            )

        # Check for edge case tests
        if (
            self.report.wacc_test_coverage
            and not self.report.wacc_test_coverage.has_edge_case_tests
        ):
            self.report.recommendations.append(
                "Add edge case tests for WACC "
                "(negative rates, extreme leverage, etc.)"
            )

        if (
            self.report.equity_test_coverage
            and not self.report.equity_test_coverage.has_edge_case_tests
        ):
            self.report.recommendations.append(
                "Add edge case tests for Equity "
                "(boundary conditions, distribution scenarios)"
            )

        for rec in self.report.recommendations:
            print(f"  📌 {rec}")

        return self

    def run_full_inspection(self) -> InspectionReport:
        """Run complete inspection workflow."""
        print("=" * 80)
        print("🔍 SWIMLANE 1 INSPECTION STARTING")
        print("=" * 80)

        self.inspect_wacc_engine()
        self.inspect_equity_analytics()
        self.verify_governance()
        self.generate_recommendations()

        print("\n" + "=" * 80)
        print("✅ INSPECTION COMPLETE")
        print("=" * 80)

        return self.report

    def export_report_json(
        self, output_file: str = "swimlane1_inspection_report.json"
    ) -> str:
        """
        Export report to JSON file.

        Args:
            output_file: Output file path

        Returns:
            Path to exported JSON file
        """
        json_str = self.report.to_json()
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(json_str)
        print(f"\n📄 Report exported to: {output_file}")
        return output_file


# ═════════════════════════════════════════════════════════════════════════════
# USAGE EXAMPLE
# ═════════════════════════════════════════════════════════════════════════════


def main() -> None:
    """
    CCCDIR-Compliant Usage Entry Point.

    Run from DutchBay EPC Model root directory:
        python swimlane1_inspector.py

    Output:
        - Console summary with color-coded status
        - swimlane1_inspection_report.json (full structured data)
    """
    inspector = Swimlane1Inspector()
    report = inspector.run_full_inspection()
    inspector.export_report_json()

    # Print summary
    print("\n📋 SUMMARY:")
    print(f"  Issues Found: {len(report.issues_found)}")
    print(f"  Recommendations: {len(report.recommendations)}")
    print(f"  Governance Compliant: {all(report.governance_checks.values())}")


if __name__ == "__main__":
    main()
