"""Finance module for DutchBay EPC Model.

Refinancing: there is no standalone refinancing engine. The balloon ``refinance``
treatment is implemented inline in ``finance.debt_v14`` (``_balloon_resolution_stream``
/ ``_refinance_terms``), selected via ``Financing_Terms.balloon_treatment`` and
parameterized by ``constraints.refinancing.{refinance_tenor_years,refinance_rate_premium}``.
The former standalone modules (``refinancing_v14_hardened``, ``refinancing_v14_hydra``,
``refinancing_v14_compat``) were retired — they had no production consumers.
"""
