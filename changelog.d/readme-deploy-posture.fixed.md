- **Corrected the README Deployment section.** It described the temporary interim in-process
  (`memory`) job posture (#928); as of #943 the durable arq + managed-Redis path is restored
  (`DUTCHBAY_JOBS_BACKEND=redis`, worker process live), so the README now states the current
  durable posture. Documentation only.
