# 服务控制台生命周期证据

## EvidenceBundleDraft

- Approved Design Spec: `docs/aegis/specs/2026-08-05-service-console-lifecycle-design.md`
- Implementation Plan: `docs/aegis/plans/2026-08-05-service-console-lifecycle.md`
- Task 1 targeted regression: `backend/.venv/bin/python -m pytest -q tests/test_api.py tests/test_agent_reports.py` from `backend/` -> 25 passed.
- Task 1 static compile: `backend/.venv/bin/python -m compileall -q backend/app` -> exit 0.
- Task 1 diff hygiene: `rtk git diff --check` -> exit 0.
- Task 2 targeted regression: `backend/.venv/bin/python -m pytest -q tests/test_api.py tests/test_agent_migrations.py` from `backend/` -> 26 passed.
- Task 2 static compile and diff hygiene -> exit 0.
- Uncovered after Task 2: TLS, packaging, frontend and full regression.
