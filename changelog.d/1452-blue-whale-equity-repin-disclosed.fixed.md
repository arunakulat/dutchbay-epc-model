- **Release record for #1452 (`P2-F3-01`).** It merged on 2026-11-06 as `cd283c5d`, moved
  equity KPIs in 16 committed scenarios, and left `VERSION` at 15.18.0, so `DOC-02` was
  not met at merge. From `cd283c5d` until this release, main reported 15.18.0 while
  computing equity KPIs that 15.18.0 (`cc4d1b59`) does not reproduce: identify any
  artefact from that window by commit SHA, not by version. The
  `1398-debt-service-shortfall-carried` fragment was corrected to the as-merged figures
  before this compile. The owner signed off the merged vector as PROVISIONAL on
  2026-11-07T14:07:21Z: these equity figures are the model's current output, but no report
  quotes them as final until #1564 (year-1 bridge-period service charged to equity with no
  matching CFADS) is resolved. Retrospective review records: #1452 issuecomment-6705659480
  (domain) and issuecomment-6707928571 (assurance).
