# 服务控制台生命周期检查点

## TaskStartSnapshot

- Root: `/Users/chenyifei/Desktop/家乐在线/服务监控`
- HEAD: `303d4b0a8f772c676fcaea6c927df3bf685db946`
- Branch: `main`
- Upstream divergence: `origin/main...HEAD = 0 behind / 2 ahead`
- Worktree: clean
- Active Git operations: none
- Worktrees: current root only

## TodoCheckpointDraft

- Active: Task 7 - retirement, documentation, ADR and full verification.
- Pending: Task 7.
- Completed: Tasks 1-6, including account/CA UI and light operational console optimization.
- Evidence refs: approved spec/plan commits `ff9a990`, `303d4b0`; Task 1 targeted test and compile evidence in `90-evidence.md`.
- Blockers: none.
- Next: commit Task 6, then run retirement scan, update ADR/docs and execute full verification.

## Active Slice Card

- Goal: 固定新服务默认停止、手动探活不自动拉起、30 天历史查询与物理清理。
- Parent plan/spec: `docs/aegis/plans/2026-08-05-service-console-lifecycle.md` Task 1.
- Files: backend service/log/monitor/scheduler owners and tests.
- Boundary: no password, TLS, frontend or packaging edits.
- Verification: targeted backend API and agent report tests.
- Stop: contract needs schema/table beyond approved plan or compatibility cannot be preserved.

## DriftCheckDraft

- Intent: aligned.
- Scope: Task 1 stayed inside service/log/scheduler owners.
- Baseline: aligned.
- Compatibility: old enabled values and API URLs preserved; only new create defaults changed.
- Retirement: `/probe` automatic start path removed; `/restart` remains explicit admin action.
- Evidence: targeted tests, compileall and diff check passed.
- Decision: continue.

## Task 2 Drift Check

- Intent: aligned with self-service password requirement.
- Scope: auth/security/user migration only.
- Compatibility: old users preserved; password reset invalidates prior sessions.
- New owner/fallback: no token blacklist or frontend fallback added.
- Evidence: 26 targeted tests, compileall and diff check passed.
- Decision: continue.

## Task 3 Drift Check

- Intent: aligned with instance-owned Agent TLS requirement.
- Scope: certificate owner, gRPC wiring, CA route and Agent identity option only.
- Compatibility: explicit cert/key deployments remain valid; missing partial material fails explicitly.
- Security: no plaintext, shared private key, verification disable or fallback path added.
- Evidence: backend 7 tests, Agent 6 tests, compileall and diff check passed.
- Decision: continue.

## Task 4 Drift Check

- Intent: aligned with current-directory direct startup requirement.
- Scope: release script, environment template, workflow bundle, packaging test and docs.
- Compatibility: `install.sh` and source `scripts/start.sh` retained unchanged.
- Security: random secrets use `/dev/urandom`; env is `0600`; existing DB without env fails explicitly.
- Evidence: 3 packaging tests, shellcheck and diff check passed.
- Decision: continue.

## Task 5 Drift Check

- Intent: aligned with independent detail page and visible manual result requirements.
- Scope: typed route, service detail, result normalization, list retirement and one backend lifecycle correction.
- Compatibility: `#/services` remains list; `#/services/{id}` is additive; API URLs unchanged.
- Repair: enabling a stopped service now makes it immediately due at the canonical service update owner.
- Retirement: list-level probe/result and direct start actions removed.
- Evidence: frontend typecheck/build, backend 3 lifecycle tests and diff check passed.
- Decision: continue.

## Task 6 Drift Check

- Intent: aligned with password access, CA distribution and deep UI optimization.
- Scope: account route/page, authenticated CA download, service stats, shell/tokens and proven dead theme removal.
- Compatibility: existing admin user page retained; account is additive for both roles.
- Retirement: dark theme hook/toggle/token branch removed; no gradient/glass remnants.
- Evidence: two fresh frontend typecheck/build runs, forbidden-style scan and diff check passed.
- Decision: continue.

## ResumeStateHint

Read this checkpoint, the approved spec and plan, then compare `git status` before continuing.
