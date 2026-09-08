Make jobs, PDF renderer and lender-risk-table dependency error tests deterministic
by controlling test-local import/dependency seams. Exercise both jobs dependencies
and WeasyPrint package/native loader failures, assert actionable errors and causes,
and retain memory, PDF and DataFrame success controls. No runtime or financial
behavior changes.
