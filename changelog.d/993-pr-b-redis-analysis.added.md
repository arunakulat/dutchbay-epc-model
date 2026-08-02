- **Async analysis jobs — redis/arq backend parity (#993 PR-B-redis)** — the async analysis
  path (`POST /v1/jobs/analysis`, MC / tornado / Morris) now runs on the durable, cross-process
  `redis` backend as well as the default in-process one, at parity with the wind-assessment job.
  A new `run_analysis_task` arq worker task (`app.jobs.worker`) runs the same `run_analysis_job`
  orchestration in a thread against the shared `RedisJobStore`, and `enqueue_analysis_job`
  produces onto the arq queue via `_enqueue_analysis_to_arq` when `DUTCHBAY_JOBS_BACKEND=redis`
  (mirroring `_enqueue_to_arq`); the previous fail-loud 501 on the redis backend is removed. The
  default `memory` backend is unchanged (byte-identical `BackgroundTasks` path). Gated on the
  optional `[jobs]` extra (arq, redis) and a live Redis, so — like the wind worker — the
  round-trip is not CI-verified; the worker import-smoke asserts the new task is registered, and
  the enqueue-to-arq dispatch is unit-tested with a faked producer. `finance/` and `analytics/`
  untouched; canonical KPIs byte-identical. With this the async analysis path (#993 PR-B) is
  complete across both backends — Monte Carlo (PR-B1), one-way tornado (PR-B2), and Morris global
  SA (PR-B3) all run either in-process (`BackgroundTasks`/`memory`) or on the durable redis/arq
  worker. Ref #788.
