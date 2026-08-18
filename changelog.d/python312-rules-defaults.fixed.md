## Fixed

- Migrated active GWTF developer and PDF-ingestion rules from the retired Python
  3.11 environment to the governed, reconstructable Python 3.12 `.venv`.
- Removed the legacy venv name from the active bootstrap and aligned Docker
  documentation with the deployed Python 3.12 image and governed dependency lock.

## Financial impact

None. This changes developer governance, bootstrap discovery, ingestion provenance,
and deployment documentation only; financial logic and canonical inputs are unchanged.
