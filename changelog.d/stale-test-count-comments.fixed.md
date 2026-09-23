- **Stale test-count claims removed from CI comments and docs.** The `test:` job comment
  in `.github/workflows/test-suite.yml` described a "~3,600-test tree" against a measured
  8,448 (CI, `28f5ee31`) / 8,420 (local collection) — understating it by ~2.3x. The figure
  was an active source of error, not a cosmetic one: it was copied verbatim into a draft
  `R21` amendment and shipped into a pull request, where review caught it as a material
  finding. Three sibling claims of the same class are corrected together — `~3,500-test
  suite` in `ci_v14_fastlane.yml`, `2,683 tests` in `docs/ARCHITECTURE.md`, and `~88 tests
  collected` in `tests/integration/README.md` (measured 219). Rather than re-pin figures
  that would drift again, each site now describes the tree qualitatively and, where useful,
  names the command that measures it. Nothing derives a count: shard balancing is by
  duration sum, and `TOTAL_SHARDS` is a literal pinned by
  `tests/lint/test_coverage_gate_policy.py`. Comment- and prose-only; both workflow files
  parse to identical trees before and after.
