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

- Active: Task 2 - user self-service password change and token invalidation.
- Pending: Tasks 2-7.
- Completed: Task 1 service lifecycle and 30-day history contract.
- Evidence refs: approved spec/plan commits `ff9a990`, `303d4b0`; Task 1 targeted test and compile evidence in `90-evidence.md`.
- Blockers: none.
- Next: commit Task 1, then implement auth token-version migration and password endpoint.

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

## ResumeStateHint

Read this checkpoint, the approved spec and plan, then compare `git status` before continuing.
