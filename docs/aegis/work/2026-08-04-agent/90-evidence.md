# Evidence

- `python3 -m compileall -q app tests`: passed after Task 1 changes.
- `python3 -m pytest tests/test_agent_migrations.py -q`: blocked because local Python has no pytest.
- Old-schema fixture executed directly with stdlib SQLite: legacy host row loaded and `PRAGMA foreign_key_check` returned no rows.
- `_rebuild_hosts_with_nullable_port` executed directly against the fixture: `port.notnull == 0`, row values preserved, expected indexes restored, foreign-key check empty.
- Start command direct assertions passed for empty user and `service-user` SSH/Agent paths.
- `python3 -m compileall -q app tests`: passed after Task 2.
- `git diff --check` on backend Agent/start-user files: passed.
- Backend full suite in an isolated Python 3.9 environment: `39 passed` after fixing probe replacement ordering, Agent host manual-probe retirement and adding a real TLS gRPC round trip.
- Agent full suite: `18 passed`.
- Frontend `npm run typecheck`: passed.
- Frontend `npm run build`: passed; Vite produced the production bundle.
- Agent package installation through `pyproject.toml` in Python 3.9: passed after explicit setuptools package ownership.
- Agent x86_64/ARM64 manylinux2014 runtime wheel availability verified for cryptography, grpcio and protobuf.
- Shell syntax and ShellCheck passed for Agent and server packaging scripts.
- GitHub Actions YAML parsed successfully for Agent build, Agent compatibility and server build workflows.
- Local macOS PyInstaller Agent binary built and `--self-test` passed; this caught and fixed the package-relative entrypoint failure.
- Local macOS PyInstaller Server binary with embedded `frontend/dist` built and `--self-test` passed; this caught and fixed `--add-data` resolution under `--specpath`.
- Remaining external evidence: execute GitHub-hosted manylinux builds, distribution smoke matrix and installed systemd lifecycle checks.
