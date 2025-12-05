#!/usr/bin/env python3
"""Inspect actual dataclass signatures."""

import inspect

from analytics.contracts_v14 import (MultiMetricTornadoResult,
                                     ParameterRangeConfig, TornadoResult)

print("=" * 70)
print("TornadoResult signature:")
print("=" * 70)
print(inspect.signature(TornadoResult))
print()
print("Fields:")
for field in TornadoResult.__dataclass_fields__.values():
    print(f"  {field.name}: {field.type}")

print("\n" + "=" * 70)
print("MultiMetricTornadoResult signature:")
print("=" * 70)
print(inspect.signature(MultiMetricTornadoResult))
print()
print("Fields:")
for field in MultiMetricTornadoResult.__dataclass_fields__.values():
    print(f"  {field.name}: {field.type}")

print("\n" + "=" * 70)
print("ParameterRangeConfig signature:")
print("=" * 70)
print(inspect.signature(ParameterRangeConfig))
print()
print("Fields:")
for field in ParameterRangeConfig.__dataclass_fields__.values():
    print(f"  {field.name}: {field.type}")
