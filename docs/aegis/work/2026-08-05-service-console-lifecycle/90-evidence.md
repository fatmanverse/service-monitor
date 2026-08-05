# 服务控制台生命周期证据

## EvidenceBundleDraft

- Approved Design Spec: `docs/aegis/specs/2026-08-05-service-console-lifecycle-design.md`
- Implementation Plan: `docs/aegis/plans/2026-08-05-service-console-lifecycle.md`
- Task 1 targeted regression: `backend/.venv/bin/python -m pytest -q tests/test_api.py tests/test_agent_reports.py` from `backend/` -> 25 passed.
- Task 1 static compile: `backend/.venv/bin/python -m compileall -q backend/app` -> exit 0.
- Task 1 diff hygiene: `rtk git diff --check` -> exit 0.
- Task 2 targeted regression: `backend/.venv/bin/python -m pytest -q tests/test_api.py tests/test_agent_migrations.py` from `backend/` -> 26 passed.
- Task 2 static compile and diff hygiene -> exit 0.
- Task 3 backend TLS regression: `backend/.venv/bin/python -m pytest -q tests/test_agent_grpc_integration.py tests/test_agent_enrollment.py` -> 7 passed.
- Task 3 Agent TLS regression: `agent/.venv/bin/python -m pytest -q tests/test_client.py tests/test_grpc_client_contract.py` -> 6 passed.
- Task 3 backend/Agent compileall and diff hygiene -> exit 0.
- Task 4 packaging behavior: `backend/.venv/bin/python -m pytest -q tests/test_packaging_layout.py` -> 3 passed.
- Task 4 shell validation: `shellcheck backend/packaging/start.sh backend/packaging/install.sh scripts/platform.sh` -> exit 0.
- Task 4 diff hygiene -> exit 0.
- Task 5 frontend: `npm run typecheck --prefix frontend && npm run build --prefix frontend` -> passed; Vite built 1609 modules.
- Task 5 backend lifecycle repair: targeted `test_api.py` selection -> 3 passed.
- Task 5 diff hygiene -> exit 0.
- Task 6 frontend: `npm run typecheck --prefix frontend && npm run build --prefix frontend` -> passed twice; Vite built 1609 modules.
- Task 6 style retirement scan: no gradient, backdrop-filter, color-mix, data-theme, useTheme or default-font remnants.
- Task 6 diff hygiene -> exit 0.
- Uncovered after Task 6: full regression, ADR/docs and final architecture review.
