- **The dashboard's removed-API guard now proves it read the dashboard** —
  `tests/integration/test_dashboard_smoke.py` asserted only that no removed API name appeared in
  its subject, which an empty or unrelated file satisfies exactly as well as a clean dashboard, so
  the guard stayed green whether or not it was reading anything. It now asserts the subject is
  non-empty and carries the dashboard's engine contract before scanning, with negative controls for
  a blank subject, a foreign subject and each individually missing marker. A missing file already
  raised from `read_text`; the empty and wrong-file cases are the ones that slipped through. No
  existing assertion was removed. (#1353 A-2.)
