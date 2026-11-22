- Jurisdiction pack resolver, not yet wired (#1843, second slice of #1841).
  `analytics/jurisdiction_packs/resolver.py` takes a project's jurisdiction bindings (the
  `ProjectCase` `JurisdictionBinding` record), its period valuation dates and any project
  overrides. It returns, for each subject and date, the pack values in force on that date,
  the pack used, every override applied with both values, and any conflicts. The output
  carries a digest of its canonical form.
  - It fails closed with a typed refusal. An unknown jurisdiction, an unregistered version,
    a missing binding for a required subject, a subject the pack does not cover or a date
    with no value in force is refused, never filled from another jurisdiction.
  - Two packs bound to one subject, or an override without provenance, are reported as
    conflicts with every candidate value, and the value is withheld.
  - A property test shows that an amendment effective after a run's valuation dates never
    changes that run's resolved values. Nothing in the engine calls the resolver, and no
    output moves.
