# Checkpoint

## Current Todo

Task 11 final release-matrix execution in GitHub Actions and end-to-end deployment evidence.

## Active Slice

- Run GitHub Actions binary compatibility matrix.
- Execute installed systemd service checks on release targets.

## Completed

- Agent design approved.
- Implementation plan written and self-reviewed.
- Persistent SSH deletion scope explicitly confirmed.
- Task 1 model and migration implementation completed.
- Raw SQLite rebuild check preserved rows, made port nullable, restored indexes and passed `foreign_key_check`.
- Task 2 start-user command builders, API fields and SSH execution integration completed.
- Agent storage, probes, nested rule engine, start command execution and command idempotency have standard-library unit coverage.
- Agent REST protocol retired; TLS gRPC is the only Agent control-plane transport.
- Agent management frontend, host execution-mode split, start user and queued command tracking completed.
- PyInstaller packaging, installers, release workflows and target-image binary smoke matrix completed in code.
- Agent execution/identity/offline-autonomy ADR recorded.

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

- Local Docker daemon is unavailable, so manylinux and target-distribution binary execution remains delegated to GitHub Actions.

## Explicit Non-Edits

- Do not touch untracked `frontend/src/app/` user changes in this slice.
- Do not clear any live SSH credential during schema migration.
- Do not commit automatically.
- Do not retain REST as a runtime fallback after gRPC migration.

## Next

Push the branch, run all GitHub Actions, and capture release asset/systemd evidence.

## Drift Check

- Scope: aligned after user-directed gRPC correction.
- Compatibility: old hosts remain SSH and retain credentials during upgrade.
- Retirement: SSH data removal remains limited to explicit Agent switch, not enrollment or upgrade.
- Protocol owner: `protocol/agent.proto`; REST Agent routes are on the retirement track.
- Decision: continue.
