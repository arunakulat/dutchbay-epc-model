"""Finance module for DutchBay EPC Model.

Refinancing: the canonical engine is ``finance.refinancing_v14_hardened`` (it
reads the real sized debt result — ``avg_debt_rate``, ``min_dscr``, etc.). The
Hydra duplicate (``refinancing_v14_hydra``) and the pydantic compatibility stubs
(``refinancing_v14_compat``, re-exported here) were retired — they had no
production or test consumers.
"""
