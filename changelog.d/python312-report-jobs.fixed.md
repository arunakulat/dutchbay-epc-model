## Fixed

- Added the retained report and async-job extras to the governed Python 3.12 lock,
  including WeasyPrint 69.0, arq 0.28.0, Redis/hiredis, and the Brotli/Zopfli
  compression backends.
- Closed the deployment audit gap in which production report/job dependencies were
  installed outside the reproducibility lock and therefore outside `pip-audit`.

## Financial impact

None. This changes report rendering, worker provisioning, and dependency governance
only; financial logic, scenario inputs, and canonical KPI calculations are unchanged.
