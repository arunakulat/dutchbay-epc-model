- Jurisdiction rule packs, first slice (#1842, tracking #1841; owner activation of #1353 P3
  "Second jurisdiction (D3)" for Phases 1-2 only, 21 Nov 2026). `analytics/jurisdiction_packs/`
  adds a strict schema and loader for versioned packs. Each parameter carries its value, unit,
  governed subject, scenario key, source citation, effective window and source status. A v1
  pack can be "supported" but never "assured".
  `conf/jurisdiction_packs/lk/1.0.0.yaml` holds 13 Sri Lanka statutory values (direct tax,
  import levies, VAT, revenue SSCL) as the repository recorded them, each with its citation.
  No primary text is pinned, so every value has status `as_recorded`. Data only: nothing in
  the engine reads the pack yet, and no output moves.
  - Scenario disagreements with the pack are listed and classified in
    `tests/fixtures/jurisdiction_packs/lk_1_0_0_scenario_disagreements.yaml`, and a test keeps
    that list in step with `scenarios/`. Fifteen scenarios still charge 2.5% revenue SSCL. The
    lender case records IPP supply to CEB as exempt (#738). These are listed for the owner to
    rule on, not corrected here.
