# Evidence

- `python3 -m compileall -q app tests`: passed.
- `bash -n ../scripts/setup.sh ../scripts/start.sh`: passed.
- Nested rule evaluation and duplicate probe reference rejection: passed with a direct Python assertion script.
- Frontend `src` strict type check: passed using the locally available TypeScript compiler and temporary React/Lucide declarations; temporary files were removed.
- Runtime permission scan: `UserService` / `user_services` references remain only in the compatibility model and migration input; routers, monitoring, scheduler, and serializers do not read legacy grants.
- Regression coverage added for retaining an existing secret only when the probe authentication type is unchanged.
- Regression coverage added to reject an explicitly empty health rule during service updates instead of falling back to the stored rule.
- Multi-alert API regression coverage added for selecting two robots, reporting service counts, deleting one target, and rejecting unknown alert IDs.
- Frontend service form now selects multiple alert targets; alert management now owns alert configuration CRUD and per-target tests.
- Host create/edit now selects multiple alert targets; host offline and recovery transitions notify every enabled target.
- Scheduler completes due host checks before selecting service work; offline hosts are excluded, and the monitoring guard preserves service state without probing, restart, log, or service alert side effects.
- `python3 -m pytest tests/test_api.py -q`: not run because the current Python environment has no `pytest`, SQLAlchemy, FastAPI, or Pydantic installed.
- Official `npm run typecheck` / build: not run because project dependencies are not installed; the offline check does not validate Vite bundling or the exact React 19 declaration package.
- SQLite migration smoke test: not run because SQLAlchemy is unavailable; static review confirms the migration marker short-circuits repeated completed runs and the data conversion commits atomically.
- Multi-alert migration preserves the old single configuration and legacy `alert_enabled` relationships as migration input; runtime reads only `service_alert_configs`.
