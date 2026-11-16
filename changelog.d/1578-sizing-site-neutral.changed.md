The solar + BESS sizing code is site-neutral (#1578 L-5). A config's `schema_version`
is accepted as its schema family or as the family after a site prefix
(`<site>_pv_bess_pricing_v1`, for example), so the module no longer names the site.
The 10 MW limit's readings are the ones the regulatory config names, and the project
sizing config must give limits for exactly those readings; they were fixed at A and B.
The sizing module, the dispatcher and the PV layout library carry no site or PR-number
wording in their strings or docstrings, and a test checks all three (#1590 A-4).

The project-IRR sentinel reads the engine's #1494 status (#1578 L-8). An absent or
undefined IRR, or a status other than `computed`, drops out of the statistics; an exact
0.0 no longer does. `annual_energy()` books energy through the dispatcher's
`TariffConfig.rate_name()` rather than a third copy of the priority-term rule (#1590 D-1).

No config, scenario, KPI or committed sizing summary changes. Reduced sizing runs are
byte-identical before and after.
