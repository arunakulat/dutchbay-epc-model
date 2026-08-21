Fixed a false pin in the grid-screening report's dependency provenance. `GRID_EXTRA_PINS` was a
hand-kept copy of pyproject that had drifted — it read `pandapower ==3.3.0` while the project
declared `>=3.5,<4` and the environment ran 3.5.4 — so the report surfaced a version the study
was never built against. The pins are now read from the installed distribution's own metadata,
with the static table demoted to a fallback for uninstalled source checkouts and held to the
declared value by a drift-guard test. The test that rendered the pin was itself asserting
`==3.3.0`, locking in the drift, and now asserts against the resolved pin set.
