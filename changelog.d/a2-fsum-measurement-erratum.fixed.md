Corrected two false statements about `math.fsum` that landed with A1/A2 in #1231, and pinned the
summation contract they were describing.

`changelog.d/a2-subannual-operating-rows.added.md` claimed that replacing `math.fsum` with the
builtin `sum` in `finance.period_grid_v14.aggregate_flows_to_annual` moves the seasonal
reconciliation distribution from 510/30 to 509/31. That figure is false on the runtime this
repository pins. Measured on Python 3.12.3 with the pinned dependency set, the distribution is
510/30 under both, and the even profile is 540/540 under both: it does not move at all. CPython 3.12
uses compensated summation for floats in the builtin, which is the cause. The 509/31 shift is a
Python 3.11 measurement, and `requirements.txt` cannot be installed on 3.11 at all, because
`scipy==1.18.1` requires `>=3.12`.

The same function's inline comment asserted two things that are also false: that A2's allocator
computes each year's closing residual against `aggregate_flows_to_annual`, and that a left-to-right
sum made the two disagree by one ULP on the live lendercase. The allocator does not call that
function; `finance.subannual_rows_v14.allocate_flow` sums its own parts with `math.fsum` directly.
Both sentences are withdrawn in place rather than deleted, and the surviving claim -- that `fsum` is
exactly rounded, so the aggregate does not depend on summation order -- is the one the code actually
earns.

A consequence of the first correction is that the `math.fsum` call was pinned by no test on the
runtime CI uses: reverting it to the builtin leaves all 1440 tests in `tests/finance` passing. Two
contract tests now pin the promise rather than the call. One asserts the aggregate equals the
correctly rounded sum of each year, computed independently with `fractions.Fraction`, and the other
asserts that every permutation of a year's periods aggregates to a bit-identical float. Both fail
when the implementation is replaced by a naive accumulation loop and neither fails when it is
replaced by the 3.12 builtin, which is stated in the tests themselves as the limitation it is.

No financial behaviour changes: no committed scenario sets `cashflow.resolution`, the annual engine
is untouched, and the canonical lender KPI vector is unchanged. Confers no grade, release, audit,
lender or Board authority.
