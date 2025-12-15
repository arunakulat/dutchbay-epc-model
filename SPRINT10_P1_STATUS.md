# Sprint 10 P1: Monte Carlo Speed Optimization - STATUS

**Phase**: P1 (Optimization, No Architecture Churn)
**Baseline**: 54.82s (9 tests)
**Target**: 20s (60% speedup)

---

## P1.1: Config Caching ✅ PLANNED

**Status**: Instructions committed to `P1_1_READY_TO_APPLY.txt`

**Changes**:
1. Add `_CONFIG_CACHE` dict to `analytics/monte_carlo_v14.py` line 27
2. Modify `run_monte_carlo_analysis()` to cache configs by path

**Expected**: 27% speedup (54.82s → 40s)

**Risk**: LOW (module-level cache, no global RNG state)

**Next Action**: Apply changes to monte_carlo_v14.py, test, commit

---

## P1.2: Skip Default CSV Writes (Planned)

**Status**: Queued

**Approach**: Add `write_output=False` parameter to skip CSV/JSONL writes during tests

**Expected**: 20-30% additional speedup (40s → 28-32s)

---

## P1.3: Parallel Iteration (Planned)

**Status**: Queued

**Approach**: Use `ThreadPoolExecutor` with thread-safe RNG seeding

**Expected**: 30-50% additional speedup (28-32s → 20s)

---

## Timeline

- **P1.1**: ~30 min (config caching)
- **P1.2**: ~30 min (write flag)
- **P1.3**: ~45 min (threading)
- **Validation**: ~30 min (determinism tests)
- **Merge**: ~15 min

**Total**: ~2.5 hours

---

## Testing Strategy

```bash
Before each phase:
  pytest tests/api/test_monte_carlo_regression_toy.py -v
  # Record runtime

After all phases:
  # Run 3x to verify determinism
  for i in {1..3}; do pytest tests/api/test_monte_carlo_regression_toy.py; done
  # All runs must have identical output
```

---

## Success Criteria

✅ Tests pass (zero failures)
✅ Results unchanged (pre/post identical)
✅ Runtime < 25s (target 20s)
✅ Deterministic (3x identical)
✅ No merge conflicts
✅ No architecture changes

---

## Notes

- **Zero Architecture Churn**: All optimizations are local, no refactoring
- **Backward Compatible**: All changes are additive (no breaking changes)
- **Test-First**: Each optimization validated before next
- **Merge Strategy**: All P1 work stays on branch until ready, then merge to main

