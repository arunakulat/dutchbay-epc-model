- **Agent session routing note.** `docs/governance/agent_session_routing.md` sends a
  session on any agent host to the rules and files that govern it, restates none of
  them, and grants no merge, review, lease or approval authority. `AGENTS.md` points
  non-Codex sessions at it, and `tests/lint/test_agent_session_routing.py` checks that
  every rule ID, path and quoted section it cites still exists. It replaces draft #1498
  and adds no ruleset row.
