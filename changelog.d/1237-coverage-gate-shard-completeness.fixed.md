- Check downloaded shard coverage files against the workflow-level `TOTAL_SHARDS`
  before combining them. Missing or unexpected counts and invalid shard configuration
  fail without reporting a misleading coverage percentage. Complete inputs still enforce
  the existing 95% floor. The literal shard matrix is checked against `TOTAL_SHARDS`.
  Test Summary distinguishes a gate that did not reach the floor from a floor/reporting
  failure. A cancelled test matrix is reported by the earlier Test gate; successful tests
  with missing artifacts reach the coverage diagnosis. File presence alone does not prove
  test completion, so the existing test-result gate remains necessary.
  Policy tests execute the actual workflow scripts, including incomplete inputs, complete
  coverage above/below 95%, and summary failures; deliberate workflow mutations must fail.
