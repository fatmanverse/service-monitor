# Evidence

- `python3 -m compileall -q app tests`: passed after Task 1 changes.
- `python3 -m pytest tests/test_agent_migrations.py -q`: blocked because local Python has no pytest.
- Old-schema fixture executed directly with stdlib SQLite: legacy host row loaded and `PRAGMA foreign_key_check` returned no rows.
- `_rebuild_hosts_with_nullable_port` executed directly against the fixture: `port.notnull == 0`, row values preserved, expected indexes restored, foreign-key check empty.
- Start command direct assertions passed for empty user and `service-user` SSH/Agent paths.
- `python3 -m compileall -q app tests`: passed after Task 2.
- `git diff --check` on backend Agent/start-user files: passed.
