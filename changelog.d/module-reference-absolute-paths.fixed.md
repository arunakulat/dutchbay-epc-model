- **`docs/MODULE_REFERENCE.md` no longer cites one machine's filesystem** — the two
  "Files referenced/read" provenance lines listed every path as
  `/Users/<user>/Downloads/dutchbay-epc-model/...`, an absolute path from the machine the
  document was generated on. Anyone else reading it was pointed at a directory that does
  not exist for them, and the paths silently went stale the moment that clone moved.
  Now repo-relative, which is what the rest of the document already uses.
