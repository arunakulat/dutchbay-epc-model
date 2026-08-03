- **Staging deployment config + Copernicus CDS endpoint (#993 PR-C, #995)** — a new
  `fly.staging.toml` provisions a separate `dutchbay-epc-model-staging` Fly app that mirrors
  the production topology (web + worker off one image, `/health` check, sin region). It keeps
  the fail-closed `DUTCHBAY_ENV="production"` auth posture — a staging app on `*.fly.dev` is a
  public surface — with JWT issuer/audience and the async job queue deliberately distinct from
  prod (`dutchbay-epc-model-staging` / `dutchbay-web-staging` / `dutchbay:wind_jobs_staging`) so
  a staging-minted token cannot be replayed against production. It also wires the Copernicus CDS
  API endpoint (#995): the non-secret `CDSAPI_URL=https://cds.climate.copernicus.eu/api` base is
  set in `[env]` of BOTH `fly.staging.toml` and the production `fly.toml` (read by
  `wind_resource/era5_retrieval.py`, which has no in-code default and is exercised by the async
  ERA5 path on both apps), while the matching `CDSAPI_KEY` stays a secret provisioned via
  `fly secrets set`. No secret value appears in either config file; the required secrets are
  documented as out-of-band runbook steps in `docs/deploy/DEPLOY.md` (now with a staging section
  and CDS entries in the env table). The `fly secrets set` runbooks — and the line printed by
  `scripts/provision_web_secrets.py` — now single-quote the credential values, because the
  pbkdf2 hash in `DUTCHBAY_API_USERS` contains `$` field separators an unquoted shell would
  expand (which would mangle the credential map so every login 401s). Deployment stays a manual
  `fly deploy -c fly.staging.toml`; CI is unchanged. Ref #788.
