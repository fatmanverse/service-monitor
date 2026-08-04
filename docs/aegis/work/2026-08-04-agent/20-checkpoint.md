# Checkpoint

## Current Todo

Task 7/8 protocol correction: local execution engine and gRPC transport.

## Active Slice

- Retire FastAPI REST Agent protocol and urllib client.
- Add protobuf as the single wire-contract owner.
- Implement center gRPC service and TLS Agent client.

## Completed

- Agent design approved.
- Implementation plan written and self-reviewed.
- Persistent SSH deletion scope explicitly confirmed.
- Task 1 model and migration implementation completed.
- Raw SQLite rebuild check preserved rows, made port nullable, restored indexes and passed `foreign_key_check`.
- Task 2 start-user command builders, API fields and SSH execution integration completed.
- Agent storage, probes, nested rule engine, start command execution and command idempotency have standard-library unit coverage.

## Evidence

- `docs/aegis/specs/2026-08-04-agent-design.md`
- `docs/aegis/plans/2026-08-04-agent.md`
- `backend/tests/test_agent_migrations.py`
- `backend/app/models.py`
- `backend/app/migrations.py`
- `backend/app/start_commands.py`
- `backend/tests/test_start_commands.py`
- `agent/tests/test_storage.py`
- `agent/tests/test_probes.py`
- `agent/tests/test_engine.py`
- `agent/tests/test_commands.py`

## Blockers

- Local Python environment may not have backend test dependencies; compile and static checks remain available.

## Explicit Non-Edits

- Do not touch untracked `frontend/src/app/` user changes in this slice.
- Do not clear any live SSH credential during schema migration.
- Do not commit automatically.
- Do not retain REST as a runtime fallback after gRPC migration.

## Next

Create `protocol/agent.proto`, generate both runtime stubs, then migrate the center service and Agent client.

## Drift Check

- Scope: aligned after user-directed gRPC correction.
- Compatibility: old hosts remain SSH and retain credentials during upgrade.
- Retirement: SSH data removal remains limited to explicit Agent switch, not enrollment or upgrade.
- Protocol owner: `protocol/agent.proto`; REST Agent routes are on the retirement track.
- Decision: continue.
