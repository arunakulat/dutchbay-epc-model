- **The financing questionnaire takes its scenario from configuration (#1783).**
  `analysis_tools/financing_questionnaire.py` no longer holds a fixed map of two scenario
  paths, and the generator's Hydra config is renamed from
  `conf/blue_whale_financing_questionnaire.yaml` to the generic
  `conf/financing_questionnaire.yaml`. Run it as
  `python scripts/generate_financing_questionnaire.py scenario=scenarios/<name>.yaml output_name=<stem>`;
  both values are required and neither has a default. Any scenario that declares every field
  the questionnaire reads is exported; one that lacks a field is refused with that field's
  path. The scenario must be a regular file under `scenarios/`. The export's `project` key is
  replaced by `scenario` (the path) and its `schema_version` moves from `1` to `2`. Both
  files leave the site-literal lint's waiver list. No KPI changes.
