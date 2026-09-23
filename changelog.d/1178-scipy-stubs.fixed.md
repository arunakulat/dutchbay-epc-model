Upgrade scipy-stubs from 1.18.0.1 to 1.18.1.0 and read the named KS-test
`pvalue` field in both Weibull diagnostics. This preserves the existing SciPy
1.18.1 calls and numerical outputs while keeping the strict mypy gate compatible
with the new stubs. No runtime dependency, financial formula or scenario changes.
