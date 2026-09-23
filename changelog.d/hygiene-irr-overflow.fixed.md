Canonical periodic IRR now detects finite cashflow coefficient normalization that
would overflow NumPy's companion matrix and fail its finite-matrix check, routing
directly through the existing numerical-failure fallback. Subnormal inputs,
caller bounds, residual validation, successful polynomial root selection and
bisection semantics are preserved. The property-test introduction now describes
the existing residual validation accurately. Unrelated reciprocal-overflow
warnings remain outside this narrowly scoped repair.
