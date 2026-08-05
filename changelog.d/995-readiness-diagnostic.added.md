- **Readiness diagnostic for the CDS credential (#995)** — a new unversioned infra endpoint
  `GET /health/readiness` reports whether the runtime-critical Copernicus config is present —
  `CDSAPI_URL` (the non-secret endpoint) and `CDSAPI_KEY` (the secret token) — as BOOLEANS only,
  so an operator or a deploy smoke check can confirm the staging/production runtime is wired for
  live ERA5 retrieval without the route ever echoing a value. Each check is `true` iff the env
  var is set and non-blank (a whitespace-only secret reads as absent); `ready` is the AND of every
  check. The route always returns 200 — it is a diagnostic, not a gate (liveness `/health` is what
  pulls an instance) — and, like `/health`, is registered directly on the app so it sits OUTSIDE
  the `/v1` auth-gated client surface. This satisfies the #995 acceptance criterion that startup or
  health diagnostics confirm the endpoint and credential are present without exposing their values.
  Ref #788.
