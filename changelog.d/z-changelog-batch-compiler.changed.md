- **Changelog fragments can be folded in deterministic batches.**
  ``scripts/compile_changelog.py --batch-size=N`` consumes a sorted suffix so
  repeated batches produce the same entry order as a single full compilation;
  invalid and ambiguous option combinations now fail loudly.
