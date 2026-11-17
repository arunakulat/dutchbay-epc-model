- Model code no longer falls back to a particular site (#1759, U9 of the owner's 2026-11-16
  ruling that the model is universal and every site input comes from configuration).
  - `run_full_pipeline_v14.py` with `wind_auto_orchestrate=true` refuses a scenario that
    names no location, instead of running it as one site.
  - `finance.irr_config.load_config` needs a path; there is no default scenario.
  - `analytics.gis.gis_export` and `wind_resource.era5_retrieval` need `GIS_EXPORT_CONFIG`
    and `ERA5_REQUEST_CONFIG`; there is no default site config.
  - The web app's base variants are read from `conf/web_base_scenarios.yaml`; they load the
    same scenarios as before.
  - The approved AEP source registry is read from `conf/aep_approved_sources.yaml`; its
    content is unchanged.
  - The resource-assurance evidence register and the demo dashboards no longer name a site,
    a met mast or a site scenario.
  - `tests/lint/test_no_site_literals_in_model_code.py` refuses site names, site scenario
    and config paths, the bare location value and coordinates as literals in model code. The
    remaining site-named schema strings are listed with the work item that removes them
    (U2 to U4).
  - No engine, scenario or KPI figure changes. The F-5 hold applies.
